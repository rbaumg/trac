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
   * Wiki page +
   * Ticket +
   * Changeset
   * Report
   * Milestone
   * Source (only as targets for now) +

  Basically, two kinds of references are supported:
   * ''implicit references between objects''
     Implicit references are created for every TracLinks that can be found
     in (any of) the wiki text(s) of a Trac object.
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
from trac.util import escape, TracError
from trac.WikiFormatter import XRefFormatter

__all__ = ['object_factory', 'TracObj', 'rebuild_cross_references', 'get_dag']


how_much_context = 40


objects = {
#    type           (module_name,   class_name)
    'wiki'        : ('Wiki',        'WikiPage'),
    'ticket'      : ('Xref',        'TracObj'),
#   'ticket'      : ('Ticket',      'Ticket'),
    'changeset'   : ('Xref',        'TracObj'),
#   'changeset'   : ('Changeset',   'Changeset'),
    'report'      : ('Xref',        'TracObj'),
#   'report'      : ('Report',      'Report'),
    'milestone'   : ('Xref',        'TracObj'),
#   'milestone'   : ('Milestone',   'Milestone'),
    'source'      : ('Browser',     'Source'),
}

def object_factory(env, type, id):
    module_name, constructor_name = objects[type]
    module = __import__(module_name, globals(),  locals())
    constructor = getattr(module, constructor_name)
    obj = constructor(env, id)
    obj.type = type  # FIXME: should be done by the subclasses
    return obj


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

    def __init__(self, env, id):
        self.env  = env
        self.id   = id
        self.force_relation = '' # FIXME: this should belongs to the XrefFormatter
# FIXME        if type == 'source':            # TODO: oo-ify
#                  self.id = id.strip('/')

    def name(self):
        if self.type == 'ticket':          # TODO: oo-ify
            return 'Ticket #%s' % self.id
        elif self.type == 'changeset':
            return 'Changeset [%s]' % self.id
        elif self.type == 'report':
            return 'Report {%s}' % self.id
        else:
            return self.type + ':' + escape(self.id)

    def shortname(self):
        if self.type == 'ticket':          # TODO: oo-ify
            return '#%s' % self.id
        elif self.type == 'changeset':
            return '[%s]' % self.id
        elif self.type == 'report':
            return '{%s}' % self.id
        else:
            return self.type + ':' + escape(self.id)

    def icon(self):
        return self.type

    def href(self, *args, **kw):
        return self.env.href(self.type, self.id, *args, **kw)

    # -- used by other Modules, for cross-referencing 

    def add_cross_refs(self, db, req):
        req.hdf['xref_nbacklinks'] = self.count_sources(db, relation=False)
        req.hdf['xref_nrelations'] = self.count_sources(db, relation=True) + self.count_destinations(db, relation=True)

    def replace_relation(self, db, relation, dest, facet='', context=''):
        """
        Replace the related object for the given 'relation'.
        The 'facet' and 'context' are only used to recreate the new relation. *** FIXME
        Best suited for 1 to 1 relationships.
        """
        print "- %s:%s --[%s]--> *:*" % (self.type, self.id, relation)
        cursor = db.cursor()
        cursor.execute("DELETE FROM xref "
                       "WHERE src_id = %s AND src_type = %s "
                       "AND relation = %s ",
                       (self.id, self.type, relation))
        self.insert_xref(db, relation, dest, facet, context)

    def replace_xrefs_from_wiki(self, db, facet, wikitext):
        """
        Remove then re-create the cross-references for the given facet.
        """
        self.delete_xrefs(db, facet)
        XRefFormatter(self.env, db, False).format(wikitext, self, facet)

    def replace_xrefs_from_list(self, db, facet, relation, wikitext):
        """
        Remove then re-create the cross-references for the given 'facet',
        forcing 'relation'.
        """
        self.delete_xrefs(db, facet)
        xreffmt = XRefFormatter(self.env, db, False)
        self.force_relation = relation
        xreffmt.format(wikitext.replace('\n', ' '), self, facet)
        self.force_relation = ''

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


    def count_sources(self, db, relation=None, facet=None):
        return self._count(db, 'dest', relation, facet)

    def count_destinations(self, db, relation=None, facet=None):
        return self._count(db, 'src', relation, facet)

    def _count(self, db, base, relation=None, facet=None):
        cursor = db.cursor()
        relation_clause = facet_clause = ""
        tuple = (self.id, self.type)
        if relation == True:
            relation_clause = "AND relation != '' "
        elif relation == False:
            relation_clause = "AND relation = '' "
        elif relation:
            relation_clause = "AND relation = %s "
            tuple += (relation,)
        if facet:
            facet_clause = "AND facet = %s "
            tuple += (facet,)
        cursor.execute(("SELECT count(*) FROM xref "
                        "WHERE <base>_id = %s AND <base>_type = %s "
                        ).replace('<base>', base) + relation_clause + facet_clause,
                       tuple)
        return cursor.fetchone()[0]

    def relation_exist(self, db, relation, other=None):
        if other:
            other_clause = "AND dest_id = %s AND dest_type = %s "
            tuple = (self.id, self.type, relation, other.id, other.type)
        else:
            other_clause = ""
            tuple = (self.id, self.type, relation)
        cursor = db.cursor()
        cursor.execute("SELECT count(*) "
                       "FROM xref WHERE src_id = %s AND src_type = %s "
                       "AND relation = %s " + other_clause,
                       tuple)
        return cursor.fetchone()[0]

    def find_sources(self, db, relation=None, facet=None):
        """
        Retrieve all the incoming relationships for this object.
        If 'relation' is given, only the sources for the given relation
        are retrieved, otherwise all relations are searched, even implicit ones.
        """
        return self._find(db, 'dest', 'src', relation, facet)

    def find_destinations(self, db, relation=None, facet=None):
        """
        Retrieve all the outgoing relationships for this object.
        If 'relation' is given, only the targets for the given relation
        are retrieved, otherwise all relations are searched, even implicit ones.
        """
        return self._find(db, 'src', 'dest', relation, facet)

    def _find(self, db, base, other, relation, facet):
        cursor = db.cursor()
        relation_clause = facet_clause = ""
        tuple = (self.id, self.type)
        if relation == True:
            relation_clause = "AND relation != '' "
        elif relation == False:
            relation_clause = "AND relation = '' "
        elif relation:
            relation_clause = "AND relation = %s "
            tuple += (relation,)
        if facet:
            facet_clause = "AND facet = %s "
            tuple += (facet,)
        cursor.execute(("SELECT <other>_type, <other>_id, relation, facet, context "
                        "FROM xref WHERE <base>_id = %s AND <base>_type = %s "
                        ).replace('<base>', base).replace('<other>', other) + relation_clause + facet_clause,
                       tuple)
        return cursor

    # -- used by the WikiFormatter.XRefFormatter:
    
    def insert_xref(self, db, relation, dest, facet, context):
        if self.force_relation:
            relation = self.force_relation
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
            src = object_factory(env, 'wiki', name)
            src.delete_xrefs(db)
            add_xrefs(src, 'content', text)
        add_xrefs(src, 'comment:%d' % version, comment)

    # -- ticket objects
    # -- -- description
    cursor.execute("SELECT id, description FROM ticket")
    for id, description in cursor:
        src = object_factory(env, 'ticket', id)
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
            src = object_factory(env, 'changeset', rev)
            src.delete_xrefs(db)
            add_xrefs(src, 'content', message)

    # -- report objects
    cursor.execute("SELECT id, description FROM report")
    for id, description in cursor:
        src = object_factory(env, 'report', id)
        src.delete_xrefs(db)
        add_xrefs(src, 'description', description)

    # -- milestone objects
    cursor.execute("SELECT name, description FROM milestone")
    for name, description in cursor:
        src = object_factory(env, 'milestone', name)
        src.delete_xrefs(db)
        add_xrefs(src, 'description', description)

    # -- attachment object
    cursor.execute("SELECT type, id, description, filename FROM attachment")
    for type, id, description, filename in cursor:
        add_xrefs(object_factory(env, type, id), 'attachment:%s' % filename, description)

    db.commit()


class CycleDetected(TracError):
    def __init__(self, seq):
        nameseq = map(lambda (type, id): "%s:%s" % (type, id), flatten_seq(seq))
        TracError.__init__(self, 'Adding relation %s &rarr; %s would create a cycle, '
                           'because of the following relation(s): %s' % \
                           (nameseq[0], nameseq[1], "  &rarr; ".join(nameseq[1:])),
                           'Cycle Detected')

def flatten_seq(seq):
    list = []
    def flatten_req((seq,elt)):
        if seq:
            flatten_req(seq)
        list.append(elt)
    flatten_req(seq)
    return list
        
def get_dag(db, start_ref, relation):
    already_visited = {}
    dag = []
    def get_dag_rec(seq):
        elt = seq[1]
        type, id = elt 
        already_visited[elt] = 1
        dag.append(seq)
        cursor = db.cursor()
        cursor.execute("SELECT dest_type, dest_id FROM xref "
                       "WHERE src_id = %s AND src_type = %s AND relation = %s ",
                       (id, type, relation))
        for ntype, nid in cursor:
            elt = (ntype, nid)
            next_seq = (seq, elt)
            if elt == start_ref:
                raise CycleDetected(next_seq)
            if not already_visited.has_key(elt):
                get_dag_rec(next_seq)
    get_dag_rec((None, start_ref))
    return dag
    

class XrefModule(Module):
    template_name = 'xref.cs'

    def render(self, req):
        type = req.args.get('type', 'wiki')
        id = req.args.get('id', 'WikiStart')
        base = object_factory(self.env, type, id)

        def dict_of_related(type, id, relation, facet, context):
            ref = object_factory(self.env, type, id)
            return {'type' : type,
                    'id' : escape(id),
                    'name' : ref.name(),
                    'icon' : ref.icon(),
                    'href' : ref.href(),
                    'relation' : relation,
                    'facet' : facet,
                    'context' : context}

        req.hdf['title'] = 'Backlinks for %s' % base.name()
        req.hdf['xref.base'] = dict_of_related(type, id, '', '', '')
        req.hdf['xref.current_href'] = escape(self.env.href.xref(type, id))

        # -- find backlinks and incoming relations
        links = []
        in_relations = []
        for tuple in base.find_sources(self.db):
            dict = dict_of_related(*tuple)
            if dict['relation']:
                in_relations.append(dict)
            else:
                links.append(dict)
        req.hdf['xref.links'] = links
        req.hdf['xref.in_relations'] = in_relations

        # -- find outgoing relations 
        out_relations = []
        for tuple in base.find_destinations(self.db, relation=True):
            out_relations.append(dict_of_related(*tuple))
        req.hdf['xref.out_relations'] = out_relations

        req.display('xref.cs')
