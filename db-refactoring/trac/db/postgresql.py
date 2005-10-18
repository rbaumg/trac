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

from trac.core import *
from trac.db import ConnectionWrapper, IDatabaseBackend


class PostgreSQLBackend(Component):
    implements(IDatabaseBackend)

    abstract = True

    def init_db(self, **args):
        cnx = self.connection(**args)
        cursor = cnx.cursor()
        from trac.db_default import schema
        for table in schema:
            for stmt in self.to_sql(table):
                cursor.execute(stmt)
        cnx.commit()

    def to_sql(cls, table):
        sql = ["CREATE TABLE %s (" % table.name]
        coldefs = []
        for column in table.columns:
            ctype = column.type
            if column.auto_increment:
                ctype = "SERIAL"
            coldefs.append("    %s %s" % (column.name, ctype))
        if len(table.key) > 1:
            coldefs.append("    CONSTRAINT %s_pk PRIMARY KEY (%s)"
                           % (table.name, ','.join(table.key)))
        sql.append(',\n'.join(coldefs) + '\n);')
        yield '\n'.join(sql)
        for index in table.indexes:
            yield "CREATE INDEX %s_idx ON %s (%s);" % (table.name, table.name,
                  ','.join(index.columns))


class Psycopg2Backend(PostgreSQLBackend):
    def identifiers(self):
        try:
            import psycopg2
            yield ("psycopg2", 4)
            yield ("psycopg", 4)
            yield ("postgres", 4)
        except ImportError:
            pass

    def connection(self, **args):
        return Psycopg2Connection(**args)


class Psycopg1Backend(PostgreSQLBackend):
    def identifiers(self):
        try:
            import psycopg
            yield ("psycopg1", 4)
            yield ("psycopg", 2)
            yield ("postgres", 2)
        except ImportError:
            pass

    def connection(self, **args):
        return Psycopg1Connection(**args)


class PgSQLlBackend(PostgreSQLBackend):
    def identifiers(self):
        try:
            from pyPgSQL import PgSQL
            yield ("pgsql", 4)
            yield ("postgres", 1)
        except:
            pass

    def connection(self, **args):
        return PgSQLConnection(**args)


class PostgreSQLConnection(ConnectionWrapper):
    """Generic Connection wrapper for PostgreSQL."""

    __slots__ = ['cnx']

    poolable = True

    def __init__(self, path, **args):
        if path.startswith('/'):
            path = path[1:]
        ConnectionWrapper.__init__(self, _create_connection(path, **args))

    def cast(self, column, type):
        # Temporary hack needed for the union of selects in the search module
        return 'CAST(%s AS %s)' % (column, type)

    def like(self):
        # Temporary hack needed for the case-insensitive string matching in the
        # search module
        return 'ILIKE'

    def get_last_id(self, cursor, table, column='id'):
        cursor.execute("SELECT CURRVAL('%s_%s_seq')" % (table, column))
        return cursor.fetchone()[0]


class Psycopg1Connection(PostgreSQLConnection):
    def _create_connection(self, path,
                           user=None, password=None, host=None, port=None,
                           params={}):
        dsn = []
        if path:
            dsn.append('dbname=' + path)
        if user:
            dsn.append('user=' + user)
        if password:
            dsn.append('password=' + password)
        if host:
            dsn.append('host=' + host)
        return self.connect(' '.join(dsn))

    def _connect(self, dsn):
        return psycopg.connect(dsn)


class Psycopg2Connection(Psycopg1Connection):
    def _connect(self, dsn):
        return psycopg2.connect(dsn)


class PgSQLConnection(PostgreSQLConnection):
    def _create_connection(path,
                           user=None, password=None, host=None, port=None,
                           params={}):
        return PgSQL.connect('', user, password, host, path, port)
