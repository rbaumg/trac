import time

sql = """
-- Initial creation of the general cross-reference table
CREATE TABLE xref (
         src_type        text,
         src_id          text,
         relation        text,
         dest_type       text,
         dest_id         text,
         facet           text,
         context         text
);

CREATE INDEX xref_src_idx       ON xref(src_id,src_type);
CREATE INDEX xref_dest_idx      ON xref(dest_id,dest_type);
"""

def do_upgrade(env, ver, cursor):
    cursor.execute(sql)

def do_db_upgrade(env, ver, db):
    """Renumbering of ticket comments (using the spare 'oldvalue' field)"""
    cursor = db.cursor()
    update_cursor = db.cursor()
    cursor.execute("SELECT ticket, time, author FROM ticket_change "
                   "WHERE field = 'comment' "
                   "ORDER BY ticket, time, author ")
    previous_ticket = None
    for ticket, time, author in cursor:
        if ticket != previous_ticket:
            previous_ticket = ticket
            n = 1
        update_cursor.execute("UPDATE ticket_change SET "
                              "oldvalue = %s ",
                              (n))
        n += 1

        













    
