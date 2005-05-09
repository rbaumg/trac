# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004, 2005 Edgewall Software
# Copyright (C) 2003, 2004, 2005 Jonas Borgström <jonas@edgewall.com>
# Copyright (C) 2004, 2005 Christopher Lenz <cmlenz@gmx.de>
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
#         Christopher Lenz <cmlenz@gmx.de>
#

from trac.core import *


class WikiChangeVeto(TracError):
    """
    TODO: doc me
    """


class IWikiChangeListener(Interface):

    def wiki_page_added(self, page):
        """
        TODO: doc me
        """

    def wiki_page_changed(self, page):
        """
        TODO: doc me
        """

    def wiki_page_deleted(self, page):
        """
        TODO: doc me
        """        


class IWikiMacroProvider(Interface):
    """
    TODO: doc me
    """

    def get_macros():
        """
        Return an iterable that provides the names of the provided macros.
        """

    def get_macro_description(name):
        """
        Return a plain text description of the macro with the specified name.
        """

    def render_macro(req, name, content):
        """
        Return the HTML output of the macro.
        """


class WikiSystem(Component):

    change_listeners = ExtensionPoint(IWikiChangeListener)
    macro_providers = ExtensionPoint(IWikiMacroProvider)

    implements(IWikiChangeListener)

    def __init__(self):
        self.pages = None

    def has_page(self, pagename):
        if self.pages == None:
            self.pages = {}
            db = self.env.get_db_cnx()
            cursor = db.cursor()
            cursor.execute("SELECT DISTINCT name FROM wiki")
            for (name,) in cursor:
                self.pages[name] = True
        return pagename in self.pages.keys()

    # IWikiChangeListener methods

    def wiki_page_added(self, page):
        if not self.has_page(page.name):
            self.log.debug('Adding page %s to index' % page.name)
            self.pages[page.name] = True

    def wiki_page_changed(self, page):
        pass

    def wiki_page_deleted(self, page):
        if self.has_page(page.name):
            self.log.debug('Removing page %s from index' % page.name)
            del self.pages[page.name]
