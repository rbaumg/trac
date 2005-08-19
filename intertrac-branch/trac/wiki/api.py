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
try:
    import threading
except ImportError:
    import dummy_threading as threading
import time
import urllib
import re

from trac.core import *
from trac.util import to_utf8


class IWikiChangeListener(Interface):
    """Extension point interface for components that should get notified about
    the creation, deletion and modification of wiki pages.
    """

    def wiki_page_added(page):
        """Called whenever a new Wiki page is added."""

    def wiki_page_changed(page, version, t, comment, author, ipnr):
        """Called when a page has been modified."""

    def wiki_page_deleted(page):
        """Called when a page has been deleted."""


class IWikiMacroProvider(Interface):
    """Extension point interface for components that provide Wiki macros."""

    def get_macros():
        """Return an iterable that provides the names of the provided macros."""

    def get_macro_description(name):
        """Return a plain text description of the macro with the specified name.
        """

    def render_macro(req, name, content):
        """Return the HTML output of the macro."""


class IWikiSyntaxProvider(Interface):
 
    def get_wiki_syntax():
        """Return an iterable that provides additional wiki syntax."""
 
    def get_link_resolvers():
        """Return an iterable over (namespace, formatter) tuples."""
 
class IWikiPageNameSyntaxProvider(Interface):
 
    def get_wiki_page_names_syntax():
        """
        Return an iterable that provides a regular expression for
        matching wiki page names (see WikiPageNames)

        Be careful to only allow __one__ implementation
        (others should be listed in the ![disabled_components]
        section of the TracIni)
        """
 

class WikiSystem(Component):
    """Represents the wiki system."""

    implements(IWikiChangeListener, IWikiSyntaxProvider)

    change_listeners = ExtensionPoint(IWikiChangeListener)
    macro_providers = ExtensionPoint(IWikiMacroProvider)
    syntax_providers = ExtensionPoint(IWikiSyntaxProvider)
    wikipagenames_providers = ExtensionPoint(IWikiPageNameSyntaxProvider)

    INDEX_UPDATE_INTERVAL = 5 # seconds

    def __init__(self):
        self._index = None
        self._last_index_update = 0
        self._index_lock = threading.RLock()
        self._compiled_rules = None
        self._link_resolvers = None
        self._helper_patterns = None
        self._external_handlers = None

    def _update_index(self):
        self._index_lock.acquire()
        try:
            now = time.time()
            if now > self._last_index_update + WikiSystem.INDEX_UPDATE_INTERVAL:
                self.log.debug('Updating wiki page index')
                db = self.env.get_db_cnx()
                cursor = db.cursor()
                cursor.execute("SELECT DISTINCT name FROM wiki")
                self._index = {}
                for (name,) in cursor:
                    self._index[name] = True
                self._last_index_update = now
        finally:
            self._index_lock.release()

    # Public API

    def get_pages(self, prefix=None):
        """Iterate over the names of existing Wiki pages.

        If the `prefix` parameter is given, only names that start with that
        prefix are included.
        """
        self._update_index()
        for page in self._index.keys():
            if not prefix or page.startswith(prefix):
                yield page

    def has_page(self, pagename):
        """Whether a page with the specified name exists."""
        self._update_index()
        return pagename in self._index.keys()

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
    
    def _prepare_rules(self):
        from trac.wiki.formatter import Formatter
        if not self._compiled_rules:
            helpers = []
            handlers = {}
            syntax = Formatter._pre_rules[:]
            i = 0
            for resolver in self.syntax_providers:
                for regexp, handler in resolver.get_wiki_syntax():
                    handlers['i'+str(i)] = handler
                    syntax.append('(?P<i%d>%s)' % (i, regexp))
                    i += 1
            syntax += Formatter._post_rules[:]
            helper_re = re.compile(r'\?P<([a-z\d_]+)>')
            for rule in syntax:
                helpers += helper_re.findall(rule)[1:]
            rules = re.compile('(?:' + '|'.join(syntax) + ')')
            self._external_handlers = handlers
            self._helper_patterns = helpers
            self._compiled_rules = rules

    def _get_link_resolvers(self):
        if not self._link_resolvers:
            resolvers = {}
            for resolver in self.syntax_providers:
                for namespace, handler in resolver.get_link_resolvers():
                    resolvers[namespace] = handler
            self._link_resolvers = resolvers
        return self._link_resolvers
    link_resolvers = property(_get_link_resolvers)

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
        only_one = True
        for wikipagenames in self.wikipagenames_providers:
            if not only_one:
                self.log.warning('More than one IWikiPageNameSyntaxProvider '
                                 'implementation available: %s' %
                                 wikipagenames.__class__.__name__)
            else:
                yield (wikipagenames.get_wiki_page_names_syntax(),
                       lambda x, y, z: self._format_link(x, 'wiki', y, y))
                only_one = False

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


class StandardWikiPageNames(Component):
    """
    Standard Trac WikiPageNames rule
    """

    implements(IWikiPageNameSyntaxProvider)

    def get_wiki_page_names_syntax(self):
        return (r"!?(^|(?<=[^A-Za-z/]))"    # where to start
                r"[A-Z][a-z]+"              # initial WikiPageNames word
                r"(?:[A-Z][a-z]*[a-z/])+"   # additional WikiPageNames word
                r"(?:#[A-Za-z0-9]+)?"       # optional trailing section link
                r"(?=\Z|\s|[.,;:!?\)}\]])"  # where to end
                r"(?!:\S)")                 # InterWiki support 

class FlexibleWikiPageNames(Component):
    """
    Standard Trac WikiPageNames rule, with digits
    and consecutive upper-case characters allowed.

    More precisely, WikiPageNames are:
     * either 2 or more starting upper case letter or digits,
       followed by lower case letters
     * either 1 or more starting upper case letter or digits,
       followed by lower case letters, repeated at least 2 times
       (with optionally '/' between repetitions)
    """

    implements(IWikiPageNameSyntaxProvider)

    def get_wiki_page_names_syntax(self):
        return (r"!?(^|(?<=[^A-Za-z\d/]))"  # where to start
                r"(?:[A-Z\d]{2,}[a-z]+"                  # 1st way
                r"|[A-Z\d]+[a-z]+(?:/?[A-Z\d]+[a-z]*)+)" # 2nd way
                r"(?:#[A-Za-z0-9]+)?"       # optional trailing section link
                r"(?=\Z|\s|[.,;:!?\)}\]])"  # where to end 
                r"(?!:\S)")                 # InterWiki support 

class SubWikiPageNames(Component):
    """
    SubWiki-like rules.
    
    See http://www.webdav.org/wiki/projects/TextFormattingRules

    Note that '/' in this style of WikiPageNames are not supported.
    """

    implements(IWikiPageNameSyntaxProvider)

    def get_wiki_page_names_syntax(self):
        return (r"!?(^|(?<=[^A-Za-z/]))"    # where to start
                r"(?:[A-Z][A-Z]+[a-z\d]+[A-Z]*"  # 1st and 3rd way
                r"|[A-Z][a-z]+(?:[A-Z][a-z]+)+)" # 2nd way
                r"(?:#[A-Za-z0-9]+)?"       # optional trailing section link
                r"(?=\Z|\s|[.,;:!?\)}\]])"  # where to end 
                r"(?!:\S)")                 # InterWiki support 

