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

from trac.web.main import *

import StringIO
import unittest


class RequestTestCase(unittest.TestCase):

    environ = None
    input = None
    output = None

    def setUp(self):
        self.input = StringIO.StringIO()
        self.output = StringIO.StringIO()

        self.environ = {}
        self.environ['wsgi.input'] = self.input
        self.environ['wsgi.errors'] = self.output
        self.environ['wsgi.version'] = (1, 0)
        self.environ['wsgi.multithread'] = False
        self.environ['wsgi.multiprocess'] = True
        self.environ['wsgi.run_once'] = True
        self.environ['wsgi.url_scheme'] = 'http'
        self.environ['REQUEST_METHOD'] = 'GET'
        self.environ['SCRIPT_NAME'] = '/cgi-bin/test.cgi'

    def testBaseURLHTTPWithHostHeader(self):
        self.environ.update({
            'HTTP_HOST': 'www.example.com:8080'
        })
        req = Request(self.environ)
        self.assertEquals('http://www.example.com:8080/cgi-bin/test.cgi',
                          req.baseURL)

    def testBaseURLHTTPWithoutHostHeader(self):
        self.environ.update({
            'SERVER_NAME': 'www.example.com',
            'SERVER_PORT': '8080'
        })
        req = Request(self.environ)
        self.assertEquals('http://www.example.com:8080/cgi-bin/test.cgi',
                          req.baseURL)

    def testBaseURLHTTPWithoutHostHeaderAndDefaultPort(self):
        self.environ.update({
            'SERVER_NAME': 'www.example.com',
            'SERVER_PORT': '80'
        })
        req = Request(self.environ)
        self.assertEquals('http://www.example.com/cgi-bin/test.cgi',
                          req.baseURL)

    def testBaseURLHTTPSWithHostHeader(self):
        self.environ.update({
            'wsgi.url_scheme': 'https',
            'HTTP_HOST': 'www.example.com:8443'
        })
        req = Request(self.environ)
        self.assertEquals('https://www.example.com:8443/cgi-bin/test.cgi',
                          req.baseURL)

    def testBaseURLHTTPSWithoutHostHeader(self):
        self.environ.update({
            'wsgi.url_scheme': 'https',
            'SERVER_NAME': 'www.example.com',
            'SERVER_PORT': '8443'
        })
        req = Request(self.environ)
        self.assertEquals('https://www.example.com:8443/cgi-bin/test.cgi',
                          req.baseURL)

    def testBaseURLHTTPSWithoutHostHeaderAndDefaultPort(self):
        self.environ.update({
            'wsgi.url_scheme': 'https',
            'SERVER_NAME': 'www.example.com',
            'SERVER_PORT': '443'
        })
        req = Request(self.environ)
        self.assertEquals('https://www.example.com/cgi-bin/test.cgi',
                          req.baseURL)


def suite():
    return unittest.makeSuite(RequestTestCase, 'test')

if __name__ == '__main__':
    unittest.main()
