# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Edgewall Software
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
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

from __future__ import generators

from trac.util import TracError
from trac.versioncontrol import Changeset, Node, Repository

import os.path
import time

from svn import fs, repos, core, delta

_kindmap = {core.svn_node_dir: Node.DIRECTORY,
            core.svn_node_file: Node.FILE}


class SubversionRepository(Repository):
    """
    TODO: authz support
    """

    def __init__(self, path, log):
        Repository.__init__(self, log)

        if core.SVN_VER_MAJOR < 1:
            raise TracError, \
                  "Subversion >= 1.0 required: Found %d.%d.%d" % \
                  (core.SVN_VER_MAJOR, core.SVN_VER_MINOR, core.SVN_VER_MICRO)
        if not os.path.isdir(path):
            raise TracError, "Subversion repository not found at %s" % path

        # Remove any trailing slash or else subversion might abort
        if not os.path.split(path)[1]:
            path = os.path.split(path)[0]
        self.path = path

        self.apr_initialized = 0
        self.pool = None
        self.repos = None
        self.fs_ptr = None

    def __del__(self):
        self.close()

    def __lazyinit(self):
        assert not self.apr_initialized, "Already initialized"

        self.log.debug("Opening subversion file-system at %s" % self.path)

        core.apr_initialize()
        self.apr_initialized = 1

        self.pool = core.svn_pool_create(None)
        self.repos = repos.svn_repos_open(self.path, self.pool)
        self.fs_ptr = repos.svn_repos_fs(self.repos)
        self.rev = fs.youngest_rev(self.fs_ptr, self.pool)

    def close(self):
        if self.pool:
            self.log.debug("Closing subversion file-system at %s" % self.path)
            core.svn_pool_destroy(self.pool)
            self.pool = None
            self.repos = None
            self.fs_ptr = None
            self.rev = None
        if self.apr_initialized:
            core.apr_terminate()
            self.apr_initialized = 0

    def get_changeset(self, rev):
        if not self.apr_initialized:
            self.__lazyinit()

        return SubversionChangeset(int(rev), self.fs_ptr, self.pool)

    def get_node(self, path, rev=None):
        if not self.apr_initialized:
            self.__lazyinit()

        if path and path[-1] == '/':
            path = path[:-1]

        if rev != None:
            try:
                rev = int(rev)
            except ValueError:
                rev = None
        if not rev:
            rev = self.rev

        return SubversionNode(path, rev, self.fs_ptr, self.pool)

    def __getattr__(self, name):
        if not self.apr_initialized:
            self.__lazyinit()
        return getattr(self, name)

class SubversionNode(Node):

    def __init__(self, path, rev, fs_ptr, pool):
        self.root = fs.revision_root(fs_ptr, rev, pool)
        self.rev = fs.node_created_rev(self.root, path, pool)
        self.fs_ptr = fs_ptr
        self.pool = pool
        Node.__init__(self, path, self.rev,
                      _kindmap[fs.check_path(self.root, path, self.pool)])

    def get_content(self):
        if self.isdir:
            return None
        return core.Stream(fs.file_contents(self.root, self.path, self.pool))

    def get_entries(self):
        if self.isfile:
            return
        entries = fs.dir_entries(self.root, self.path, self.pool)
        for item in entries.keys():
            path = '/'.join((self.path, item))
            yield SubversionNode(path, self.rev, self.fs_ptr, self.pool)

    def get_history(self):
        history = []
        def history_cb(path, rev, pool):
            history.append((path, rev))
        repos.svn_repos_history(self.fs_ptr, self.path, history_cb,
                                self.rev, 0, 1, self.pool)
        for item in history:
            yield item

    def get_properties(self):
        return fs.node_proplist(self.root, self.path, self.pool)

    def get_content_length(self):
        return fs.file_length(self.root, self.path, self.pool)

    def get_content_type(self):
        return self._get_prop(core.SVN_PROP_MIME_TYPE)

    def get_last_modified(self):
        date = fs.revision_prop(self.fs_ptr, self.rev,
                                core.SVN_PROP_REVISION_DATE, self.pool)
        seconds = core.svn_time_from_cstring(date, self.pool) / 1000000
        return time.gmtime(seconds)

    def _get_prop(self, name):
        return fs.node_prop(self.root, self.path, name, self.pool)


class SubversionChangeset(Changeset):

    def __init__(self, rev, fs_ptr, pool):
        self.rev = rev
        self.fs_ptr = fs_ptr
        self.pool = pool
        message = self._get_prop(core.SVN_PROP_REVISION_LOG)
        author = self._get_prop(core.SVN_PROP_REVISION_AUTHOR)
        date = self._get_prop(core.SVN_PROP_REVISION_DATE)
        date = core.svn_time_from_cstring(date, pool) / 1000000
        Changeset.__init__(self, rev, message, author, date)

    def get_changes(self):
        root = fs.revision_root(self.fs_ptr, self.rev, self.pool)
        editor = repos.RevisionChangeCollector(self.fs_ptr, self.rev, self.pool)
        e_ptr, e_baton = delta.make_editor(editor, self.pool)
        repos.svn_repos_replay(root, e_ptr, e_baton, self.pool)

        for path, change in editor.changes.items():
            base_path, base_rev = change.base_path, change.base_rev
            if base_path and base_path[0] == '/':
                base_path = base_path[1:]
            action = ''
            if not change.path:
                action = Changeset.DELETE
            elif change.added:
                if change.base_path and change.base_rev:
                    action = Changeset.COPY
                else:
                    action = Changeset.ADD
            else:
                action = Changeset.EDIT
            kind = _kindmap[change.item_kind]
            yield path, kind, action, base_path, base_rev

    def _get_prop(self, name):
        return fs.revision_prop(self.fs_ptr, self.rev, name, self.pool)
