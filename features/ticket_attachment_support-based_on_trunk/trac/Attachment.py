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
from Module import Module

class NoTracReposDefinedException(Exception):

    def __init__(self):
        Exception.__init__(self, "Environment variable TRAC_REPOS needs to be defined")


def getAttachmentDir(module, id, createIfNotExist=0):

    tracReposDir = os.getenv('TRAC_REPOS')
    if not tracReposDir:
        raise NoTracReposDefinedException()

    typeName = module.__name__
    pos = typeName.rfind('.')
    if pos > -1:
        typeName = typeName[pos+1:]

    dir = tracReposDir+'/attachments/' + typeName + '/' + str(id)

    exists = os.access(dir, os.F_OK)
    if createIfNotExist:
        if not exists:
            os.makedirs(dir)

    exists = os.access(dir, os.F_OK)
    if not exists:
        dir = None

    return dir

def createAttachment(module, id, file):
    dir = getAttachmentDir(module, id, 1)
    f = open(dir+'/'+file.filename, 'wb')
    f.write(file.value)
    f.close()


def getAttachments(module, id):
    dir = getAttachmentDir(module, id)
    files = []
    if dir:
        files = os.listdir(dir)

    return files

def getAttachmentPath(module, id, filename):
    dir = getAttachmentDir(module, id)
    return dir + '/'+filename


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

        f = open(getAttachmentPath(m, self.args['id'], self.args['filename']), 'rb')
        self.req.write(f.read())
        f.close()
