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
from trac.util import escape

from protocols import *

import time


class INavigationContributor(Interface):
    """
    Extension point interface for plug-ins that contribute links to the
    site navigation.
    """

    def getNavigationLinks(req, category):
        """
        Return a list of navigation links for the specified category. The
        category can be one of 'metanav', 'mainnav' or 'ctxtnav'. If no links
        are to be contributed to the given category, return an empty list.
        
        TODO: We need a way to configure/determine the order of the navigation
              items.
        """


class ChromePlugin(Plugin):
    """
    Plug-in that manages the non-content parts of web-pages, such as the
    navigation and logo.
    """

    # Plug-in info

    _id = 'chrome'
    _extends = ['dispatcher.requestFilters']
    advise(instancesProvide=[dispatcher.IRequestFilter])

    navigationContributors = ExtensionPoint(INavigationContributor)

    # dispatcher.IRequestFilter methods

    def beforeProcessingRequest(self, req, resp):
        data = req['template_data']
        assert data, "Template data not available"

        from trac.__init__ import __version__

        # TODO: The following has been adapted from trac.core.populate_hdf.
        # It should be cleaned up.
        htdocs_location = self.env.get_config('trac', 'htdocs_location')
        if htdocs_location[-1] != '/':
            htdocs_location += '/'
        data['htdocs_location'] = htdocs_location
        data['project'] = {
            'name': self.env.get_config('project', 'name'),
            'name.encoded': escape(self.env.get_config('project', 'name')),
            'descr': self.env.get_config('project', 'descr'),
            'footer': self.env.get_config('project', 'footer',
                ' Visit the Trac open source project at<br />'
                '<a href="http://trac.edgewall.com/">http://trac.edgewall.com/</a>'),
            'url': self.env.get_config('project', 'url')
        }
        data['trac'] = {
            'href': {
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
            },
            'version': __version__,
            'time': time.strftime('%c', time.localtime())
        }

        src = self.env.get_config('header_logo', 'src')
        src_abs = src[:7] == 'http://' and 1 or 0
        if not src[0] == '/' and not src_abs:
            src = htdocs_location + src
        data['header_logo'] = {
            'link': self.env.get_config('header_logo', 'link'),
            'alt': self.env.get_config('header_logo', 'alt'),
            'src': src,
            'src_abs': str(src_abs),
            'width': self.env.get_config('header_logo', 'width'),
            'height': self.env.get_config('header_logo', 'height')
        }
        if req:
            data['cgi_location'] = req.scriptName
            data['trac.authname'] = escape(req['user'])

        for category in ['metanav', 'mainnav', 'ctxtnav']:
            items = []
            for contributor in self.navigationContributors:
                items += contributor.getNavigationLinks(req, category) or []
            data['navigation'][category] = items

    def afterProcessingRequest(self, req, resp, exc_info):
        pass
