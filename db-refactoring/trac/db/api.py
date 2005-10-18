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

from __future__ import generators

import os
import time
import urllib
try:
    import threading
except ImportError:
    import dummy_threading as threading
    threading._get_ident = lambda: 0
import weakref

from trac.core import *


### Database backend interface and manager

class IDatabaseBackend(Interface):
    """A relational database backend for Trac"""

    def identifiers(self):
        """DB string prefixes that are supported by the backends,
        and their relative priorities.

        Highest number is highest priority.
        """

    def connection(self):
        """Create a new connection to the database"""
        
    def init_db(self, **params):
        """Initialize the database"""

    def parse_connection_string(self,str):
        """Convert a connection string to a dictionary"""


class DatabaseBackendManager(Component):

    backends = ExtensionPoint(IDatabaseBackend)

    def __init__(self):
        self._backend_map = None

    def init_db(self, db_str):
        backend, args = self._get_backend(self.env.path, db_str)
        backend.init_db(**args)
    
    def get_cnx_pool(self):
        db_str = self.env.config.get('trac', 'database')
        backend, args = self._get_backend(self.env.path, db_str)
        return ConnectionPool(5, backend, **args)

    def _get_backend(self, env_path, db_str):
        scheme, args = _parse_db_str(db_str)
        if not self._backend_map:
            self._backend_map = {}
            for backend in self.backends:
                for ident, prio in backend.identifiers():
                    print ident, prio
                    if ident in self._backend_map:
                        highest = self._backend_map[ident][1]
                    else:
                        highest = 0
                    if prio > highest:
                        self._backend_map[ident] = (backend, prio)
        print self._backend_map
        if not scheme in self._backend_map:
            raise TracError, 'Unsupported database type "%s"' % scheme

        if scheme == 'sqlite': # FIXME
            # Special case for SQLite to support a path relative to the
            # environment directory
            if args['path'] != ':memory:' and \
                   not args['path'].startswith('/'):
                args['path'] = os.path.join(env_path,
                                            args['path'].lstrip('/'))

        return self._backend_map[scheme][0], args

    

### Schema specification classes, for init_db

class Table(object):
    """Declare a table in a database schema."""

    def __init__(self, name, key=[]):
        self.name = name
        self.columns = []
        self.indexes = []
        self.key = key
        if isinstance(key, (str, unicode)):
            self.key = [key]

    def __getitem__(self, objs):
        self.columns = [o for o in objs if isinstance(o, Column)]
        self.indexes = [o for o in objs if isinstance(o, Index)]
        return self

class Column(object):
    """Declare a table column in a database schema."""

    def __init__(self, name, type='text', size=None, unique=False,
                 auto_increment=False):

        self.name = name
        self.type = type
        self.size = size
        self.auto_increment = auto_increment

class Index(object):
    """Declare an index for a database schema."""

    def __init__(self, columns):
        self.columns = columns


### Reusable wrappers, for connection and cursors

class IterableCursor(object):
    """Wrapper for DB-API cursor objects that makes the cursor iterable.
    
    Iteration will generate the rows of a SELECT query one by one.
    """
    __slots__ = ['cursor']

    def __init__(self, cursor):
        self.cursor = cursor

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def __iter__(self):
        while True:
            row = self.cursor.fetchone()
            if not row:
                return
            yield row


class ConnectionWrapper(object):
    """Generic wrapper around connection objects.
    
    This wrapper makes cursors produced by the connection iterable using
    `IterableCursor`.
    """
    __slots__ = ['cnx']

    def __init__(self, cnx):
        self.cnx = cnx

    def __getattr__(self, name):
        if hasattr(self, 'cnx'):
            return getattr(self.cnx, name)
        return object.__getattr__(self, name)

    def cursor(self):
        return IterableCursor(self.cnx.cursor())


class TimeoutError(Exception):
    """Exception raised by the connection pool when no connection has become
    available after a given timeout."""


class PooledConnection(ConnectionWrapper):
    """A database connection that can be pooled. When closed, it gets returned
    to the pool.
    """

    def __init__(self, pool, cnx):
        ConnectionWrapper.__init__(self, cnx)
        self._pool = pool

    def close(self):
        if self.cnx:
            self._pool._return_cnx(self.cnx)
            self.cnx = None

    def __del__(self):
        self.close()


### The Connection pool 

class ConnectionPool(object):
    """A very simple connection pool implementation."""

    backends = ExtensionPoint(IDatabaseBackend)

    def __init__(self, maxsize, backend, **args):
        self._dormant = [] # inactive connections in pool
        self._active = {} # active connections by thread ID
        self._available = threading.Condition(threading.RLock())
        self._maxsize = maxsize # maximum pool size
        self._cursize = 0 # current pool size, includes active connections
        self._backend = backend
        self._args = args

    def get_cnx(self, timeout=None):
        start = time.time()
        self._available.acquire()
        try:
            tid = threading._get_ident()
            if tid in self._active:
                self._active[tid][0] += 1
                return PooledConnection(self, self._active[tid][1])
            while True:
                if self._dormant:
                    cnx = self._dormant.pop()
                    break
                elif self._maxsize and self._cursize < self._maxsize:
                    cnx = self._backend.connection(**self._args)
                    self._cursize += 1
                    break
                else:
                    if timeout:
                        self._available.wait(timeout)
                        if (time.time() - start) >= timeout:
                            raise TimeoutError, 'Unable to get database ' \
                                                'connection within %d seconds' \
                                                % timeout
                    else:
                        self._available.wait()
            self._active[tid] = [1, cnx]
            return PooledConnection(self, cnx)
        finally:
            self._available.release()

    def _return_cnx(self, cnx):
        self._available.acquire()
        try:
            tid = threading._get_ident()
            if tid in self._active:
                num, cnx_ = self._active.get(tid)
                assert cnx is cnx_
                if num > 1:
                    self._active[tid][0] = num - 1
                else:
                    del self._active[tid]
                    if cnx not in self._dormant:
                        cnx.rollback()
                        if cnx.poolable:
                            self._dormant.append(cnx)
                        else:
                            self._cursize -= 1
                        self._available.notify()
        finally:
            self._available.release()

    def shutdown(self):
        self._available.acquire()
        try:
            for cnx in self._dormant:
                cnx.cnx.close()
        finally:
            self._available.release()



### Utilities (FIXME)

def _parse_db_str(db_str):
    scheme, rest = db_str.split(':', 1)

    if not rest.startswith('/'):
        if scheme == 'sqlite':
            # Support for relative and in-memory SQLite connection strings
            host = None
            path = rest
        else:
            raise TracError, 'Database connection string %s must start with ' \
                             'scheme:/' % db_str
    else:
        if rest.startswith('/') and not rest.startswith('//'):
            host = None
            rest = rest[1:]
        elif rest.startswith('///'):
            host = None
            rest = rest[3:]
        else:
            rest = rest[2:]
            if rest.find('/') == -1:
                host = rest
                rest = ''
            else:
                host, rest = rest.split('/', 1)
        path = None

    if host and host.find('@') != -1:
        user, host = host.split('@', 1)
        if user.find(':') != -1:
            user, password = user.split(':', 1)
        else:
            password = None
    else:
        user = password = None
    if host and host.find(':') != -1:
        host, port = host.split(':')
        port = int(port)
    else:
        port = None

    if not path:
        path = '/' + rest
    if os.name == 'nt':
        # Support local paths containing drive letters on Win32
        if len(rest) > 1 and rest[1] == '|':
            path = "%s:%s" % (rest[0], rest[2:])

    params = {}
    if path.find('?') != -1:
        path, qs = path.split('?', 1)
        qs = qs.split('&')
        for param in qs:
            name, value = param.split('=', 1)
            value = urllib.unquote(value)
            params[name] = value

    args = zip(('user', 'password', 'host', 'port', 'path', 'params'),
               (user, password, host, port, path, params))
    return scheme, dict([(key, value) for key, value in args if value])
