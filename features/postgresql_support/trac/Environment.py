# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004 Edgewall Software
# Copyright (C) 2003, 2004 Jonas Borgström <jonas@edgewall.com>
#
# Trac is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Trac is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Author: Jonas Borgström <jonas@edgewall.com>
#
# Todo: Move backup and upgrade from db.py
#

import os
import ConfigParser

import db_default

import sqlite

class Environment:
    """
    Trac stores project information in a Trac environment.

    A Trac environment consists of a directory structure containing
    among other things:
     * a configuration file.
     * a sqlite database (stores tickets, wiki pages...)
     * Project specific templates and wiki macros.
     * wiki and ticket attachments.
    """
    def __init__(self, path, create=0, db_str=None):
        self.path = path
        if create:
            self.create(db_str)
        self.verify()
        self.load_config()

    def verify(self):
        """Verifies that self.path is a compatible trac environment"""
        fd = open(os.path.join(self.path, 'VERSION'), 'r')
        assert fd.read(26) == 'Trac Environment Version 1'
        fd.close()

    def get_db_cnx(self, check_exists=1):
        db_str = self.get_config('trac',
                                 'database',
                                 'sqlite:"db/trac.db",timeout=10000')

        pos = db_str.find(':')
        if pos == -1:
            raise EnvironmentError, 'Connection param must be of form ' \
                  '<db_module_name>:<db_connect_params>, the value "%s" ' \
                  'does not match' % db_str

        module_name = db_str[:pos]
        connect_params = db_str[pos+1:].split(',')
        
        # following is very crude code for parsing the arguments in the
        # db_connect_params string
        kargs = {}
        arg_list = []
        for x in connect_params:
            pos1 = x.find('=')
            pos2 = x.find('"')
            pos3 = x.find("'")
            if pos1 > -1:
                if pos2 > -1 and pos2 < pos1:
                    arg_list.append(eval(x))
                elif pos3 > -1 and pos3 < pos1:
                    arg_list.append(eval(x))
                else:
                    name = x[:pos1].strip()
                    value = eval(x[pos1+1:].strip())
                    kargs[name] = value
            else:
                arg_list.append(eval(x))
        args = tuple(arg_list)


        # since Trac has a slightly closer relationship with sqlite than
        # other db's, there's a special case setup here so that when the
        # path to the sqlite db is specified, its relative to TRAC_ENV
        if module_name == 'sqlite':
            db_name = os.path.join(self.path, args[0])
            args = list(args)
            args[0] = '%s' % db_name
            args = tuple(args)
            if check_exists == 1 and not os.access(db_name, os.F_OK):
                raise EnvironmentError, 'Database "%s" not found.' % db_name
        
            directory = os.path.dirname(db_name)
            if (check_exists == 1 and not os.access(db_name, os.R_OK + os.W_OK)) or not os.access(directory, os.R_OK + os.W_OK):
                raise EnvironmentError, \
                      'The web server user requires read _and_ write permission\n' \
                      'to the database %s and the directory this file is located in.' % db_name

        exec 'import %s' % module_name
        m = eval(module_name)

        print "Connecting to database module [%s] with: args=%s, kargs=%s" % (module_name, str(args), str(kargs))
        
        conn = m.connect(*args, **kargs)

        return conn

    def create(self, db_str=None):
        # Create the directory structure
        os.mkdir(self.path)
        os.mkdir(os.path.join(self.path, 'conf'))
        os.mkdir(os.path.join(self.path, 'db'))
        os.mkdir(os.path.join(self.path, 'attachments'))
        os.mkdir(os.path.join(self.path, 'templates'))
        os.mkdir(os.path.join(self.path, 'wiki-macros'))
        # Create a few static files
        fd = open(os.path.join(self.path, 'VERSION'), 'w')
        fd.write('Trac Environment Version 1\n')
        fd = open(os.path.join(self.path, 'README'), 'w')
        fd.write('This directory contains a Trac project.\n'
                 'Visit http://trac.edgewall.com/ for more information.\n')
        fd = open(os.path.join(self.path, 'conf', 'trac.ini'), 'w')
        fd.close()
        self.load_config()
        self.setup_default_config()
        if db_str:
            self.cfg.set('trac', 'database', db_str)
        self.save_config()
        cnx = self.get_db_cnx(check_exists=0)
        cursor = cnx.cursor()
        cursor.execute(db_default.schema)
        cnx.commit()

    def insert_default_data(self):
        def prep_value(v):
            if v == None:
                return 'NULL'
            else:
                prepped = v
                if type(v) == str:
                    prepped = prepped.replace("'", "''")
                return "'%s'" % prepped
        cnx = self.get_db_cnx()
        cursor = cnx.cursor()
        
        for t in xrange(0, len(db_default.data)):
            table = db_default.data[t][0]
            cols = ','.join(db_default.data[t][1])
            for row in db_default.data[t][2]:
                values = ','.join(map(prep_value, row))
                sql = "INSERT INTO %s (%s) VALUES(%s);" % (table, cols, values)
                cursor.execute(sql)
        cnx.commit()

    def setup_default_config(self):
        for s,n,v in db_default.default_config:
            if not self.cfg.has_section(s):
                self.cfg.add_section(s)
            self.cfg.set(s, n, v)

    def get_version(self):
        cnx = self.get_db_cnx()
        cursor = cnx.cursor()
        cursor.execute("SELECT value FROM system"
                       " WHERE name='database_version'")
        row = cursor.fetchone()
        return row and int(row[0])

    def load_config(self):
        self.cfg = ConfigParser.ConfigParser()
        self.cfg.read(os.path.join(self.path, 'conf', 'trac.ini'))

    def get_config(self, section, name, default=''):
        if not self.cfg.has_option(section, name):
            return default
        return self.cfg.get(section, name)

    def set_config(self, section, name, value):
        """Changes a config value, these changes are _not_ persistent
        unless saved with save_config()"""
        return self.cfg.set(section, name, value)

    def save_config(self):
        self.cfg.write(open(os.path.join(self.path, 'conf', 'trac.ini'), 'w'))

    def get_templates_dir(self):
        return os.path.join(self.path, 'templates')
    
    def get_attachments_dir(self):
        return os.path.join(self.path, 'attachments')
