# -*- coding: iso8859-1 -*-
"""
Lists Wiki pages that are referenced but don't exist.

FIXME: That macro has an additional ''feature'': it shows
       all the ''false positive'' Wiki page names that are identified
       by the XRefFormatter(CommonFormatter) but shouldn't...
       (macros names, wiki page names in URLs, etc.)
"""

from StringIO import StringIO

from trac.Wiki import WikiPage
from trac.Xref import object_factory


def execute(hdf, args, env):
    buf = StringIO()
    db = env.get_db_cnx()

    cursor = db.cursor()
    cursor.execute("SELECT dest_id, src_type, src_id FROM xref "
                   " WHERE dest_type = 'wiki' "
                   " AND dest_id NOT IN (SELECT DISTINCT(name) FROM wiki) "
                   " ORDER BY dest_id, src_type, src_id ")
    missing = []
    previous_page = None
    previous_src = None
    for page,src_type,src_id in cursor:
        src = (src_type, src_id)
        if page != previous_page:
            missing.append((WikiPage(env,page),[src]))
            previous_page = page
        else:
            if src != previous_src:
                missing[-1][1].append(src)
        previous_src = src
                
    first = 1
    buf.write('<dl>')
    def simple_link(obj):
        return ('<a class="%s" href="%s">%s</a>' %
                (obj.icon(), obj.href(), obj.name()))
    def simple_missing_link(obj): # FIXME: simple_link should be enough
        return ('<a class="missing %s" href="%s">%s?</a>' %
                (obj.icon(), obj.href(), obj.name()))
    for page,refs in missing:
        buf.write('<dt>%s<dt>' % simple_missing_link(page))
        objs = [object_factory(env,type,id) for type,id in refs]
        buf.write('<dl>referenced in: %s</dl>' %
                  (', '.join([simple_link(obj) for obj in objs])))
    buf.write('</dl>')
    return buf.getvalue()
