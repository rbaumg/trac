# -*- coding: iso8859-1 -*-
"""
Lists Wiki pages that are referenced but not yet created
"""

from StringIO import StringIO

from trac.Wiki import WikiPage
from trac.Xref import object_factory


def execute(hdf, args, env):
    buf = StringIO()
    db = env.get_db_cnx()

    cursor = db.cursor()
    cursor.execute("SELECT src_type, src_id, dest_id FROM xref"
                   " WHERE dest_type = 'wiki' "
                   "   AND dest_id NOT IN (SELECT DISTINCT(name) FROM wiki)"
                   " ORDER BY dest_id")
    broken_links = {}
    previous_dest_id = None
    for src_type, src_id, dest_id in cursor:
        if dest_id != previous_dest_id:
            broken_links[dest_id] = []
            previous_dest_id = dest_id
        broken_links[dest_id].append(object_factory(env, src_type, src_id))
        
    buf.write('<dl>')
    sorted_keys = broken_links.keys()
    sorted_keys.sort()
    for dest_id in sorted_keys:
        dest = WikiPage(env, dest_id)
        buf.write('<dt><a class="missing wiki" href=%s>%s?</a></dt>' % (dest.href(), dest.name()))
        buf.write('<dd>')
        for src in broken_links[dest_id]:
            buf.write('<a class="%s" href="%s">%s</a> ' % (src.icon(), src.href(), src.name()))
        buf.write('</dd>')
    buf.write('</dl>')

    return buf.getvalue()
