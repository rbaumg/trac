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

from protocols import *
from trac.plugin import *

import sys


class IRequestProcessor(Interface):
    """
    Extension point interface for plug-ins that want to do the main processing
    of specific HTTP requests.
    """

    def matchRequest(req):
        """TODO"""

    def processRequest(req, resp):
        """TODO"""


class IRequestFilter(Interface):
    """
    Extension point interface that allows plug-ins to hook into the processing
    of HTTP requests. Plug-ins implementing this interface will get a chance
    to look at or modify requests before and after they are processed by the
    IRequestProcessor that matches the request.
    """

    def beforeProcessingRequest(req, resp):
        """TODO"""

    def afterProcessingRequest(req, resp, exc_info):
        """TODO"""


class RequestDispatcher(Plugin):

    _id = 'dispatcher'
    requestFilters = ExtensionPoint(IRequestFilter)
    requestProcessors = ExtensionPoint(IRequestProcessor)

    def dispatch(self, req, resp):
        """
        Dispatches the given HTTP request to the plugin matching it, or sends
        a "404 Not Found" error if no plugin matches.
        """

        # Get the list of configured request filters. This determines both the
        # enablement and the order in which the filters are run.
        filters = map(lambda x: x.strip(),
                      self.env.get_config('web', 'filters', '').split(','))
        filterEnabled = lambda x: x in filters
        filterOrder = lambda a,b: cmp(filters.index(a), filters.index(b))

        # Let the request filters pre-process the request.
        for requestFilter in self.requestFilters(constrain=filterEnabled,
                                                 order=filterOrder):
            requestFilter.beforeProcessingRequest(req, resp)

        # Select the processor that should process this request
        if not req.pathInfo or req.pathInfo == '/':
            defaultProcessor = self.env.get_config('web', 'default')
            if not defaultProcessor:
                resp.status = "500 Internal Server Error"
                raise Exception, "No default request processor configured"
            isDefault = lambda x: x == defaultProcessor
            processors = [p for p in self.requestProcessors(constrain=isDefault)]
        else:
            processors = [p for p in self.requestProcessors
                          if p.matchRequest(req)]

        exc_info = None
        try:
            # Make sure we have one (and only one plug-in ready to process the
            # request, and let it do its work
            if not processors: # 404 Not Found
                resp.status = "404 Not Found"
                raise Exception, "No processor matched the request to %s" \
                                 % req.pathInfo
            if len(processors) > 1: # 500 Internal Server Error
                resp.status = "500 Internal Server Error"
                raise Exception, "More than one processor matched the request (%s)" \
                                 % map(str, processors)
            processors[0].processRequest(req, resp)
        except:
            from trac.web import SendResponse
            exc_info = sys.exc_info()
            if exc_info[0] != SendResponse:
                raise exc_info[0], exc_info[1], exc_info[2]

        # Give request filters a chance to post-process the request (in reverse
        # order)
        for requestFilter in self.requestFilters(constrain=filterEnabled,
                                                 order=filterOrder, reverse=1):
            requestFilter.afterProcessingRequest(req, resp, exc_info)


__all__ = ['IRequestFilter', 'IRequestProcessor', 'RequestDispatcher']
