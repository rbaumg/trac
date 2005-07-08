sql = """
-- Initial creation of the general cross-reference table
CREATE TABLE xref (
         src_type        text,
         src_id          text,
         facet           text,
         context         text,
         time            integer,
         relation        text,
         dest_type       text,
         dest_id         text
);

CREATE INDEX xref_src_idx       ON xref(src_id,src_type);
CREATE INDEX xref_dest_idx      ON xref(dest_id,dest_type);
"""

def do_upgrade(env, ver, cursor):
    cursor.execute(sql)

    # Numbering of ticket comments (using the spare 'oldvalue' field)
    # (ticket comment:n facet) and later threading support
    cursor.execute("SELECT ticket, time, author FROM ticket_change "
                   "WHERE field = 'comment' "
                   "ORDER BY ticket, time, author ")
    all_comments = {}
    previous_ticket = None
    for ticket, time, author in cursor:
        if ticket != previous_ticket:
            previous_ticket = ticket
            all_comments[ticket] = [(time, author)]
        else:
            all_comments[ticket].append((time, author))
    for ticket in all_comments.keys():
        comments = all_comments[ticket]
        comments.sort()
        i = 0
        for time, author in comments:
            i += 1
            cursor.execute("UPDATE ticket_change SET oldvalue = %s"
                           " WHERE ticket=%s AND field='comment'"
                           "   AND time=%s AND author=%s",
                           (i, ticket, time, author))

