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
import re
import time


_kindmap = {'D': Node.DIRECTORY, 'F': Node.FILE}
_actionmap = {'A': Changeset.ADD, 'C': Changeset.COPY,
              'D': Changeset.DELETE, 'E': Changeset.EDIT,
              'M': Changeset.MOVE}


class CachedRepository(Repository):

    def __init__(self, db, repos, authz, log):
        Repository.__init__(self, authz, log)
        self.db = db
        self.repos = repos
        self.synced = 0

    def __getattr__(self, name):
        return getattr(self.repos, name)

    def get_changeset(self, rev):
        if not self.synced:
            self.sync()
            self.synced = 1
        return CachedChangeset(rev, self.db, self.authz)

    def sync(self):
        self.log.debug("Checking whether sync with repository is needed")
        cursor = self.db.cursor()
        cursor.execute("SELECT COALESCE(max(rev), 0) FROM revision")
        youngest_stored =  int(cursor.fetchone()[0])
        if youngest_stored < self.repos.rev:
            kindmap = dict(zip(_kindmap.values(), _kindmap.keys()))
            actionmap = dict(zip(_actionmap.values(), _actionmap.keys()))
            self.log.info("Syncing with repository (%s to %s)"
                          % (youngest_stored, self.repos.rev))
            for rev in range(youngest_stored + 1, self.repos.rev + 1):
                changeset = self.repos.get_changeset(rev)
                cursor.execute("INSERT INTO revision (rev,time,author,message) "
                               "VALUES (%s,%s,%s,%s)", (rev, changeset.date,
                               changeset.author, changeset.message))
                for path,kind,action,base_path,base_rev in changeset.get_changes():
                    self.log.debug("Caching node change in [%s]: %s"
                                   % (rev, (path, kind, action, base_path, base_rev)))
                    kind = kindmap[kind]
                    action = actionmap[action]
                    cursor.execute("INSERT INTO node_change (rev,path,kind,"
                                   "change,base_path,base_rev) "
                                   "VALUES (%s,%s,%s,%s,%s,%s)", (rev, path,
                                   kind, action, base_path, base_rev))
            self.db.commit()

    def get_node(self, path, rev=None):
        return self.repos.get_node(path, rev)


class CachedChangeset(Changeset):

    def __init__(self, rev, db, authz):
        self.db = db
        self.authz = authz
        cursor = self.db.cursor()
        cursor.execute("SELECT time,author,message FROM revision "
                       "WHERE rev=%s", (rev,))
        date, author, message = cursor.fetchone()
        Changeset.__init__(self, rev, message, author, int(date))

    def __getattr__(self, name):
        return getattr(self.repos, name)

    def get_changes(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT path,kind,change,base_path,base_rev "
                       "FROM node_change WHERE rev=%s", (self.rev,))
        for path, kind, change, base_path, base_rev in cursor:
            if not self.authz.has_permission(path):
                # FIXME: what about the base_path?
                continue
            kind = _kindmap[kind]
            change = _actionmap[change]
            yield path, kind, change, base_path, base_rev
