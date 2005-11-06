sql = [
#-- Initial creation of the general cross-reference table
"""CREATE TABLE xref (
         source_type       text,
         source_id         text,
         facet             text,
         context           text,
         time              integer,
         author            text,
         relation          text,
         target_type       text,
         target_id         text
);""",
"""CREATE INDEX xref_source_idx      ON xref(source_id,source_type);""",
"""CREATE INDEX xref_target_idx      ON xref(target_id,target_type);""",
]

def do_upgrade(env, ver, cursor):
    for s in sql:
        cursor.execute(s)

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

