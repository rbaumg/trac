sql = """
-- Add category to 'ticket'
CREATE TEMP TABLE ticket_old AS SELECT * FROM ticket;
DROP TABLE ticket;
CREATE TABLE ticket (
        id              integer PRIMARY KEY,
        category        text,           -- the nature of the ticket
        time            integer,        -- the time it was created
        changetime      integer,
        component       text,
        severity        text,
        priority        text,
        owner           text,           -- who is this ticket assigned to
        reporter        text,
        cc              text,           -- email addresses to notify
        url             text,           -- url related to this ticket
        version         text,           --
        milestone       text,           --
        status          text,
        resolution      text,
        summary         text,           -- one-line summary
        description     text,           -- problem description (long)
        keywords        text
);

INSERT INTO ticket(id, category, time, changetime, component,
                   severity, priority, owner, reporter, cc, url, version,
                   milestone, status, resolution, summary, description, keywords)
  SELECT id, 'Bug', time, changetime, component,
         severity, priority, owner, reporter, cc, url, version,
         milestone, status, resolution, summary, description, keywords FROM ticket_old
  WHERE severity <> 'enhancement';

INSERT INTO ticket(id, category, time, changetime, component,
                   severity, priority, owner, reporter, cc, url, version,
                   milestone, status, resolution, summary, description, keywords)
  SELECT id, 'Feature', time, changetime, component,
         'normal', priority, owner, reporter, cc, url, version,
         milestone, status, resolution, summary, description, keywords FROM ticket_old
  WHERE severity = 'enhancement';
"""

def do_upgrade(env, ver, cursor):
    cursor.execute(sql)
