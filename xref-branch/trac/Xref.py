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

  This module implements a general cross-reference facility for Trac,
  as suggested in #1242.

  Currently, cross-references between the following Trac objects are supported:
   * Wiki page
   * Ticket
   * Changeset
   * Report
   * Milestone
   * Source (only as targets for now)

  Basically, two kinds of references are supported:
   * ''implicit references between objects''
     Implicit references are created for every TracLinks that can be found
     in (any of) the wiki text of a Trac object.
     Indeed, some objects may have separately editable wiki texts,
     each of them being a ''facet'' of this object.
     (TODO: generic fine grained anchoring: <object href>#<facet> should go to the facet)
   * ''explicit relation between objects''
     An explicit relation must be created explicitely as such,
     by some programmatic mean.
     Currently, some of the ticket fields are setting up explicit relationships.

   Note that implicit references always have an empty 'relation',
   whereas explicit references may use the 'facet' for informative purpose.

"""


from trac.Module import Module
from trac.util import escape
from trac.WikiFormatter import XRefFormatter

__all__ = ['TracObj', 'rebuild_cross_references']


how_much_context = 40


class TracObj:
    """
    A TracObj encapsulate the identity of a Trac Object
    (changeset, wiki page, ticket, ...) and can be used to perform
    generic tasks on those objects:
     * manage the relationships to other Trac Objects
     * handle custom fields
     * handle facets editing and anchoring

    The cross-reference information is stored in the XREF table
    (see trac/db_default.py).
    
    Besides the obvious 'type' and 'id' information for the source and the
    destination objects, there is also:
     * facet: the location of the cross-reference within the source object.
     * context: the wikitext surrounding the cross-reference, if any
     * relation: the explicit nature of the relationship.
    """

    def __init__(self, type, id):
        self.type = type
        self.id   = id
        if type == 'source':            # TODO: oo-ify
            self.id = id.strip('/')

    def name(self):
        if self.type == 'wiki':         # TODO: oo-ify
            # TODO: use canonical name if it doesn't follow the WikiPageNames conventions
            return escape(self.id)
        elif self.type == 'ticket':
            return 'Ticket #%s' % self.id
        elif self.type == 'changeset':
            return 'Changeset [%s]' % self.id
        elif self.type == 'report':
            return 'Report {%s}' % self.id
        else:
            return self.type + ':' + escape(self.id)

    def icon(self):
        if self.type == 'ticket':       # TODO: oo-ify
            return 'newticket'
        else:
            return self.type

    def href(self, env):
        m = getattr(env.href, self.type)
        if m:
            return m(self.id)
        else:
            return env.href.wiki()

    # -- used by other Modules

    def add_backlinks(self, db, req):
        req.hdf['xref_count'] = self.count_sources(db)

    def replace_relation(self, db, relation, dest, facet='', context=''):
        """
        Replace the related object for the given 'relation'.
        The 'facet' and 'context' are only used to recreate the new relation.
        Best suited for 1 to 1 relationships.
        """
        print "- %s:%s --[%s]--> *:*" % (self.type, self.id, relation)
        cursor = db.cursor()
        cursor.execute("DELETE FROM xref "
                       "WHERE src_id = %s AND src_type = %s "
                       "AND relation = %s ",
                       (self.id, self.type, relation))
        self.insert_xref(db, relation, dest, facet, context)

    def replace_xrefs_from_wiki(self, env, db, facet, wikitext):
        """
        Remove then re-create the cross-references for the given facet.
        """
        self.delete_xrefs(db, facet)
        self._create_xrefs_from_wiki(env, db, facet, wikitext)


    def _create_xrefs_from_wiki(self, env, db, facet, wikitext):
        """
        Parse the given 'wikitext' in order to generate all the cross-reference.
        It is assumed that self is the source object for these references.
        """
        XRefFormatter(env, db, False).format(wikitext, self, facet)

    def delete_xrefs(self, db, facet=None):
        """
        Remove all the cross-references having this reference as a source.
        Only delete the cross-references for the 'facet', if given.
        """
        cursor = db.cursor()
        if facet:
            facet_clause = "AND facet = %s"
            tuple = (self.id, self.type, facet)
            print "- %s:%s --[*]--> *:* (in %s)" % (self.type, self.id, facet)
        else:
            facet_clause = ""
            tuple = (self.id, self.type)
            print "- %s:%s --[*]--> *:*" % (self.type, self.id)
        cursor.execute("DELETE FROM xref "
                       "WHERE src_id = %s AND src_type = %s " + facet_clause,
                       tuple)


    def count_sources(self, db):
        return self._count(db, 'dest')

    def count_destinations(self, db):
        return self._count(db, 'src')

    def _count(self, db, base):
        cursor = db.cursor()
        cursor.execute("SELECT count(*) FROM xref "
                       "WHERE <base>_id = %s AND <base>_type = %s ".replace('<base>', base),
                       (self.id, self.type))
        return cursor.fetchone()[0]


    def find_sources(self, db, relation=None):
        """
        Retrieve all the incoming relationships for this object.
        If 'relation' is given, only the sources for the given relation
        are retrieved, otherwise all relations are searched, even implicit ones.
        """
        return self._find(db, 'dest', 'src', relation)

    def find_destinations(self, db, relation=None):
        """
        Retrieve all the outgoing relationships for this object.
        If 'relation' is given, only the targets for the given relation
        are retrieved, otherwise all relations are searched, even implicit ones.
        """
        return self._find(db, 'src', 'dest', relation)

    def _find(self, db, base, other, relation):
        cursor = db.cursor()
        if relation:
            relation_clause = "AND relation = %s"
            tuple = (self.id, self.type, relation)
        else:
            relation_clause = ""
            tuple = (self.id, self.type)
        cursor.execute(("SELECT <other>_type, <other>_id, relation, facet, context "
                        "FROM xref WHERE <base>_id = %s AND <base>_type = %s "
                        ).replace('<base>', base).replace('<other>', other) + relation_clause,
                       tuple)
        return cursor

    # -- used by the WikiFormatter.XRefFormatter:
    
    def insert_xref(self, db, relation, dest, facet, context):
        print "+ %s:%s --[%s]--> %s:%s (in %s %s)" % (self.type, self.id, 
                                                      relation,
                                                      dest.type, dest.id,
                                                      facet, context)
        cursor = db.cursor()
        cursor.execute("INSERT INTO xref VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       (self.type, self.id, relation, dest.type, dest.id, facet, context))

    def extract_context(self, text, start, end):
        start_ellipsis = end_ellipsis = '...'
        start = start - how_much_context
        if start < 0:
            start = 0
            start_ellipsis = ''
        end = end + how_much_context
        if end > len(text):
            end = len(text)
            end_ellipsis = ''
        return start_ellipsis + text[start:end] + end_ellipsis





def rebuild_cross_references(env, db, do_changesets=True):
    """
    Rebuild all cross-references in the given environment.

    As an option, the rebuilding of the references found in
    changesets can be skipped, as this is done by a 'resync'
    operation, which is what is advised to do in trac-admin.
    """
    cursor  = db.cursor()
    xreffmt = XRefFormatter(env, db, False)

    def add_xrefs(src, facet, text):
        xreffmt.format(text, src, facet)

    # -- wiki objects
    cursor.execute("SELECT name, text, comment, version FROM wiki "
                   "ORDER BY name, version DESC")
    previous_page = None
    src = None
    for name, text, comment, version in cursor:
        if name != previous_page:
            previous_page = name
            src = TracObj('wiki', name)
            src.delete_xrefs(db)
            add_xrefs(src, 'content', text)
        add_xrefs(src, 'comment:%d' % version, comment)

    # -- ticket objects
    # -- -- description
    cursor.execute("SELECT id, description FROM ticket")
    for id, description in cursor:
        src = TracObj('ticket', id)
        src.delete_xrefs(db)
        add_xrefs(src, 'description', description)
        # -- -- comments
        comment_cursor = db.cursor()
        comment_cursor.execute("SELECT oldvalue, newvalue FROM ticket_change "
                               "WHERE ticket = %s AND field = 'comment'",
                               (id))
        for n, value in comment_cursor:
            add_xrefs(src, 'comment:%s' % n, value)
        # -- -- custom fields
        # (uncomment when the custom fields will support wiki formatting)
        # ... "SELECT name, value FROM ticket_custom"

    # -- changeset objects
    if do_changesets:
        cursor.execute("SELECT rev, message FROM revision")
        for rev, message in cursor:
            src = TracObj('changeset', rev)
            src.delete_xrefs(db)
            add_xrefs(src, 'content', message)

    # -- report objects
    cursor.execute("SELECT id, description FROM report")
    for id, description in cursor:
        src = TracObj('report', id)
        src.delete_xrefs(db)
        add_xrefs(src, 'description', description)

    # -- milestone objects
    cursor.execute("SELECT name, description FROM milestone")
    for name, description in cursor:
        src = TracObj('milestone', name)
        src.delete_xrefs(db)
        add_xrefs(src, 'description', description)

    # -- attachment object
    cursor.execute("SELECT type, id, description, filename FROM attachment")
    for type, id, description, filename in cursor:
        add_xrefs(TracObj(type, id), 'attachment:%s' % filename, description)

    db.commit()




def find_orphaned_objects(db):
    # Most interesting 'orphans' order: wikis, tickets, milestones then reports and changesets
    queries = [
        "SELECT DISTINCT(name), 'wiki' FROM wiki "
        "WHERE name NOT IN (SELECT DISTINCT(dest_id) FROM xref WHERE dest_type = 'wiki') "
        ,
        "SELECT id, 'ticket' FROM ticket "
        "WHERE id NOT IN (SELECT DISTINCT(dest_id) FROM xref WHERE dest_type = 'ticket') "
        ,
        "SELECT name, 'milestone' FROM milestone "
        "WHERE name NOT IN (SELECT DISTINCT(dest_id) FROM xref WHERE dest_type = 'milestone') "
        ,
        "SELECT id, 'report' FROM report "
        "WHERE id NOT IN (SELECT DISTINCT(dest_id) FROM xref WHERE dest_type = 'report') "
        , 
        "SELECT rev, 'changeset' FROM revision "
        "WHERE rev NOT IN (SELECT DISTINCT(dest_id) FROM xref WHERE dest_type = 'changeset') "
        ,
        # Not sure about this one: it works, but produces a huge list (good for testing, though :)
        # "SELECT DISTINCT(name), 'source' FROM node_change "
        # "WHERE name NOT IN (SELECT DISTINCT(dest_id) FROM xref WHERE dest_type = 'source') "
        ]
    cursor = db.cursor()
    cursor.execute(" UNION ALL ".join(queries))
    return cursor




class XrefModule(Module):
    template_name = 'xref.cs'

    def render(self, req):
        mode = req.args.get('mode', 'xref')
        req.hdf['xref.mode'] = mode
        if mode == 'orphans':
            self._orphans(req)
            self.template_name = 'orphans.cs'
        else:
            direction = req.args.get('direction','back')
            if direction == 'forward':
                req.hdf['xref.direction.name'] = 'Forward Link'
                base = self._base(req)
                self._references(req, base.find_destinations(self.db))
            else: # direction == back
                req.hdf['xref.direction.back'] = 1
                req.hdf['xref.direction.name'] = 'Backlink'
                base = self._base(req)
                self._references(req, base.find_sources(self.db))

    def _base(self, req):
        type = req.args.get('type', 'wiki')
        id = req.args.get('id', 'WikiStart')
        base = TracObj(type, id)
        req.hdf['title'] = req.hdf['xref.direction.name'] + ' for ' + base.name()
        req.hdf['xref.base.type'] = type
        req.hdf['xref.base.id'] = escape(id)
        req.hdf['xref.base.name'] = base.name()
        req.hdf['xref.base.icon'] = base.icon()
        req.hdf['xref.base.href'] = base.href(self.env)
        req.hdf['xref.current_href'] = escape(self.env.href.xref(type, id))
        return base

    def _references(self, req, refs):
        links = []
        relations = []
        for type, id, relation, facet, context in refs:
            other_ref = TracObj(type, id)
            dict = {'type' : type,
                    'id' : id,
                    'name' : other_ref.name(),
                    'icon' : other_ref.icon(),
                    'href' : other_ref.href(self.env),
                    'relation' : relation,
                    'facet' : facet,
                    'context' : context}
            if relation:
                relations.append(dict)
            else:
                links.append(dict)
        req.hdf['xref.links'] = links
        req.hdf['xref.relations'] = relations

    def _orphans(self, req):
        req.hdf['title'] = 'Orphaned objects'
        orphans = []
        for id, type in find_orphaned_objects(self.db):
            ref = TracObj(type, id)
            obj = {'type' : type,
                    'id' : id,
                    'name' : ref.name(),
                    'icon' : ref.icon(),
                    'href' : ref.href(self.env)}
            orphans.append(obj)
        req.hdf['orphans'] = orphans
        
