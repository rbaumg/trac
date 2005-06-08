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
import posixpath

from trac import mimeview, perm, util
from trac.core import *
from trac.versioncontrol import Changeset, Node
from trac.versioncontrol.diff import get_diff_options, hdf_diff, unified_diff
from trac.web.chrome import add_link, add_stylesheet
from trac.web.main import IRequestHandler
from trac.wiki import wiki_to_html, wiki_to_oneliner


class Diff(dict):
    def __getattr__(self,str):
        return self[str]
    

class DiffModule(Component):

    implements(IRequestHandler)

    # IRequestHandler methods

    def match_request(self, req):
        match = re.match(r'/diff(?:(/.*)|$)', req.path_info)
        if match:
            req.args['path'] = match.group(1)
            return 1

    def process_request(self, req):
        req.perm.assert_permission(perm.CHANGESET_VIEW)

        path = req.args.get('path')
        repos = self.env.get_repository(req.authname)
        path = repos.normalize_path(path)
        rev = req.args.get('rev', repos.youngest_rev) # 'path history' mode
        old = req.args.get('old')                     # 'arbitrary diff' mode
        new = req.args.get('new')
        old_path = req.args.get('old_path', path)
        if old_path == path and old == new: # force 'path history' mode
            print "force 'path history' mode"
            rev = old
            old_path = old = new = None

        diff_options = get_diff_options(req)
        if req.args.has_key('update'):
            if old or new:
                req.redirect(self.env.href.diff(path, new=new, old_path=old_path, old=old))
            else:
                req.redirect(self.env.href.diff(path, rev=rev))

        rpath = path.replace('/','_') # for the .zip filename
        if old or new:
            chgset = None
            if not new:
                new = repos.youngest_rev
            elif not old:
                old = repos.youngest_rev
            if not old_path:
                old_path = path
            diff = Diff(old_path=old_path, old_rev=old,
                        new_path=path, new_rev=new)
            diffargs = 'new=%s&old_path=%s&old=%s' \
                       % (new, old_path, old)
            reverse_href = self.env.href.diff(old_path,new=old,
                                              old_path=path,old=new)
            if old_path != path:
                if old_path == '/':
                    zipfilename = '%s-r%s' % (rpath, old)
                else:
                    zipfilename = 'diff-%s-r%s-%s-r%s' \
                                  % (old_path.replace('/','_'), old, rpath, new)
            else:
                zipfilename = 'diff-%s-r%s-to-r%s' % (rpath, old, new)
        else:
            chgset = repos.get_changeset(rev)
            diff = Diff(old_path=path, old_rev=repos.previous_rev(rev),
                        new_path=path, new_rev=rev)
            diffargs = 'rev=%s' % rev
            reverse_href = None
            zipfilename = 'diff_%s_r%s' % (rpath, rev)
            
        # TODO:
#         req.check_modified(chgset.date,
#                            diff_options[0] + ''.join(diff_options[1]))
        req.hdf['diff'] = diff
        if reverse_href:
            req.hdf['diff.reverse_href'] = reverse_href
            
        format = req.args.get('format')
        if format == 'diff':
            self._render_diff(req, repos, diff, chgset, diff_options)
            return
        elif format == 'zip':
            self._render_zip(req, zipfilename, repos, diff, chgset)
            return

        self._render_html(req, repos, diff, chgset, diff_options)
        add_link(req, 'alternate', '?format=diff&'+diffargs, 'Unified Diff',
                 'text/plain', 'diff')
        add_link(req, 'alternate', '?format=zip&'+diffargs, 'Zip Archive',
                 'application/zip', 'zip')
        add_stylesheet(req, 'changeset.css')
        add_stylesheet(req, 'diff.css')
        return 'diff.cs', None


    # Internal methods

    def _render_html(self, req, repos, diff, chgset, diff_options):
        """HTML version"""
        req.hdf['diff.href'] = {
            'new_rev': self.env.href.changeset(diff.new_rev),
            'old_rev': self.env.href.changeset(diff.old_rev),
            'new_path': self.env.href.browser(diff.new_path, rev=diff.new_rev),
            'old_path': self.env.href.browser(diff.old_path, rev=diff.old_rev)
            }
        if chgset: # 'path history' mode
            req.hdf['title'] = 'Changes for %s at Revision %s' % (diff.new_path, chgset.rev)
            req.hdf['changeset'] = {
                'revision': chgset.rev,
                'time': time.strftime('%c', time.localtime(chgset.date)),
                'author': util.escape(chgset.author or 'anonymous'),
                'message': wiki_to_html(chgset.message or '--', self.env, req,
                                        escape_newlines=True)
                }

            oldest_rev = repos.oldest_rev
            if chgset.rev != oldest_rev:
                add_link(req, 'first', self.env.href.diff(diff.old_path, rev=oldest_rev),
                         'Changeset %s' % oldest_rev) # FIXME (use the history)
                previous_rev = repos.previous_rev(chgset.rev)
                add_link(req, 'prev', self.env.href.diff(diff.old_path, rev=previous_rev),
                         'Changeset %s' % previous_rev)
            youngest_rev = repos.youngest_rev
            if str(chgset.rev) != str(youngest_rev):
                next_rev = repos.next_rev(chgset.rev)
                add_link(req, 'next', self.env.href.diff(diff.new_path, rev=next_rev),
                         'Changeset %s' % next_rev)
                add_link(req, 'last', self.env.href.diff(diff.new_path, rev=youngest_rev),
                         'Changeset %s' % youngest_rev)
        elif diff.new_path == diff.old_path: # 'diff between 2 revisions' mode
            req.hdf['title'] = 'Diff r%s:%s for %s' \
                               % (diff.old_rev, diff.new_rev, diff.new_path)
        else:                           # 'arbitrary diff' mode
            req.hdf['title'] = 'Diff from %s @ %s to %s @ %s' \
                               % (diff.old_path, diff.old_rev,
                                  diff.new_path, diff.new_rev)

        def _change_info(old_node, new_node, change):
            info = {'change': change}
            if old_node:
                info['path.old'] = old_node.path
                info['rev.old'] = old_node.rev # this is the created rev.
                old_href = self.env.href.browser(old_node.path, rev=diff.old_rev)
                # Reminder: old_node.path may not exist at old_node.rev
                info['browser_href.old'] = old_href
            if new_node:
                info['path.new'] = new_node.path
                info['rev.new'] = new_node.rev # created rev.
                new_href = self.env.href.browser(new_node.path, rev=diff.new_rev)
                # (same remark as above)
                info['browser_href.new'] = new_href
            return info

        def _prop_changes(old_node, new_node):
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
            return changed_props

        def _content_changes(old_node, new_node):
            """
            Returns the list of differences.
            The list is empty when no differences between comparable files
            are detected, but the return value is None for non-comparable files.
            """
            default_charset = self.config.get('trac', 'default_charset')
            old_content = old_node.get_content().read()            
            if mimeview.is_binary(old_content):
                return None
            charset = mimeview.get_charset(old_node.content_type) or \
                      default_charset
            old_content = util.to_utf8(old_content, charset)

            new_content = new_node.get_content().read()
            if mimeview.is_binary(new_content):
                return None
            charset = mimeview.get_charset(new_node.content_type) or \
                      default_charset
            new_content = util.to_utf8(new_content, charset)

            if old_content != new_content:
                context = 3
                for option in diff_options[1]:
                    if option[:2] == '-U':
                        context = int(option[2:])
                        break
                tabwidth = int(self.config.get('diff', 'tab_width'))
                return hdf_diff(old_content.splitlines(),
                                new_content.splitlines(),
                                context, tabwidth,
                                ignore_blank_lines='-B' in diff_options[1],
                                ignore_case='-i' in diff_options[1],
                                ignore_space_changes='-b' in diff_options[1])
            else:
                return []

        idx = 0
        for old_node, new_node, kind, change in repos.get_deltas(**diff):
            if change in (Changeset.ADD, Changeset.DELETE):
                show_entry = True
            else:
                show_entry = False
                assert old_node and new_node
                props = _prop_changes(old_node, new_node)
                if props:
                    req.hdf['diff.changes.%d.props' % idx] = props
                    show_entry = True
                if kind == Node.FILE:
                    diffs = _content_changes(old_node, new_node)
                    if diff != []:
                        if diffs:
                            req.hdf['diff.changes.%d.diff' % idx] = diffs
                        # elif None (i.e. binary) manually compare to (previous)
                        show_entry = True
            if show_entry:
                info = _change_info(old_node, new_node, change)
                req.hdf['diff.changes.%d' % idx] = info
            idx += 1 # the sequence should be immutable

    def _render_diff(self, req, repos, diff, chgset, diff_options):
        """Raw Unified Diff version"""
        req.send_response(200)
        req.send_header('Content-Type', 'text/plain;charset=utf-8')
        req.send_header('Content-Disposition',
                        'filename=Changeset%s.diff' % req.args.get('rev'))
        req.end_headers()

        for old_node, new_node, kind, change in repos.get_deltas(**diff):
            # TODO: Property changes

            # Content changes
            if kind == Node.DIRECTORY:
                continue

            default_charset = self.config.get('trac', 'default_charset')
            new_content = old_content = ''
            new_node_info = old_node_info = ('','')

            if old_node:
                print old_node.path, old_node.rev
                print old_node.created_path, old_node.created_rev
                charset = mimeview.get_charset(old_node.content_type) or \
                          default_charset
                old_content = util.to_utf8(old_node.get_content().read(),
                                           charset)
                old_node_info = (old_node.path, old_node.rev)
                if mimeview.is_binary(old_content):
                    continue

            if new_node:
                charset = mimeview.get_charset(new_node.content_type) or \
                          default_charset
                new_content = util.to_utf8(new_node.get_content().read(),
                                           charset)
                new_node_info = (new_node.path, new_node.rev)
                if mimeview.is_binary(new_content):
                    continue
                new_path = new_node.path
            else:
                old_node_path = repos.normalize_path(old_node.path)
                diff_old_path = repos.normalize_path(diff.old_path)
                new_path = posixpath.join(diff.new_path,
                                          old_node_path[len(diff_old_path)+1:])

            if old_content != new_content:
                context = 3
                for option in diff_options[1]:
                    if option[:2] == '-U':
                        context = int(option[2:])
                        break
                req.write('Index: ' + new_path + util.CRLF)
                req.write('=' * 67 + util.CRLF)
                req.write('--- %s (revision %s)' % old_node_info +
                          util.CRLF)
                req.write('+++ %s (revision %s)' % new_node_info +
                          util.CRLF)
                for line in unified_diff(old_content.splitlines(),
                                         new_content.splitlines(), context,
                                         ignore_blank_lines='-B' in diff_options[1],
                                         ignore_case='-i' in diff_options[1],
                                         ignore_space_changes='-b' in diff_options[1]):
                    req.write(line + util.CRLF)

    def _render_zip(self, req, filename, repos, diff, chgset):
        """ZIP archive with all the added and/or modified files."""
        new_rev = diff.new_rev
        req.send_response(200)
        req.send_header('Content-Type', 'application/zip')
        req.send_header('Content-Disposition',
                        'filename=%s.zip' % filename)
        req.end_headers()

        try:
            from cStringIO import StringIO
        except ImportError:
            from StringIO import StringIO
        from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

        buf = StringIO()
        zipfile = ZipFile(buf, 'w', ZIP_DEFLATED)
        for old_node, new_node, kind, change in repos.get_deltas(**diff):
            if kind == Node.FILE and change != Changeset.DELETE:
                assert new_node
                zipinfo = ZipInfo()
                zipinfo.filename = new_node.path
                zipinfo.date_time = time.gmtime(new_node.last_modified)[:6]
                zipinfo.compress_type = ZIP_DEFLATED
                zipfile.writestr(zipinfo, new_node.get_content().read())
        zipfile.close()
        req.write(buf.getvalue())
