# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004, 2005 Edgewall Software
# Copyright (C) 2003, 2004, 2005 Christopher Lenz <cmlenz@gmx.de>
#
# Trac is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Trac is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Author: Christopher Lenz <cmlenz@gmx.de>

from trac import perm
from trac.core import *
from trac.Ticket import get_custom_fields, insert_custom_fields, Ticket
from trac.web.chrome import add_link, INavigationContributor
from trac.web.main import IRequestHandler
from trac.WikiFormatter import wiki_to_html, wiki_to_oneliner
from trac.util import escape, sql_escape, CRLF

from time import gmtime, localtime, strftime, time
import re


class QuerySyntaxError(Exception):
    pass


class Query(object):

    def __init__(self, env, constraints=None, order=None, desc=0, group=None,
                 groupdesc = 0, verbose=0):
        self.env = env
        self.constraints = constraints or {}
        self.order = order
        self.desc = desc
        self.group = group
        self.groupdesc = groupdesc
        self.verbose = verbose
        self.cols = [] # lazily initialized

        if self.order != 'id' and not self.order in Ticket.std_fields:
            # order by priority by default
            self.order = 'priority'

    def from_string(cls, env, string, **kw):
        filters = string.split('&')
        constraints = {}
        for filter in filters:
            filter = filter.split('=')
            if len(filter) != 2:
                raise QuerySyntaxError, 'Query filter requires field and ' \
                                        'constraints separated by a "="'
            field,values = filter
            if not field:#
                raise QuerySyntaxError, 'Query filter requires field name'
            values = values.split('|')
            mode, neg = '', ''
            if field[-1] in ('~', '^', '$'):
                mode = field[-1]
                field = field[:-1]
            if field[-1] == '!':
                neg = '!'
                field = field[:-1]
            values = map(lambda x: neg + mode + x, values)
            constraints[field] = values
        return cls(env, constraints, **kw)
    from_string = classmethod(from_string)

    def get_columns(self):
        if self.cols:
            return self.cols

        # FIXME: the user should be able to configure which columns should
        # be displayed
        cols = ['id', 'summary', 'status', 'owner', 'priority', 'milestone',
                'component', 'version', 'severity', 'resolution', 'reporter']
        cols += [f['name'] for f in get_custom_fields(self.env)]

        # Semi-intelligently remove columns that are restricted to a single
        # value by a query constraint.
        for col in [k for k in self.constraints.keys() if k in cols]:
            constraint = self.constraints[col]
            if len(constraint) == 1 and constraint[0] \
                    and not constraint[0][0] in ('!', '~', '^', '$'):
                if col in cols:
                    cols.remove(col)
            if col == 'status' and not 'closed' in constraint \
                    and 'resolution' in cols:
                cols.remove('resolution')
        if self.group in cols:
            cols.remove(self.group)

        def sort_columns(col1, col2):
            constrained_fields = self.constraints.keys()
            # Ticket ID is always the first column
            if 'id' in [col1, col2]:
                return col1 == 'id' and -1 or 1
            # Ticket summary is always the second column
            elif 'summary' in [col1, col2]:
                return col1 == 'summary' and -1 or 1
            # Constrained columns appear before other columns
            elif col1 in constrained_fields or col2 in constrained_fields:
                return col1 in constrained_fields and -1 or 1
            return 0
        cols.sort(sort_columns)

        # Only display the first seven columns by default
        # FIXME: Make this configurable on a per-user and/or per-query basis
        self.cols = cols[:7]
        if not self.order in self.cols and not self.order == self.group:
            # Make sure the column we order by is visible, if it isn't also
            # the column we group by
            self.cols[-1] = self.order

        return self.cols

    def execute(self, db):
        if not self.cols:
            self.get_columns()

        sql = self.get_sql()
        self.env.log.debug("Query SQL: %s" % sql)

        cursor = db.cursor()
        cursor.execute(sql)
        columns = cursor.description
        results = []
        for row in cursor:
            id = int(row[0])
            result = {'id': id, 'href': self.env.href.ticket(id)}
            for i in range(1, len(columns)):
                name, val = columns[i][0], row[i]
                if name == self.group:
                    val = escape(val or 'None')
                elif name == 'reporter':
                    val = escape(val or 'anonymous')
                elif name in ['changetime', 'time']:
                    val = int(val)
                elif val is None:
                    val = '--'
                elif name != 'description':
                    val = escape(val)
                result[name] = val
            results.append(result)
        cursor.close()
        return results

    def get_href(self, format=None):
        return self.env.href.query(self.constraints, order=self.order,
                                   desc=self.desc and 1 or None,
                                   group=self.group,
                                   groupdesc=self.groupdesc and 1 or None,
                                   verbose=self.verbose and 1 or None,
                                   format=format)

    def get_sql(self):
        if not self.cols:
            self.get_columns()

        # Build the list of actual columns to query
        cols = self.cols[:]
        def add_cols(*args):
            for col in args:
                if not col in cols:
                    cols.append(col)
        if self.group and not self.group in cols:
            add_cols(self.group)
        if self.verbose:
            add_cols('reporter', 'description')
        add_cols('priority', 'time', 'changetime', self.order)
        cols.extend([c for c in self.constraints.keys() if not c in cols])
        add_cols('priority.value AS priority_value') # for row coloring

        custom_fields = [f['name'] for f in get_custom_fields(self.env)]

        sql = []
        sql.append("SELECT " + ",".join([c for c in cols
                                         if c not in custom_fields]))
        for k in [k for k in cols if k in custom_fields]:
            sql.append(", %s.value AS %s" % (k, k))
        sql.append("\nFROM ticket")
        for k in [k for k in cols if k in custom_fields]:
           sql.append("\n  LEFT OUTER JOIN ticket_custom AS %s ON " \
                      "(id=%s.ticket AND %s.name='%s')" % (k, k, k, k))

        for col in [c for c in ['status', 'resolution', 'priority', 'severity']
                    if c == self.order or c == self.group or c == 'priority']:
            sql.append("\n  LEFT OUTER JOIN enum AS %s ON (%s.type='%s' AND %s.name=%s)"
                       % (col, col, col, col, col))
        for col in [c for c in ['milestone', 'version']
                    if c == self.order or c == self.group]:
            sql.append("\n  LEFT OUTER JOIN %s ON (%s.name=%s)" % (col, col, col))

        def get_constraint_sql(name, value, mode, neg):
            value = sql_escape(value[len(mode and '!' or '' + mode):])
            if mode == '~' and value:
                return "COALESCE(%s,'') %sLIKE '%%%s%%'" % (
                       name, neg and 'NOT ' or '', value)
            elif mode == '^' and value:
                return "COALESCE(%s,'') %sLIKE '%s%%'" % (
                       name, neg and 'NOT ' or '', value)
            elif mode == '$' and value:
                return "COALESCE(%s,'') %sLIKE '%%%s'" % (
                       name, neg and 'NOT ' or '', value)
            elif mode == '':
                return "COALESCE(%s,'')%s='%s'" % (
                       name, neg and '!' or '', value)

        clauses = []
        for k, v in self.constraints.items():
            # Determine the match mode of the constraint (contains, starts-with,
            # negation, etc)
            neg = len(v[0]) and v[0][0] == '!'
            mode = ''
            if len(v[0]) > neg and v[0][neg] in ('~', '^', '$'):
                mode = v[0][neg]

            # Special case for exact matches on multiple values
            if not mode and len(v) > 1:
                inlist = ",".join(["'" + sql_escape(val[neg and 1 or 0:]) + "'"
                                   for val in v])
                clauses.append("COALESCE(%s,'') %sIN (%s)"
                               % (k, neg and 'NOT ' or '', inlist))
            elif len(v) > 1:
                constraint_sql = [get_constraint_sql(k, val, mode, neg)
                                  for val in v]
                if neg:
                    clauses.append("(" + " AND ".join(constraint_sql) + ")")
                else:
                    clauses.append("(" + " OR ".join(constraint_sql) + ")")
            elif len(v) == 1:
                clauses.append(get_constraint_sql(k, v[0][neg and 1 or 0:], mode, neg))

        clauses = filter(None, clauses)
        if clauses:
            sql.append("\nWHERE " + " AND ".join(clauses))

        sql.append("\nORDER BY ")
        order_cols = [(self.order, self.desc)]
        if self.group and self.group != self.order:
            order_cols.insert(0, (self.group, self.groupdesc))
        for col, desc in order_cols:
            if col == 'id':
                # FIXME: This is a somewhat ugly hack.  Can we also have the
                #        column type for this?  If it's an integer, we do first
                #        one, if text, we do 'else'
                if desc:
                    sql.append("COALESCE(%s,0)=0 DESC," % col)
                else:
                    sql.append("COALESCE(%s,0)=0," % col)
            else:
                if desc:
                    sql.append("COALESCE(%s,'')='' DESC," % col)
                else:
                    sql.append("COALESCE(%s,'')=''," % col)
            if col in ['status', 'resolution', 'priority', 'severity']:
                if desc:
                    sql.append("%s.value DESC" % col)
                else:
                    sql.append("%s.value" % col)
            elif col in ['milestone', 'version']:
                time_col = col == 'milestone' and 'due' or 'time'
                if desc:
                    sql.append("COALESCE(%s.%s,0)=0 DESC,%s.%s DESC,%s DESC"
                               % (col, time_col, col, time_col, col))
                else:
                    sql.append("COALESCE(%s.%s,0)=0,%s.%s,%s"
                               % (col, time_col, col, time_col, col))
            else:
                if desc:
                    sql.append("%s DESC" % col)
                else:
                    sql.append("%s" % col)
            if col == self.group and not col == self.order:
                sql.append(",")
        if self.order != 'id':
            sql.append(",id")

        return "".join(sql)


class QueryModule(Component):

    implements(IRequestHandler, INavigationContributor)

    # INavigationContributor methods

    def get_active_navigation_item(self, req):
        return 'tickets'

    def get_navigation_items(self, req):
        return []

    # IRequestHandler methods

    def match_request(self, req):
        return req.path_info == '/query'

    def process_request(self, req):
        req.perm.assert_permission(perm.TICKET_VIEW)

        constraints = self._get_constraints(req)
        if not constraints and not req.args.has_key('order'):
            # avoid displaying all tickets when the query module is invoked
            # with no parameters. Instead show only open tickets, possibly
            # associated with the user
            constraints = {'status': ('new', 'assigned', 'reopened')}
            if req.authname and req.authname != 'anonymous':
                constraints['owner'] = (req.authname,)
            else:
                email = req.session.get('email')
                name = req.session.get('name')
                if email or name:
                    constraints['cc'] = ('~%s' % email or name,)

        query = Query(self.env, constraints, req.args.get('order'),
                      req.args.has_key('desc'), req.args.get('group'),
                      req.args.has_key('groupdesc'),
                      req.args.has_key('verbose'))

        if req.args.has_key('update'):
            req.redirect(query.get_href())

        add_link(req, 'alternate', query.get_href('rss'), 'RSS Feed',
                 'application/rss+xml', 'rss')
        add_link(req, 'alternate', query.get_href('csv'),
                 'Comma-delimited Text', 'text/plain')
        add_link(req, 'alternate', query.get_href('tab'), 'Tab-delimited Text',
                 'text/plain')

        constraints = {}
        for k, v in query.constraints.items():
            constraint = {'values': [], 'mode': ''}
            for val in v:
                neg = val[:1] == '!'
                if neg:
                    val = val[1:]
                mode = ''
                if val[:1] in ('~', '^', '$'):
                    mode, val = val[:1], val[1:]
                constraint['mode'] = (neg and '!' or '') + mode
                constraint['values'].append(val)
            constraints[k] = constraint
        req.hdf['query.constraints'] = constraints

        format = req.args.get('format')
        if format == 'rss':
            self.display_rss(req, query)
            return 'query_rss.cs', 'application/rss+xml'
        elif format == 'csv':
            self.display_csv(req, query)
        elif format == 'tab':
            self.display_csv(req, query, '\t')
        else:
            self.display_html(req, query)
            return 'query.cs', None

    # Internal methods

    def _get_constraints(self, req):
        constraints = {}
        custom_fields = [f['name'] for f in get_custom_fields(self.env)]

        # A special hack for Safari/WebKit, which will not submit dynamically
        # created check-boxes with their real value, but with the default value
        # 'on'. See also htdocs/query.js#addFilter()
        checkboxes = [k for k in req.args.keys() if k.startswith('__')]
        if checkboxes:
            import cgi
            for checkbox in checkboxes:
                (real_k, real_v) = checkbox[2:].split(':', 2)
                req.args.list.append(cgi.MiniFieldStorage(real_k, real_v))

        # For clients without JavaScript, we remove constraints here if
        # requested
        remove_constraints = {}
        to_remove = [k[10:] for k in req.args.keys()
                     if k.startswith('rm_filter_')]
        if to_remove: # either empty or containing a single element
            match = re.match(r'(\w+?)_(\d+)$', to_remove[0])
            if match:
                remove_constraints[match.group(1)] = int(match.group(2))
            else:
                remove_constraints[to_remove[0]] = -1

        constrained_fields = [k for k in req.args.keys()
                              if k in Ticket.std_fields or k in custom_fields]
        for field in constrained_fields:
            vals = req.args[field]
            if not isinstance(vals, (list, tuple)):
                vals = [vals]
            vals = map(lambda x: x.value, vals)
            if vals:
                mode = req.args.get(field + '_mode')
                if mode:
                    vals = map(lambda x: mode + x, vals)
                if field in remove_constraints.keys():
                    idx = remove_constraints[field]
                    if idx >= 0:
                        del vals[idx]
                        if not vals:
                            continue
                    else:
                        continue
                constraints[field] = vals

        return constraints

    def _get_ticket_properties(self, db):
        # FIXME: This should be in the ticket module
        properties = []

        cursor = db.cursor()
        def rows_to_list(sql):
            list = []
            cursor.execute(sql)
            while 1:
                row = cursor.fetchone()
                if not row:
                    break
                list.append(row[0])
            return list

        properties.append({'name': 'summary', 'type': 'text',
                           'label': 'Summary'})
        properties.append({
            'name': 'status', 'type': 'radio', 'label': 'Status',
            'options': rows_to_list("SELECT name FROM enum WHERE type='status' "
                                    "ORDER BY value")})
        properties.append({
            'name': 'resolution', 'type': 'radio', 'label': 'Resolution',
            'options': [''] + rows_to_list("SELECT name FROM enum "
                                           "WHERE type='resolution' ORDER BY value")})
        properties.append({
            'name': 'component', 'type': 'select', 'label': 'Component',
            'options': rows_to_list("SELECT name FROM component "
                                    "ORDER BY name")})
        properties.append({
            'name': 'milestone', 'type': 'select', 'label': 'Milestone',
            'options': rows_to_list("SELECT name FROM milestone "
                                    "ORDER BY name")})
        properties.append({
            'name': 'version', 'type': 'select', 'label': 'Version',
            'options': rows_to_list("SELECT name FROM version ORDER BY name")})
        properties.append({
            'name': 'priority', 'type': 'select', 'label': 'Priority',
            'options': rows_to_list("SELECT name FROM enum "
                                    "WHERE type='priority' ORDER BY value")})
        properties.append({
            'name': 'severity', 'type': 'select', 'label': 'Severity',
            'options': rows_to_list("SELECT name FROM enum "
                                    "WHERE type='severity' ORDER BY value")})
        properties.append({'name': 'keywords', 'type': 'text',
                           'label': 'Keywords'})
        properties.append({'name': 'owner', 'type': 'text', 'label': 'Owner'})
        properties.append({'name': 'reporter', 'type': 'text',
                           'label': 'Reporter'})
        properties.append({'name': 'cc', 'type': 'text', 'label': 'CC list'})

        custom_fields = get_custom_fields(self.env)
        for field in [field for field in custom_fields
                      if field['type'] in ['text', 'radio', 'select']]:
            property = {'name': field['name'], 'type': field['type'],
                        'label': field['label'] or field['name']}
            if field.has_key('options'):
                property['options'] = filter(None, field['options'])
            if field['type'] == 'radio':
                property['options'].insert(0, '')
            properties.append(property)

        return properties

    def _get_constraint_modes(self):
        modes = {}
        modes['text'] = [
            {'name': "contains", 'value': "~"},
            {'name': "doesn't contain", 'value': "!~"},
            {'name': "begins with", 'value': "^"},
            {'name': "ends with", 'value': "$"},
            {'name': "is", 'value': ""},
            {'name': "is not", 'value': "!"}
        ]
        modes['select'] = [
            {'name': "is", 'value': ""},
            {'name': "is not", 'value': "!"}
        ]
        return modes

    def display_html(self, req, query):
        req.hdf['title'] = 'Custom Query'

        db = self.env.get_db_cnx()

        req.hdf['ticket.properties'] = self._get_ticket_properties(db)
        req.hdf['query.modes'] = self._get_constraint_modes()

        # For clients without JavaScript, we add a new constraint here if
        # requested
        if req.args.has_key('add'):
            field = req.args.get('add_filter')
            if field:
                idx = 0
                if query.constraints.has_key(field):
                    idx = len(query.constraints[field])
                req.hdf['query.constraints.%s.values.%d' % (field, idx)] = ''

        cols = query.get_columns()
        for i in range(len(cols)):
            header = {'name': cols[i]}
            if cols[i] == query.order:
                href = self.env.href.query(query.constraints, order=query.order,
                                           desc=query.desc and None or 1,
                                           group=query.group,
                                           groupdesc=query.groupdesc and 1 or None,
                                           verbose=query.verbose and 1 or None)
                header['href'] = escape(href)
                header['order'] = query.desc and 'desc' or 'asc'
            else:
                href = self.env.href.query(query.constraints, order=cols[i],
                                           group=query.group,
                                           groupdesc=query.groupdesc and 1 or None,
                                           verbose=query.verbose and 1 or None)
                header['href'] = escape(href)
            req.hdf['query.headers.%d' % i] = header

        req.hdf['query.order'] = query.order
        if query.desc:
            req.hdf['query.desc'] = 1
        if query.group:
            req.hdf['query.group'] = query.group
            if query.groupdesc:
                req.hdf['query.groupdesc'] = 1
        if query.verbose:
            req.hdf['query.verbose'] = 1

        tickets = query.execute(db)

        # The most recent query is stored in the user session
        orig_list = rest_list = None
        orig_time = int(time())
        if str(query.constraints) != req.session.get('query_constraints'):
            # New query, initialize session vars
            req.session['query_constraints'] = str(query.constraints)
            req.session['query_time'] = int(time())
            req.session['query_tickets'] = ' '.join([str(t['id']) for t in tickets])
        else:
            orig_list = [int(id) for id in req.session.get('query_tickets', '').split()]
            rest_list = orig_list[:]
            orig_time = int(req.session.get('query_time', 0))
        req.session['query_href'] = query.get_href()

        # Find out which tickets originally in the query results no longer
        # match the constraints
        if rest_list:
            for tid in [t['id'] for t in tickets if t['id'] in rest_list]:
                rest_list.remove(tid)
            for rest_id in rest_list:
                ticket = {}
                ticket.update(Ticket(db, int(rest_id)).data)
                ticket['removed'] = 1
                tickets.insert(orig_list.index(rest_id), ticket)

        for ticket in tickets:
            if orig_list:
                # Mark tickets added or changed since the query was first
                # executed
                if int(ticket['time']) > orig_time:
                    ticket['added'] = 1
                elif int(ticket['changetime']) > orig_time:
                    ticket['changed'] = 1
            ticket['time'] = strftime('%c', localtime(ticket['time']))
            if ticket.has_key('description'):
                ticket['description'] = wiki_to_oneliner(ticket['description'] or '',
                                                         self.env, db)

        req.session['query_tickets'] = ' '.join([str(t['id']) for t in tickets])

        req.hdf['query.results'] = tickets
        req.hdf['session.constraints'] = req.session.get('query_constraints')
        req.hdf['session.tickets'] = req.session.get('query_tickets')

    def display_csv(self, req, query, sep=','):
        req.send_response(200)
        req.send_header('Content-Type', 'text/plain;charset=utf-8')
        req.end_headers()

        cols = query.get_columns()
        req.write(sep.join([col for col in cols]) + CRLF)

        results = query.execute(self.env.get_db_cnx())
        for result in results:
            req.write(sep.join([str(result[col]).replace(sep, '_')
                                                .replace('\n', ' ')
                                                .replace('\r', ' ')
                                for col in cols]) + CRLF)

    def display_rss(self, req, query):
        query.verbose = 1
        db = self.env.get_db_cnx()
        results = query.execute(db)
        for result in results:
            if result['reporter'].find('@') == -1:
                result['reporter'] = ''
            if result['description']:
                result['description'] = escape(wiki_to_html(result['description'] or '',
                                                            None, self.env, db, 1))
            if result['time']:
                result['time'] = strftime('%a, %d %b %Y %H:%M:%S GMT',
                                          gmtime(result['time']))
        req.hdf['query.results'] = results
