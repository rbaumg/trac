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

import os
from sys import stdin, stderr, stdout


def run(application):
    """Run the given WSGI application under CGI."""

    environ = {}
    environ.update(os.environ)
    environ['wsgi.input'] = stdin
    environ['wsgi.errors'] = stderr
    environ['wsgi.version'] = (1, 0)
    environ['wsgi.multithread'] = False
    environ['wsgi.multiprocess'] = True
    environ['wsgi.run_once'] = True
    if os.environ.get('HTTPS', '').lower() in ('on', '1'):
        environ['wsgi.url_scheme'] = 'https'
    else:
        environ['wsgi.url_scheme'] = 'http'

    def start_response(status, headers, exc_info=None):
        print 'Status: %s' % status
        for name,value in headers:
            print '%s: %s' % (name,value)
        print
        return stdout.write

    result = application(environ, start_response)
    try:
        for data in result:
            stdout.write(data)
    finally:
        if hasattr(result,'close'):
            result.close()

    stdout.close()
