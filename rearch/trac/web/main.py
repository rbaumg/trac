# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004 Edgewall Software
# Copyright (C) 2003, 2004 Christopher Lenz <cmlenz@gmx.de>
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

from trac.web import dispatcher

import cgi
from Cookie import SimpleCookie
from StringIO import StringIO
import time


class SendResponse(Exception):
    """
    Exception used internally for control flow (sorry, purists). It is used to
    skip further processing and deliver the response immediately, for example
    for sending error pages or redirects.
    """


class Request(object):
    """
    High-level abstraction of an HTTP request.
    """

    _environ = None
    _body = None
    _data = None
    _params = None
    _baseURL = None

    headers = None
    params = None

    class __Headers(object):

        def __init__(self, environ):
            self._environ = environ

        def __getitem__(self, name):
            if name.lower() in ['content-type', 'content-length']:
                return self._environ.get(name.replace('-', '_').upper())
            return self._environ.get('HTTP_' + name.replace('-', '_').upper())


    def __init__(self, environ):
        self._environ = environ
        self._data = {}
        self._body = self._environ['wsgi.input']
        self.headers = self.__Headers(environ)

        # parse parameters
        form = cgi.FieldStorage(self._body, environ=self._environ,
                                keep_blank_values=True, strict_parsing=False)
        params = {}
        for key in form.keys():
            value = form[key]
            if not isinstance(value, list):
                if not value.filename:
                    value = str(value.value)
            else:
                value = [str(v.value) for v in value]
            params[key] = value
        if self._environ['REQUEST_METHOD'].upper() == 'POST':
            qs = cgi.parse_qs(self.queryString, keep_blank_values=True,
                                       strict_parsing=False)
            for key, value in qs.items():
                if not params.has_key(key):
                    params[key] = value
        self.params = params

        # parse cookies
        cookie = SimpleCookie()
        if self._environ.has_key('HTTP_COOKIE'):
            try:
                cookie.load(self._environ['HTTP_COOKIE'])
            except:
                import traceback
                traceback.print_exc(file=self._environ['wsgi.errors'])
        cookies = {}
        for key in cookie.keys():
            cookies[key] = cookie[key].value
        self.cookies = cookies

    def __getitem__(self, name):
        return self._data.get(name)

    def __setitem__(self, name, value):
        self._data[name] = value

    method = property(fget=lambda x: x._environ['REQUEST_METHOD'])
    scriptName = property(fget=lambda x: x._environ.get('SCRIPT_NAME') or '')
    pathInfo = property(fget=lambda x: x._environ.get('PATH_INFO') or '')
    queryString = property(fget=lambda x: x._environ.get('QUERY_STRING') or '')
    serverName = property(fget=lambda x: x._environ.get('SERVER_NAME'))
    serverPort = property(fget=lambda x: x._environ.get('SERVER_PORT'))
    serverProtocol = property(fget=lambda x: x._environ.get('SERVER_PROTOCOL'))
    scheme = property(fget=lambda x: x._environ['wsgi.url_scheme'])
    baseURL = property(fget=lambda x: x._baseURL or x._reconstructBaseURL())

    remoteUser = property(fget=lambda x: x._environ.get('REMOTE_USER') or '')
    remoteAddr = property(fget=lambda x: x._environ.get('REMOTE_ADDR') or '')
    remoteHost = property(fget=lambda x: x._environ.get('REMOTE_HOST') or '')

    def read(self, len=None):
        return self._body.read(len)

    def _reconstructBaseURL(self):
        from urllib import quote
        url = '%s://' % self.scheme

        if self.headers['HTTP_HOST']:
            url += self.headers['HTTP_HOST']
        else:
            url += self.serverName
            if self.scheme == 'https':
                if self.serverPort != '443':
                   url += ':' + self.serverPort
            else:
                if self.serverPort != '80':
                   url += ':' + self.serverPort
        url += quote(self.scriptName)

        self._baseURL = url
        return self._baseURL


class Cookie(object):

    _name = None
    _path = None
    value = None
    expires = None
    _secure = 0

    def __init__(self, value, expires=None):
        self.value = value
        self.expires = expires

    def __str__(self):
        cookies = SimpleCookie()
        cookies[self._name] = self.value
        cookie = cookies[self._name]
        if self.expires != None:
            cookie['expires'] = time.strftime('%a, %d-%b-%y %H:%M:%S GMT',
                                              time.gmtime(self.expires))
            if self.expires <= time.time():
                cookie['max-age'] = 0
        if self._path != None:
            cookie['path'] = self._path
        if self._secure:
            cookie['secure'] = 1
        return cookies.output(header='')


class Response(object):
    """
    High-level abstraction of an HTTP response. Provides access to all the
    response related methods and data, such as writing to the response body,
    settings response headers, and so on.
    """

    status = None
    headers = None

    _req = None
    _start_response = None
    _started = False
    _body = None

    class __Headers(object):

        _data = None

        def __init__(self):
            self._data = []

        def __setitem__(self, name, value):
            self._data.append((name, value))


    class __Cookies(object):

        _req = None
        _data = None

        def __init__(self, req):
            self._req = req
            self._data = []

        def __setitem__(self, name, value):
            assert isinstance(value, Cookie)
            value._name = name
            value._path = self._req.scriptName
            self._data.append(value)

        def __delitem__(self, name):
            self[name] = Cookie('', 0)
            pass


    def __init__(self, req, start_response):
        self._req = req
        self._start_response = start_response
        self.status = "200 OK"
        self.headers = self.__Headers()
        self.cookies = self.__Cookies(req)
        self._body = []

    def __iter__(self):
        if not self._started:
            headers = self.headers._data[:]
            cookies = self.cookies._data
            for cookie in cookies:
                headers.append(('Set-Cookie', str(cookie)))
            self._start_response(self.status, headers)
            self._started = True
        return iter(self._body)

    def write(self, data):
        self._body.append(data)

    def sendFile(self, file, block_size=1024):
        if 'wsgi.file_wrapper' in self._req._environ:
            self._body = self._environ['wsgi.file_wrapper'](file, block_size)
        else:
            self._body = lambda: file.read(block_size)
        raise SendResponse

    def sendRedirect(self, location):
        if location.startswith('/'):
            location = self._req.baseURL + location
        self.status = "302 Moved Temporarily"
        self.headers['Location'] = location
        self.headers['Content-Type'] = 'text/plain'
        self.headers['Pragma'] = 'no-cache'
        self.headers['Cache-control'] = 'no-cache'
        self.headers['Expires'] = 'Fri, 01 Jan 1999 00:00:00 GMT'
        self.write("Redirecting...")
        raise SendResponse

    def sendError(self, status, e=None):
        # TODO: use start_response() with an exc_info parameter here?
        self.status = status
        raise SendResponse


class Application(object):
    """
    WSGI application that runs Trac on a given environment.
    """

    def __init__(self, env):
        self.env = env
        self.dispatcher = env.plugin("dispatcher")

    def __call__(self, environ, start_response):
        req = Request(environ)
        resp = Response(req, start_response)
        try:
            try:
                self.dispatcher.dispatch(req, resp)
            except SendResponse, e:
                pass
        except Exception, e:
            self.sendError(req, resp, e)

        return resp

    def sendError(self, req, resp, e):
        resp.status = '500 Internal Server Error'
        resp.headers['Content-Type'] = 'text/html; charset=utf-8'

        import traceback
        import StringIO
        buf = StringIO.StringIO()
        traceback.print_exc(file=buf)

        resp.write("""<html>
<head><title>Internal error</title></head>
<body>
<h1>Internal error</h1>
<p>%s</p>
<pre>%s</pre>
</body></html>""" % (e, buf.getvalue()))
        return resp


__all__ = ['Application', 'Cookie', 'Request', 'Response', 'SendResponse']
