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

from trac.plugin import *
from trac.web import dispatcher
from trac.web import SendResponse

from protocols import *

import os.path
import StringIO


class ClearSilverTemplatingFilter(Plugin):

    _id = 'clearsilver'
    _extends = ['dispatcher.requestFilters']
    advise(instancesProvide=[dispatcher.IRequestFilter])

    def beforeProcessingRequest(self, req, resp):
        import neo_cgi
        neo_cgi.update()
        import neo_util
        hdf = neo_util.HDF()
        templateData = HDFNode(hdf)

        req['template_data'] = templateData
        req['template_file'] = None

    def afterProcessingRequest(self, req, resp, exc_info):
        if exc_info and exc_info[0] == SendResponse:
            return

        templateData = req['template_data']
        assert templateData, 'No template data to process'

        if req.params.has_key('debug'):
            # write out the template data for debugging
            resp.headers['Content-Type'] = 'text/plain'
            resp.write(str(templateData))

        else:
            templateData['hdf']['loadpaths'] = [
                self.env.get_config('trac', 'templates_dir'),
                os.path.join(self.env.path, 'templates')
            ]
            import neo_cs
            cs = neo_cs.CS(templateData.hdf)

            templateFile = req['template_file']
            assert templateFile, 'No template file specified'
            cs.parseFile(templateFile)

            resp.headers['Content-Type'] = 'text/html; charset=utf-8'
            resp.write(cs.render())


def add_to_hdf(hdf, name, value):
    prefix = str(name)
    if type(value) is dict:
        for k,v in value.items():
            add_to_hdf(hdf, prefix + '.' + k, v)
    elif type(value) is list:
        for i in range(len(value)):
            add_to_hdf(hdf, prefix + '.' + str(i), value[i])
    else:
        hdf.setValue(prefix, str(value))


class HDFNode(object):
    """
    Facade over ClearSilver data sets that allows us to use primitive python
    data structures such as lists and dicts to populate the template data.
    """

    def __init__(self, hdf, prefix=''):
        self.hdf = hdf
        self.prefix = prefix

    def __delitem__(self, name):
        prefix = str(name)
        if self.prefix:
            prefix = self.prefix + '.' + prefix
        subhdf = self.hdf.getObj(prefix)
        if subhdf:
            self.hdf.removeTree(prefix)

    def __getitem__(self, name):
        prefix = str(name)
        if self.prefix:
            prefix = self.prefix + '.' + prefix
        subhdf = self.hdf.getObj(prefix)
        if not subhdf:
            return HDFNode(self.hdf, prefix)
        else:
            return HDFNode(subhdf)

    def __setitem__(self, name, value):
        prefix = str(name)
        if self.prefix:
            prefix = self.prefix + '.' + prefix
        add_to_hdf(self.hdf, prefix, value)
        if self.prefix:
            self.hdf = self.hdf.getObj(self.prefix)
            self.prefix = ''

    def __iadd__(self, other):
        idx = 0
        if self.prefix:
            parent = self.hdf.getObj(self.prefix)
            if parent:
                child = parent.child()
            else:
                add_to_hdf(self.hdf, '%s.%s' % (self.prefix, 0), other)
                self.hdf = self.hdf.getObj('%s.%s' % (self.prefix, 0))
                self.prefix = ''
                return self
        else:
            child = self.hdf.child()
        try:
            while 1:
                if not child:
                    add_to_hdf(self.hdf, idx, other)
                    break
                child = child.next()
                idx += 1
        except ValueError:
            raise Exception, 'Cannot add template node to non-list parent'


        return self

    def __str__(self):
        buf = StringIO.StringIO()
        def tree_walk(node, prefix=''):
            while node:
                name = node.name() or ''
                if not node.child():
                    value = node.value()
                    buf.write('%s%s = ' % (prefix, name))
                    if value.find('\n') == -1:
                        buf.write('%s\n' % value)
                    else:
                        buf.write('<< EOM\n%s\nEOM\n' % value)
                else:
                    buf.write('%s%s {\n' % (prefix, name))
                    tree_walk(node.child(), prefix + '  ')
                    buf.write('%s}\n' % prefix)
                node = node.next()
        tree_walk(self.hdf.child(), self.prefix)
        return buf.getvalue()

    def clear(self):
        if self.prefix:
            return
        child = self.hdf.child()
        names = []
        while child:
            names.append(child.name() or '')
            child = child.next()
        for name in filter(None, names):
            self.hdf.removeTree(name)

    def getObj(self, name):
        # Deprecated, will be dropped when all code has been migrated to the
        # new API
        prefix = str(name)
        if self.prefix:
            prefix = self.prefix + '.' + prefix
        return self.hdf.getObj(prefix)

    def getValue(self, name, default=''):
        # Deprecated, will be dropped when all code has been migrated to the
        # new API
        prefix = str(name)
        if self.prefix:
            prefix = self.prefix + '.' + prefix
        return self.hdf.getValue(prefix, default)

    def setValue(self, name, value):
        # Deprecated, will be dropped when all code has been migrated to the
        # new API
        prefix = str(name)
        if self.prefix:
            prefix = self.prefix + '.' + prefix
        self.hdf.setValue(prefix, value)

