# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004, 2005 Edgewall Software
# Copyright (C) 2003, 2004, 2005 Jonas Borgström <jonas@edgewall.com>
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

import time
import util
import re

from trac import perm
from trac.Module import Module
from trac.WikiFormatter import wiki_to_html
from trac.versioncontrol import Changeset, Node
from trac.versioncontrol.diff import get_diff_options, hdf_diff, unified_diff


class Changeset(Module):
    template_name = 'changeset.cs'

    def render(self, req):
        self.perm.assert_permission(perm.CHANGESET_VIEW)

        self.add_link('alternate', '?format=diff', 'Unified Diff',
                      'text/plain', 'diff')
        self.add_link('alternate', '?format=zip', 'Zip Archive',
                      'application/zip', 'zip')

        rev = req.args.get('rev')
        repos = self.env.get_repository(req.authname)

        diff_options = get_diff_options(req)
        if req.args.has_key('update'):
            req.redirect(self.env.href.changeset(rev))

        req.hdf['title'] = '[%s]' % rev

        changeset = repos.get_changeset(rev)
        req.check_modified(changeset.date,
                           diff_options[0] + ''.join(diff_options[1]))

        req.hdf['changeset'] = {
            'revision': rev,
            'time': time.asctime(time.localtime(changeset.date)),
            'author': util.escape(changeset.author or 'anonymous'),
            'message': wiki_to_html(util.wiki_escape_newline(changeset.message or '--'),
                                    req.hdf, self.env, self.db)
        }

        # FIXME: this cruft is only here so that the various display_xxx methods
        # have the info available they need to render the diffs
        self.repos = repos
        self.rev = rev
        self.diff_options = diff_options
        self.edits = []

        changes = []
        idx = 0
        for path, kind, change, base_path, base_rev in changeset.get_changes():
            info = {'change': change}
            if base_path:
                info['path.old'] = base_path
                info['rev.old'] = base_rev
                info['browser_href.old'] = self.env.href.browser(base_path, base_rev)
            if path:
                info['path.new'] = path
                info['rev.new'] = rev
                info['browser_href.new'] = self.env.href.browser(path, rev)
            if change == 'edit': # Changeset.EDIT
                self.edits.append((idx, path, kind, base_path, base_rev))
            changes.append(info)
            idx += 1
        req.hdf['changeset.changes'] = changes

        # FIXME: this code assumes integer revision identifiers
        if int(rev) > 1:
            self.add_link('first', self.env.href.changeset(1), 'Changeset 1')
            self.add_link('prev', self.env.href.changeset(int(rev) - 1),
                          'Changeset %s' % (int(rev) - 1))
        if int(rev) < int(repos.rev):
            self.add_link('next', self.env.href.changeset(int(rev) + 1),
                          'Changeset %s' % (int(rev) + 1))
            self.add_link('last', self.env.href.changeset(repos.rev),
                          'Changeset %s' % repos.rev)

    def display(self, req):
        """HTML version"""
        for idx, path, kind, base_path, base_rev in self.edits:
            old_node = self.repos.get_node(base_path or path, base_rev)
            new_node = self.repos.get_node(path, self.rev)

            # Property changes
            old_props = old_node.get_properties()
            new_props = new_node.get_properties()
            changed_props = {}
            if old_props != new_props:
                for k,v in old_props.items():
                    if not k in new_props:
                        changed_props[k] = {'old': v}
                    elif v != new_props[k]:
                        changed_props[k] = {'old': v, 'new': new_props[k]}
                for k,v in new_props.items():
                    if not k in old_props:
                        changed_props[k] = {'new': v}
                req.hdf['changeset.changes.%d.props' % idx] = changed_props

            # Content changes
            old_content = old_node.get_content().read()
            if self.env.mimeview.is_binary(old_content):
                continue
            new_content = new_node.get_content().read()
            if old_content != new_content:
                context = 3
                for option in self.diff_options:
                    if option[:2] == '-U':
                        context = int(option[2:])
                        break
                tabwidth = int(self.env.get_config('diff', 'tab_width', '8'))
                changes = hdf_diff(old_content.splitlines(),
                                   new_content.splitlines(),
                                   context, tabwidth,
                                   ignore_blank_lines='-B' in self.diff_options,
                                   ignore_case='-i' in self.diff_options,
                                   ignore_space_changes='-b' in self.diff_options)
                req.hdf['changeset.changes.%d.diff' % idx] = changes
        Module.display(self, req)

    def display_diff(self, req):
        """Raw Unified Diff version"""
        req.send_response(200)
        req.send_header('Content-Type', 'text/plain;charset=utf-8')
        req.send_header('Content-Disposition',
                        'filename=Changeset%s.diff' % req.args.get('rev'))
        req.end_headers()

        for idx, path, kind, base_path, base_rev in self.edits:
            old_node = self.repos.get_node(base_path or path, base_rev)
            new_node = self.repos.get_node(path, self.rev)

            # TODO: Property changes

            # Content changes
            old_content = old_node.get_content().read()
            if self.env.mimeview.is_binary(old_content):
                continue
            new_content = new_node.get_content().read()
            if old_content != new_content:
                context = 3
                for option in self.diff_options:
                    if option[:2] == '-U':
                        context = int(option[2:])
                        break
                req.write('Index: ' + path + util.CRLF)
                req.write('=' * 67 + util.CRLF)
                req.write('--- %s (revision %s)' % (old_node.path, old_node.rev) +
                          util.CRLF)
                req.write('+++ %s (revision %s)' % (new_node.path, new_node.rev) +
                          util.CRLF)
                for line in unified_diff(old_content.split('\n'),
                                         new_content.split('\n'), context,
                                         ignore_blank_lines='-B' in self.diff_options,
                                         ignore_case='-i' in self.diff_options,
                                         ignore_space_changes='-b' in self.diff_options):
                    req.write(line + util.CRLF)

    def display_zip(self, req):
        """ZIP archive with all the added and/or modified files."""
        req.send_response(200)
        req.send_header('Content-Type', 'application/zip')
        req.send_header('Content-Disposition',
                        'filename=Changeset%s.zip' % req.args.get('rev'))
        req.end_headers()

        from cStringIO import StringIO
        from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

        buf = StringIO()
        zipfile = ZipFile(buf, 'w', ZIP_DEFLATED)
        for path in [edit[0] for edit in self.edits if edit[1] == Node.FILE]:
            node = self.repos.get_node(path, self.rev)
            zipinfo = ZipInfo()
            zipinfo.filename = node.path
            zipinfo.date_time = node.last_modified[:6]
            zipinfo.compress_type = ZIP_DEFLATED
            zipfile.writestr(zipinfo, node.get_content().read())
        zipfile.close()
        req.write(buf.getvalue())
