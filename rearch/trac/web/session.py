# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2004 Edgewall Software
# Copyright (C) 2004 Daniel Lundin <daniel@edgewall.com>
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
# Author: Daniel Lundin <daniel@edgewall.com>

from trac.plugin import *
from trac.util import hex_entropy, TracError
from trac.web import Cookie, dispatcher

from protocols import *

import sys
import time


class Session(object):

    _id = None
    _originalID = None
    _vars = None
    _oldVars = None

    id = property(fget=lambda x: x._id, fset=lambda x,y: x._changeID(y))

    def __init__(self, id, vars={}, isNew=0):
        self._id = id
        if not isNew:
            self._originalID = id
        self._vars = vars
        self._oldVars = vars.copy()

    def __getitem__(self, key):
        return self._vars[key]

    def __setitem__(self, key, val):
        return self.set(key, val)

    def __delitem__(self, key):
        return self.set(key, None)

    def get(self, *args):
        return apply(self._vars.get, args)

    def keys(self):
        return self._vars.keys()

    def set(self, key, value):
        currentValue = self._vars.get(key)
        if currentValue != value:
            self._vars[key] = value

    def _changeID(self, newID):
        if newID == self._id:
            return
        self._id = newID


class SessionPlugin(Plugin):
    """Basic session handling and per-session storage."""

    # Plug-in info

    _id = 'session'
    _extends = ['dispatcher.requestFilters']
    advise(instancesProvide=[dispatcher.IRequestFilter])

    DEPARTURE_INTERVAL = 3600 # If you're idle for an hour, you left
    UPDATE_INTERVAL = 300     # Update session every 5 mins
    PURGE_AGE = 3600*24*90    # Purge session after 90 days idle

    # dispatcher.IRequestFilter methods

    def beforeProcessingRequest(self, req, resp):

        session = None
        sessionID = req.cookies.get('trac_session')
        if not sessionID or req.params.has_key('newsession'):
            sessionID = hex_entropy(24)
            session = Session(sessionID, isNew=1)
        else:
            session = self._fetchSession(sessionID, req['user'])

        req['session'] = session
        data = req['template_data']
        assert data, "No template data available"
        data['trac']['session']['id'] = sessionID
        if session:
            data['trac']['session']['var'] = session._vars

    def afterProcessingRequest(self, req, resp, exc_info):
        session = req['session']

        # Update last mod and access time
        modTime = int(session.get('mod_time', 0))
        lastVisit = int(session.get('last_visit', 0))

        now = int(time.time())
        idle = now - modTime

        if idle > self.DEPARTURE_INTERVAL or not lastVisit:
            session['last_visit'] = modTime
            self._purgeExpiredSessions()
        if idle > self.UPDATE_INTERVAL or not modTime:
            session['mod_time'] = now
            resp.cookies['trac_session'] = Cookie(session.id, time.time() + self.PURGE_AGE)
        elif session.id != session._originalID:
            resp.cookies['trac_session'] = Cookie(session.id, time.time() + self.PURGE_AGE)

        db = self.env.getDBConnection()
        try:
            self._updateSession(db, session)
        finally:
            db.close()

    # Internal methods

    def _fetchSession(self, sessionID, userName):
        session = None
        rows = None
        db = self.env.getDBConnection()
        try:
            cursor = db.cursor()
            cursor.execute("SELECT username,var_name,var_value FROM session "
                           "WHERE sid=%s", sessionID)
            rows = cursor.fetchall()
        finally:
            db.close()

        if (not rows                            # No session data yet
            or rows[0][0] == 'anonymous'        # Anonymous session
            or rows[0][0] == userName): # Session is mine
            vars = {}
            for u,k,v in rows:
                vars[k] = v
            session = Session(sessionID, vars)
            return session

        if not userName:
            err = ('Session cookie requires authentication. <p>'
                   'Please choose action:</p>'
                   '<ul><li><a href="%s">Log in and continue session</a>'
                   '</li><li><a href="%s?newsession=1">Create new session'
                   '(no login required)</a></li></ul>'
                   % (self.env.href.login(), self.env.href.settings()))
        else:
            err = ('Session belongs to another authenticated user.'
                   '<p><a href="%s?newsession=1">Create new session</a></p>'
                   % self.env.href.settings())
        raise TracError(err, 'Error accessing authenticated session')

    def _purgeExpiredSessions(self):
        mintime = int(time.time()) - self.PURGE_AGE
        self.log.debug('Purging old, expired, sessions.')
        db = self.env.getDBConnection()
        try:
            cursor = db.cursor()
            cursor.execute("DELETE FROM session WHERE sid IN "
                           "(SELECT sid FROM session WHERE var_name='mod_time'"
                           "AND var_value<%s)", mintime)
            db.commit()
        finally:
            db.close()

    def _updateSession(self, db, session):
        cursor = db.cursor()

        if session._originalID and session.id != session._originalID:
            # Update the session ID
            self.log.debug("ID of session '%s' changed to '%s'"
                           % (session._originalID, session._id))
            cursor = db.cursor()
            cursor.execute("UPDATE session SET sid=%s WHERE sid=%s",
                           session._id, session._originalID)

        for k in session._vars.keys():
            value = session.get(k)
            if not value:
                continue
            if not k in session._oldVars.keys():
                # Delete the variable from the DB
                cursor.execute("INSERT INTO session "
                               "(sid,username,var_name,var_value) "
                               "VALUES(%s,%s,%s,%s)",
                               session.id, None, k, value)
            elif value != session._oldVars.get(k):
                # Update the session variable in the DB
                cursor.execute("UPDATE session SET var_value=%s "
                               "WHERE sid=%s AND var_name=%s",
                               value, session.id, k)
                del session._oldVars[k]

        db.commit()
