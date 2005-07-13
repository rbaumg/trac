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


from trac.core import *
from trac.util import escape

__all__ = ['TracObject']


class ITracObjectManager(Interface):

    def get_object_types():
        """
        Return pair of managed object type and its corresponding
        factory method: a method taking an `id` argument, returning
        the TracObject of the appropriate subclass, with the given `id`.
        """

    def rebuild_xrefs():
        """
        Clear and re-create all the cross-references originating
        from the objects controlled by this Object Manager.
        """


class TracObject:
    """
    A TracObject encapsulate the identity of a Trac Object
    (changeset, wiki page, ticket, ...) and can be used to perform
    generic tasks on those objects:
     * manage the relationships to other Trac Objects
     * handle custom fields (future)

    Note: `type` __must__ be a static class member.
    """

    def __init__(self, env, id):
        self.env = env
        self.id = id

    def fqname(self):
        """Return the fully qualified Trac Wiki Link for that object"""
        return '%s:%s' % (self.type, escape(self.id))

    def shortname(self):
        """Return the shorthand Trac Wiki Link for that object"""
        return self.fqname()

    def htmlclass(self):
        """Return the relevant HTML class attribute for that object"""
        return self.type

    def href(self, *args, **kw):
        """Return the href for that object"""
        return self.env.href(self.type, self.id, *args, **kw)

    # Counting cross-references
    
    def xref_count_to_hdf(self, req, db):
        """Setup the HDF with the count of backlinks and relations"""
        req.hdf['xref.count'] = {
            'backlinks': self.count_backlinks(db, relation=False),
            'all': self.count_backlinks(db) + self.count_links(db,
                                                               relation=True)
            } 

    # TODO: disguard the facet argument?
    
    def count_backlinks(self, db, relation=None, facet=None):
        """Count how many backlinks point to this object."""
        return self._xref_count('dest', db, relation, facet)

    def count_links(self, db, relation=None, facet=None):
        """Count how many links orginate from this object"""
        return self._xref_count('src', db, relation, facet)

    def find_backlinks(self, db, relation=None, facet=None):
        """Retrieve all the links pointing to this object.
        
        If `relation` is given, only the links having this semantic
        are retrieved.
        """
        return self._xref_find('dest', 'src', db, relation, facet)

    def find_links(self, db, relation=None, facet=None):
        """Retrieve all the outgoing relationships for this object.
        
        If `relation` is given, only the links having this semantic
        are retrieved.
        """
        return self._xref_find('src', 'dest', db, relation, facet)

    def has_relation(self, db, relation, other=None):
        """e.g. obj.has_relation('is-a', component)"""
        other_clause = ''
        tuple = (self.type, self.id, relation)
        if other:
            other_clause = " AND dest_type=%s AND dest_id=%s"
            tuple += (other.type, other.id)
        cursor = db.cursor()
        cursor.execute("SELECT count(*) FROM xref "
                       " WHERE src_type=%s AND src_id=%s"
                       "   AND relation=%s " + other_clause, tuple)
        return cursor.fetchone()[0]

    def delete_links(self, db, relation=None): ### FIXME: keep it at all?
        cursor = db.cursor()
        tuple = (self.type, self.id)
        tuple, relation_clause = self._relation_clause(tuple, relation)
        cursor.execute("DELETE FROM xref"
                       " WHERE src_type=%s AND src_id=%s" + relation_clause,
                       tuple)
        print "- -- %s:%s --[%s]--> *:*" % (self.type, self.id, relation)
    
    ## XRef helper methods

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
            relation_clause = " AND relation=''"
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

