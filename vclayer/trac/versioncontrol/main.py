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


class Repository(object):

    def __init__(self, authz, log):
        self.authz = authz or Authorizer()
        self.log = log

    def close(self):
        raise NotImplementedError

    def get_changeset(self, rev):
        raise NotImplementedError

    def get_node(self, path, rev=None):
        raise NotImplementedError


class Node(object):

    DIRECTORY = "dir"
    FILE = "file"

    def __init__(self, path, rev, kind):
        self.path = path
        self.rev = rev
        self.kind = kind

    def get_content(self):
        raise NotImplementedError

    def get_entries(self):
        raise NotImplementedError

    def get_history(self):
        raise NotImplementedError

    def get_properties(self):
        raise NotImplementedError

    def get_content_length(self):
        raise NotImplementedError
    content_length = property(lambda x: x.get_content_length())

    def get_content_type(self):
        raise NotImplementedError
    content_type = property(lambda x: x.get_content_type())

    def get_name(self):
        return self.path.split('/')[-1]
    name = property(lambda x: x.get_name())

    def get_last_modified(self):
        raise NotImplementedError
    last_modified = property(lambda x: x.get_last_modified())

    isdir = property(lambda x: x.kind is Node.DIRECTORY)
    isfile = property(lambda x: x.kind is Node.FILE)


class Changeset(object):

    ADD = 'add'
    COPY = 'copy'
    DELETE = 'delete'
    EDIT = 'edit'
    MOVE = 'move'

    rev = None
    message = None
    author = None
    date = None

    def __init__(self, rev, message, author, date):
        self.rev = rev
        self.message = message
        self.author = author
        self.date = date

    def get_changes(self):
        """
        Generator that produces a (path, kind, change, base_rev, base_path)
        tuple for every change in the changeset, where change can be one of
        ADD, COPY, DELETE, EDIT or MOVE.
        """
        raise NotImplementedError


class PermissionDenied(Exception):
    pass


class Authorizer(object):

    def assert_permission(self, path):
        if not self.has_permission(path):
            raise PermissionDenied, \
                  'Insufficient permissions to access %s' % path

    def has_permission(self, path):
        return 1

