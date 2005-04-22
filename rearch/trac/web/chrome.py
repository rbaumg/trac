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

from trac.core import *
from trac.util import enum, escape

def add_link(req, rel, href, title=None, type=None, class_name=None):
    link = {'href': escape(href)}
    if title: link['title'] = escape(title)
    if type: link['type'] = type
    if class_name: link['class'] = class_name
    idx = 0
    while req.hdf.get('links.%s.%d.href' % (rel, idx)):
        idx += 1
    req.hdf['links.%s.%d' % (rel, idx)] = link


class INavigationContributor(Interface):

    def get_navigation_items(req):
        """
        FIGUREMEOUT
        """


class Chrome(Component):
    """
    Responsible for assembling the web site chrome, i.e. everything that
    is not actual page content.
    """

    navigation_contributors = ExtensionPoint(INavigationContributor)

    def populate_hdf(self, req):
        htdocs_location = self.config.get('trac', 'htdocs_location')
        if htdocs_location[-1] != '/':
            htdocs_location += '/'
        req.hdf['htdocs_location'] = htdocs_location
        req.hdf['HTTP.PathInfo'] = req.path_info

        # Logo image
        logo_src = self.config.get('header_logo', 'src')
        logo_src_abs = logo_src.startswith('http://') or \
                       logo_src.startswith('https://')
        if not logo_src[0] == '/' and not logo_src_abs:
            logo_src = htdocs_location + logo_src
        req.hdf['header_logo'] = {
            'link': self.config.get('header_logo', 'link'),
            'alt': escape(self.config.get('header_logo', 'alt')),
            'src': logo_src,
            'src_abs': logo_src_abs,
            'width': self.config.get('header_logo', 'width'),
            'height': self.config.get('header_logo', 'height')
        }

        # HTML <head> links
        add_link(req, 'start', self.env.href.wiki())
        add_link(req, 'search', self.env.href.search())
        add_link(req, 'help', self.env.href.wiki('TracGuide'))
        icon = self.config.get('project', 'icon')
        if icon:
            if not icon[0] == '/' and icon.find('://') < 0:
                icon = htdocs_location + icon
            mimetype = self.env.mimeview.get_mimetype(icon)
            add_link(req, 'icon', icon, type=mimetype)
            add_link(req, 'shortcut icon', icon, type=mimetype)

        navigation_items = []
        for contributor in self.navigation_contributors:
            navigation_items += contributor.get_navigation_items(req)
