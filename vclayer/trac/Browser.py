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

from trac import perm, util
from trac.Module import Module
from trac.WikiFormatter import wiki_to_oneliner

import time
import posixpath


CHUNK_SIZE = 4096
DISP_MAX_FILE_SIZE = 256 * 1024

def _short_log_message(env, db, message):
    message = util.shorten_line(util.wiki_escape_newline(message))
    return wiki_to_oneliner(message, env, db)

def _get_changes(env, db, repos, revs):
    changes = {}
    for rev in filter(lambda x: x in revs, revs):
        changeset = repos.get_changeset(rev)
        changes[rev] = {
            'date_seconds': changeset.date,
            'date': time.strftime('%x %X', time.localtime(changeset.date)),
            'age': util.pretty_timedelta(changeset.date),
            'author': changeset.author or 'anonymous',
            'message': _short_log_message(env, db, changeset.message)
        }
    return changes

def _get_path_links(href, path, rev):
    links = []
    parts = path.split('/')
    if not parts[-1]:
        parts.pop()
    path = '/'
    for i,part in util.enum(parts):
        path = path + part + '/'
        links.append({
            'name': part or 'root',
            'href': href.browser(path, rev)
        })
    return links


class BrowserModule(Module):
    template_name = 'browser.cs'

    def render(self, req):
        rev = req.args.get('rev')
        path = req.args.get('path', '/')
        order = req.args.get('order', 'name').lower()
        desc = req.args.has_key('desc')

#       self.authzperm.assert_permission (path)

        repos = self.env.get_repository()

        req.hdf['title'] = path
        req.hdf['browser'] = {
            'path': path,
            'order': order,
            'desc': desc and 1 or 0,
            'log_href': self.env.href.log(path)
        }

        path_links = _get_path_links(self.env.href, path, rev)
        req.hdf['browser.path'] = path_links
        if len(path_links) > 1:
            self.add_link('up', path_links[-2]['href'], 'Parent directory')

        node = repos.get_node(path, rev)
        if node.isdir:
            req.hdf['node.is_dir'] = 1
            self.render_directory(req, repos, node, rev, order, desc)
        else:
            self.render_file(req, repos, node, rev)

        req.hdf['browser.revision'] = repos.rev

    def render_directory(self, req, repos, node, rev=None, order=None, desc=0):
        self.perm.assert_permission(perm.BROWSER_VIEW)

        info = []
        for entry in node.get_entries():
            entry_rev = rev and entry.rev
            info.append({
                'name': entry.name,
                'fullpath': entry.path,
                'is_dir': int(entry.isdir),
                'rev': entry.rev,
                'permission': 1, # FIXME
                'log_href': self.env.href.log(entry.path, entry_rev),
                'browser_href': self.env.href.browser(entry.path, entry_rev)
            })
        changes = _get_changes(self.env, self.db, repos,
                               [i['rev'] for i in info])

        def cmp_func(a, b):
            dir_cmp = (a['is_dir'] and -1 or 0) + (b['is_dir'] and 1 or 0)
            if dir_cmp:
                return dir_cmp
            neg = desc and -1 or 1
            if order == 'date':
                return neg * cmp(changes[b['rev']]['date_seconds'],
                                 changes[a['rev']]['date_seconds'])
            else:
                return neg * cmp(a['name'].lower(), b['name'].lower())
        info.sort(cmp_func)

        req.hdf['browser.items'] = info
        req.hdf['browser.changes'] = changes

    def render_file(self, req, repos, node, rev=None):
        self.perm.assert_permission(perm.FILE_VIEW)

        changeset = repos.get_changeset(node.rev)
        req.hdf['node'] = {
            'rev': node.rev,
            'changeset_href': self.env.href.changeset(node.rev),
            'date': time.strftime('%x %X', time.localtime(changeset.date)),
            'age': util.pretty_timedelta(changeset.date),
            'author': changeset.author or 'anonymous',
            'message': _short_log_message(self.env, self.db, changeset.message)
        }

        content = node.get_content()
        first_chunk = content.read(DISP_MAX_FILE_SIZE)

        mime_type = node.content_type
        if not mime_type or mime_type == 'application/octet-stream':
            mime_type = self.env.mimeview.get_mimetype(node.name)
            if not mime_type:
                if self.env.mimeview.is_binary(first_chunk):
                    mime_type = 'application/octet-stream'
                else:
                    mime_type = 'text/plain'

        # We don't have to guess if the charset is specified in the
        # svn:mime-type property
        ctpos = mime_type.find('charset=')
        if ctpos >= 0:
            charset = mime_type[ctpos + 8:]
        else:
            charset = self.env.get_config('trac', 'default_charset',
                                          'iso-8859-15')

        if req.args.has_key('format'):
            # We need to tuck away some info so that it is available in the
            # display_xxx methods. It'd be better to store them with the
            # request, but this will do as long as modules don't outlive
            # requests
            self.node = node
            self.content = content
            self.first_chunk = first_chunk
            self.charset = charset
            return

        # Generate HTML preview
        content = util.to_utf8(first_chunk, charset)
        if len(content) == DISP_MAX_FILE_SIZE:
            req.hdf['browser.max_file_size_reached'] = 1
            req.hdf['browser.max_file_size'] = DISP_MAX_FILE_SIZE
            preview = ' '
        else:
            preview = self.env.mimeview.display(content, filename=node.name,
                                                rev=node.rev,
                                                mimetype=mime_type)
        req.hdf['browser.preview'] = preview

        raw_href = self.env.href.browser(node.path, rev and node.rev, 'raw')
        self.add_link('alternate', raw_href, 'Original Format', mime_type)

    def display_raw(self, req):
        node = self.node

        req.send_response(200)
        req.send_header('Content-Type', node.content_type)
        req.send_header('Content-Length', node.content_length)
        req.send_header('Last-Modified',
                        time.strftime("%a, %d %b %Y %H:%M:%S GMT",
                                      node.last_modified))
        req.end_headers()

        req.write(self.first_chunk)
        content = self.content
        while 1:
            chunk = content.read(CHUNK_SIZE)
            if not chunk:
                break
            req.write(chunk)


class FileModule(Module):
    """
    Legacy module that redirects to the browser for URI backwards compatibility.
    """

    def render(self, req):
        path = req.args.get('path', '/')
        rev = req.args.get('rev')
        # FIXME: This should be a permanent redirect
        req.redirect(self.env.href.browser(path, rev))


class LogModule(Module):
    template_name = 'log.cs'
    template_rss_name = 'log_rss.cs'

    def render(self, req):
        self.perm.assert_permission(perm.LOG_VIEW)

        path = req.args.get('path', '/')
        rev = req.args.get('rev')

#       self.authzperm.assert_permission(self.path)

        req.hdf['title'] = path + ' (log)'
        req.hdf['log.path'] = path
        req.hdf['log.browser_href'] = self.env.href.browser(path)

        path_links = _get_path_links(self.env.href, path, rev)
        req.hdf['log.path'] = path_links
        if path_links:
            self.add_link('up', path_links[-1]['href'], 'Parent directory')

        repos = self.env.get_repository()
        node = repos.get_node(path, rev)
        if not node:
            # FIXME: we should send a 404 error here
            raise util.TracError("The file or directory '%s' doesn't exist in "
                                 "the repository at revision %d." % (path, rev),
                                 'Nonexistent path')
        info = []
        for old_path, old_rev in node.get_history():
            info.append({
                'rev': old_rev,
                'browser_href': self.env.href.browser(old_path, old_rev),
                'changeset_href': self.env.href.changeset(old_rev)
            })
        req.hdf['log.items'] = info
        req.hdf['log.changes'] = _get_changes(self.env, self.db, repos,
                                              [i['rev'] for i in info])

        rss_href = self.env.href.log(path, rev=rev, format='rss')
        self.add_link('alternate', rss_href, 'RSS Feed', 'application/rss+xml',
                      'rss')

    def display_rss(self, req):
        req.display(self.template_rss_name, 'application/rss+xml')
