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

from trac.plugin import *
from trac.util import hex_entropy
from trac.web import chrome, dispatcher
from trac.web import Cookie

from protocols import *

import time


class ExternalAuthPlugin(Plugin):
    """
    This plug-in implements optional login/logout of users based on HTTP
    authentication (performed by the web-server) and cookies (for identifying
    the user even on requests to non-protected resources).
    """

    # Plug-in info

    _id = 'external_auth'
    _extends = ['chrome.navigationContributors',
                'dispatcher.requestFilters',
                'dispatcher.requestProcessors']
    advise(instancesProvide=[chrome.INavigationContributor,
                             dispatcher.IRequestFilter,
                             dispatcher.IRequestProcessor])

    # chrome.INavigationContributor methods

    def getNavigationLinks(self, req, category):
        if category == 'metanav':
            if req['user'] and req['user'] != 'anonymous':
                return [{'label': 'Logged in as %s' % req['user']},
                        {'label': 'Logout', 'link': req.baseURL + '/logout'}]
            else:
                return [{'label': 'Login', 'link': req.baseURL + '/login'}]

    # dispatcher.IRequestFilter methods

    def beforeProcessingRequest(self, req, resp):
        authToken = req.cookies.get('trac_auth')
        if authToken:
            db = self.env.getDBConnection()
            try:
                cursor = db.cursor()
                cursor.execute("SELECT name FROM auth_cookie WHERE cookie=%s "
                               "AND ipnr=%s", authToken, req.remoteAddr)
                if cursor.rowcount >= 1:
                    req['user'] = cursor.fetchone()[0]
                else:
                    # The token in the cookie doesn't match any known login, so
                    # remove the cookie
                    del req.cookies['trac_auth']
            finally:
                db.close()

    def afterProcessingRequest(self, req, resp, exc_info):
        pass

    # dispatcher.IRequestProcessor methods

    def matchRequest(self, req):
        return req.pathInfo in ['/login', '/logout']

    def processRequest(self, req, resp):
        if req.pathInfo == '/login':
            if not req.remoteUser:
                self.log.warn("Not logged in, probably the web server "
                              "isn't configured to require authentication "
                              "on the /login URL.")
            else:
                self._login(req, resp)
        else:
            self._logout(req, resp)

        referer = req.headers['Referer']
        if referer and referer.startswith(req.baseURL):
            # only redirect to referer if the latter is from the same instance
            referer = None
        resp.sendRedirect(referer or '/')

    # Internal methods

    def _login(self, req, resp):
        assert not req['user'], 'Remote user already logged in'
        authToken = hex_entropy(32)
        db = self.env.getDBConnection()
        try:
            cursor = db.cursor()
            cursor.execute("INSERT INTO auth_cookie (cookie, name, ipnr, time) "
                           "VALUES (%s, %s, %s, %s)", authToken, req.remoteUser,
                           req.remoteAddr, time.time())
            db.commit()
            resp.cookies['trac_auth'] = Cookie(authToken)
        finally:
            db.close()

    def _logout(self, req, resp):
        assert req['user'], 'Remote user not logged in'
        db = self.env.getDBConnection()
        try:
            cursor = db.cursor()
            cursor.execute("DELETE FROM auth_cookie WHERE name=%s", req['user'])
            db.commit()
            del resp.cookies['trac_auth']
        finally:
            db.close()
