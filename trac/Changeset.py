# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004 Edgewall Software
# Copyright (C) 2003, 2004 Jonas Borgstr�m <jonas@edgewall.com>
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

from util import *
from Module import Module
from Wiki import wiki_to_html
import Diff, perm

from svn import fs, util, delta, repos, core

class HtmlDiffEditor (delta.Editor):
    """
    generates a htmlized unified diff of the changes for a given changeset.
    the output is written to stdout.
    """
    def __init__(self, old_root, new_root, rev, req, args, env):
        self.old_root = old_root
        self.new_root = new_root
        self.rev = rev
        self.req = req
        self.args = args
        self.env = env
        self.fileno = 0

    def print_diff (self, old_path, new_path, pool):
        if not old_path or not new_path:
            return

        old_rev = fs.node_created_rev(self.old_root, old_path, pool)
        new_rev = fs.node_created_rev(self.new_root, new_path, pool)

        options = Diff.get_options(self.env, self.req, self.args, 1)
        differ = fs.FileDiff(self.old_root, old_path, self.new_root, new_path,
                             pool, options)
        differ.get_files()
        pobj = differ.get_pipe()
        prefix = 'changeset.diff.files.%d' % (self.fileno)
        tabwidth = int(self.env.get_config('diff', 'tab_width', '8'))
        builder = Diff.HDFBuilder(self.req.hdf, prefix, tabwidth)
        self.fileno += 1
        builder.writeline('header %s %s | %s %s redaeh' % (old_path, old_rev,
                                                           new_path, new_rev))
        while 1:
            line = pobj.readline()
            if not line:
                break
            builder.writeline(escape(to_utf8(line)))
        builder.close()

    def add_file(self, path, parent_baton, copyfrom_path,
                 copyfrom_revision, file_pool):
        return [None, path, file_pool]

    def open_file(self, path, parent_baton, base_revision, file_pool):
        return [path, path, file_pool]

    def apply_textdelta(self, file_baton, base_checksum):
        self.print_diff (*file_baton)


class UnifiedDiffEditor(HtmlDiffEditor):
    """
    generates a unified diff of the changes for a given changeset.
    the output is written to stdout.
    """

    def __init__(self, old_root, new_root, rev, req, args, env):
        HtmlDiffEditor.__init__(self, old_root, new_root, rev, req, args, env)
        self.output = req

    def print_diff (self, old_path, new_path, pool):
        options = ['-u']
        options.append('-L')
        options.append("%s\t(revision %d)" % (old_path, self.rev-1))
        options.append('-L')
        options.append("%s\t(revision %d)" % (new_path, self.rev))

        differ = fs.FileDiff(self.old_root, old_path,
                             self.new_root, new_path, pool, options)
        differ.get_files()
        pobj = differ.get_pipe()
        line = pobj.readline()
        while line:
            self.output.write(line)
            line = pobj.readline()


class Changeset (Module):
    template_name = 'changeset.cs'
    perm = None
    fs_ptr = None
    pool = None

    def get_changeset_info (self, rev):
        cursor = self.db.cursor ()
        cursor.execute ('SELECT time, author, message FROM revision ' +
                        'WHERE rev=%d', rev)
        row = cursor.fetchone()
        if not row:
            raise TracError('Changeset %d does not exist.' % rev,
                            'Invalid Changset')
        return row

    def get_change_info (self, rev):
        cursor = self.db.cursor ()
        cursor.execute ('SELECT name, change FROM node_change ' +
                        'WHERE rev=%d', rev)
        info = []
        while 1:
            row = cursor.fetchone()
            if not row:
                break
            info.append({'name': row['name'],
                         'change': row['change'],
                         'browser_href': self.env.href.browser(row['name'], rev),
                         'log_href': self.env.href.log(row['name'])})
        return info

    def render (self):
        self.perm.assert_permission (perm.CHANGESET_VIEW)

        self.add_link('alternate', '?format=diff', 'Unified Diff',
            'text/plain', 'diff')

        if self.args.has_key('rev'):
            self.rev = int(self.args.get('rev'))
        else:
            self.rev = fs.youngest_rev(self.fs_ptr, self.pool)

        change_info = self.get_change_info (self.rev)
        for item in change_info:
            item['log_href'] = self.env.href.log(item['name'])

        changeset_info = self.get_changeset_info (self.rev)

        self.req.hdf.setValue('changeset.time',
                              time.asctime (time.localtime(int(changeset_info['time']))))
        author = changeset_info['author'] or 'None'
        self.req.hdf.setValue('changeset.author', escape(author))
        self.req.hdf.setValue('changeset.message',
                              wiki_to_html(wiki_escape_newline(changeset_info['message']),
                                           self.req.hdf, self.env))
        self.req.hdf.setValue('changeset.revision', str(self.rev))
        add_dictlist_to_hdf(change_info, self.req.hdf, 'changeset.changes')
        self.req.hdf.setValue('changeset.href',
            self.env.href.changeset(self.rev))
        self.req.hdf.setValue('title', '[%d] (changeset)' % self.rev)

    def render_diffs(self, editor_class=HtmlDiffEditor):
        """
        generates a unified diff of the changes for a given changeset.
        the output is written to stdout.
        """
        try:
            old_root = fs.revision_root(self.fs_ptr, int(self.rev) - 1, self.pool)
            new_root = fs.revision_root(self.fs_ptr, int(self.rev), self.pool)
        except core.SubversionException:
            raise TracError('Invalid revision number: %d' % int(self.rev))

        editor = editor_class(old_root, new_root, int(self.rev), self.req,
                              self.args, self.env)
        e_ptr, e_baton = delta.make_editor(editor, self.pool)

        if util.SVN_VER_MAJOR == 0 and util.SVN_VER_MINOR == 37:
            repos.svn_repos_dir_delta(old_root, '', '',
                                      new_root, '', e_ptr, e_baton, None, None,
                                      0, 1, 0, 1, self.pool)
        else:
            def authz_cb(root, path, pool): return 1
            repos.svn_repos_dir_delta(old_root, '', '',
                                      new_root, '', e_ptr, e_baton, authz_cb,
                                      0, 1, 0, 1, self.pool)

    def display(self):
        """Pretty HTML view of the changeset"""
        self.render_diffs()
        Module.display(self)

    def display_hdf(self):
        self.render_diffs()
        Module.display_hdf(self)

    def display_diff (self):
        """Raw Unified Diff version"""
        self.req.send_response(200)
        self.req.send_header('Content-Type', 'text/plain')
        self.req.end_headers()
        self.render_diffs(UnifiedDiffEditor)
