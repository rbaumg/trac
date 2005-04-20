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

from trac import perm
from trac.core import *
from trac.util import enum, escape, shorten_line
from trac.versioncontrol.svn_authz import SubversionAuthorizer
from trac.web.chrome import add_link
from trac.WikiFormatter import wiki_to_oneliner, wiki_to_html

import time

AVAILABLE_FILTERS = ('ticket', 'changeset', 'wiki', 'milestone')


class TimelineModule(Component):

    extends('RequestDispatcher.handlers')

    # IRequestHandler methods

    def match_request(self, req):
        return req.path_info == '/timeline'

    def process_request(self, req):
        req.perm.assert_permission(perm.TIMELINE_VIEW)

        # Kludge: needed to force new check-ins to show up in the timeline
        repos = self.env.get_repository()
        repos.sync()
        self.authzperm = repos.authz
        repos.close()

        # Parse the from date and adjust the timestamp to the last second of
        # the day
        t = time.localtime()
        if req.args.has_key('from'):
            try:
                t = time.strptime(req.args.get('from'), '%x')
            except:
                pass
        fromdate = time.mktime((t[0], t[1], t[2], 23, 59, 59, t[6], t[7], t[8]))

        try:
            daysback = max(0, int(req.args.get('daysback', '')))
        except ValueError:
            daysback = 30
        req.hdf['timeline.from'] = time.strftime('%x', time.localtime(fromdate))
        req.hdf['timeline.daysback'] = daysback

        stop = fromdate
        start = stop - (daysback + 1) * 86400
        maxrows = int(req.args.get('max', 0))

        filters = [k for k in AVAILABLE_FILTERS if k in req.args.keys()]
        if not filters:
            filters = AVAILABLE_FILTERS[:]

        req.hdf['title'] = 'Timeline'
        format = req.args.get('format')

        db = self.env.get_db_cnx()
        events = self.get_info(req, db, start, stop, maxrows, filters)
        for idx, event in enum(events):
            render_func = getattr(self, '_render_%s' % event['type'])
            event = render_func(req, db, event)
            if not event:
                continue

            if format == 'rss':
                # For RSS, author must be an email address
                if event['author'].find('@') != -1:
                    event['author.email'] = event['author']

            req.hdf['timeline.items.%d' % idx] = event

        if format == 'rss':
            self.display_rss(req)
        else:
            self.display_html(req, filters)

    # Internal methods

    def get_info(self, req, db, start, stop, maxrows,
                 filters=AVAILABLE_FILTERS):
        perm_map = {'ticket': perm.TICKET_VIEW, 'changeset': perm.CHANGESET_VIEW,
                    'wiki': perm.WIKI_VIEW, 'milestone': perm.MILESTONE_VIEW}
        filters = list(filters) # copy list so we can make modifications
        for k,v in perm_map.items():
            if k in filters and not req.perm.has_permission(v):
                filters.remove(k)
        if not filters:
            return []

        sql, params = [], []
        if 'changeset' in filters:
            sql.append("SELECT time,rev,'','changeset',message,author"
                       " FROM revision WHERE time>=%s AND time<=%s")
            params += (start, stop)
        if 'ticket' in filters:
            sql.append("SELECT time,id,'','newticket',summary,reporter"
                       " FROM ticket WHERE time>=%s AND time<=%s")
            params += (start, stop)
            sql.append("SELECT time,ticket,'','reopenedticket','',author "
                       "FROM ticket_change WHERE field='status' "
                       "AND newvalue='reopened' AND time>=%s AND time<=%s")
            params += (start, stop)
            sql.append("SELECT t1.time,t1.ticket,t2.newvalue,'closedticket',"
                       "t3.newvalue,t1.author"
                       " FROM ticket_change t1"
                       "   INNER JOIN ticket_change t2 ON t1.ticket = t2.ticket"
                       "     AND t1.time = t2.time"
                       "   LEFT OUTER JOIN ticket_change t3 ON t1.time = t3.time"
                       "     AND t1.ticket = t3.ticket AND t3.field = 'comment'"
                       " WHERE t1.field = 'status' AND t1.newvalue = 'closed'"
                       "   AND t2.field = 'resolution'"
                       "   AND t1.time >= %s AND t1.time <= %s")
            params += (start,stop)
        if 'wiki' in filters:
            sql.append("SELECT time,-1,name,'wiki',comment,author"
                       " FROM wiki WHERE time>=%s AND time<=%s")
            params += (start, stop)
        if 'milestone' in filters:
            sql.append("SELECT completed AS time,-1,name,'milestone','',''" 
                       " FROM milestone WHERE completed>=%s AND completed<=%s")
            params += (start, stop)

        sql = ' UNION ALL '.join(sql) + ' ORDER BY time DESC'
        if maxrows:
            sql += ' LIMIT %d'
            params += (maxrows,)

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(sql, params)

        # Make the data more HDF-friendly
        info = []
        for idx, row in enum(cursor):
            if idx == 0:
                req.check_modified(int(row[0]))
            t = time.localtime(int(row[0]))
            gmt = time.gmtime(int(row[0]))
            item = {
                'time': time.strftime('%H:%M', t),
                'date': time.strftime('%x', t),
                'datetime': time.strftime('%a, %d %b %Y %H:%M:%S GMT', gmt),
                'idata': int(row[1]),
                'tdata': escape(row[2]),
                'type': row[3],
                'message': row[4] or '',
                'author': escape(row[5] or 'anonymous')
            }
            info.append(item)
        return info

    def display_html(self, req, filters):
        rss_href = self.env.href.timeline([(x,'on') for x in filters],
                                          daysback=90, max=50, format='rss')
        add_link(req, 'alternate', rss_href, 'RSS Feed', 'application/rss+xml',
                 'rss')

        filter_labels = {'wiki': 'Wiki changes', 'ticket': 'Ticket changes',
                         'changeset': 'Repository check-ins',
                         'milestone': 'Milestones'}
        perm_map = {'ticket': perm.TICKET_VIEW, 'changeset': perm.CHANGESET_VIEW,
                    'wiki': perm.WIKI_VIEW, 'milestone': perm.MILESTONE_VIEW}
        for idx,fltr in enum([f for f in AVAILABLE_FILTERS
                              if req.perm.has_permission(perm_map[f])]):
            req.hdf['timeline.filters.%d' % idx] = {
                'name': fltr, 'label': filter_labels[fltr],
                'enabled': int(fltr in filters)
            }

        req.display('timeline.cs')

    def display_rss(self, req):
        req.display('timeline_rss.cs', 'application/rss+xml')

    def _render_changeset(self, req, db, item):
        absurls = req.args.get('format') == 'rss'
        href = self.env.href
        if absurls:
            href = self.env.abs_href

        if not self.authzperm.has_permission_for_changeset(item['idata']):
            return None

        item['href'] = escape(href.changeset(item['idata']))
        if req.args.get('format') == 'rss':
            item['message'] = escape(wiki_to_html(item['message'], req.hdf,
                                                  self.env, db, absurls=absurls))
        else:
            item['message'] = wiki_to_oneliner(item['message'], self.env, db,
                                               absurls=absurls)

        try:
            show_files = int(self.config.get('timeline', 'changeset_show_files'))
        except ValueError, e:
            self.log.warning("Invalid 'changeset_show_files' value, "
                             "please fix trac.ini: %s" % e)
            show_files = 0

        if show_files:
            cursor = db.cursor()
            cursor.execute("SELECT path,change FROM node_change WHERE rev=%s",
                           (item['idata']))
            files = []
            class_map = {'A': 'add', 'C': 'add', 'D': 'rem', 'M': 'mod'}
            for path, change in cursor:
                if show_files > 0 and len(files) >= show_files:
                    files.append('...')
                    break
                if not self.authzperm.has_permission(path):
                    continue
                files.append('<span class="diff-%s">%s</span>'
                             % (class_map.get(change, 'mod'), path))
            item['node_list'] = ', '.join(files) + ': '

        return item

    def _render_ticket(self, req, db, item):
        absurls = req.args.get('format') == 'rss'
        href = self.env.href
        if absurls:
            href = self.env.abs_href

        item['href'] = escape(href.ticket(item['idata']))
        if req.args.get('format') == 'rss':
            item['message'] = escape(wiki_to_html(item['message'],
                                                  req.hdf, self.env, db,
                                                  absurls=absurls))
        else:
            item['message'] = wiki_to_oneliner(shorten_line(item['message']),
                                               self.env, db, absurls=absurls)
        return item
    _render_reopenedticket = _render_ticket
    _render_newticket = _render_ticket
    _render_closedticket = _render_ticket

    def _render_milestone(self, req, db, item):
        absurls = req.args.get('format') == 'rss'
        href = self.env.href
        if absurls:
            href = self.env.abs_href

        item['href'] = escape(href.milestone(item['tdata']))
        return item

    def _render_wiki(self, req, db, item):
        absurls = req.args.get('format') == 'rss'
        href = self.env.href
        if absurls:
            href = self.env.abs_href

        item['href'] = escape(href.wiki(item['tdata']))
        item['message'] = wiki_to_oneliner(shorten_line(item['message']),
                                           self.env, db, absurls=absurls)
        if req.args.get('format') == 'rss':
            item['message'] = escape(item['message'])
        return item
