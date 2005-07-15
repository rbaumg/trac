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

from __future__ import generators
import urllib
import re

from trac.core import *
from trac.object import ITracObjectManager
from trac.util import to_utf8


class IWikiChangeListener(Interface):
    """
    Extension point interface for components that should get notified about the
    creation, deletion and modification of wiki pages.
    """

    def wiki_page_added(page):
        """
        Called whenever a new Wiki page is added.
        """

    def wiki_page_changed(page, version, t, comment, author, ipnr):
        """
        Called when a page has been modified.
        """

    def wiki_page_deleted(page):
        """
        Called when a page has been deleted.
        """


class IWikiMacroProvider(Interface):
    """
    Extension point interface for components that provide Wiki macros.
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


class IWikiSyntaxProvider(Interface):
 
    def get_wiki_syntax():
        """
        Return an iterable that provides additional wiki syntax.
        """
 
    def get_link_resolvers():
        """
        Return an iterable over (namespace, formatter) tuples.
        """
 

class WikiSystem(Component):
    """
    Represents the wiki system.
    """
    implements(IWikiChangeListener, IWikiSyntaxProvider, ITracObjectManager)

    change_listeners = ExtensionPoint(IWikiChangeListener)
    macro_providers = ExtensionPoint(IWikiMacroProvider)
    syntax_providers = ExtensionPoint(IWikiSyntaxProvider)

    def __init__(self):
        self._pages = None
        self._compiled_rules = None
        self._helper_patterns = None
        self._link_resolvers = None
        self._external_handlers = None
        self._xref_link_resolvers = None
        self._xref_external_handlers = None

    def _load_pages(self):
        self._pages = {}
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT DISTINCT name FROM wiki")
        for (name,) in cursor:
            self._pages[name] = True

    # Public API

    def get_pages(self, prefix=None):
        if self._pages is None:
            self._load_pages()
        for page in self._pages.keys():
            if not prefix or page.startswith(prefix):
                yield page

    def has_page(self, pagename):
        if self._pages is None:
            self._load_pages()
        return pagename in self._pages.keys()

    def _get_rules(self):
        self._prepare_rules()
        return self._compiled_rules
    rules = property(_get_rules)

    def _get_helper_patterns(self):
        self._prepare_rules()
        return self._helper_patterns
    helper_patterns = property(_get_helper_patterns)

    def _get_external_handlers(self):
        self._prepare_rules()
        return self._external_handlers
    external_handlers = property(_get_external_handlers)
    
    def _get_xref_external_handlers(self):
        self._prepare_rules()
        return self._xref_external_handlers
    xref_external_handlers = property(_get_xref_external_handlers)
    
    def _prepare_rules(self):
        from trac.wiki.formatter import Formatter
        if not self._compiled_rules:
            helpers = []
            handlers = {}
            xref_handlers = {}
            syntax = Formatter._pre_rules[:]
            i = 0
            for resolver in self.syntax_providers:
                for data in resolver.get_wiki_syntax():
                    regexp, handler = data[:2]
                    key = 'i'+str(i)
                    handlers[key] = handler
                    if len(data) > 2:
                        xref_handlers[key] = data[2]
                    syntax.append('(?P<i%d>%s)' % (i, regexp))
                    i += 1
            syntax += Formatter._post_rules[:]
            helper_re = re.compile(r'\?P<([a-z\d_]+)>')
            for rule in syntax:
                helpers += helper_re.findall(rule)[1:]
            rules = re.compile('(?:' + '|'.join(syntax) + ')')
            self._external_handlers = handlers
            self._xref_external_handlers = xref_handlers
            self._helper_patterns = helpers
            self._compiled_rules = rules

    def _get_link_resolvers(self):
        self._prepare_resolvers()
        return self._link_resolvers
    link_resolvers = property(_get_link_resolvers)

    def _get_xref_link_resolvers(self):
        self._prepare_resolvers()
        return self._xref_link_resolvers
    xref_link_resolvers = property(_get_xref_link_resolvers)

    def _prepare_resolvers(self):
        if not self._link_resolvers:
            resolvers = {}
            xref_resolvers = {}
            for resolver in self.syntax_providers:
                for data in resolver.get_link_resolvers():
                    namespace, handler = data[:2]
                    resolvers[namespace] = data[1]
                    if len(data) > 2:
                        xref_resolvers[namespace] = data[2]
            self._link_resolvers = resolvers
            self._xref_link_resolvers = xref_resolvers

    # IWikiChangeListener methods

    def wiki_page_added(self, page):
        if not self.has_page(page.name):
            self.log.debug('Adding page %s to index' % page.name)
            self._pages[page.name] = True

    def wiki_page_changed(self, page, version, t, comment, author, ipnr):
        pass

    def wiki_page_deleted(self, page):
        if self.has_page(page.name):
            self.log.debug('Removing page %s from index' % page.name)
            del self._pages[page.name]
            
    # IWikiSyntaxProvider methods
    
    def get_wiki_syntax(self):
        yield (r"!?(^|(?<=[^A-Za-z]))"     # where to start
               r"[A-Z][a-z]+"              # initial WikiPageNames component
               r"(?:[A-Z][a-z]*[a-z/])+"   # additional WikiPageNames components
               r"(?:#[A-Za-z0-9]+)?"       # optional trailing section link
               r"(?=\Z|\s|[.,;:!?\)}\]])"  # where to end
               r"(?!:\S)",                 # InterWiki support               
               lambda x, y, z: self._format_link(x, 'wiki', y, y),
               lambda x, y, z: self._parse_link(x, 'wiki', y, y))

    def get_link_resolvers(self):
        yield ('wiki', self._format_link)

    def _format_link(self, formatter, ns, page, label):
        anchor = ''
        if page.find('#') != -1:
            anchor = page[page.find('#'):]
            page = page[:page.find('#')]
        page = urllib.unquote(page)
        label = urllib.unquote(label)

        if not self.has_page(page):
            return '<a class="missing wiki" href="%s" rel="nofollow">%s?</a>' \
                   % (formatter.href.wiki(page) + anchor, label)
        else:
            return '<a class="wiki" href="%s">%s</a>' \
                   % (formatter.href.wiki(page) + anchor, label)

    def _parse_link(self, formatter, ns, target, label):
        from trac.wiki import WikiPage
        wiki = WikiPage(self.env)
        wiki.id = wiki.name = target
        return wiki

    # ITracObjectManager methods

    def get_object_types(self):
        from trac.wiki.model import WikiPage
        yield ('wiki', lambda id: WikiPage(self.env, id))

    def rebuild_xrefs(self, db):
        from trac.wiki.model import WikiPage
        cursor = db.cursor()
        cursor.execute("SELECT name,time,author,text"
                       "  FROM wiki ORDER BY name,version DESC")
        src = previous = None
        for name,time,author,text in cursor:
            if name != previous:
                previous = name
                src = WikiPage(self.env, None) # no _fetch
                src.id = name
                src.name = name
                yield (src, 'content', time, author, text)
            # Note: wiki edit comments are not yet modifiable
            #       therefore it's not condidered to be a facet.

