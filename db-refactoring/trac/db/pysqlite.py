# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Edgewall Software
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.com/license.html.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://projects.edgewall.com/trac/.
#
# Author: Christopher Lenz <cmlenz@gmx.de>

import os
import weakref

from trac.core import *
from trac.db import ConnectionWrapper, IDatabaseBackend

global pysqlite1
global pysqlite2

class PySQLiteBackend(Component):

    implements(IDatabaseBackend)

    abstract = True

    def init_db(self, path, params={}):
        if path != ':memory:':
            # make the directory to hold the database
            if os.path.exists(path):
                raise TracError, 'Database already exists at %s' % path
            os.makedirs(os.path.split(path)[0])

        cnx = self.connection(path,params)
        cursor = cnx.cursor()
        from trac.db_default import schema
        for table in schema:
            for stmt in self.to_sql(table):
                cursor.execute(stmt)
        cnx.commit()
        
    def to_sql(self, table):
        sql = ["CREATE TABLE %s (" % table.name]
        coldefs = []
        for column in table.columns:
            ctype = column.type.lower()
            if column.auto_increment:
                ctype = "integer PRIMARY KEY"
            elif len(table.key) == 1 and column.name in table.key:
                ctype += " PRIMARY KEY"
            elif ctype == "int":
                ctype = "integer"
            coldefs.append("    %s %s" % (column.name, ctype))
        if len(table.key) > 1:
            coldefs.append("    UNIQUE (%s)" % ','.join(table.key))
        sql.append(',\n'.join(coldefs) + '\n);')
        yield '\n'.join(sql)
        for index in table.indexes:
            yield "CREATE INDEX %s_idx ON %s (%s);" % (table.name,
                  table.name, ','.join(index.columns))


class Pysqlite1Backend(PySQLiteBackend):
    def identifiers(self):
        try:
            global pysqlite1
            import sqlite as pysqlite1
            yield ("pysqlite1", 8)
            yield ("sqlite2", 4)
            yield ("sqlite3", 2)
            yield ("sqlite", 2)
        except:
            pass

    def connection(self, **args):
        return PySQLite1Connection(**args)


class Pysqlite2Backend(PySQLiteBackend):
    def identifiers(self):
        try:
            global pysqlite2
            import pysqlite2.dbapi2 as pysqlite2
            yield ("pysqlite2", 8)
            yield ("sqlite3", 4)
            yield ("sqlite", 4)
        except:
            pass

    def connection(self, **args):
        return PySQLite2Connection(**args)


### Connection classes

class SQLiteConnection(ConnectionWrapper):
    """Generic Connection wrapper for SQLite, via pysqlite 1 or 2"""

    __slots__ = ['cnx']

    poolable = False

    def __init__(self, path, params={}):
        self.cnx = None
        if path != ':memory:':
            if not os.access(path, os.F_OK):
                raise TracError, 'Database "%s" not found.' % path

            dbdir = os.path.dirname(path)
            if not os.access(path, os.R_OK + os.W_OK) or \
                   not os.access(dbdir, os.R_OK + os.W_OK):
                from getpass import getuser
                raise TracError, 'The user %s requires read _and_ write ' \
                                 'permission to the database file %s and the ' \
                                 'directory it is located in.' \
                                 % (getuser(), path)

        timeout = int(params.get('timeout', self.timeout))
        cnx = self._make_connection(path, timeout=timeout)
        ConnectionWrapper.__init__(self, cnx)

    def cast(self, column, type):
        return column

    def like(self):
        return 'LIKE'


class PySQLite1Connection(SQLiteConnection):
    """Connection wrapper for SQLite via pysqlite-1."""

    timeout = 10000

    def _make_connection(self, path, timeout):
        global pysqlite1
        return pysqlite1.connect(path, timeout)

    def cursor(self):
        return self.cnx.cursor()

    def get_last_id(self, cursor, table, column='id'):
        return self.cnx.db.sqlite_last_insert_rowid()



class PySQLite2Connection(SQLiteConnection):
    """Connection wrapper for SQLite via pysqlite-2"""

    __slots__ = ['_active_cursors']

    timeout = 10.0
    
    def __init__(self, path, params={}):
        self._active_cursors = weakref.WeakKeyDictionary()
        # Convert unicode to UTF-8 bytestrings. This is case-sensitive, so
        # we need two converters
        global pysqlite2
        pysqlite2.register_converter('text', str)
        pysqlite2.register_converter('TEXT', str)
        SQLiteConnection.__init__(self, path, params)

    def _make_connection(self, path, timeout):
        global pysqlite2
        return pysqlite2.connect(path, timeout=timeout,
                                 detect_types=pysqlite2.PARSE_DECLTYPES,
                                 check_same_thread=False) # i.e. we know
                                                          # we do it right
    def cursor(self):
        cursor = self.cnx.cursor(PyFormatCursor)
        self._active_cursors[cursor] = True
        cursor.cnx = self
        return cursor

    def rollback(self):
        for cursor in self._active_cursors.keys():
            cursor.close()
        self.cnx.rollback()

    def get_last_id(self, cursor, table, column='id'):
        return cursor.lastrowid

try:
    import pysqlite2.dbapi2 as pysqlite2
    
    class PyFormatCursor(pysqlite2.Cursor):
        def _rollback_on_error(self, function, *args, **kwargs):
            try:
                return function(self, *args, **kwargs)
            except pysqlite2.OperationalError, e:
                self.cnx.rollback()
                raise

        def execute(self, sql, args=None):
            if args:
                sql = sql % (('?',) * len(args))
            return self._rollback_on_error(pysqlite2.Cursor.execute, sql,
                                           args or [])

        def executemany(self, sql, args=None):
            if args:
                sql = sql % (('?',) * len(args[0]))
            return self._rollback_on_error(pysqlite2.Cursor.executemany, sql,
                                           args or [])

        def _convert_row(self, row):
            return tuple([(isinstance(v, unicode) and [v.encode('utf-8')] or \
                           [v])[0] for v in row])
        def fetchone(self):
            row = pysqlite2.Cursor.fetchone(self)
            return row and self._convert_row(row) or None
        
        def fetchmany(self, num):
            rows = pysqlite2.Cursor.fetchmany(self, num)
            return rows != None and [self._convert_row(row)
                                     for row in rows] or None
        
        def fetchall(self):
            rows = pysqlite2.Cursor.fetchall(self)
            return rows != None and [self._convert_row(row)
                                     for row in rows] or None
except:
    pass
