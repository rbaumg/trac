# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004 Edgewall Software
# Copyright (C) 2003, 2004 Jonas Borgstr�m <jonas@edgewall.com>
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
# Author: Jonas Borgstr�m <jonas@edgewall.com>

import os,os.path
import time

from util import *
from Href import href
from Module import Module
from Wiki import wiki_to_html
import perm
import neo_cgi
import neo_cs

class Report (Module):
    template_name = 'report.cs'
    template_rss_name = 'report_rss.cs'
    template_csv_name = 'report_csv.cs'

    def get_info (self, id):
        cursor = self.db.cursor()

        if id == -1:
            # If no special report was requested, display
            # a list of available reports instead
            cursor.execute("SELECT id AS report, title "
                           "FROM report "
                           "ORDER BY report")
            title = 'Available reports'
        else:
            cursor.execute('SELECT title, sql from report WHERE id=%s', id)
            row = cursor.fetchone()
            title = row[0]
            sql   = row[1]
            cursor.execute(sql)

        # FIXME: fetchall should probably not be used.
        info = cursor.fetchall()
        cols = cursor.rs.col_defs
        # Escape the values so that they are safe to have as html parameters
#        info = map(lambda row: map(lambda x: escape(x), row), info)
        return [cols, info, title]
        
    def create_report(self, title, sql):
        self.perm.assert_permission(perm.REPORT_CREATE)

        cursor = self.db.cursor()
        
        cursor.execute('INSERT INTO report (id, title, sql)'
                        'VALUES (NULL, %s, %s)', title, sql)
        id = self.db.db.sqlite_last_insert_rowid()
        self.db.commit()
        redirect (href.report(id))

    def delete_report(self, id):
        self.perm.assert_permission(perm.REPORT_DELETE)
        
        cursor = self.db.cursor ()
        cursor.execute('DELETE FROM report WHERE id=%s', id)
        self.db.commit()
        redirect(href.report())

    def commit_changes(self, id):
        """
        saves report changes to the database
        """
        self.perm.assert_permission(perm.REPORT_MODIFY)

        cursor = self.db.cursor()
        title = self.args['title']
        sql   = self.args['sql']

        cursor.execute('UPDATE report SET title=%s, sql=%s WHERE id=%s',
                       title, sql, id)
        self.db.commit()
        redirect(href.report(id))

    def render_report_editor(self, id, action='commit', copy=0):
        self.perm.assert_permission(perm.REPORT_MODIFY)
        cursor = self.db.cursor()

        if id == -1:
            title = sql = ""
        else:
            cursor.execute('SELECT title, sql FROM report WHERE id=%s', id)
            row = cursor.fetchone()
            sql = row[1]
            title = row[0]

        if copy:
            title += ' copy'
        
        self.cgi.hdf.setValue('report.mode', 'editor')
        self.cgi.hdf.setValue('report.title', title)
        self.cgi.hdf.setValue('report.id', str(id))
        self.cgi.hdf.setValue('report.action', action)
        self.cgi.hdf.setValue('report.sql', sql)
    
    def render_report_list(self, id):
        """
        uses a user specified sql query to extract some information
        from the database and presents it as a html table.
        """
        if self.perm.has_permission(perm.REPORT_CREATE):
            self.cgi.hdf.setValue('report.create_href',
                                  href.report(None, 'new'))
            
        if id != -1:
            if self.perm.has_permission(perm.REPORT_MODIFY):
                self.cgi.hdf.setValue('report.edit_href',
                                      href.report(id, 'edit'))
            if self.perm.has_permission(perm.REPORT_CREATE):
                self.cgi.hdf.setValue('report.copy_href',
                                      href.report(id, 'copy'))
            if self.perm.has_permission(perm.REPORT_DELETE):
                self.cgi.hdf.setValue('report.delete_href',
                                      href.report(id, 'delete'))

        self.cgi.hdf.setValue('report.mode', 'list')
        try:
            [self.cols, self.rows, title] = self.get_info(id)
        except Exception, e:
            self.cgi.hdf.setValue('report.message', 'report failed: %s' % e)
            return
        
        self.cgi.hdf.setValue('title', title + ' (report)')
        self.cgi.hdf.setValue('report.title', title)
        self.cgi.hdf.setValue('report.id', str(id))

        # Convert the header info to HDF-format
        idx = 0
        for col in self.cols:
            title=col[0].capitalize()
            if not title[0] == '_':
                self.cgi.hdf.setValue('report.headers.%d.title' % idx, title)
            idx = idx + 1

        # Convert the rows and cells to HDF-format
        row_idx = 0
        for row in self.rows:
            col_idx = 0
            for cell in row:
                column = self.cols[col_idx][0]
                value = {}
                # Special columns begin and end with '__'
                if column[:2] == '__' and column[-2:] == '__':
                    value['hidden'] = 1
                elif column[0] == '_' and column[-1] == '_':
                    value['fullrow'] = 1
                    column = column[1:-1]
                    self.cgi.hdf.setValue(prefix + '.breakrow', '1')
                elif column[0] == '_':
                    value['hidehtml'] = 1
                    column = column[1:]
                if column in ['ticket', '#']:
                    value['ticket_href'] = href.ticket(cell)
                elif column == 'description':
                    value['parsed'] = wiki_to_html(cell)
                elif column == 'report':
                    value['report_href'] = href.report(cell)
                elif column in ['time', 'date','changetime', 'created', 'modified']:
                    t = time.localtime(int(cell))
                    value['date'] = time.strftime('%x', t)
                    value['time'] = time.strftime('%X', t)
                    value['datetime'] = time.strftime('%c', t)
                    value['gmt'] = time.strftime('%a, %d %b %Y %H:%M:%S GMT',
                                                 time.gmtime(int(cell)))
                prefix = 'report.items.%d.%s' % (row_idx, str(column))
                self.cgi.hdf.setValue(prefix, escape(str(cell)))
                for key in value.keys():
                    self.cgi.hdf.setValue(prefix + '.' + key, str(value[key]))

                col_idx += 1
            row_idx += 1
        

    def render(self):
        self.perm.assert_permission(perm.REPORT_VIEW)
        # did the user ask for any special report?
        id = int(dict_get_with_default(self.args, 'id', -1))
        action = dict_get_with_default(self.args, 'action', 'list')

        if action == 'create':
            self.create_report(self.args['title'], self.args['sql'])
        elif action == 'delete':
            self.delete_report(id)
        elif action == 'commit':
            self.commit_changes(id)
        elif action == 'new':
            self.render_report_editor(-1, 'create')
        elif action == 'copy':
            self.render_report_editor(id, 'create', 1)
        elif action == 'edit':
            self.render_report_editor(id, 'commit')
        else:
            self.render_report_list(id)


    def display_rss(self):
        cs = neo_cs.CS(self.cgi.hdf)
        cs.parseFile(self.template_rss_name)
        print "Content-type: text/xml\r\n"
        print cs.render()

    def display_csv(self,sep=','):
        print "Content-type: text/plain\r\n"
        titles = ''
        print sep.join([c[0] for c in self.cols])
        for row in self.rows:
            print sep.join([str(c).replace(sep,"_").replace('\n',' ').replace('\r',' ') for c in row])

    def display_tab(self):
        self.display_csv('\t')

