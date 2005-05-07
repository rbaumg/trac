# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2004, 2005 Edgewall Software
# Copyright (C) 2004, 2005 Christopher Lenz <cmlenz@gmx.de>
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
from trac.Ticket import get_custom_fields, Ticket
from trac.Timeline import ITimelineEventProvider
from trac.web.chrome import add_link, INavigationContributor
from trac.web.main import IRequestHandler
from trac.WikiFormatter import wiki_to_html, wiki_to_oneliner
from trac.util import *

import time


class Milestone(object):

    def __init__(self, env, perm_=None, name=None, db=None):
        self.env = env
        self.old_name = name
        self.perm = perm_
        if name:
            self._fetch(name, db)
        else:
            self.name = None
            self.due = 0
            self.completed = 0
            self.description = ''

    def _fetch(self, name, db=None):
        if self.perm: self.perm.assert_permission(perm.MILESTONE_VIEW)
        if not db:
            db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT name,due,completed,description "
                       "FROM milestone WHERE name=%s", (name,))
        row = cursor.fetchone()
        cursor.close()
        if not row:
            raise TracError('Milestone %s does not exist.' % name,
                            'Invalid Milestone Name')
        self.name = row[0]
        self.due = row[1] and int(row[1]) or 0
        self.completed = row[2] and int(row[2]) or 0
        self.description = row[3] or ''

    exists = property(fget=lambda self: self.old_name is not None)
    is_late = property(fget=lambda self: self.due and self.due < time.time())

    def delete(self, retarget_to=None, db=None):
        if self.perm: self.perm.assert_permission(perm.MILESTONE_DELETE)
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        cursor = db.cursor()
        self.env.log.info('Deleting milestone %s' % self.name)
        cursor.execute("DELETE FROM milestone WHERE name=%s", (self.name,))

        if retarget_to:
            self.env.log.info('Retargeting milestone field of all tickets '
                              'associated with milestone "%s" to milestone "%s"'
                              % (self.name, retarget_to))
            cursor.execute("UPDATE ticket SET milestone=%s WHERE milestone=%s",
                           (retarget_to, self.name))
        else:
            self.env.log.info('Resetting milestone field of all tickets '
                              'associated with milestone %s' % self.name)
            cursor.execute("UPDATE ticket SET milestone=NULL "
                           "WHERE milestone=%s", (self.name,))

        if handle_ta:
            db.commit()

    def insert(self, db=None):
        if self.perm: self.perm.assert_permission(perm.MILESTONE_CREATE)
        assert self.name, 'Cannot create milestone with no name'
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        cursor = db.cursor()
        self.env.log.debug("Creating new milestone '%s'" % self.name)
        cursor.execute("INSERT INTO milestone (name,due,completed,description) "
                       "VALUES (%s,%s,%s,%s)",
                       (self.name, self.due, self.completed, self.description))

        if handle_ta:
            db.commit()

    def update(self, db=None):
        if self.perm: self.perm.assert_permission(perm.MILESTONE_MODIFY)
        assert self.name, 'Cannot update milestone with no name'
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        cursor = db.cursor()
        self.env.log.info('Updating milestone "%s"' % self.name)
        cursor.execute("UPDATE milestone SET name=%s,due=%s,"
                       "completed=%s,description=%s WHERE name=%s",
                       (self.name, self.due, self.completed, self.description,
                        self.old_name))
        self.env.log.info('Updating milestone field of all tickets '
                          'associated with milestone "%s"' % self.name)
        cursor.execute("UPDATE ticket SET milestone=%s WHERE milestone=%s",
                       (self.name, self.old_name))
        self.old_name = self.name

        if handle_ta:
            db.commit()


def get_tickets_for_milestone(env, db, milestone, field='component'):
    custom = field not in Ticket.std_fields
    cursor = db.cursor()
    sql = "SELECT ticket.id AS id, ticket.status AS status, "
    if custom:
        sql += "ticket_custom.value AS %s " \
               "FROM ticket LEFT OUTER JOIN ticket_custom ON id=ticket " \
               "WHERE name='%s' AND milestone='%s'" % (
               sql_escape(field), sql_escape(field), sql_escape(milestone))
    else:
        sql += "ticket.%s AS %s FROM ticket WHERE milestone='%s'" % (
               field, field, sql_escape(milestone))
    sql += " ORDER BY %s" % field

    cursor.execute(sql)
    tickets = []
    while 1:
        row = cursor.fetchone()
        if not row:
            break
        ticket = {
            'id': int(row['id']),
            'status': row['status'],
            field: row[field]
        }
        tickets.append(ticket)
    return tickets

def get_query_links(env, milestone, grouped_by='component', group=None):
    q = {}
    if not group:
        q['all_tickets'] = env.href.query(milestone=milestone)
        q['active_tickets'] = env.href.query(milestone=milestone,
                                             status=('new', 'assigned', 'reopened'))
        q['closed_tickets'] = env.href.query(milestone=milestone, status='closed')
    else:
        q['all_tickets'] = env.href.query({grouped_by: group},
                                          milestone=milestone)
        q['active_tickets'] = env.href.query({grouped_by: group},
                                             milestone=milestone,
                                             status=('new', 'assigned', 'reopened'))
        q['closed_tickets'] = env.href.query({grouped_by: group},
                                             milestone=milestone,
                                             status='closed')
    return q

def calc_ticket_stats(tickets):
    total_cnt = len(tickets)
    active = [ticket for ticket in tickets if ticket['status'] != 'closed']
    active_cnt = len(active)
    closed_cnt = total_cnt - active_cnt

    percent_active, percent_closed = 0, 0
    if total_cnt > 0:
        percent_active = round(float(active_cnt) / float(total_cnt) * 100)
        percent_closed = round(float(closed_cnt) / float(total_cnt) * 100)
        if percent_active + percent_closed > 100:
            percent_closed -= 1

    return {
        'total_tickets': total_cnt,
        'active_tickets': active_cnt,
        'percent_active': percent_active,
        'closed_tickets': closed_cnt,
        'percent_closed': percent_closed
    }

def _get_groups(env, db, by='component'):
    cursor = db.cursor()
    groups = []
    if by in ['status', 'resolution', 'severity', 'priority']:
        cursor.execute("SELECT name FROM enum WHERE type = %s "
                       "AND COALESCE(name,'')!='' ORDER BY value", (by,))
    elif by in ['component', 'milestone', 'version']:
        cursor.execute("SELECT name FROM %s "
                       "WHERE COALESCE(name,'')!='' ORDER BY name" % (by,))
    elif by == 'owner':
        cursor.execute("SELECT DISTINCT owner AS name FROM ticket "
                       "ORDER BY owner")
    elif by not in Ticket.std_fields:
        fields = get_custom_fields(env)
        field = [f for f in fields if f['name'] == by]
        if not field:
            return []
        return [o for o in field[0]['options'] if o]
    while 1:
        row = cursor.fetchone()
        if not row:
            break
        groups.append(row['name'] or '')
    return groups

def _milestone_to_hdf(req, db, m):
    hdf = {'name': m.name}
    if m.description:
        hdf['description_source'] = m.description
        hdf['description'] = wiki_to_html(m.description, req.hdf, m.env, db)
    if m.due:
        hdf['due'] = m.due
        hdf['due_date'] = time.strftime('%x', time.localtime(m.due))
        hdf['due_delta'] = pretty_timedelta(m.due)
        hdf['late'] = m.is_late
    if m.completed:
        hdf['completed'] = m.completed
        hdf['completed_date'] = time.strftime('%x %X', time.localtime(m.completed))
        hdf['completed_delta'] = pretty_timedelta(m.completed)

    return hdf

def _parse_date(datestr):
    seconds = None
    datestr = datestr.strip()
    for format in ['%x %X', '%x, %X', '%X %x', '%X, %x', '%x', '%c',
                   '%b %d, %Y']:
        try:
            date = time.strptime(datestr, format)
            seconds = time.mktime(date)
            break
        except ValueError:
            continue
    if seconds == None:
        raise TracError('%s is not a known date format.' % datestr,
                        'Invalid Date Format')
    return seconds


class MilestoneModule(Component):

    implements(INavigationContributor, IRequestHandler, ITimelineEventProvider)

    # INavigationContributor methods

    def get_active_navigation_item(self, req):
        return 'roadmap'

    def get_navigation_items(self, req):
        return []

    # ITimelineEventProvider methods

    def get_timeline_filters(self, req):
        if req.perm.has_permission(perm.MILESTONE_VIEW):
            yield ('milestone', 'Milestones')

    def get_timeline_events(self, req, start, stop, filters):
        if 'milestone' in filters:
            absurls = req.args.get('format') == 'rss' # Kludge
            db = self.env.get_db_cnx()
            cursor = db.cursor()
            cursor.execute("SELECT completed,name,description FROM milestone "
                           "WHERE completed>=%s AND completed<=%s", start, stop)
            for completed,name,description in cursor:
                if absurls:
                    href = self.env.abs_href.milestone(name)
                else:
                    href = self.env.href.milestone(name)
                title = 'Milestone <em>%s</em> completed' % escape(name)
                message = wiki_to_oneliner(shorten_line(description),
                                           self.env, db, absurls=absurls)
                yield 'milestone', href, title, completed, None, message

    # IRequestHandler methods

    def match_request(self, req):
        import re, urllib
        match = re.match(r'/milestone(?:/([^\?]+))?(?:/(.*)/?)?', req.path_info)
        if match:
            if match.group(1):
                req.args['id'] = urllib.unquote(match.group(1))
            return 1

    def process_request(self, req):
        req.perm.assert_permission(perm.MILESTONE_VIEW)

        add_link(req, 'up', self.env.href.roadmap(), 'Roadmap')

        db = self.env.get_db_cnx()
        m = Milestone(self.env, req.perm, req.args.get('id'), db)

        action = req.args.get('action', 'view')
        if action in ('new', 'edit'):
            self._render_editor(req, db, m)
        elif action == 'delete':
            self._render_confirm(req, db, m)
        elif action == 'commit_changes':
            self._do_save(req, db, m)
        elif action == 'confirm_delete':
            self._do_delete(req, db, m)
        else:
            self._render_view(req, db, m)

        return 'milestone.cs', None

    # Internal methods

    def _do_delete(self, req, db, milestone):
        if req.args.has_key('delete'):
            retarget_to = None
            if req.args.has_key('retarget'):
                retarget_to = req.args.get('target')
            milestone.delete(retarget_to)
            db.commit()
            req.redirect(self.env.href.roadmap())
        else:
            req.redirect(self.env.href.milestone(milestone.name))

    def _do_save(self, req, db, milestone):
        if req.args.has_key('save'):
            if not 'name' in req.args.keys():
                raise TracError('You must provide a name for the milestone.',
                                'Required Field Missing')
            milestone.name = req.args.get('name')

            due = req.args.get('duedate', '')
            if due:
                milestone.due = _parse_date(due)

            if 'completed' in req.args.keys():
                completed = req.args.get('completeddate', '')
                if completed:
                    milestone.completed = _parse_date(completed)
            else:
                milestone.completed = 0

            if 'description' in req.args.keys():
                milestone.description = req.args.get('description')

            if milestone.exists:
                milestone.update()
            else:
                milestone.insert()
            db.commit()

        if milestone.exists:
            req.redirect(self.env.href.milestone(milestone.name))
        else:
            req.redirect(self.env.href.roadmap())

    def _render_confirm(self, req, db, m):
        req.perm.assert_permission(perm.MILESTONE_DELETE)

        req.hdf['title'] = 'Milestone %s' % m.name
        req.hdf['milestone'] = _milestone_to_hdf(req, db, m)
        req.hdf['milestone.mode'] = 'delete'
        req.hdf['milestone.href'] = self.env.href.milestone(m.name)

        cursor = db.cursor()
        cursor.execute("SELECT name FROM milestone "
                       "WHERE name!='' ORDER BY name")
        for idx, (name,) in enum(cursor):
            req.hdf['milestones.%d' % idx] = name

    def _render_editor(self, req, db, milestone):

        if milestone.exists:
            req.perm.assert_permission(perm.MILESTONE_MODIFY)
            req.hdf['title'] = 'Milestone %s' % milestone.name
            req.hdf['milestone.mode'] = 'edit'
        else:
            req.perm.assert_permission(perm.MILESTONE_CREATE)
            req.hdf['title'] = 'New Milestone'
            req.hdf['milestone.mode'] = 'new'

        req.hdf['milestone'] = _milestone_to_hdf(req, db, milestone)
        req.hdf['milestone.href'] = self.env.href.milestone(milestone.name)
        req.hdf['milestone.date_hint'] = get_date_format_hint()
        req.hdf['milestone.datetime_hint'] = get_datetime_format_hint()
        req.hdf['milestone.datetime_now'] = time.strftime('%x %X',
                                                          time.localtime(time.time()))

    def _render_view(self, req, db, milestone):
        req.hdf['title'] = 'Milestone %s' % milestone.name
        req.hdf['milestone.mode'] = 'view'

        # If the milestone name contains slashes, we'll need to include the 'id'
        # parameter in the forms for editing/deleting the milestone. See #806.
        if milestone.name.find('/') >= 0:
            req.hdf['milestone.id_param'] = 1

        req.hdf['milestone'] = _milestone_to_hdf(req, db, milestone)

        available_groups = map(lambda x: {'name': x, 'label': x.capitalize()},
                               ['component', 'version', 'severity', 'priority',
                                'owner'])
        for f in [f for f in get_custom_fields(self.env)
                  if f['type'] in ('select', 'radio')]:
            available_groups.append({'name': f['name'],
                                     'label': f['label'] or f['name']})
        req.hdf['milestone.stats.available_groups'] = available_groups

        by = req.args.get('by', 'component')
        req.hdf['milestone.stats.grouped_by'] = by

        tickets = get_tickets_for_milestone(self.env, db, milestone.name, by)
        stats = calc_ticket_stats(tickets)
        req.hdf['milestone.stats'] = stats
        queries = get_query_links(self.env, milestone.name)
        req.hdf['milestone.queries'] = queries

        groups = _get_groups(self.env, db, by)
        group_no = 0
        max_percent_total = 0
        for group in groups:
            group_tickets = [t for t in tickets if t[by] == group]
            if not group_tickets:
                continue
            prefix = 'milestone.stats.groups.%s' % group_no
            req.hdf['%s.name' % prefix] = group
            percent_total = 0
            if len(tickets) > 0:
                percent_total = float(len(group_tickets)) / float(len(tickets))
                if percent_total > max_percent_total:
                    max_percent_total = percent_total
            req.hdf['%s.percent_total' % prefix] = percent_total * 100
            stats = calc_ticket_stats(group_tickets)
            req.hdf[prefix] = stats
            queries = get_query_links(self.env, milestone.name, by, group)
            req.hdf['%s.queries' % prefix] = queries
            group_no += 1
        req.hdf['milestone.stats.max_percent_total'] = max_percent_total * 100
