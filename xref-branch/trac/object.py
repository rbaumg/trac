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


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


from trac.core import *
from trac.util import escape

__all__ = ['TracObject', 'TracObjectSystem']



class TracObject:
    """A TracObject encapsulate the identity of a Trac Object.
    
    It can be a changeset, a wiki page, a ticket, etc.

    The methods at the TracObject level can be used to perform
    generic tasks on the object, which usually won't depend
    on the actual content of the object, but rather on its
    `type` and `id`-entity:
     * manage the relationships to other Trac Objects
     * handle custom fields (future)
    Therefore, the `factory` method produces objects that are not
    fully loaded, as this would introduces an extra cost which is not
    usually worth it.

    But the methods at the sub-class level usually require that the
    Trac Object is fully loaded. Therefore, if the object was obtained
    by the `factory` method, the `reload()` method must be called first.

    When a Trac Object is directly created using the sub-class
    constructor, the `id` is usually set, and the object is the loaded.
    However,  in some cases, the id ''might'' not be set
    (e.g. while creating a new object).
    In that case, most of the TracObject methods won't produce a
    meaningful result.
    """

    def _factory(cls, env, type, id):
        return TracObjectSystem(env).object_factory(type, id)
    factory = classmethod(_factory)

    def __init__(self, env, id=None):
        self.env = env
        self.id = id

    def setid(self, id):
        """Identity change. Usually reimplemented."""
        self.id = id
        return self

    def reload(self):
        """Load additional object data. Usually reimplemented"""
        pass

    # -- Generic methods

    def fqname(self):
        """Return the fully qualified Trac Wiki Link for that object"""
        return '%s:%s' % (self.type, escape(self.id))

    def shortname(self):
        """Return the shorthand Trac Wiki Link for that object"""
        return escape(self.id)

    def displayname(self):
        """Return an explicit designation of the object"""
        return escape(self.id)

    def htmlclass(self):
        """Return the relevant HTML class attribute for that object"""
        return self.type

    def href(self, *args, **kw):
        """Return the href for that object"""
        return self.env.href(self.type, self.id, *args, **kw)

    def get_facet(self, facet, db=None):
        """Return the Wiki content of the given `facet`"""
        return ''

    # -- -- Wiki formatting methods

    def wiki_to_html(self, facet, wikitext, req,
                     db=None, absurls=0, escape_newlines=False):
        from trac.wiki.formatter import Formatter
        out = StringIO()
        Formatter(self.env, req, absurls, db).format(self, facet, wikitext,
                                                     out, escape_newlines)
        return out.getvalue()
                  
    def wiki_to_oneliner(self, facet, wikitext,
                         db=None, absurls=0):
        from trac.wiki.formatter import OneLinerFormatter
        out = StringIO()
        OneLinerFormatter(self.env, absurls, db).format(self, facet, wikitext,
                                                        out)
        return out.getvalue()

    def wiki_to_outline(self, facet, wikitext,
                        db=None, absurls=0, max_depth=None, min_depth=None):
        from trac.wiki.formatter import OutlineFormatter
        out = StringIO()
        OutlineFormatter(self.env, absurls, db).format(self, facet, wikitext,
                                                       out, max_depth, min_depth)
        return out.getvalue()

    # -- -- Cross-references related methods
    
    def xref_count_to_hdf(self, req, db):
        """Setup the HDF with the count of backlinks and relations"""
        req.hdf['xref.count'] = {
            'backlinks': self.count_backlinks(db, relation=False),
            'relations': (self.count_backlinks(db, relation=True) +
                          self.count_links(db, relation=True))
            } 

    # TODO: disguard the facet argument?
    
    def count_backlinks(self, db, relation=None, facet=None):
        """Count how many backlinks point to this object."""
        return self._xref_count('target', db, relation, facet)

    def count_links(self, db, relation=None, facet=None):
        """Count how many links orginate from this object"""
        return self._xref_count('source', db, relation, facet)

    def find_backlinks(self, db, relation=None, facet=None):
        """Retrieve all the links pointing to this object.
        
        If `relation` is given, only the links having this semantic
        are retrieved.
        """
        return self._xref_find('target', 'source', db, relation, facet)

    def find_links(self, db, relation=None, facet=None):
        """Retrieve all the outgoing relationships for this object.
        
        If `relation` is given, only the links having this semantic
        are retrieved.
        """
        return self._xref_find('source', 'target', db, relation, facet)

    def has_relation(self, db, relation, other=None):
        """e.g. obj.has_relation('is-a', component)"""
        other_clause = ''
        tuple = (self.type, self.id, relation)
        if other:
            other_clause = " AND target_type=%s AND target_id=%s"
            tuple += (other.type, other.id)
        cursor = db.cursor()
        cursor.execute("SELECT count(*) FROM xref "
                       " WHERE source_type=%s AND source_id=%s"
                       "   AND relation=%s " + other_clause, tuple)
        return cursor.fetchone()[0]

    def create_xref(self, db, facet, time, author, target, context,
                    relation=None):
        """
        Create a cross-reference from this object to the given `target` object.
        """
        #print ("(+) %s:%s --[%s]--> %s:%s" % (self.type, self.id, relation,
        #                                      target.type, target.id) +
        #       " (in %s at %s by %s %s)" % (facet, time, author, context))
        cursor = db.cursor()
        cursor.execute("INSERT INTO xref VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                       (self.type, self.id, facet, context, time, author,
                        relation, target.type, target.id))

    def update_links(self, db, facet, time, author, wikitext, relation=None):
        """
        Update the cross-references originating from this object,
        in the specified `facet` containing the given `wikitext`.
        An optional `relation` can be given, which will be used for all
        links created.
        """
        from trac.xref import XRefParser
        if not wikitext:
            return
        old_xrefs = {}
        cursor = db.cursor()
        cursor.execute("SELECT target_type, target_id, context, relation, "
                       "       time, author FROM xref "
                       " WHERE source_type=%s AND source_id=%s AND facet=%s",
                       (self.type, self.id, facet))
        for t_type,t_id,context,rel,old_time,old_author in cursor:
            old_xrefs[(t_type,t_id,context,rel)] = (old_time, old_author)
        self.delete_links(db, facet=facet)
        new_xrefs = XRefParser(self.env, db).parse(self, facet, wikitext)
        for target, context, relname in new_xrefs:
            relname = relname or relation
            key = (target.type, target.id, context, relname)
            if old_xrefs.has_key(key):
                t, a = old_xrefs[key]
            else:
                t, a = time, author
            self.create_xref(db, facet, t, a, target, context, relname)

    def delete_links(self, db, relation=None, facet=None):
        cursor = db.cursor()
        tuple = (self.type, self.id)
        tuple, relation_clause = self._relation_clause(tuple, relation)
        tuple, facet_clause = self._facet_clause(tuple, facet)
        cursor.execute("DELETE FROM xref"
                       " WHERE source_type=%s AND source_id=%s"
                       + relation_clause + facet_clause,
                       tuple)
        #print "(-) -- %s:%s --[%s]--> *:*" % (self.type, self.id, relation)
    
    ## -- Helper methods

    def _relation_clause(self, tuple, relation):
        """
        `relation` maybe None, in which case all cross-references
        are taken into account.
        If it's True, then only the relations are considered.
        If it's False, then only the backlinks are considered.
        If it has a defined value, only those relations are used.
        """
        relation_clause = ''
        if relation == True:
            relation_clause = " AND relation!=''"
        elif relation == False:
            relation_clause = " AND COALESCE(relation,'')=''"
        elif relation:
            relation_clause = " AND relation=%s"
            tuple += (relation,)
        return tuple, relation_clause
        
    def _facet_clause(self, tuple, facet):
        """
        If `facet` is given, only consider links ''originating'' from this
        type of facet.
        """
        facet_clause = ''
        if facet:
            facet_clause = " AND facet=%s"
            tuple += (facet,)
        return tuple, facet_clause

    def _xref_count(self, me, db, relation=None, facet=None):
        cursor = db.cursor()
        tuple = (self.type, self.id)
        tuple, relation_clause = self._relation_clause(tuple, relation)
        tuple, facet_clause = self._facet_clause(tuple, facet)
        cursor.execute("SELECT count(*) FROM xref"
                       " WHERE %(me)s_type=%%s AND %(me)s_id=%%s" \
                       % {'me':me} + relation_clause + facet_clause,
                       tuple)
        return cursor.fetchone()[0]

    def _xref_find(self, me, other, db, relation, facet):
        cursor = db.cursor()
        relation_clause = facet_clause = ''
        tuple = (self.type, self.id)
        tuple, relation_clause = self._relation_clause(tuple, relation)
        tuple, facet_clause = self._facet_clause(tuple, facet)
        cursor.execute("SELECT %(other)s_type,%(other)s_id,"
                       "       facet,context,time,author,relation FROM xref"
                       " WHERE %(me)s_type=%%s AND %(me)s_id=%%s" \
                       % { 'me':me, 'other':other }
                       + relation_clause + facet_clause, tuple)
        return cursor



class ITracObjectManager(Interface):

    def get_object_types():
        """Generator that yield a type and the corresponding factory method

        A factory method is a method which takes an `id` argument
        and returns an '''unloaded''' instance of the appropriate
        subclass of TracObject which has this `id`.
        """

    def rebuild_xrefs():
        """
        Generator that yields (source, facet, time, author, wikitext) tuples,
        one for each facet of each object controlled by this Object Manager.
        """



class TracObjectSystem(Component):

    object_managers = ExtensionPoint(ITracObjectManager)

    def __init__(self):
        self._object_factories = None

    def rebuild_xrefs(self, db, do_changesets=True):
        """Rebuild all cross-references in the given environment.

        As an option, the rebuilding of the references found in
        changesets can be skipped, as this is done by a `resync`
        operation, which is what is advised to do in `trac-admin`.
        """
        for mgr in self.object_managers:
            for source, facet, time, author, wikitext in mgr.rebuild_xrefs(db):
                source.update_links(db, facet, time, author, wikitext)
        db.commit()

    def _get_object_factories(self):
        if not self._object_factories:
            self._object_factories = {}
            for mgr in self.object_managers:
                for type, fn in mgr.get_object_types():
                    self._object_factories[type] = fn
        return self._object_factories

    def object_factory(self, type, id):
        """Create a Trac Object of the given `type`, with the given `id`.

        The Trac Object will __not__ be preloaded.
        For the custom methods to work, an explicit call to `load()`
        is still necessary.
        """
        return self._get_object_factories()[type](id)
