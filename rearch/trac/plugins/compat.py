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
import trac.core as legacy

from protocols import *

import re


class LegacyRequestWrapper(legacy.Request):

    req = None
    resp = None

    def __init__(self, req, resp):
        self.req = req
        self.resp = resp
        self.hdf = req['template_data']

    def read(self, len):
        return self.req.read(len)

    def write(self, data):
        return self.resp.write(data)

    def get_header(self, name):
        return self.req.headers[name]

    def send_response(self, code):
        self.resp.status = code

    def send_header(self, name, value):
        self.response.headers[name] = value

    def end_headers(self):
        pass

    def check_modified(self, timesecs, extra=''):
        # TODO: This needs to be implemented in the new web layer
        pass

    def redirect(self, url):
        if url.startswith(self.req.scriptName):
            # the new Response class adds the SCRIPT_NAME automatically
            url = url[len(self.req.scriptName):]
        self.resp.sendRedirect(url)

    def display(self, cs, content_type='text/html', response=200):
        self.req['template_file'] = cs
        self.resp.status = response
        self.resp.headers['Content-Type'] = content_type

    cgi_location = property(fget=lambda x: x.req.scriptName)
    authname = property(fget=lambda x: x.req['user'] or 'anonymous')
    session = property(fget=lambda x: x.req['session'])


class CompatPlugin(Plugin):
    """
    Compatibility layer for old-style Trac modules. This will be removed once
    all the modules have been ported to the new plug-in system.
    """

    # Plug-in info

    _id = 'compat'
    _extends = ['dispatcher.requestFilters',
                'dispatcher.requestProcessors']

    advise(instancesProvide=[dispatcher.IRequestFilter,
                             dispatcher.IRequestProcessor])

    # dispatcher.IRequestFilters methods

    def beforeProcessingRequest(self, req, resp):
        data = req['template_data']

        # Setup the Href helper
        from trac import Href
        self.env.href = Href.Href(req.scriptName)
        self.env.abs_href = Href.Href(req.baseURL)

        data['trac']['href'] = {
            'wiki': self.env.href.wiki(),
            'browser': self.env.href.browser('/'),
            'timeline': self.env.href.timeline(),
            'roadmap': self.env.href.roadmap(),
            'milestone': self.env.href.milestone(None),
            'report': self.env.href.report(),
            'query': self.env.href.query(),
            'newticket': self.env.href.newticket(),
            'search': self.env.href.search(),
            'about': self.env.href.about(),
            'about_config': self.env.href.about('config'),
            'login': self.env.href.login(),
            'logout': self.env.href.logout(),
            'settings': self.env.href.settings(),
            'homepage': 'http://trac.edgewall.com/'
        }

        # Setup the permissions helper
        from trac import perm
        self.env.perm = perm.PermissionCache(self.env.getDBConnection(),
                                             req['user'])
        self.env.perm.add_to_hdf(data)

        # Add request parameters to HDF
        data['args'] = req.params

    def afterProcessingRequest(self, req, resp, exc_info):
        pass

    # dispatcher.IRequestProcessor methods

    def matchRequest(self, req):
        if req.pathInfo in ['/login', '/logout']:
            return 0
        match = re.search('^/(about_trac|wiki)(?:/(.*))?', req.pathInfo)
        if match:
            req['mode'] = match.group(1)
            if match.group(2):
                req.params['page'] = match.group(2)
            return 1
        match = re.search('^/(newticket|timeline|search|roadmap|query)/?', req.pathInfo)
        if match:
            req['mode'] = match.group(1)
            return 1
        match = re.search('^/(ticket|report)(?:/([0-9]+)/*)?', req.pathInfo)
        if match:
            req['mode'] = match.group(1)
            if match.group(2):
                req.params['id'] = match.group(2)
            return 1
        match = re.search('^/(browser|log|file)(?:(/.*))?', req.pathInfo)
        if match:
            req['mode'] = match.group(1)
            if match.group(2):
                req.params['path'] = match.group(2)
            return 1
        match = re.search('^/changeset/([0-9]+)/?', req.pathInfo)
        if match:
            req['mode'] = 'changeset'
            req.params['rev'] = match.group(1)
            return 1
        match = re.search('^/attachment/([a-zA-Z_]+)/([^/]+)(?:/(.*)/?)?', req.pathInfo)
        if match:
            req['mode'] = 'attachment'
            req.params['type'] = match.group(1)
            req.params['id'] = urllib.unquote(match.group(2))
            req.params['filename'] = match.group(3)
            return 1
        match = re.search('^/milestone(?:/([^\?]+))?(?:/(.*)/?)?', req.pathInfo)
        if match:
            req['mode'] = match.group(1)
            if match.group(1):
                req.params['id'] = urllib.unquote_plus(match.group(1))
            return 1

    def processRequest(self, req, resp):
        data = req['template_data']

        if not req['mode']: # set as default processor
            req['mode'] = 'wiki'

        args = {'mode': req['mode']}
        args.update(req.params)

        try:
            pool = None
            # Load the selected module
            module = legacy.module_factory(args, self.env,
                                           self.env.get_db_cnx(),
                                           LegacyRequestWrapper(req, resp))
            pool = module.pool
            module.run()
        finally:
            # We do this even if the cgi will terminate directly after. A pool
            # destruction might trigger important clean-up functions.
            if pool:
                import svn.core
                svn.core.svn_pool_destroy(pool)
