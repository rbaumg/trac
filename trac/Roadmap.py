# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2004 Edgewall Software
# Copyright (C) 2004 Christopher Lenz <cmlenz@gmx.de>
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

from __future__ import nested_scopes
import re
from time import localtime, strftime, time

from __init__ import __version__
import perm
import Milestone
from util import add_to_hdf, pretty_timedelta, CRLF, TracError
from Module import Module
from Ticket import Ticket
from Wiki import wiki_to_html


class Roadmap(Module):
    template_name = 'roadmap.cs'

    def render(self, req):
        self.req = req # FIXME
        self.perm.assert_permission(perm.ROADMAP_VIEW)
        self.req.hdf.setValue('title', 'Roadmap')

        icalhref = '?format=ics'
        show = self.req.args.get('show', 'current')
        if show == 'all':
            icalhref += '&show=all'
            query = "SELECT name,due,completed,description FROM milestone " \
                    "WHERE COALESCE(name,'')!='' " \
                    "ORDER BY COALESCE(due,0)=0,due,name"
        else:
            self.req.hdf.setValue('roadmap.showall', '1')
            query = "SELECT name,due,completed,description FROM milestone " \
                    "WHERE COALESCE(name,'')!='' " \
                    "AND COALESCE(completed,0)=0 " \
                    "ORDER BY COALESCE(due,0)=0,due,name"

        if self.req.authname and self.req.authname != 'anonymous':
            icalhref += '&user=' + self.req.authname
        self.add_link('alternate', icalhref, 'iCalendar', 'text/calendar', 'ics')

        cursor = self.db.cursor()
        cursor.execute(query)
        self.milestones = []
        while 1:
            row = cursor.fetchone()
            if not row:
                break
            milestone = {
                'name': row['name'],
                'href': self.env.href.milestone(row['name']),
                'due': row['due'] and int(row['due']),
                'completed': row['completed'] and int(row['completed'])
            }
            description = row['description']
            if description:
                milestone['description'] = wiki_to_html(description,
                                                        self.req.hdf,
                                                        self.env, self.db)
                milestone['description_text'] = description
            if milestone['due'] > 0:
                milestone['due_date'] = strftime('%x', localtime(milestone['due']))
                milestone['due_delta'] = pretty_timedelta(milestone['due'])
                if milestone['due'] < time():
                    milestone['late'] = 1
            if milestone['completed'] > 0:
                milestone['completed_date'] = strftime('%x', localtime(milestone['completed']))
                milestone['completed_delta'] = pretty_timedelta(milestone['completed'])
            self.milestones.append(milestone)
        cursor.close()
        add_to_hdf(self.milestones, self.req.hdf, 'roadmap.milestones')

        milestone_no = 0
        for milestone in self.milestones:
            tickets = Milestone.get_tickets_for_milestone(self.env, self.db,
                                                          milestone['name'],
                                                          'owner')
            stats = Milestone.calc_ticket_stats(tickets)
            add_to_hdf(stats, self.req.hdf,
                       'roadmap.milestones.%d.stats' % int(milestone_no))
            queries = Milestone.get_query_links(self.env, milestone['name'])
            add_to_hdf(queries, self.req.hdf,
                       'roadmap.milestones.%d.queries' % int(milestone_no))
            milestone['tickets'] = tickets
            milestone_no += 1

    def display_ics(self, req):
        req.send_response(200)
        req.send_header('Content-Type', 'text/calendar;charset=utf-8')
        req.end_headers()

        priority_mapping = {'highest': '1', 'high': '3', 'normal': '5',
                            'low': '7', 'lowest': '9'}
    
        def get_status(ticket):
            status = ticket['status']
            if status == 'new' or status == 'reopened' and not ticket['owner']:
                return 'NEEDS-ACTION'
            elif status == 'assigned' or status == 'reopened':
                return 'IN-PROCESS'
            elif status == 'closed':
                if ticket['resolution'] == 'fixed': return 'COMPLETED'
                else: return 'CANCELLED'
            else: return ''

        def write_prop(name, value, params={}):
            text = ';'.join([name] + [k + '=' + v for k, v in params.items()]) \
                 + ':' + '\\n'.join(re.split(r'[\r\n]+', value))
            firstline = 1
            while text:
                if not firstline: text = ' ' + text
                else: firstline = 0
                req.write(text[:75] + CRLF)
                text = text[75:]

        def write_date(name, value, params={}):
            params['VALUE'] = 'DATE'
            write_prop(name, strftime('%Y%m%d', value), params)

        def write_utctime(name, value, params={}):
            write_prop(name, strftime('%Y%m%dT%H%M%SZ', value), params)

        host = req.base_url[req.base_url.find('://') + 3:]
        user = req.args.get('user', 'anonymous')

        write_prop('BEGIN', 'VCALENDAR')
        write_prop('VERSION', '2.0')
        write_prop('PRODID', '-//Edgewall Software//NONSGML Trac %s//EN'
                   % __version__)
        write_prop('X-WR-CALNAME',
                   self.env.get_config('project', 'name') + ' - Roadmap')
        for milestone in self.milestones:
            uid = '<%s/milestone/%s@%s>' % (req.cgi_location,
                                            milestone['name'], host)
            if milestone.has_key('date'):
                write_prop('BEGIN', 'VEVENT')
                write_prop('UID', uid)
                if milestone.has_key('date'):
                    write_date('DTSTART', localtime(milestone['due']))
                write_prop('SUMMARY', 'Milestone %s' % milestone['name'])
                write_prop('URL', req.base_url + '/milestone/' + milestone['name'])
                if milestone.has_key('description'):
                    write_prop('DESCRIPTION', milestone['description_text'])
                write_prop('END', 'VEVENT')
            for ticket in [ticket for ticket in milestone['tickets']
                          if ticket['owner'] == user]:
                ticket = Ticket(self.db, ticket['id'])
                write_prop('BEGIN', 'VTODO')
                if milestone.has_key('date'):
                    write_prop('RELATED-TO', uid)
                    write_date('DUE', localtime(milestone['due']))
                write_prop('SUMMARY', 'Ticket #%i: %s' % (ticket['id'],
                                                          ticket['summary']))
                write_prop('URL', req.base_url + '/ticket/' + str(ticket['id']))
                write_prop('DESCRIPTION', ticket['description'])
                write_prop('PRIORITY', priority_mapping[ticket['priority']])
                write_prop('STATUS', get_status(ticket))
                if ticket['status'] == 'closed':
                    cursor = self.db.cursor()
                    cursor.execute("SELECT time FROM ticket_change "
                                   "WHERE ticket = %s AND field = 'status' "
                                   "ORDER BY time desc LIMIT 1", ticket['id'])
                    row = cursor.fetchone()
                    if row: write_utctime('COMPLETED', localtime(row['time']))
                write_prop('END', 'VTODO')
        write_prop('END', 'VCALENDAR')
