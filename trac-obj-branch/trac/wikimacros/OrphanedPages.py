# -*- coding: iso8859-1 -*-
"""
Lists Wiki pages that are not referenced by another Trac object.
"""

from StringIO import StringIO

from trac.Wiki import WikiPage


def execute(hdf, args, env):
    buf = StringIO()
    db = env.get_db_cnx()

    cursor = db.cursor()
    cursor.execute("SELECT DISTINCT(name) FROM wiki "
                   "WHERE name NOT IN (SELECT DISTINCT(dest_id) FROM xref WHERE dest_type = 'wiki' "
                   "                   AND ( src_type = 'wiki' AND dest_id != src_id OR src_type != 'wiki' ) )")
    orphans = []
    for id, in cursor:
        orphans.append(WikiPage(env, id))
        
    first = 1
    for obj in orphans:
        if not first:
            buf.write(', ')
        else:
            first = 0
        buf.write('<a class="%s" href="%s">%s</a>' % (obj.icon(), obj.href(), obj.name()))

    return buf.getvalue()
