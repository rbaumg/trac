# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2004 Rocky Burt <rocky@carterscove.com>
# Copyright (C) 2004 Edgewall Software
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
# Author: Rocky Burt <rocky@carterscove.com>

import os
import util

class NoTracReposDefinedException(Exception):

    def __init__(self):
        Exception.__init__(self, "Environment variable TRAC_REPOS needs to be defined")


def get_attachment_dir(module, id, create_if_not_exist=0):

    trac_repos_dir = os.getenv('TRAC_REPOS')
    if not trac_repos_dir:
        raise NoTracReposDefinedException()

    type_name = module.__name__
    pos = type_name.rfind('.')
    if pos > -1:
        type_name = type_name[pos+1:]

    dir = os.path.join(trac_repos_dir, 'attachments', type_name, str(id))

    exists = os.access(dir, os.F_OK)
    if create_if_not_exist:
        if not exists:
            os.makedirs(dir)

    exists = os.access(dir, os.F_OK)
    if not exists:
        dir = None

    return dir

def create_attachment(module, id, file):
    dir = get_attachment_dir(module, id, 1)
    p = os.path.join(dir, file.filename)
    f = open(p, 'wb')
    f.write(file.value)
    f.close()


def get_attachments(module, id):
    dir = get_attachment_dir(module, id)
    files = []
    if dir:
        files = os.listdir(dir)

    return files

def get_attachment_path(module, id, filename):
    dir = get_attachment_dir(module, id)
    return os.path.join(dir, filename)


class Attachment:
    def __init__(self, config, args):
        self.config = config
        self.args = args

    def run(self):
        self.display()
    
    def display(self):
        self.req.send_response(200)
        self.req.send_header('Content-Type', 'application/octet-stream')
        self.req.end_headers()

        m = __import__(self.args['type'], globals(),  locals(), [])

        f = open(get_attachment_path(m, self.args['id'], self.args['filename']), 'rb')
        self.req.write(f.read())
        f.close()
