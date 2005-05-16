sql = """
-- Add 'type' column to 'ticket' table
--
CREATE TEMP TABLE ticket_old AS SELECT * FROM ticket;
DROP TABLE ticket;
CREATE TABLE ticket (
        id              integer PRIMARY KEY,
        type            text,           -- the nature of the ticket
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

-- Convert existing tickets with 'enhancement' severity to real 'Enhancement' tickets
--
INSERT INTO ticket(id, type, time, changetime, component,
                   severity, priority, owner, reporter, cc, url, version,
                   milestone, status, resolution, summary, description, keywords)
  SELECT id, 'Defect', time, changetime, component,
         severity, priority, owner, reporter, cc, url, version,
         milestone, status, resolution, summary, description, keywords FROM ticket_old
  WHERE severity <> 'enhancement';

INSERT INTO ticket(id, type, time, changetime, component,
                   severity, priority, owner, reporter, cc, url, version,
                   milestone, status, resolution, summary, description, keywords)
  SELECT id, 'Enhancement', time, changetime, component,
         'major', priority, owner, reporter, cc, url, version,
         milestone, status, resolution, summary, description, keywords FROM ticket_old
  WHERE severity = 'enhancement';


-- Rename 'type' column to 'kind' column in 'enum' table
--
CREATE TEMP TABLE enum_old AS SELECT * FROM enum;
DROP TABLE enum;
CREATE TABLE enum (
        kind            text,
        name            text,
        value           text,
        UNIQUE(name,kind)
);

INSERT INTO enum (kind, name, value) SELECT type, name, value FROM enum_old;

INSERT INTO enum (kind, name, value) VALUES ('ticket_type', 'Defect', '1');
INSERT INTO enum (kind, name, value) VALUES ('ticket_type', 'Enhancement', '2');
INSERT INTO enum (kind, name, value) VALUES ('ticket_type', 'Task', '3');
DELETE FROM enum WHERE kind = 'severity' AND name = 'enhancement';

"""
                
def do_upgrade(env, ver, cursor):
    # -- simple upgrade
    cursor.execute(sql)
    # -- upgrade reports (involve a rename)
    cursor.execute("SELECT id,sql FROM report")
    reports = {}
    for id, rsql in cursor:
        reports[id] = rsql
    for id, rsql in reports.items():
        cursor.execute("UPDATE report SET sql=%s WHERE id=%s",
                       (rsql \
                        .replace('severity,','type, severity,') \
                        .replace('p.type','p.kind'),id))

