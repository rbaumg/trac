#!/usr/bin/env python
# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004, 2005 Edgewall Software
# Copyright (C) 2003, 2004, 2005 Jonas Borgström <jonas@edgewall.com>
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
# Author: Jonas Borgström <jonas@edgewall.com>

import os

try:
    # Open the environment
    env_path = os.environ['TRAC_ENV']
    if not env_path:
        raise RuntimeError, "Missing TRAC_ENV environment variable."
    from trac.env import Environment
    env = Environment(env_path)

    # Load the plugins
    # TODO: the list of plugins to load shouldn't be hard-coded like this
    from trac.web import chrome, clearsilver, extauth, session
    from trac.plugins import compat, settings

    # Run the application
    from trac.web import cgiserver, Application
    cgiserver.run(Application(env))

except Exception, e:
    print 'Status: 500 Internal Server Error'
    print 'Content-Type: text/html'
    print

    import traceback
    import StringIO
    buf = StringIO.StringIO()
    traceback.print_exc(file=buf)

    print """<html>
<head><title>Internal error</title></head>
<body>
<h1>Internal error</h1>
<p>%s</p>
<pre>%s</pre>
</body></html>""" % (e, buf.getvalue())
