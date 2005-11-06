# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003-2005 Edgewall Software
# Copyright (C) 2003-2005 Jonas Borgström <jonas@edgewall.com>
# Copyright (C) 2004-2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.com/license.html.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://projects.edgewall.com/trac/.
#
# Author: Jonas Borgström <jonas@edgewall.com>
#         Christopher Lenz <cmlenz@gmx.de>

try:
    import threading
except ImportError:
    import dummy_threading as threading
import time
import urllib
import re

from trac.core import *
from trac.object import ITracObjectManager
from trac.util import to_utf8, TRUE


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

    def render_macro(req, source, facet, name, content):
        """Return the HTML output of the macro.

         * `req` is the current request if there's one
         * `source` is the Trac object owning the wiki text containing the macro
         * `name` is the name of the macro
         * `content` contains the arguments for the macro
        """


class IWikiSyntaxProvider(Interface):
 
    def get_wiki_syntax():
        """Return an iterable that provides additional wiki syntax."""
 
    def get_link_resolvers():
        """Return an iterable over (namespace, formatter) tuples."""
 

class WikiSystem(Component):
    """Represents the wiki system."""

    implements(IWikiChangeListener, IWikiSyntaxProvider, ITracObjectManager)

    change_listeners = ExtensionPoint(IWikiChangeListener)
    macro_providers = ExtensionPoint(IWikiMacroProvider)
    syntax_providers = ExtensionPoint(IWikiSyntaxProvider)

    INDEX_UPDATE_INTERVAL = 5 # seconds

    def __init__(self):
        self._index = None
        self._last_index_update = 0
        self._index_lock = threading.RLock()
        self._compiled_rules = None
        self._helper_patterns = None
        self._link_resolvers = None
        self._external_handlers = None
        self._xref_link_resolvers = None
        self._xref_external_handlers = None

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
        return self._index.has_key(pagename)

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
            self._index[page.name] = True

    def wiki_page_changed(self, page, version, t, comment, author, ipnr):
        pass

    def wiki_page_deleted(self, page):
        if self.has_page(page.name):
            self.log.debug('Removing page %s from index' % page.name)
            del self._index[page.name]

    # IWikiSyntaxProvider methods
    
    def get_wiki_syntax(self):
        ignore_missing = self.config.get('wiki', 'ignore_missing_pages')
        ignore_missing = ignore_missing in TRUE
        yield (r"!?(?<!/)\b[A-Z][a-z]+(?:[A-Z][a-z]*[a-z/])+"
                "(?:#[A-Za-z0-9]+)?(?=\Z|\s|[.,;:!?\)}\]])",
               lambda x, y, z: self._format_link(x, 'wiki', y, y,
                                                 ignore_missing),
               lambda x, y, z: self._parse_link(x, 'wiki', y, y))

    def get_link_resolvers(self):
        yield ('wiki', self._format_fancy_link, self._parse_link)

    def _format_fancy_link(self, f, n, p, l):
        return self._format_link(f, n, p, l, False)

    def _format_link(self, formatter, ns, page, label, ignore_missing):
        anchor = ''
        if page.find('#') != -1:
            anchor = page[page.find('#'):]
            page = page[:page.find('#')]
        page = urllib.unquote(page)
        label = urllib.unquote(label)

        if not self.has_page(page):
            if ignore_missing:
                return label
            return '<a class="missing wiki" href="%s" rel="nofollow">%s?</a>' \
                   % (formatter.href.wiki(page) + anchor, label)
        else:
            return '<a class="wiki" href="%s">%s</a>' \
                   % (formatter.href.wiki(page) + anchor, label)

    def _parse_link(self, formatter, ns, target, label):
        return self._wiki_factory(target)

    # ITracObjectManager methods

    def get_object_types(self):
        yield ('wiki', self._wiki_factory)

    def rebuild_xrefs(self, db):
        cursor = db.cursor()
        cursor.execute("SELECT name,time,author,text"
                       "  FROM wiki ORDER BY name,version DESC")
        src = previous = None
        for name,time,author,text in cursor:
            if name != previous:
                previous = name
                yield (self._wiki_factory(name), 'content', time, author, text)
            # Note: wiki edit comments are not yet editable,
            #       therefore they are not yet considered to be facets.

    def _wiki_factory(self, id):
        from trac.wiki.model import WikiPage
        return WikiPage(self.env).setid(id)

