# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004, 2005 Edgewall Software
# Copyright (C) 2003, 2004, 2005 Jonas Borgström <jonas@edgewall.com>
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

from trac import perm
from trac.Diff import get_diff_options, hdf_diff
from trac.Module import Module
from trac.util import enum, escape, TracError, get_reporter_id
from trac.WikiFormatter import *
from trac.Xref import TracObj

import os
import time
import StringIO


__all__ = ['populate_page_dict', 'WikiPage', 'WikiModule']


def populate_page_dict(db, env):
    """Extract wiki page names. This is used to detect broken wiki-links"""
    page_dict = {}
    cursor = db.cursor()
    cursor.execute("SELECT DISTINCT name FROM wiki")
    while 1:
        row = cursor.fetchone()
        if not row:
            break
        page_dict[row[0]] = 1
    env._wiki_pages = page_dict


class WikiPage(TracObj):
    """
    Represents a wiki page (new or existing).
    """

    def __init__(self, name, version, perm_, env, db):
        TracObj.__init__(self, 'wiki', name)
        self.env = env
        self.db  = db
        self.perm = perm_
        cursor = self.db.cursor ()
        if version:
            cursor.execute("SELECT version,text,readonly FROM wiki "
                           "WHERE name=%s AND version=%s",
                           (name, version))
        else:
            cursor.execute("SELECT version,text,readonly FROM wiki "
                           "WHERE name=%s ORDER BY version DESC LIMIT 1",
                           (name,))
        row = cursor.fetchone()
        if row:
            self.new = 0
            self.version = int(row[0])
            self.text = row[1]
            self.readonly = row[2] and int(row[2]) or 0
        else:
            self.version = 0
            self.new = 1
            if not self.perm.has_permission(perm.WIKI_CREATE):
                self.text = 'Wiki page %s not found' % name
                self.readonly = 1
            else:
                self.text = 'describe %s here' % name
                self.readonly = 0
        self.old_readonly = self.readonly
        self.modified = 0

    def name(self):
        # TODO: use canonical name if it doesn't follow the WikiPageNames conventions
        return escape(self.id)
    
    def href2(self, *args, **kw): # TODO: unify Xref.href, WikiPage.href2 
        return self.env.href('wiki', *args, **kw)

    def set_content(self, text):
        self.modified = self.text != text
        self.text = text

    def commit(self, author, comment, remote_addr):
        if self.readonly:
            self.perm.assert_permission(perm.WIKI_ADMIN)
        elif self.new:
            self.perm.assert_permission(perm.WIKI_CREATE)
        else:
            self.perm.assert_permission(perm.WIKI_MODIFY)

        if not self.modified and self.readonly != self.old_readonly:
            cursor = self.db.cursor()
            cursor.execute("UPDATE wiki SET readonly=%s WHERE name=%s"
                           "AND version=%s",
                           (self.readonly, self.id, self.version))
            self.db.commit()
            self.old_readonly = self.readonly
        elif self.modified:
            cursor = self.db.cursor()
            cursor.execute ("INSERT INTO WIKI (name,version,time,author,ipnr,"
                            "text,comment,readonly) VALUES (%s,%s,%s,%s,%s,%s,"
                            "%s,%s)", (self.id, self.version + 1,
                            int(time.time()), author, remote_addr, self.text,
                            comment, self.readonly))
            self.replace_xrefs_from_wiki(self.env, self.db, 'content', self.text)
            self.db.commit()
            self.version += 1
            self.old_readonly = self.readonly
            self.modified = 0
        else:
            raise TracError('Page not modified')


class WikiModule(Module):

    def render(self, req):
        action = req.args.get('action', 'view')
        pagename = req.args.get('page', 'WikiStart')
        req.hdf['wiki.action'] = action
        req.hdf['wiki.page_name'] = escape(pagename)

        obj = WikiPage(pagename, None, self.perm, self.env, self.db)
        obj.add_cross_refs(self.db, req)

        req.hdf['wiki.current_href'] = escape(obj.href2())

        if action == 'diff':
            version = int(req.args.get('version', 0))
            self._render_diff(req, obj, version)
        elif action == 'history':
            self._render_history(req, obj)
        elif action == 'edit':
            self._render_editor(req, obj)
        elif action == 'delete':
            version = None
            if req.args.has_key('delete_version'):
                version = int(req.args.get('version'))
            self._delete_page(req, obj, version)
        elif action == 'save':
            if req.args.has_key('cancel'):
                req.redirect(obj.href2())
            elif req.args.has_key('preview'):
                req.hdf['wiki.action'] = 'preview'
                self._render_editor(req, obj, 1)
            else:
                self._save_page(req, obj)
        else:
            self._render_view(req, obj)

        if req.args.get('format') == 'txt':
            self.render_txt(req)
        else:
            req.display('wiki.cs')

    def render_txt(self, req):
        req.send_response(200)
        req.send_header('Content-Type', 'text/plain;charset=utf-8')
        req.end_headers()
        req.write(req.hdf.get('wiki.page_source', ''))

    def _delete_page(self, req, obj, version=None):
        self.perm.assert_permission(perm.WIKI_DELETE)

        page_deleted = 0
        cursor = self.db.cursor()
        if version is not None: # Delete only a specific page version
            cursor = self.db.cursor()
            cursor.execute("DELETE FROM wiki WHERE name=%s and version=%s",
                           (obj.id, version))
            obj.delete_xrefs(self.db, 'comment:%s' % version)
            self.log.info('Deleted version %d of page %s' % (version, obj.id))
            cursor.execute("SELECT COUNT(*) FROM wiki WHERE name=%s", (obj.id,))
            last_version = cursor.fetchone()[0]
            if last_version == 0:
                page_deleted = 1
            elif version > last_version: # resurrect the previous 'content' 
                cursor.execute("SELECT text FROM wiki WHERE name=%s ORDER BY version DESC",
                               (obj.id))
                text = cursor.fetchone()[0]
                obj.replace_xrefs_from_wiki(self.env, self.db, 'content', text)
        else: # Delete a wiki page completely
            cursor.execute("DELETE FROM wiki WHERE name=%s", (obj.id,))
            page_deleted = 1
            self.log.info('Deleted page %s' % obj.id)
        self.db.commit()

        if page_deleted:
            obj.delete_xrefs(self.db)
            # Delete orphaned attachments
            for attachment in self.env.get_attachments(self.db, obj.type, obj.id):
                self.env.delete_attachment(self.db, obj.type, obj.id, attachment[0])
            req.redirect(self.env.href.wiki())
        else:
            req.redirect(obj.href2())

    def _render_diff(self, req, obj, version):
        # Stores the diff-style in the session if it has been changed, and adds
        # diff-style related item to the HDF
        self.perm.assert_permission(perm.WIKI_VIEW)

        diff_style, diff_options = get_diff_options(req)
        if req.args.has_key('update'):
           req.redirect(obj.href2(version, action='diff'))

        # Ask web spiders to not index old versions
        req.hdf['html.norobots'] = 1

        cursor = self.db.cursor()
        cursor.execute("SELECT text,author,comment,time FROM wiki "
                       "WHERE name=%s AND version IN (%s,%s) ORDER BY version",
                       (obj.id, version - 1, version))
        rows = cursor.fetchall()
        if not rows:
            raise TracError('Version %d of page "%s" not found.'
                            % (version, obj.id),
                            'Page Not Found')
        info = {
            'version': version,
            'time': time.strftime('%c', time.localtime(int(rows[-1][3]))),
            'author': escape(rows[-1][1] or ''),
            'comment': escape(rows[-1][2] or ''),
            'history_href': escape(obj.href2(action='history'))
        }
        req.hdf['wiki'] = info

        if len(rows) == 1:
            oldtext = ''
        else:
            oldtext = rows[0][0].splitlines()
        newtext = rows[-1][0].splitlines()

        context = 3
        for option in diff_options:
            if option[:2] == '-U':
                context = int(option[2:])
                break
        changes = hdf_diff(oldtext, newtext, context=context,
                           ignore_blank_lines='-B' in diff_options,
                           ignore_case='-i' in diff_options,
                           ignore_space_changes='-b' in diff_options)
        req.hdf['wiki.diff'] = changes

    def _render_editor(self, req, obj, preview=0):
        self.perm.assert_permission(perm.WIKI_MODIFY)

        if req.args.has_key('text'):
            obj.set_content(req.args.get('text'))
        if preview:
            obj.readonly = req.args.has_key('readonly')

        author = req.args.get('author', get_reporter_id(req))
        version = req.args.get('edit_version', None)
        comment = req.args.get('comment', '')
        editrows = req.args.get('editrows')
        if editrows:
            pref = req.session.get('wiki_editrows', '20')
            if editrows != pref:
                req.session['wiki_editrows'] = editrows
        else:
            editrows = req.session.get('wiki_editrows', '20')

        req.hdf['title'] = obj.name() + ' (edit)'
        info = {
            'page_source': escape(obj.text),
            'version': obj.version,
            'author': escape(author),
            'comment': escape(comment),
            'readonly': obj.readonly,
            'history_href': escape(obj.href2(action='history')),
            'edit_rows': editrows,
            'scroll_bar_pos': req.args.get('scroll_bar_pos', '')
        }
        if preview:
            info['page_html'] = wiki_to_html(obj.text, req.hdf, self.env, self.db)
        req.hdf['wiki'] = info

    def _render_history(self, req, obj):
        """
        Extract the complete history for a given page and stores it in the hdf.
        This information is used to present a changelog/history for a given page
        """
        self.perm.assert_permission(perm.WIKI_VIEW)

        cursor = self.db.cursor ()
        cursor.execute("SELECT version,time,author,comment,ipnr FROM wiki "
                       "WHERE name=%s ORDER BY version DESC", (obj.id,))
        for i, row in enum(cursor):
            version, t, author, comment, ipnr = row
            item = {
                'url': escape(obj.href2(version)),
                'diff_url': escape(obj.href2(version=version, action='diff')),
                'version': version,
                'time': time.strftime('%x %X', time.localtime(int(t))),
                'author': escape(author),
                'comment': wiki_to_oneliner(comment or '', self.env, self.db),
                'ipaddr': ipnr
            }
            req.hdf['wiki.history.%d' % i] = item

    def _render_view(self, req, obj):
        self.perm.assert_permission(perm.WIKI_VIEW)

        if obj.id == 'WikiStart':
            req.hdf['title'] = ''
        else:
            req.hdf['title'] = escape(obj.id)

        version = req.args.get('version')
        if version:
            self.add_link(req, 'alternate',
                          '?version=%s&amp;format=txt' % version, 'Plain Text',
                          'text/plain')
            # Ask web spiders to not index old versions
            req.hdf['html.norobots'] = 1
        else:
            self.add_link(req, 'alternate', '?format=txt', 'Plain Text',
                          'text/plain')

        obj.version = version

        info = {
            'version': obj.version,
            'readonly': obj.readonly,
            'page_html': wiki_to_html(obj.text, req.hdf, self.env, self.db),
            'page_source': obj.text, # for plain text view
            'history_href': escape(obj.href2(action='history'))
        }
        req.hdf['wiki'] = info

        self.env.get_attachments_hdf(self.db, obj.type, obj.id, req.hdf,
                                     'wiki.attachments')
        req.hdf['wiki.attach_href'] = self.env.href.attachment('wiki', obj.id)
        # xref-branch: template support (pretty much nothing at this point)
        if obj.relation_exist(self.db, 'is-a', TracObj('wiki', 'TracTemplate')):
            req.hdf['wiki.create_from_template_href'] = obj.href2(action='create_from_template')

    def _save_page(self, req, obj):
        self.perm.assert_permission(perm.WIKI_MODIFY)

        if req.args.has_key('text'):
            obj.set_content(req.args.get('text'))

        # Modify the read-only flag if it has been changed and the user is
        # WIKI_ADMIN
        if self.perm.has_permission(perm.WIKI_ADMIN):
            obj.readonly = int(req.args.has_key('readonly'))

        # We store the page version when we start editing a page.
        # This way we can stop users from saving changes if they are
        # not based on the latest version any more
        edit_version = int(req.args.get('version'))
        if edit_version != obj.version:
            raise TracError('Sorry, cannot create new version. This page has '
                            'already been modified by someone else.')

        obj.commit(req.args.get('author'), req.args.get('comment'),
                        req.remote_addr)
        req.redirect(obj.href2())
