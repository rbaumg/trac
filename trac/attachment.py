# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004, 2005 Edgewall Software
# Copyright (C) 2003, 2004, 2005 Jonas Borgstr�m <jonas@edgewall.com>
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

import os
import re
import shutil
import time
import urllib

from trac import perm, util
from trac.core import *
from trac.mimeview import *
from trac.web.chrome import add_link, INavigationContributor
from trac.web.main import IRequestHandler


class Attachment(object):

    def __init__(self, env, parent_type, parent_id, filename=None, db=None):
        self.env = env
        self.parent_type = parent_type
        self.parent_id = str(parent_id)
        if filename:
            self._fetch(filename, db)
        else:
            self.filename = None
            self.description = None
            self.size = None
            self.time = None
            self.author = None
            self.ipnr = None

    def _fetch(self, filename, db=None):
        if not db:
            db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT filename,description,size,time,author,ipnr "
                       "FROM attachment WHERE type=%s AND id=%s "
                       "AND filename=%s ORDER BY time",
                       (self.parent_type, self.parent_id, filename))
        row = cursor.fetchone()
        cursor.close()
        if not row:
            raise TracError('Attachment %s/%s/%s does not exist.'
                            % (self.parent_type, self.parent_id, filename),
                            'Invalid Attachment')
        self.filename = row[0]
        self.description = row[1]
        self.size = row[2] and int(row[2]) or 0
        self.time = row[3] and int(row[3]) or 0
        self.author = row[4]
        self.ipnr = row[5]

    def _get_path(self):
        path = os.path.join(self.env.get_attachments_dir(), self.parent_type,
                            urllib.quote(self.parent_id))
        if self.filename:
            path = os.path.join(path, urllib.quote(self.filename))
        return path
    path = property(fget=lambda self: self._get_path())

    def delete(self, db=None):
        assert self.filename, 'Cannot delete non-existent attachment'
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        cursor = db.cursor()
        cursor.execute("DELETE FROM attachment WHERE type=%s AND id=%s "
                       "AND filename=%s", (self.parent_type, self.parent_id,
                       self.filename))

        path = os.path.join(self.env.get_attachments_dir(), self.parent_type,
                            urllib.quote(self.parent_id),
                            urllib.quote(self.filename))
        try:
            os.unlink(path)
        except OSError:
            raise TracError, 'Attachment not found'

        self.env.log.info('Attachment removed: %s/%s/%s'
                          % (self.parent_type, self.parent_id, self.filename))
        if handle_ta:
            db.commit()

    def insert(self, filename, fileobj, size, time=time.time(), db=None):
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        # Maximum attachment size (in bytes)
        max_size = int(self.env.config.get('attachment', 'max_size'))
        if max_size >= 0 and size > max_size:
            raise TracError('Maximum attachment size: %d bytes' % max_size,
                            'Upload failed')
        self.size = size
        self.time = time

        if not os.access(self.path, os.F_OK):
            os.makedirs(self.path)
        filename = urllib.quote(filename)
        try:
            path, targetfile = util.create_unique_file(os.path.join(self.path,
                                                                    filename))
            filename = urllib.unquote(os.path.basename(path))

            cursor = db.cursor()
            cursor.execute("INSERT INTO attachment "
                           "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                           (self.parent_type, self.parent_id, filename,
                            self.size, self.time, self.description, self.author,
                            self.ipnr))
            shutil.copyfileobj(fileobj, targetfile)
            self.filename = filename

            self.env.log.info('New attachment: %s/%s/%s by %s'
                              % (self.parent_type, self.parent_id,
                                 self.filename, self.author))
            if handle_ta:
                db.commit()
        finally:
            targetfile.close()

    def select(cls, env, parent_type, parent_id, db=None):
        if not db:
            db = env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT filename,description,size,time,author,ipnr "
                       "FROM attachment WHERE type=%s AND id=%s ORDER BY time",
                       (parent_type, parent_id))
        for filename,description,size,time,author,ipnr in cursor:
            attachment = Attachment(env, parent_type, parent_id)
            attachment.filename = filename
            attachment.description = description
            attachment.size = size
            attachment.time = time
            attachment.author = author
            attachment.ipnr = ipnr
            yield attachment

    select = classmethod(select)

    def open(self):
        self.env.log.debug('Trying to open attachment at %s' % self.path)
        try:
            fd = open(self.path, 'rb')
        except IOError:
            raise TracError('Attachment %s not found' % self.filename)
        return fd


def attachment_to_hdf(env, db, req, attachment):
    from Wiki import wiki_to_oneliner
    if not db:
        db = env.get_db_cnx()
    hdf = {
        'filename': attachment.filename,
        'description': wiki_to_oneliner(attachment.description, env, db),
        'author': util.escape(attachment.author),
        'ipnr': attachment.ipnr,
        'size': util.pretty_size(attachment.size),
        'time': time.strftime('%c', time.localtime(attachment.time)),
        'href': env.href.attachment(attachment.parent_type,
                                    attachment.parent_id,
                                    attachment.filename)
    }
    return hdf


class AttachmentModule(Component):

    implements(IRequestHandler, INavigationContributor)

    CHUNK_SIZE = 4096
    DISP_MAX_FILE_SIZE = 256 * 1024

    # INavigationContributor methods

    def get_active_navigation_item(self, req):
        return req.args.get('type')

    def get_navigation_items(self, req):
        return []

    # IReqestHandler methods

    def match_request(self, req):
        match = re.match(r'^/attachment/(ticket|wiki)(?:/(.*))?$', req.path_info)
        if match:
            req.args['type'] = match.group(1)
            req.args['path'] = match.group(2)
            return 1

    def process_request(self, req):
        parent_type = req.args.get('type')
        path = req.args.get('path')
        if not parent_type or not path:
            raise TracError('Bad request')
        if not parent_type in ['ticket', 'wiki']:
            raise TracError('Unknown attachment type')

        action = req.args.get('action', 'view')
        if action == 'new':
            self._render_form(req, parent_type, path)
            return 'attachment.cs', None
        elif action == 'save':
            self._do_save(req, parent_type, path)
        else:
            segments = path.split('/')
            parent_id = '/'.join(segments[:-1])
            filename = segments[-1]

            attachment = Attachment(self.env, parent_type, parent_id, filename)
            if action == 'delete':
                self._do_delete(req, attachment)
                return
            self._render_view(req, attachment)
            return 'attachment.cs', None

    # Internal methods

    def _do_save(self, req, parent_type, parent_id):
        perm_map = {'ticket': perm.TICKET_APPEND, 'wiki': perm.WIKI_MODIFY}
        req.perm.assert_permission(perm_map[parent_type])

        if req.args.has_key('cancel'):
            req.redirect(self.env.href(parent_type, parent_id))

        upload = req.args['attachment']
        if not upload.filename:
            raise TracError, 'No file uploaded'
        if hasattr(upload.file, 'fileno'):
            size = os.fstat(upload.file.fileno())[6]
        else:
            size = upload.file.len

        filename = upload.filename.replace('\\', '/').replace(':', '/')
        filename = os.path.basename(filename)
        assert filename, 'No file uploaded'

        # We try to normalize the filename to utf-8 NFC if we can.
        # Files uploaded from OS X might be in NFD.
        import sys, unicodedata
        if sys.version_info[0] > 2 or \
           (sys.version_info[0] == 2 and sys.version_info[1] >= 3):
           filename = unicodedata.normalize('NFC', unicode(filename, 'utf-8')).encode('utf-8')

        attachment = Attachment(self.env, parent_type, parent_id)
        attachment.description = req.args.get('description', '')
        attachment.author = req.args.get('author', '')
        attachment.ipnr = req.remote_addr
        attachment.insert(filename, upload.file, size)

        # Redirect the user to the newly created attachment
        req.redirect(self.env.href.attachment(attachment.parent_type,
                                              attachment.parent_id,
                                              attachment.filename))

    def _do_delete(self, req, attachment):
        perm_map = {'ticket': perm.TICKET_ADMIN, 'wiki': perm.WIKI_DELETE}
        req.perm.assert_permission(perm_map[attachment.parent_type])

        attachment.delete()

        # Redirect the user to the attachment parent page
        req.redirect(self.env.href(attachment.parent_type,
                                   attachment.parent_id))

    def _get_parent_link(self, parent_type, parent_id):
        if parent_type == 'ticket':
            return ('Ticket #' + parent_id, self.env.href.ticket(parent_id))
        elif parent_type == 'wiki':
            return (parent_id, self.env.href.wiki(parent_id))
        return (None, None)

    def _render_form(self, req, parent_type, parent_id):
        perm_map = {'ticket': perm.TICKET_APPEND, 'wiki': perm.WIKI_MODIFY}
        req.perm.assert_permission(perm_map[parent_type])

        text, link = self._get_parent_link(parent_type, parent_id)
        req.hdf['attachment'] = {
            'mode': 'new',
            'author': util.get_reporter_id(req),
            'parent': {'type': parent_type, 'id': parent_id, 'name': text,
                       'href': link}
        }

    def _render_view(self, req, attachment):
        perm_map = {'ticket': perm.TICKET_VIEW, 'wiki': perm.WIKI_VIEW}
        req.perm.assert_permission(perm_map[attachment.parent_type])

        req.check_modified(attachment.time)
        mime_type = get_mimetype(attachment.filename) or 'application/octet-stream'
        charset = self.config.get('trac', 'default_charset')

        if req.args.get('format') in ('raw', 'txt'):
            # Render raw file
            self._render_raw(req, attachment, mime_type, charset)
            return

        # Render HTML view
        text, link = self._get_parent_link(attachment.parent_type,
                                           attachment.parent_id)
        add_link(req, 'up', link, text)

        req.hdf['title'] = '%s%s: %s' % (attachment.parent_type == 'ticket' and '#' or '',
                                         attachment.parent_id,
                                         attachment.filename)
        req.hdf['attachment'] = attachment_to_hdf(self.env, None, req, attachment)
        req.hdf['attachment.parent'] = {
            'type': attachment.parent_type, 'id': attachment.parent_id,
            'name': text, 'href': link,
        }

        raw_href = self.env.href.attachment(attachment.parent_type,
                                            attachment.parent_id,
                                            attachment.filename,
                                            format='raw')
        add_link(req, 'alternate', raw_href, 'Original Format', mime_type)
        req.hdf['attachment.raw_href'] = raw_href

        perm_map = {'ticket': perm.TICKET_ADMIN, 'wiki': perm.WIKI_DELETE}
        if req.perm.has_permission(perm_map[attachment.parent_type]):
            req.hdf['attachment.can_delete'] = 1

        self.log.debug("Rendering preview of file %s with mime-type %s"
                       % (attachment.filename, mime_type))
        fd = attachment.open()
        try:
            data = fd.read(self.DISP_MAX_FILE_SIZE)
            if not is_binary(data):
                data = util.to_utf8(data, charset)
                add_link(req, 'alternate',
                         self.env.href.attachment(attachment.parent_type,
                                                  attachment.parent_id,
                                                  attachment.filename,
                                                  format='txt'),
                         'Plain Text', mime_type)
            if len(data) >= self.DISP_MAX_FILE_SIZE:
                req.hdf['attachment.max_file_size_reached'] = 1
                req.hdf['attachment.max_file_size'] = self.DISP_MAX_FILE_SIZE
                vdata = ''
            else:
                mimeview = Mimeview(self.env)
                vdata = mimeview.display(mime_type, data, attachment.filename)
            req.hdf['attachment.preview'] = vdata
        finally:
            fd.close()

    def _render_raw(self, req, attachment, mime_type, charset):
        fd = attachment.open()
        try:
            data = fd.read(self.CHUNK_SIZE)
            if not is_binary(data):
                if req.args.get('format') == 'txt':
                    mime_type = 'text/plain'
                mime_type = mime_type + ';charset=' + charset

            req.send_response(200)
            req.send_header('Content-Type', mime_type)
            req.send_header('Content-Length', str(attachment.size))
            req.send_header('Last-Modified', util.http_date(attachment.time))
            req.end_headers()

            while data:
                req.write(data)
                data = fd.read(self.CHUNK_SIZE)
        finally:
            fd.close()
