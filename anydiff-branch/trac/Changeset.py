# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004, 2005 Edgewall Software
# Copyright (C) 2003, 2004, 2005 Jonas Borgström <jonas@edgewall.com>
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
# Author: Jonas Borgström <jonas@edgewall.com>
#         Christopher Lenz <cmlenz@gmx.de>

from __future__ import generators
import time
import re

from trac import mimeview, util
from trac.core import *
from trac.perm import IPermissionRequestor
from trac.Timeline import ITimelineEventProvider
from trac.versioncontrol import Changeset, Node
from trac.web.main import IRequestHandler
from trac.wiki import wiki_to_html, wiki_to_oneliner, IWikiSyntaxProvider
from trac.Diff import DiffMixin

class ChangesetModule(Component,DiffMixin):

    implements(IRequestHandler, ITimelineEventProvider, IWikiSyntaxProvider)

    # IRequestHandler methods

    def match_request(self, req):
        match = re.match(r'/changeset/([0-9]+)$', req.path_info)
        if match:
            req.args['rev'] = match.group(1)
            return 1

    def process_request(self, req):
        req.perm.assert_permission('CHANGESET_VIEW')
        return DiffMixin.process_request(self, req)

    # ITimelineEventProvider methods

    def get_timeline_filters(self, req):
        if req.perm.has_permission('CHANGESET_VIEW'):
            yield ('changeset', 'Repository checkins')

    def get_timeline_events(self, req, start, stop, filters):
        if 'changeset' in filters:
            format = req.args.get('format')
            show_files = int(self.config.get('timeline',
                                             'changeset_show_files'))
            db = self.env.get_db_cnx()
            repos = self.env.get_repository()
            rev = repos.youngest_rev
            while rev:
                chgset = repos.get_changeset(rev)
                if chgset.date < start:
                    return
                if chgset.date < stop:
                    title = 'Changeset <em>[%s]</em> by %s' % (
                            util.escape(chgset.rev), util.escape(chgset.author))
                    if format == 'rss':
                        href = self.env.abs_href.changeset(chgset.rev)
                        message = wiki_to_html(chgset.message or '--', self.env,
                                               db, absurls=True)
                    else:
                        href = self.env.href.changeset(chgset.rev)
                        excerpt = util.shorten_line(chgset.message or '--')
                        message = wiki_to_oneliner(excerpt, self.env, db)
                    if show_files:
                        files = []
                        for chg in chgset.get_changes():
                            if show_files > 0 and len(files) >= show_files:
                                files.append('...')
                                break
                            files.append('<span class="%s">%s</span>'
                                         % (chg[2], util.escape(chg[0])))
                        message = '<span class="changes">' + ', '.join(files) +\
                                  '</span>: ' + message
                    yield 'changeset', href, title, chgset.date, chgset.author,\
                          message
                rev = repos.previous_rev(rev)

    # IWikiSyntaxProvider methods
    
    def get_wiki_syntax(self):
        yield (r"!?\[\d+\]|\br\d+\b", (lambda x, y, z: self._format_link(x, 'changeset', y[0] == 'r' and y[1:] or y[1:-1], y)))

    def get_link_resolvers(self):
        yield ('changeset', self._format_link)

    def _format_link(self, formatter, ns, rev, label):
        cursor = formatter.db.cursor()
        cursor.execute('SELECT message FROM revision WHERE rev=%s', (rev,))
        row = cursor.fetchone()
        if row:
            return '<a class="changeset" title="%s" href="%s">%s</a>' \
                   % (util.escape(util.shorten_line(row[0])),
                      formatter.href.changeset(rev), label)
        else:
            return '<a class="missing changeset" href="%s" rel="nofollow">%s</a>' \
                   % (formatter.href.changeset(rev), label)
