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
from util import add_to_hdf, escape, sql_escape


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
                constraints[field] = vals

        from pprint import pprint
        from StringIO import StringIO
        buf = StringIO()
        pprint(constraints, buf)
        self.log.debug("Query constraints:\n%s" % buf.getvalue())

        return constraints

    def _get_results(self, sql):
        cursor = self.db.cursor()
        cursor.execute(sql)
        results = []
        while 1:
            row = cursor.fetchone()
            if not row:
                break
            id = int(row['id'])
            result = {
                'id': id,
                'href': self.env.href.ticket(id),
                'summary': escape(row['summary'] or '(no summary)'),
                'status': row['status'] or '',
                'component': row['component'] or '',
                'owner': row['owner'] or '',
                'priority': row['priority'] or ''
            }
            results.append(result)
        cursor.close()
        return results

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
            {'name': "contains", 'value': "~",'novalue': 1},
            {'name': "doesn't cointain", 'value': "!~",'novalue': 1},
            {'name': "begins with", 'value': "^",'novalue': 1},
            {'name': "ends with", 'value': "$",'novalue': 1},
            {'name': "is", 'value': "",'novalue': 1},
            {'name': "is not", 'value': "!",'novalue': 1}
        ]
        modes['select'] = [
            {'name': "is", 'value': "",'novalue': 1},
            {'name': "is not", 'value': "!",'novalue': 1}
        ]
        return modes

    def render(self):
        self.perm.assert_permission(perm.TICKET_VIEW)

        constraints = self._get_constraints()
        order = self.args.get('order', 'priority')
        desc = self.args.has_key('desc')

        if self.args.has_key('update'):
            self.req.redirect(self.env.href.query(constraints, order, desc))
        props = self._get_ticket_properties()
        add_to_hdf(props, self.req.hdf, 'ticket.properties')
        modes = self._get_constraint_modes()
        add_to_hdf(modes, self.req.hdf, 'query.modes')

        self._render_results(constraints, order, desc)

        # For clients without JavaScript, we add a new constraint here if
        # requested
        if self.args.has_key('add'):
            field = self.args.get('add_filter')
            if field:
                self.req.hdf.setValue('query.constraints.%s.0' % field, '')

    def _render_results(self, constraints, order, desc):
        self.req.hdf.setValue('title', 'Custom Query')

        # FIXME: the user should be able to configure which columns should
        # be displayed
        headers = [ 'id', 'summary', 'status', 'component', 'owner' ]
        cols = headers
        if not 'priority' in cols:
            cols.append('priority')

        if order != 'id' and not order in Ticket.std_fields:
            # order by priority by default
            order = 'priority'
        for i in range(len(headers)):
            self.req.hdf.setValue('query.headers.%d.name' % i, headers[i])
            if headers[i] == order:
                self.req.hdf.setValue('query.headers.%d.href' % i,
                    self.env.href.query(constraints, order, not desc))
                self.req.hdf.setValue('query.headers.%d.order' % i,
                    desc and 'desc' or 'asc')
            else:
                self.req.hdf.setValue('query.headers.%d.href' % i,
                    self.env.href.query(constraints, headers[i]))

        sql = []
        sql.append("SELECT " + ", ".join(headers))
        custom_fields = [f['name'] for f in get_custom_fields(self.env)]
        for k in [k for k in constraints.keys() if k in custom_fields]:
            sql.append(", %s.value AS %s" % (k, k))
        sql.append(" FROM ticket")
        for k in [k for k in constraints.keys() if k in custom_fields]:
           sql.append(" LEFT OUTER JOIN ticket_custom AS %s ON " \
                      "(id=%s.ticket AND %s.name='%s')"
                      % (k, k, k, k))

        for col in [c for c in ['status', 'resolution', 'priority', 'severity']
                    if c in cols]:
            sql.append(" INNER JOIN (SELECT name AS %s_name, value AS %s_value " \
                                   "FROM enum WHERE type='%s')" \
                       " ON %s_name=%s" % (col, col, col, col, col))

        clauses = []
        for k, v in constraints.items():
            if len(v) > 1:
                inlist = ["'" + sql_escape(val) + "'" for val in v]
                clauses.append("%s IN (%s)" % (k, ",".join(inlist)))
                add_to_hdf(v, self.req.hdf, 'query.constraints.%s' % k)
            elif len(v) == 1:
                val = v[0]

                neg = val[:1] == '!'
                if neg:
                    val = val[1:]
                mode = ''
                if val[:1] in "~^$*|-":
                    mode, val = val[:1], val[1:]
                self.req.hdf.setValue('query.constraints.%s.mode' % k, (neg and '!' or '') + mode)
                add_to_hdf([val], self.req.hdf, 'query.constraints.%s' % k)

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
            sql.append(" WHERE " + " AND ".join(clauses))

        if order in ['status', 'resolution', 'priority', 'severity']:
            sql.append(" ORDER BY %s_value" % order)
        else:
            sql.append(" ORDER BY " + order)
        self.req.hdf.setValue('query.order', order)
        if desc:
            sql.append(" DESC")
            self.req.hdf.setValue('query.desc', '1')

        sql = "".join(sql)
        self.log.debug("SQL Query: %s" % sql)
        results = self._get_results(sql)
        add_to_hdf(results, self.req.hdf, 'query.results')
