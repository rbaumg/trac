# svntrac
#
# Copyright (C) 2003 Xyche Software
# Copyright (C) 2003 Jonas Borgstr�m <jonas@xyche.com>
#
# svntrac is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# svntrac is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Author: Jonas Borgstr�m <jonas@xyche.com>

import sys
import time
import StringIO
from types import *
from svn import util
from db import get_connection
from xml.sax import saxutils

cgi_name = 'svntrac.cgi'
authcgi_name = 'svntrac_auth.cgi'

def set_cgi_name(name):
    global cgi_name
    cgi_name = name

def get_cgi_name():
    return cgi_name

def set_authcgi_name(name):
    global authcgi_name
    authcgi_name = name

def get_authcgi_name():
    return authcgi_name

def time_to_string(date):
    date = time.asctime(time.localtime(date))
    return date[4:-8]

def format_date(date, pool):
    date = util.svn_time_from_cstring(date, pool)
    return time_to_string (date / 1000000)

def redirect (url):
    """
    redirects the user agent to a different url
    """
    print 'Location: %s\r\n\r\n' % url
    sys.exit(0)

def enum_selector (sql, name, selected=None,default_empty=0):
    out = StringIO.StringIO()
    out.write ('<select size="1" name="%s">' % name)

    cnx = get_connection()
    cursor = cnx.cursor ()
    cursor.execute (sql)

    if default_empty:
        out.write ('<option></option>')
    while 1:
	row = cursor.fetchone()
        if not row:
            break
        if selected == row[0]:
            out.write ('<option selected>%s</option>' % row[0])
        else:
            out.write ('<option>%s</option>' % row[0])

    out.write ('</select>')
    return out.getvalue()

def escape(text, param={'"':'&#34;'}):
    """Escapes &, <, > and \""""
    if not text:
	return ''
    elif type(text) is StringType:
	return saxutils.escape(text, param)
    else:
	return text

def get_first_line(text, maxlen):
    """
    returns the first line of text. If the line is longer then
    maxlen characters it is truncated. The line is also html escaped.
    """
    lines = text.splitlines()
    line  = lines[0]
    if len(lines) > 1:
        return escape(line[:maxlen] + '...')
    elif len(line) > maxlen-3:
        return escape(line[:maxlen] + '...')
    else:
        return escape(line)

def href_join(u1, *tail):
    for u2 in tail:
        if u1[-1] == '/' and u2[0] != '/' or \
            u1[-1] != '/' and u2[0] == '/':
                u1 = u1 + u2
        else:
            u1 = u1 + '/' + u2
    return u1

def dict_get_with_default(dict, key, default):
    """Returns dict[key] if it exists else default"""
    if dict.has_key(key):
        return dict[key]
    else:
        return default
