# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004, 2005 Edgewall Software
# Copyright (C) 2003, 2004, 2005 Jonas Borgstr�m <jonas@edgewall.com>
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
# Author: Jonas Borgstr�m <jonas@edgewall.com>

from __future__ import generators

from trac import util
from trac.core import *
from trac.perm import IPermissionRequestor
from trac.object import ITracObjectManager
from trac.wiki import IWikiSyntaxProvider
from trac.Search import ISearchSource, query_to_sql, shorten_result


class MyLinkResolver(Component):
    """
    A dummy macro used by the unit test. We need to supply our own macro
    because the real HelloWorld-macro can not be loaded using our
    'fake' environment.
    """


class TicketSystem(Component):
    implements(IPermissionRequestor, IWikiSyntaxProvider, ITracObjectManager,
               ISearchSource)

    # Public API

    def get_available_actions(self, ticket, perm_):
        """Returns the actions that can be performed on the ticket."""
        actions = {
            'new':      ['leave', 'resolve', 'reassign', 'accept'],
            'assigned': ['leave', 'resolve', 'reassign'          ],
            'reopened': ['leave', 'resolve', 'reassign'          ],
            'closed':   ['leave',                        'reopen']
        }
        perms = {'resolve': 'TICKET_MODIFY', 'reassign': 'TICKET_CHGPROP',
                 'accept': 'TICKET_CHGPROP', 'reopen': 'TICKET_CREATE'}
        return [action for action in actions.get(ticket['status'], ['leave'])
                if action not in perms or perm_.has_permission(perms[action])]

    def get_ticket_fields(self):
        """Returns the list of fields available for tickets."""
        from trac.ticket import model
        from trac.Milestone import Milestone

        db = self.env.get_db_cnx()
        fields = []

        # Basic text fields
        for name in ('summary', 'reporter'):
            field = {'name': name, 'type': 'text', 'label': name.title()}
            fields.append(field)

        # Owner field, can be text or drop-down depending on configuration
        field = {'name': 'owner', 'label': 'Owner'}
        if self.config.get('ticket', 'restrict_owner').lower() in util.TRUE:
            field['type'] = 'select'
            users = []
            for username, name, email in self.env.get_known_users(db):
                users.append(username)
            field['options'] = users
        else:
            field['type'] = 'text'
        fields.append(field)

        # Description
        fields.append({'name': 'description', 'type': 'textarea',
                       'label': 'Description'})

        # Default select and radio fields
        selects = [('type', model.Type), ('status', model.Status),
                   ('priority', model.Priority), ('milestone', Milestone),
                   ('component', model.Component), ('version', model.Version),
                   ('severity', model.Severity), ('resolution', model.Resolution)]
        for name, cls in selects:
            options = [val.name for val in cls.select(self.env, db=db)]
            if not options:
                # Fields without possible values are treated as if they didn't
                # exist
                continue
            field = {'name': name, 'type': 'select', 'label': name.title(),
                     'value': self.config.get('ticket', 'default_' + name),
                     'options': options}
            if name in ('status', 'resolution'):
                field['type'] = 'radio'
            elif name in ('milestone', 'version'):
                field['optional'] = True
            fields.append(field)

        # Advanced text fields
        for name in ('keywords', 'cc', ):
            field = {'name': name, 'type': 'text', 'label': name.title()}
            fields.append(field)

        custom_fields = self.get_custom_fields()
        for field in custom_fields:
            field['custom'] = True

        return fields + custom_fields

    def get_custom_fields(self):
        fields = []
        for name in [option for option, value
                     in self.config.options('ticket-custom')
                     if '.' not in option]:
            field = {
                'name': name,
                'type': self.config.get('ticket-custom', name),
                'order': int(self.config.get('ticket-custom', name + '.order', '0')),
                'label': self.config.get('ticket-custom', name + '.label', ''),
                'value': self.config.get('ticket-custom', name + '.value', '')
            }
            if field['type'] == 'select' or field['type'] == 'radio':
                options = self.config.get('ticket-custom', name + '.options')
                field['options'] = [value.strip() for value in options.split('|')]
            elif field['type'] == 'textarea':
                field['width'] = self.config.get('ticket-custom', name + '.cols')
                field['height'] = self.config.get('ticket-custom', name + '.rows')
            fields.append(field)

        fields.sort(lambda x, y: cmp(x['order'], y['order']))
        return fields

    # IPermissionRequestor methods

    def get_permission_actions(self):
        return ['TICKET_APPEND', 'TICKET_CREATE', 'TICKET_CHGPROP',
                'TICKET_VIEW',  
                ('TICKET_MODIFY', ['TICKET_APPEND', 'TICKET_CHGPROP']),  
                ('TICKET_ADMIN', ['TICKET_CREATE', 'TICKET_MODIFY',  
                                  'TICKET_VIEW'])]

    # IWikiSyntaxProvider methods

    def get_link_resolvers(self):
        return [('bug', self._format_link, self._parse_link),
                ('ticket', self._format_link, self._parse_link)]

    def get_wiki_syntax(self):
        yield (r"!?#(?P<it_ticket>[a-zA-Z_-]{0,3})\d+",
               lambda x, y, z: self._format_link(x, 'ticket', y[1:], y, z),
               lambda x, y, z: self._parse_link(x, 'ticket', y[1:], y, z))

    def _format_link(self, formatter, ns, target, label, fullmatch=None):
        intertrac = formatter.shorthand_intertrac_helper(ns, target, label,
                                                         fullmatch)
        if intertrac:
            return intertrac
        cursor = formatter.db.cursor()
        cursor.execute("SELECT summary,status FROM ticket WHERE id=%s",
                       (target,))
        row = cursor.fetchone()
        if row:
            summary = util.escape(util.shorten_line(row[0]))
            return '<a class="%s ticket" href="%s" title="%s (%s)">%s</a>' \
                   % (row[1], formatter.href.ticket(target), summary, row[1],
                      label)
        else:
            return '<a class="missing ticket" href="%s" rel="nofollow">%s</a>' \
                   % (formatter.href.ticket(target), label)

    def _parse_link(self, formatter, ns, target, label, fullmatch=None):
        intertrac = formatter.shorthand_intertrac_helper(ns, target, label,
                                                         fullmatch)
        if not intertrac:
            from trac.ticket import Ticket
            ticket = Ticket(self.env)
            ticket.id = target
            return ticket
    
    # ITracObjectManager methods

    def get_object_types(self):
        from trac.ticket.model import Ticket
        yield ('ticket', lambda id: Ticket(self.env, id))

    def rebuild_xrefs(self, db):
        from trac.ticket.model import Ticket
        cursor = db.cursor()
        cursor.execute("SELECT id,description,time,reporter FROM ticket")
        for id,description,time,reporter in cursor:
            src = Ticket(self.env, None)
            src.id = id
            descr_time = time
            descr_author = reporter
            chg_cursor = db.cursor()
            chg_cursor.execute("SELECT field,oldvalue,newvalue,time,author"
                               "  FROM ticket_change"
                               " WHERE ticket=%s"
                               "   AND field IN ('comment','description')"
                               " ORDER BY time", (id,))
            for field,n,value,time,author in chg_cursor:
                if field == 'description':
                    descr_time = time
                    descr_author = author
                    description = value
                elif field == 'comment':
                    yield (src, 'comment:%s' % n, time, author, value)
                # TODO: custom fields?
            yield (src, 'description', descr_time, descr_author, description)

    # ISearchProvider methods

    def get_search_filters(self, req):
        if req.perm.has_permission('TICKET_VIEW'):
            yield ('ticket', 'Tickets')

    def get_search_results(self, req, query, filters):
        if not 'ticket' in filters:
            return
        db = self.env.get_db_cnx()
        sql = "SELECT DISTINCT a.summary,a.description,a.reporter, " \
              "a.keywords,a.id,a.time FROM ticket a " \
              "LEFT JOIN ticket_change b ON a.id = b.ticket " \
              "WHERE (b.field='comment' AND %s ) OR " \
              "%s OR %s OR %s OR %s OR %s" % \
              (query_to_sql(db, query, 'b.newvalue'),
               query_to_sql(db, query, 'summary'),
               query_to_sql(db, query, 'keywords'),
               query_to_sql(db, query, 'description'),
               query_to_sql(db, query, 'reporter'),
               query_to_sql(db, query, 'cc'))
        cursor = db.cursor()
        cursor.execute(sql)
        for summary,desc,author,keywords,tid,date in cursor:
            yield (self.env.href.ticket(tid),
                   '#%d: %s' % (tid, util.escape(util.shorten_line(summary))),
                   date, author,
                   util.escape(shorten_result(desc, query.split())))
            
