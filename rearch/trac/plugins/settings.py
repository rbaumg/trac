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
from trac.web import dispatcher

from protocols import *

import re
import time


class SettingsPlugin(Plugin):
    """
    This plug-in adds a form that let's the user edit some of her settings,
    such as full name and email address.
    """

    # Plug-in info

    _id = 'settings'
    _extends = ['dispatcher.requestProcessors']
    advise(instancesProvide=[dispatcher.IRequestProcessor])

    # dispatcher.IRequestProcessor methods

    def matchRequest(self, req):
        return req.pathInfo == '/settings'

    def processRequest(self, req, resp):
        req['template_file'] = 'settings.cs'

        data = req['template_data']
        data['title'] = 'Settings'

        session = req['session']        
        assert session, 'No session available'

        action = req.params.get('action')
        if action == 'save':
            self._saveSettings(req, resp, session)
            resp.sendRedirect('/settings')
        elif action == 'load':
            self._loadSettings(req, resp, session)

    # Internal methods

    def _loadSettings(self, req, resp, session):
        raise NotImplementedError, "Loading sessions is not implemented"
        pass

    def _saveSettings(self, req, resp, session):
        # If a new session ID was specified, make sure no other session already
        # exists with the ID
        newID = req.params.get('newsid')
        if newID and newID != session.id:
            db = self.env.getDBConnection()
            try:
                cursor = db.cursor()
                cursor.execute("SELECT sid FROM session WHERE sid=%s", newID)
                if cursor.fetchone():
                    raise TracError("Session '%s' already exists.<br />"
                                    "Please choose a different session id."
                                    % value, "Error renaming session")
                session.id = newID
            finally:
                db.close()

        for field in ('name', 'email'):
            value = req.params.get(field)
            if value:
                session[field] = value
