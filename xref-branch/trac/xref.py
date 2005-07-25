# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Edgewall Software
# Copyright (C) 2005 Christian Boos <cboos@wanadoo.fr>
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
# Author: Christian Boos <cboos@wanadoo.fr>

"""
  This module implements a general cross-reference facility for Trac
  (TracCrossReferences).
 
  A cross-reference is a link created in one Trac object (the ''source'')
  pointing to another Trac object (the ''destination'').
  When the link is considered in the reversed direction,
  one can design it by the term `backlink`.
  By extension, the backlink can refer to the source Trac object, and
  a link can refer to the destination Trac object.

  Usually, this link is created after processing a Wiki text
  attached to the source object (a ''facet'').

  Example: terminology with the central TracObject taken as reference
  {{{
  .--------------------.           .============.           .----------------.
  | TracObject  ,------| backlink  | TracObject |    link   | TracObject (b) |
  |            ( facet |---------->|            |---------->|                |
  | (a) source  \__f___|           |    (me)    |           |  destination   |
  '--------------------'           '============'           '----------------'
                              me: destination for (a)
   (a) link to (me)        (a) reached through a backlink
   stored in facet f            me: source for (b)
                            (b) reached through a link
  }}}
  
  Here's the current list of Trac objects that can reference
  each other, with their related facets:
   * Wiki page `trac.wiki.WikiPage`
     * content facet
     * attachment comment facets
   * Ticket `trac.ticket.Ticket`
     * summary facet
     * description facet
     * comments facets
     * attachment comment facets
     * (more to come...)
   * Changeset `trac.versioncontrol.Changeset`
     * log message facet
   * Report `?`
     * title facet
     * description facet
   * Milestone `trac.Milestone`
     * title facet
     * description facet
   * Source `trac.versioncontrol.Node`
     * (no facet, only as a target)

  A cross-reference is also called a relation if a specific semantic is
  attached to the link from the source object to the destination object
  (stored in the `relation` field).
  If the `relation` is unset, the cross-reference semantic can be inferred
  from the `context` (usually the Wiki text in which the link was created).

"""

from StringIO import StringIO

from trac.core import *
from trac.object import TracObject, ITracObjectManager
from trac.wiki.formatter import Formatter
from trac.wiki.api import WikiSystem, IWikiMacroProvider
from trac.web.main import IRequestHandler
from trac.web.chrome import add_stylesheet
from trac.util import escape, TracError, pretty_timedelta

__all__ = ['XRefParser']


class XRefParser(Formatter):
    """
    This `Formatter` scans the wiki text of the given facet
    and process only the links, in order to create the
    corresponding cross-references.
    """
    flavor = 'xref'
    
    how_much_context = 40

    # Public API

    def __init__(self, env, db, relation=None):
        Formatter.__init__(self, env, db=db)
        self.relation = relation

    def parse(self, source, facet, time, author, wikitext):
        self.time = time
        self.author = author
        class NullOut:
            def write(self,*args): pass
        self.format(source, facet, wikitext, NullOut())

    # Reimplemented methods
    
    def replace(self, fullmatch):
        wiki = WikiSystem(self.env)
        for itype, match in fullmatch.groupdict().items():
            if match and not itype in wiki.helper_patterns:
                # Check for preceding escape character '!'
                if match[0] == '!':
                    continue
                target = None
                if itype in wiki.xref_external_handlers:
                    target = wiki.xref_external_handlers[itype](self, match,
                                                                fullmatch)
                else:
                    if itype == 'shref':
                        target = self._shref_formatter(match, fullmatch)
                    elif itype == 'href':
                        target = self._lhref_formatter(match, fullmatch)
                    # ignore the rest...
                if target and issubclass(target.__class__, TracObject):
                    self.source.create_xref(self.db, self.facet,
                                            self.time, self.author, target,
                                            self._extract_context(fullmatch),
                                            self.relation)

    def _macro_formatter(self, match, fullmatch):
        pass
                    
    def _make_link(self, ns, target, match, label):
        wiki = WikiSystem(self.env)
        # check first for an alias defined in trac.ini
        ns = self.env.config.get('intertrac', ns.upper(), ns)
        if ns in wiki.xref_link_resolvers:
            return wiki.xref_link_resolvers[ns](self, ns, target, label)

    # Helper method
    
    def _extract_context(self, fullmatch):
        start, end, text = fullmatch.start(), fullmatch.end(), fullmatch.string
        start_ellipsis = end_ellipsis = '...'
        start = start - self.how_much_context
        if start < 0:
            start = 0
            start_ellipsis = ''
        end = end + self.how_much_context
        if end > len(text):
            end = len(text)
            end_ellipsis = ''
        return start_ellipsis + text[start:end] + end_ellipsis



class XRefModule(Component):

    implements(IRequestHandler)

    # IRequestHandler methods

    def match_request(self, req):
        import re
        match = re.match(r'/xref/([^/]+)/(.+)', req.path_info)
        if match:
            req.args['type'] = match.group(1)
            req.args['id'] = match.group(2)
            return 1

    def process_request(self, req):
        # req.perm.assert_permission('WIKI_VIEW')

        type = req.args.get('type', 'wiki')
        id = req.args.get('id', 'WikiStart')

        me = TracObject.factory(self.env, type, id)

        def link_to_dict(type, id, facet, context, time, author, relation):
            obj = TracObject.factory(self.env, type, id)
            return {'type': type,
                    'id': escape(id), 
                    'fqname': obj.fqname(),
                    'shortname': obj.shortname(),
                    'htmlclass': obj.htmlclass(),
                    'href': obj.href(),
                    'facet': facet,
                    'context': context,
                    'time': time,
                    'age': pretty_timedelta(time),
                    'author': author or 'anonymous',
                    'relation': relation
                    }

        req.hdf['title'] = 'Backlinks for %s' % me.shortname()
        req.hdf['xref.me'] = {
            'fqname': me.fqname(),
            'shortname': me.shortname(),
            'htmlclass': me.htmlclass(),
            'href': me.href(),
            }
        req.hdf['xref.href'] = self.env.href.xref(type, id)

        db = self.env.get_db_cnx()

        # -- find backlinks and incoming relations
        backlinks = []
        relations_in = []
        for tuple in me.find_backlinks(db):
            dict = link_to_dict(*tuple)
            if dict['relation']:
                relations_in.append(dict)
            else:
                backlinks.append(dict)
        backlinks.sort(lambda x,y: cmp(y['time'], x['time']))
        req.hdf['xref.backlinks'] = backlinks
        relations_in.sort(lambda x,y: cmp(y['time'], x['time']))
        req.hdf['xref.relations.in'] = relations_in

        # -- find outgoing relations 
        relations_out = []
        for tuple in me.find_links(db, relation=True):
            relations_out.append(link_to_dict(*tuple))
        relations_out.sort(lambda x,y: cmp(y['time'], x['time']))
        req.hdf['xref.relations.out'] = relations_out

        add_stylesheet(req, 'css/timeline.css')
        return 'xref.cs', None


# -- Macros (focus on WikiPage objects)

class BacklinksMacro(Component):
    """Inline a list of backlinks to the current object."""
    
    implements(IWikiMacroProvider)

    def get_macros(self):
        yield 'Backlinks'

    def get_macro_description(self, name):
        return inspect.getdoc(BacklinksMacro)

    def render_macro(self, req, source, facet, name, content):
        db = self.env.get_db_cnx()
        buf = StringIO()
        first = True
        for backlink in source.find_backlinks(db):
            dst_type,dst_id,facet,context,time,author,relation = backlink
            if not first:
                buf.write(', ')
            else:
                first = False
            dst = TracObject.factory(self.env, dst_type, dst_id)
            buf.write('<a class="%s" href="%s">%s</a>' \
                          % (dst.htmlclass(), dst.href(), dst.shortname()))
        return buf.getvalue()


class OrphanedPagesMacro(Component):
    """List Wiki pages that are not referenced by any another Trac object."""
    
    implements(IWikiMacroProvider)

    def get_macros(self):
        yield 'OrphanedPages'

    def get_macro_description(self, name):
        return inspect.getdoc(OrphanedPagesMacro)

    def render_macro(self, req, source, facet, name, content):
        from trac.wiki.model import WikiPage

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT DISTINCT(name) FROM wiki"
                       " WHERE name NOT IN ("
                       "   SELECT DISTINCT(dest_id) FROM xref"
                       "    WHERE dest_type='wiki'"
                       "      AND (src_type='wiki' AND dest_id!=src_id"
                       "           OR src_type!='wiki'))")
        buf = StringIO()
        first = True
        for id, in cursor:
            if not first:
                buf.write(', ')
            else:
                first = False
            page = WikiPage(self.env, id)
            buf.write('<a class="%s" href="%s">%s</a>' \
                          % (page.htmlclass(), page.href(), page.shortname()))
        return buf.getvalue()


class MissingLinksMacro(Component):
    """List Wiki pages that are referenced but don't exist."""
    
    implements(IWikiMacroProvider)

    def get_macros(self):
        yield 'MissingLinks'

    def get_macro_description(self, name):
        return inspect.getdoc(MissingLinksMacro)

    def render_macro(self, req, source, facet, name, content):
        from trac.wiki.model import WikiPage

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT dest_id,src_type,src_id FROM xref "
                       " WHERE dest_type='wiki' "
                       " AND dest_id NOT IN (SELECT DISTINCT(name) FROM wiki) "
                       " ORDER BY dest_id,src_type,src_id ")
        missing = []
        previous_page = None
        previous_src = None
        for page,src_type,src_id in cursor:
            src = (src_type, src_id)
            if page != previous_page:
                missing.append((WikiPage(self.env, page),[src]))
                previous_page = page
            else:
                if src != previous_src:
                    missing[-1][1].append(src)
            previous_src = src

        buf = StringIO()
        buf.write('<dl>')
        def format_link(obj, missing=None): # FIXME: method of TracObject?
            return ('<a class="%s%s" href="%s">%s</a>' %
                    (missing and 'missing ' or '', obj.htmlclass(),
                     obj.href(), obj.shortname()))
        for page,refs in missing:
            buf.write('<dt>%s, referenced in:<dt>' \
                      % format_link(page, missing=True))
            buf.write('<dd>')
            first = True
            for type, id in refs:
                if not first:
                    buf.write(', ')
                else:
                    first = False
                buf.write(format_link(TracObject.factory(self.env, type, id)))
            buf.write('</dd>')
        buf.write('</dl>')
        return buf.getvalue()

