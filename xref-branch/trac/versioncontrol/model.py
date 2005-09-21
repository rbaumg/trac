# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Edgewall Software
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.com/license.html.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://projects.edgewall.com/trac/.
#
# Author: Christian Boos <cboos@neuf.fr>

from __future__ import generators

from trac.core import *
from trac.object import TracObject, ITracObjectManager
from trac.versioncontrol import Changeset

class ChangesetObject(TracObject):
    """
    Trac Object encapsulating a Changeset
    """

    type = 'changeset'

    def __init__(self, env, rev=None, changeset=None):
        TracObject.__init__(self, env, rev)
        self.setid(rev)
        self.changeset = changeset
        if rev and not changeset:
            self.reload()


    def setid(self, rev):
        self.changeset = None
        # Note: don't normalize rev: we need a string at this level
        return TracObject.setid(self, rev)

    def reload(self):
        if self.id:
            self.changeset = self.env.get_repository().get_changeset(self.id)

    def shortname(self):
        return '[%s]' % self.id

    def displayname(self):
        return 'Changeset [%s]' % self.id


class SourceObject(TracObject):
    """
    Trac Object encapsulating a Node.
    The revision is not taken into account, only the path matters.
    """

    type = 'source'

    def __init__(self, env, path=None, node=None):
        TracObject.__init__(self, env, path)
        self.node = node
        if path:
            self.setid(path)
            if not node:
                self.reload()                

    def setid(self, rev):
        self.node = None
        repos = self.env.get_repository()
        return TracObject.setid(self, repos.normalize_path(path))

    def reload(self):
        repos = self.env.get_repository()
        self.node = self.id and repos.get_node(self.id)

    def displayname(self):
        return 'Source %s' % self.id
    

class VersionControl(Component):

    implements(ITracObjectManager)

    def get_object_types(self):
        yield ('changeset', lambda id: ChangesetObject(self.env).setid(id))
        yield ('source', lambda id: SourceObject(self.env).setid(id))

    def rebuild_xrefs(self, db):
        # -- for changesets
        cursor = db.cursor()
        cursor.execute("SELECT rev, time, author, message FROM revision")
        for rev, time, author, message in cursor:
            source = ChangesetObject(self.env).setid(rev)
            yield (source, 'content', time, author, message)
        # -- for sources
        # (nothing yet)
