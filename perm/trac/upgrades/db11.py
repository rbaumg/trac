import os.path
import shutil

sql = """
-- Remove empty values from the milestone list
DELETE FROM milestone WHERE COALESCE(name,'')='';

-- Add a description column to the version table, and remove unnamed versions
CREATE TEMP TABLE version_old AS SELECT * FROM version;
DROP TABLE version;
CREATE TABLE version (
        name            text PRIMARY KEY,
        time            integer,
        description     text
);
INSERT INTO version(name,time,description)
    SELECT name,time,'' FROM version_old WHERE COALESCE(name,'')<>'';

-- Add a description column to the component table, and remove unnamed components
CREATE TEMP TABLE component_old AS SELECT * FROM component;
DROP TABLE component;
CREATE TABLE component (
        name            text PRIMARY KEY,
        owner           text,
        description     text
);
INSERT INTO component(name,owner,description)
    SELECT name,owner,'' FROM component_old WHERE COALESCE(name,'')<>'';
"""

def do_upgrade(env, ver, cursor):
    cursor.execute(sql)

    # Copy the new default wiki macros over to the environment
    from trac.config import default_dir
    macros_dir = default_dir('macros')
    for f in os.listdir(macros_dir):
        if not f.endswith('.py'):
            continue
        src = os.path.join(macros_dir, f)
        dst = os.path.join(env.path, 'wiki-macros', f)
        if not os.path.isfile(dst):
            shutil.copy2(src, dst)
