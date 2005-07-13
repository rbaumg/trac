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
   * Source `?`
     * (no facet, only as a target)

  A cross-reference is also called a relation if a specific semantic is
  attached to the link from the source object to the destination object
  (stored in the `relation` field).
  If the `relation` is unset, the cross-reference semantic can be inferred
  from the `context` (usually the Wiki text in which the link was created).

"""


from trac.core import *
from trac.object import TracObject, ITracObjectManager
from trac.wiki.formatter import Formatter
from trac.wiki.api import WikiSystem
from trac.web.main import IRequestHandler
from trac.web.chrome import add_stylesheet
from trac.util import escape, TracError, pretty_timedelta

__all__ = ['XRefSystem', 'Facet']



class Facet(object):
    """
    A facet encapsulates the context in which link information,
    in the form of a reference written in a Wiki text,
    is entered in the system.

    A facet is not (yet?) directly persistent, but rather composed of
    data attached to other objects.
    """
    
    def __init__(self, src, name, time, author):
        self.src = src
        self.name = name
        self.author = author
        self.time = time

    def add_xref(self, db, dest, context=None, relation=None):
        """
        Add a new cross-reference from this facet to the given `target`,
        annotating it with the given `context`.
        """
        print ("+ %s:%s --[%s]--> %s:%s" % (self.src.type, self.src.id, 
                                            relation,
                                            dest.type, dest.id) +
               " (in %s at %s by %s %s)" % (self.name, self.time, self.author,
                                            context))
        cursor = db.cursor()
        cursor.execute("INSERT INTO xref VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                       (self.src.type, self.src.id,
                        self.name, context, self.time, self.author,
                        relation, dest.type, dest.id))

    def update_relation(self, db, relation, dest, context=None):
        """
        Delete any outgoing `relation` and recreate it.
        The `facet` and `context` are only used to recreate the new relation.
        """
        if not relation:
            raise TracError, 'No relation specified'
        self.delete_links(db, relation) # ?
        self.add_xref(db, relation, dest, context)

    def update_links(self, db, wikitext, relation=None):
        """
        The facet's content has changed and the corresponding cross-references
        must be updated.
        A default `relation` can be given, which will be added for all
        the implicit links found in `wikitext`. *** FIXME
        """
        self.delete_links(db)
        self._parse(wikitext)
#        self._parse(wikitext.replace('\n', ' '))

    def _parse(self, wikitext, relation=None, xf=None): # FIXME integrate in the above?
        if not xf:
            xf = XRefParser(env, db, relation=relation)
        xf.parse(self, wikitext)

    def delete_links(self, db):
        """
        Remove all the cross-references originating from this facet.
        """
        print ("- -- %s:%s --[*]--> *:*" % (self.src.type, self.src.id) +
               " (in %s at %s by %s)" % (self.name, self.time, self.author))
        cursor = db.cursor()
        cursor.execute("DELETE FROM xref"
                       " WHERE src_type=%s AND src_id=%s"
                       "   AND facet=%s", (self.src.type, self.src.id, self.name))


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

    def parse(self, facet, text):
        self.facet = facet
        class NullOut:
            def write(self,*args): pass
        self.format(text, NullOut())

    # Reimplemented methods and helpers
    
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
                    self.facet.add_xref(self.db, target,
                                        self._extract_context(fullmatch))
                    
    def _make_link(self, ns, target, match, label):
        wiki = WikiSystem(self.env)
        # check first for an alias defined in trac.ini
        ns = self.env.config.get('intertrac', ns.upper(), ns)
        if ns in wiki.xref_link_resolvers:
            return wiki.xref_link_resolvers[ns](self, ns, target, label)

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



class XRefSystem(Component):

    object_managers = ExtensionPoint(ITracObjectManager)

    def __init__(self):
        self._object_factories = None

    def rebuild_xrefs(self, db, do_changesets=True):
        """
        Rebuild all cross-references in the given environment.

        As an option, the rebuilding of the references found in
        changesets can be skipped, as this is done by a 'resync'
        operation, which is what is advised to do in trac-admin.
        """
        xf = XRefParser(self.env, db)
        for mgr in self.object_managers:
            for facet, text in mgr.rebuild_xrefs(db):
                facet.delete_links(db)
                xf.parse(facet, text)
        db.commit()

    def _get_object_factories(self):
        if not self._object_factories:
            self._object_factories = {}
            for mgr in self.object_managers:
                for type, fn in mgr.get_object_types():
                    self._object_factories[type] = fn
        return self._object_factories
    object_factories = property(_get_object_factories)



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

        xref = XRefSystem(self.env)
        me = xref.object_factories[type](id)

        def link_to_dict(type, id, facet, context, time, author, relation):
            obj = xref.object_factories[type](id)
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
