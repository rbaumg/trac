import time

sql = """
CREATE TABLE user (
         username        text,
	 name            text,
	 email           text,
	 role            text,
	 desc            text,
	 team            text,
	 UNIQUE(username)
);							       
"""

def do_upgrade(env, ver, cursor):
    cursor.execute(sql)
