# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004 Edgewall Software
# Copyright (C) 2003, 2004 Jonas Borgström <jonas@edgewall.com>
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
# Author: Jonas Borgström <jonas@edgewall.com>

from __future__ import nested_scopes
from types import ListType

import perm
from Module import Module
from Ticket import get_custom_fields, insert_custom_fields, Ticket
from Wiki import wiki_to_html
from util import add_to_hdf, escape, sql_escape


class Query:

    def __init__(self, env, constraints=None, order=None, desc=0, verbose=0):
        self.env = env
        self.constraints = constraints or {}
        self.order = order
        self.desc = desc
        self.verbose = verbose
        self.cols = [] # lazily initialized

        if self.order != 'id' and not self.order in Ticket.std_fields:
            # order by priority by default
            self.order = 'priority'

    def get_columns(self):
        if self.cols:
            return self.cols

        # FIXME: the user should be able to configure which columns should
        # be displayed
        cols = [ 'id', 'summary', 'status', 'owner', 'priority', 'milestone',
                 'component', 'version', 'severity', 'resolution', 'reporter' ]

        # Semi-intelligently remove columns that are restricted to a single
        # value by a query constraint.
        for col in [k for k in self.constraints.keys() if k in cols]:
            constraint = self.constraints[col]
            if len(constraint) == 1 and constraint[0] \
                    and not constraint[0][0] in '!~^$':
                cols.remove(col)
            if col == 'status' and not 'closed' in constraint \
                    and 'resolution' in cols:
                cols.remove('resolution')

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
        if not self.order in self.cols:
            # Make sure the column we order by is visible
            self.cols[-1] = self.order

        return self.cols

    def execute(self, db):
        if not self.cols:
            self.get_columns()

        cursor = db.cursor()
        cursor.execute(self.to_sql())
        results = []
        while 1:
            row = cursor.fetchone()
            if not row:
                break
            id = int(row['id'])
            result = { 'id': id, 'href': self.env.href.ticket(id) }
            for col in self.cols:
                result[col] = escape(row[col] or '--')
            if self.verbose:
                result['description'] = wiki_to_html(row['description'] or '',
                                                     None, self.env, db)
            results.append(result)
        cursor.close()
        return results

    def to_sql(self):
        if not self.cols:
            self.get_columns()

        cols = self.cols[:]
        if not self.order in cols:
            cols.append(self.order)
        if not 'priority' in cols:
            # Always add the priority column for coloring the resolt rows
            cols.append('priority')
        if self.verbose:
            cols.append('description')

        sql = []
        sql.append("SELECT " + ",".join(cols))
        custom_fields = [f['name'] for f in get_custom_fields(self.env)]
        for k in [k for k in self.constraints.keys() if k in custom_fields]:
            sql.append(", %s.value AS %s" % (k, k))
        sql.append("\nFROM ticket")
        for k in [k for k in self.constraints.keys() if k in custom_fields]:
           sql.append("\n  LEFT OUTER JOIN ticket_custom AS %s ON " \
                      "(id=%s.ticket AND %s.name='%s')"
                      % (k, k, k, k))

        for col in [c for c in ['status', 'resolution', 'priority', 'severity']
                    if c == self.order]:
            sql.append("\n  LEFT OUTER JOIN (SELECT name AS %s_name, " \
                                         "value AS %s_value " \
                                         "FROM enum WHERE type='%s')" \
                       " ON %s_name=%s" % (col, col, col, col, col))
        for col in [c for c in ['milestone', 'version'] if c == self.order]:
            sql.append("\n  LEFT OUTER JOIN (SELECT name AS %s_name, " \
                                         "time AS %s_time FROM %s)" \
                       " ON %s_name=%s" % (col, col, col, col, col))

        clauses = []
        for k, v in self.constraints.items():
            if len(v) > 1:
                inlist = ["'" + sql_escape(val) + "'" for val in v]
                clauses.append("%s IN (%s)" % (k, ",".join(inlist)))
            elif len(v) == 1:
                val = v[0]

                neg = val[:1] == '!'
                if neg:
                    val = val[1:]
                mode = ''
                if val[:1] in "~^$":
                    mode, val = val[:1], val[1:]

                val = sql_escape(val)
                if mode == '~' and val:
                    if neg:
                        clauses.append("IFNULL(%s,'') NOT LIKE '%%%s%%'" % (k, val))
                    else:
                        clauses.append("IFNULL(%s,'') LIKE '%%%s%%'" % (k, val))
                elif mode == '^' and val:
                    clauses.append("IFNULL(%s,'') LIKE '%s%%'" % (k, val))
                elif mode == '$' and val:
                    clauses.append("IFNULL(%s,'') LIKE '%%%s'" % (k, val))
                elif mode == '':
                    if neg:
                        clauses.append("IFNULL(%s,'')!='%s'" % (k, val))
                    else:
                        clauses.append("IFNULL(%s,'')='%s'" % (k, val))

        if clauses:
            sql.append("\nWHERE " + " AND ".join(clauses))

        sql.append("\nORDER BY IFNULL(%s,'')=''%s,"
                   % (self.order, self.desc and ' DESC' or ''))
        if self.order in ['status', 'resolution', 'priority', 'severity']:
            if self.desc:
                sql.append("%s_value DESC" % self.order)
            else:
                sql.append("%s_value" % self.order)
        elif self.order in ['milestone', 'version']:
            if self.desc:
                sql.append("IFNULL(%s_time,0)=0 DESC,%s_time DESC,%s DESC"
                           % (self.order, self.order, self.order))
            else:
                sql.append("IFNULL(%s_time,0)=0,%s_time,%s"
                           % (self.order, self.order, self.order))
        else:
            if self.desc:
                sql.append("%s DESC" % self.order)
            else:
                sql.append("%s" % self.order)
        if self.order != 'id':
            sql.append(",id")

        return "".join(sql)


class QueryModule(Module):
    template_name = 'query.cs'

    def _get_constraints(self):
        constraints = {}
        custom_fields = [f['name'] for f in get_custom_fields(self.env)]

        # A special hack for Safari/WebKit, which will not submit dynamically
        # created check-boxes with their real value, but with the default value
        # 'on'. See also htdocs/query.js#addFilter()
        checkboxes = [k for k in self.args.keys() if k.startswith('__')]
        if checkboxes:
            import cgi
            for checkbox in checkboxes:
                (real_k, real_v) = checkbox[2:].split(':', 2)
                self.args.list.append(cgi.MiniFieldStorage(real_k, real_v))

        # For clients without JavaScript, we add a new constraint here if
        # requested
        removed_fields = [k[10:] for k in self.args.keys()
                          if k.startswith('rm_filter_')]

        constrained_fields = [k for k in self.args.keys()
                              if k in Ticket.std_fields or k in custom_fields]
        for field in constrained_fields:
            vals = self.args[field]
            if not type(vals) is ListType:
                vals = [vals]
            vals = map(lambda x: x.value, vals)
            if vals:
                mode = self.args.get(field + '_mode')
                if mode:
                    vals = map(lambda x: mode + x, vals)
                if not field in removed_fields:
                    constraints[field] = vals

        return constraints

    def _get_ticket_properties(self):
        properties = []

        cursor = self.db.cursor()

        def rows_to_list(sql):
            list = []
            cursor.execute(sql)
            while 1:
                row = cursor.fetchone()
                if not row:
                    break
                list.append(row[0])
            return list

        properties.append({'name': 'summary', 'type': 'text', 'label': 'Summary'})
        properties.append({
            'name': 'status', 'type': 'radio', 'label': 'Status',
            'options': rows_to_list("SELECT name FROM enum WHERE type='status' ORDER BY value")})
        properties.append({
            'name': 'resolution', 'type': 'radio', 'label': 'Resolution',
            'options': rows_to_list("SELECT name FROM enum WHERE type='resolution' ORDER BY value")})
        properties.append({
            'name': 'component', 'type': 'select', 'label': 'Component',
            'options': rows_to_list("SELECT name FROM component ORDER BY name")})
        properties.append({
            'name': 'milestone', 'type': 'select', 'label': 'Milestone',
            'options': rows_to_list("SELECT name FROM milestone ORDER BY name")})
        properties.append({
            'name': 'version', 'type': 'select', 'label': 'Version',
            'options': rows_to_list("SELECT name FROM version ORDER BY name")})
        properties.append({
            'name': 'priority', 'type': 'select', 'label': 'Priority',
            'options': rows_to_list("SELECT name FROM enum WHERE type='priority' ORDER BY value")})
        properties.append({
            'name': 'severity', 'type': 'select', 'label': 'Severity',
            'options': rows_to_list("SELECT name FROM enum WHERE type='severity' ORDER BY value")})
        properties.append({'name': 'keywords', 'type': 'text', 'label': 'Keywords'})
        properties.append({'name': 'owner', 'type': 'text', 'label': 'Owner'})
        properties.append({'name': 'reporter', 'type': 'text', 'label': 'Reporter'})
        properties.append({'name': 'cc', 'type': 'text', 'label': 'CC list'})

        return properties

    def _get_constraint_modes(self):
        modes = {}
        modes['text'] = [
            {'name': "contains", 'value': "~"},
            {'name': "doesn't cointain", 'value': "!~"},
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

    def render(self):
        self.perm.assert_permission(perm.TICKET_VIEW)

        query = Query(self.env, self._get_constraints(),
                      self.args.get('order'), self.args.has_key('desc'),
                      self.args.has_key('verbose'))

        if self.args.has_key('update'):
            self.req.redirect(self.env.href.query(query.constraints,
                                                  query.order, query.desc,
                                                  query.verbose))

        props = self._get_ticket_properties()
        add_to_hdf(props, self.req.hdf, 'ticket.properties')
        modes = self._get_constraint_modes()
        add_to_hdf(modes, self.req.hdf, 'query.modes')

        self._render_results(query)

        # For clients without JavaScript, we add a new constraint here if
        # requested
        if self.args.has_key('add'):
            field = self.args.get('add_filter')
            if field:
                self.req.hdf.setValue('query.constraints.%s.0' % field, '')

    def _render_results(self, query):
        self.req.hdf.setValue('title', 'Custom Query')

        cols = query.get_columns()
        for i in range(len(cols)):
            self.req.hdf.setValue('query.headers.%d.name' % i, cols[i])
            if cols[i] == query.order:
                self.req.hdf.setValue('query.headers.%d.href' % i,
                    self.env.href.query(query.constraints, query.order,
                                        not query.desc, query.verbose))
                self.req.hdf.setValue('query.headers.%d.order' % i,
                    query.desc and 'desc' or 'asc')
            else:
                self.req.hdf.setValue('query.headers.%d.href' % i,
                    self.env.href.query(query.constraints, cols[i],
                                        query.verbose))

        for k, v in query.constraints.items():
            if len(v) > 1:
                add_to_hdf(v, self.req.hdf, 'query.constraints.%s' % k)
            elif len(v) == 1:
                val = v[0]
                neg = val[:1] == '!'
                if neg:
                    val = val[1:]
                mode = ''
                if val[:1] in "~^$":
                    mode, val = val[:1], val[1:]
                self.req.hdf.setValue('query.constraints.%s.mode' % k,
                                      (neg and '!' or '') + mode)
                add_to_hdf([val], self.req.hdf, 'query.constraints.%s' % k)

        self.req.hdf.setValue('query.order', query.order)
        if query.desc:
            self.req.hdf.setValue('query.desc', '1')
        if query.verbose:
            self.req.hdf.setValue('query.verbose', '1')

        results = query.execute(self.db)
        add_to_hdf(results, self.req.hdf, 'query.results')
