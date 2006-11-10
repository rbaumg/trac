# -*- coding: utf-8 -*-
#
# Copyright (C) 2003-2006 Edgewall Software
# Copyright (C) 2003-2005 Jonas Borgström <jonas@edgewall.com>
# Copyright (C) 2004-2006 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2005-2006 Christian Boos <cboos@neuf.fr>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.
#
# Author: Jonas Borgström <jonas@edgewall.com>
#         Christopher Lenz <cmlenz@gmx.de>
#         Christian Boos <cboos@neuf.fr>

from datetime import datetime
import posixpath
import re
from StringIO import StringIO
import time

from genshi.builder import tag

from trac import util
from trac.config import BoolOption, IntOption
from trac.core import *
from trac.mimeview import Mimeview, is_binary
from trac.perm import IPermissionRequestor
from trac.Search import ISearchSource, search_to_sql, shorten_result
from trac.timeline.api import ITimelineEventProvider, TimelineEvent
from trac.util import embedded_numbers
from trac.util.compat import sorted
from trac.util.datefmt import pretty_timedelta, utc
from trac.util.html import html, escape, unescape, Markup
from trac.util.text import unicode_urlencode, shorten_line, CRLF
from trac.versioncontrol import Changeset, Node, NoSuchChangeset
from trac.versioncontrol.diff import get_diff_options, diff_blocks, \
                                     unified_diff
from trac.versioncontrol.web_ui.util import render_node_property
from trac.web import IRequestHandler, RequestDone
from trac.web.chrome import add_link, add_script, add_stylesheet, \
                            INavigationContributor
from trac.wiki import IWikiSyntaxProvider, Formatter


class ChangesetModule(Component):
    """Provide flexible functionality for showing sets of differences.

    If the differences shown are coming from a specific changeset,
    then that changeset informations can be shown too.

    In addition, it is possible to show only a subset of the changeset:
    Only the changes affecting a given path will be shown.
    This is called the ''restricted'' changeset.

    But the differences can also be computed in a more general way,
    between two arbitrary paths and/or between two arbitrary revisions.
    In that case, there's no changeset information displayed.
    """

    implements(INavigationContributor, IPermissionRequestor, IRequestHandler,
               ITimelineEventProvider, IWikiSyntaxProvider, ISearchSource)

    timeline_show_files = IntOption('timeline', 'changeset_show_files', 0,
        """Number of files to show (`-1` for unlimited, `0` to disable).""")

    timeline_long_messages = BoolOption('timeline', 'changeset_long_messages',
                                        'false',
        """Whether wiki-formatted changeset messages should be multiline or not.

        If this option is not specified or is false and `wiki_format_messages`
        is set to true, changeset messages will be single line only, losing
        some formatting (bullet points, etc).""")

    max_diff_files = IntOption('changeset', 'max_diff_files', 0,
        """Maximum number of modified files for which the changeset view will
        attempt to show the diffs inlined (''since 0.10'').""")

    max_diff_bytes = IntOption('changeset', 'max_diff_bytes', 10000000,
        """Maximum total size in bytes of the modified files (their old size
        plus their new size) for which the changeset view will attempt to show
        the diffs inlined (''since 0.10'').""")

    wiki_format_messages = BoolOption('changeset', 'wiki_format_messages',
                                      'true',
        """Whether wiki formatting should be applied to changeset messages.
        
        If this option is disabled, changeset messages will be rendered as
        pre-formatted text.""")

    # INavigationContributor methods

    def get_active_navigation_item(self, req):
        return 'browser'

    def get_navigation_items(self, req):
        return []

    # IPermissionRequestor methods

    def get_permission_actions(self):
        return ['CHANGESET_VIEW']

    # IRequestHandler methods

    _request_re = re.compile(r"/changeset(?:/([^/]+))?(/.*)?$")

    def match_request(self, req):
        match = re.match(self._request_re, req.path_info)
        if match:
            new, new_path = match.groups()
            if new:
                req.args['new'] = new
            if new_path:
                req.args['new_path'] = new_path
            return True

    def process_request(self, req):
        """The appropriate mode of operation is inferred from the request
        parameters:

         * If `new_path` and `old_path` are equal (or `old_path` is omitted)
           and `new` and `old` are equal (or `old` is omitted),
           then we're about to view a revision Changeset: `chgset` is True.
           Furthermore, if the path is not the root, the changeset is
           ''restricted'' to that path (only the changes affecting that path,
           its children or its ancestor directories will be shown).
         * In any other case, the set of changes corresponds to arbitrary
           differences between path@rev pairs. If `new_path` and `old_path`
           are equal, the ''restricted'' flag will also be set, meaning in this
           case that the differences between two revisions are restricted to
           those occurring on that path.

        In any case, either path@rev pairs must exist.
        """
        req.perm.require('CHANGESET_VIEW')

        # -- retrieve arguments
        new_path = req.args.get('new_path')
        new = req.args.get('new')
        old_path = req.args.get('old_path')
        old = req.args.get('old')

        if old and '@' in old:
            old_path, old = unescape(old).split('@')
        if new and '@' in new:
            new_path, new = unescape(new).split('@')

        # -- normalize and check for special case
        repos = self.env.get_repository(req.authname)
        new_path = repos.normalize_path(new_path)
        new = repos.normalize_rev(new)

        repos.authz.assert_permission_for_changeset(new)

        old_path = repos.normalize_path(old_path or new_path)
        old = repos.normalize_rev(old or new)

        if old_path == new_path and old == new: # revert to Changeset
            old_path = old = None

        style, options, diff_data = get_diff_options(req)

        # -- setup the `chgset` and `restricted` flags, see docstring above.
        chgset = not old and not old_path
        if chgset:
            restricted = new_path not in ('', '/') # (subset or not)
        else:
            restricted = old_path == new_path # (same path or not)

        # -- redirect if changing the diff options
        if req.args.has_key('update'):
            if chgset:
                if restricted:
                    req.redirect(req.href.changeset(new, new_path))
                else:
                    req.redirect(req.href.changeset(new))
            else:
                req.redirect(req.href.changeset(new, new_path, old=old,
                                                old_path=old_path))

        # -- preparing the data
        if chgset:
            prev = repos.get_node(new_path, new).get_previous()
            if prev:
                prev_path, prev_rev = prev[:2]
            else:
                prev_path, prev_rev = new_path, repos.previous_rev(new)
            data = {'old_path': prev_path, 'old_rev': prev_rev,
                    'new_path': new_path, 'new_rev': new}
        else:
            if not new:
                new = repos.youngest_rev
            elif not old:
                old = repos.youngest_rev
            if not old_path:
                old_path = new_path
            data = {'old_path': old_path, 'old_rev': old,
                    'new_path': new_path, 'new_rev': new}
        data['diff'] = diff_data
        data['wiki_format_messages'] = self.wiki_format_messages
        
        if chgset:
            chgset = repos.get_changeset(new)
            # TODO: find a cheaper way to reimplement r2636
            req.check_modified(chgset.date, [
                style, ''.join(options), repos.name,
                repos.rev_older_than(new, repos.youngest_rev),
                chgset.message,
                pretty_timedelta(chgset.date, None, 3600)])

        format = req.args.get('format')

        if format in ['diff', 'zip']:
            req.perm.require('FILE_VIEW')
            # choosing an appropriate filename
            rpath = new_path.replace('/','_')
            if chgset:
                if restricted:
                    filename = 'changeset_%s_r%s' % (rpath, new)
                else:
                    filename = 'changeset_r%s' % new
            else:
                if restricted:
                    filename = 'diff-%s-from-r%s-to-r%s' \
                                  % (rpath, old, new)
                elif old_path == '/': # special case for download (#238)
                    filename = '%s-r%s' % (rpath, old)
                else:
                    filename = 'diff-from-%s-r%s-to-%s-r%s' \
                               % (old_path.replace('/','_'), old, rpath, new)
            if format == 'diff':
                self._render_diff(req, filename, repos, data)
            elif format == 'zip':
                self._render_zip(req, filename, repos, data)

        # -- HTML format
        self._render_html(req, repos, chgset, restricted, data)
        
        if chgset:
            diff_params = 'new=%s' % new
        else:
            diff_params = unicode_urlencode({'new_path': new_path,
                                             'new': new,
                                             'old_path': old_path,
                                             'old': old})
        add_link(req, 'alternate', '?format=diff&'+diff_params, 'Unified Diff',
                 'text/plain', 'diff')
        add_link(req, 'alternate', '?format=zip&'+diff_params, 'Zip Archive',
                 'application/zip', 'zip')
        add_stylesheet(req, 'common/css/changeset.css')
        add_stylesheet(req, 'common/css/diff.css')
        add_stylesheet(req, 'common/css/code.css')
        return 'changeset.html', data, None

    # Internal methods

    def _render_html(self, req, repos, chgset, restricted, data):
        """HTML version"""
        data['chgset'] = chgset and True
        data['restricted'] = restricted

        if chgset: # Changeset Mode (possibly restricted on a path)
            path, rev = data['new_path'], data['new_rev']

            # -- getting the change summary from the Changeset.get_changes
            def get_changes():
                for npath, kind, change, opath, orev in chgset.get_changes():
                    old_node = new_node = None
                    if (restricted and
                        not (npath == path or                # same path
                             npath.startswith(path + '/') or # npath is below
                             path.startswith(npath + '/'))): # npath is above
                        continue
                    if change != Changeset.ADD:
                        old_node = repos.get_node(opath, orev)
                    if change != Changeset.DELETE:
                        new_node = repos.get_node(npath, rev)
                    yield old_node, new_node, kind, change

            def _changeset_title(rev):
                if restricted:
                    return 'Changeset %s for %s' % (rev, path)
                else:
                    return 'Changeset %s' % rev

            title = _changeset_title(rev)
            properties = []
            for name, value, wikiflag, htmlclass in chgset.get_properties():
                properties.append({'name': name, 'value': value,
                                   'htmlclass': htmlclass,
                                   'wikiflag': wikiflag})

            data['changeset'] = chgset
            data['changeset_properties'] = properties
            oldest_rev = repos.oldest_rev
            if chgset.rev != oldest_rev:
                if restricted:
                    prev = repos.get_node(path, rev).get_previous()
                    if prev:
                        prev_path, prev_rev = prev[:2]
                        if prev_rev:
                            prev_href = req.href.changeset(prev_rev, prev_path)
                    else:
                        prev_path = prev_rev = None
                else:
                    add_link(req, 'first', req.href.changeset(oldest_rev),
                             'Changeset %s' % oldest_rev)
                    prev_path = data['old_path']
                    prev_rev = repos.previous_rev(chgset.rev)
                    if prev_rev:
                        prev_href = req.href.changeset(prev_rev)
                if prev_rev:
                    add_link(req, 'prev', prev_href, _changeset_title(prev_rev))
            youngest_rev = repos.youngest_rev
            if str(chgset.rev) != str(youngest_rev):
                if restricted:
                    next_rev = repos.next_rev(chgset.rev, path)
                    if next_rev:
                        if repos.has_node(path, next_rev):
                            next_href = req.href.changeset(next_rev, path)
                        else: # must be a 'D'elete or 'R'ename, show full cset
                            next_href = req.href.changeset(next_rev)
                else:
                    add_link(req, 'last', req.href.changeset(youngest_rev),
                             'Changeset %s' % youngest_rev)
                    next_rev = repos.next_rev(chgset.rev)
                    if next_rev:
                        next_href = req.href.changeset(next_rev)
                if next_rev:
                    add_link(req, 'next', next_href, _changeset_title(next_rev))

        else: # Diff Mode
            # -- getting the change summary from the Repository.get_changes
            def get_changes():
                for d in repos.get_changes(
                    new_path=data['new_path'], new_rev=data['new_rev'],
                    old_path=data['old_path'], old_rev=data['old_rev']):
                    yield d
            title = self.title_for_diff(data)
            
        data['title'] = title

        if 'BROWSER_VIEW' not in req.perm:
            return

        def node_info(node):
            return {'path': node.path,
                    'rev': node.rev,
                    'shortrev': repos.short_rev(node.rev),
                    'href': req.href.browser(node.created_path,
                                             rev=node.created_rev),
                    'title': ('Show revision %s of this file in browser' %
                              node.rev)}
        # Reminder: node.path may not exist at node.rev
        #           as long as node.rev==node.created_rev
        #           ... and data['old_rev'] may have nothing to do
        #           with _that_ node specific history...

        hidden_properties = self.config.getlist('browser', 'hide_properties')

        def _prop_changes(old_node, new_node):
            old_props = old_node.get_properties()
            new_props = new_node.get_properties()
            changed_props = {}
            if old_props != new_props:
                for k,v in old_props.items():
                    if not k in new_props:
                        changed_props[k] = {
                            'old': render_node_property(self.env, k, v)}
                    elif v != new_props[k]:
                        changed_props[k] = {
                            'old': render_node_property(self.env, k, v),
                            'new': render_node_property(self.env, k,
                                                        new_props[k])}
                for k,v in new_props.items():
                    if not k in old_props:
                        changed_props[k] = {
                            'new': render_node_property(self.env, k, v)}
                for k in hidden_properties:
                    if k in changed_props:
                        del changed_props[k]
            changed_properties = []
            for name, props in changed_props.iteritems():
                props.update({'name': name})
                changed_properties.append(props)
            return changed_properties

        def _estimate_changes(old_node, new_node):
            old_size = old_node.get_content_length()
            new_size = new_node.get_content_length()
            return old_size + new_size

        def _content_changes(old_node, new_node):
            """Returns the list of differences.

            The list is empty when no differences between comparable files
            are detected, but the return value is None for non-comparable files.
            """
            old_content = old_node.get_content().read()
            if is_binary(old_content):
                return None

            new_content = new_node.get_content().read()
            if is_binary(new_content):
                return None

            mview = Mimeview(self.env)
            old_content = mview.to_unicode(old_content, old_node.content_type)
            new_content = mview.to_unicode(new_content, new_node.content_type)

            if old_content != new_content:
                options = data['diff']['options']
                context = options.get('contextlines', 3)
                if context < 0:
                    context = None
                tabwidth = self.config['diff'].getint('tab_width') or \
                           self.config['mimeviewer'].getint('tab_width', 8)
                ignore_blank_lines = options.get('ignoreblanklines')
                ignore_case = options.get('ignorecase')
                ignore_space = options.get('ignorewhitespace')
                return diff_blocks(old_content.splitlines(),
                                   new_content.splitlines(),
                                   context, tabwidth,
                                   ignore_blank_lines=ignore_blank_lines,
                                   ignore_case=ignore_case,
                                   ignore_space_changes=ignore_space)
            else:
                return []

        if 'FILE_VIEW' in req.perm:
            diff_bytes = diff_files = 0
            if self.max_diff_bytes or self.max_diff_files:
                for old_node, new_node, kind, change in get_changes():
                    if change in Changeset.DIFF_CHANGES and kind == Node.FILE:
                        diff_files += 1
                        diff_bytes += _estimate_changes(old_node, new_node)
            show_diffs = (not self.max_diff_files or \
                          diff_files <= self.max_diff_files) and \
                         (not self.max_diff_bytes or \
                          diff_bytes <= self.max_diff_bytes or \
                          diff_files == 1)
        else:
            show_diffs = False

        has_diffs = False
        changes = []
        for old_node, new_node, kind, change in get_changes():
            props = []
            diffs = []
            show_entry = change != Changeset.EDIT
            if change in Changeset.DIFF_CHANGES and 'FILE_VIEW' in req.perm:
                assert old_node and new_node
                props = _prop_changes(old_node, new_node)
                if props:
                    show_entry = True
                if kind == Node.FILE and show_diffs:
                    diffs = _content_changes(old_node, new_node)
                    if diffs != []:
                        if diffs:
                            has_diffs = True
                        # elif None (means: manually compare to (previous))
                        show_entry = True
            if show_entry or not show_diffs:
                info = {'change': change,
                        'old': old_node and node_info(old_node),
                        'new': new_node and node_info(new_node),
                        'props': props,
                        'diffs': diffs}
                if change in Changeset.DIFF_CHANGES and not show_diffs:
                    if chgset:
                        diff_href = req.href.changeset(new_node.rev,
                                                       new_node.path)
                    else:
                        diff_href = req.href.changeset(
                            new_node.created_rev, new_node.created_path,
                            old=old_node.created_rev,
                            old_path=old_node.created_path)
                    info['diff_href'] = diff_href
            else:
                info = None
            changes.append(info) # the sequence should be immutable

        data.update({'has_diffs': has_diffs, 'changes': changes,
                     'longcol': 'Revision', 'shortcol': 'r'})
        return data

    def _render_diff(self, req, filename, repos, data):
        """Raw Unified Diff version"""
        req.send_response(200)
        req.send_header('Content-Type', 'text/plain;charset=utf-8')
        req.send_header('Content-Disposition', 'inline;'
                        'filename=%s.diff' % filename)
        req.end_headers()

        mimeview = Mimeview(self.env)
        for old_node, new_node, kind, change in repos.get_changes(
            new_path=data['new_path'], new_rev=data['new_rev'],
            old_path=data['old_path'], old_rev=data['old_rev']):
            # TODO: Property changes

            # Content changes
            if kind == Node.DIRECTORY:
                continue

            new_content = old_content = ''
            new_node_info = old_node_info = ('','')
            mimeview = Mimeview(self.env)

            if old_node:
                old_content = old_node.get_content().read()
                if is_binary(old_content):
                    continue
                old_node_info = (old_node.path, old_node.rev)
                old_content = mimeview.to_unicode(old_content,
                                                  old_node.content_type)
            if new_node:
                new_content = new_node.get_content().read()
                if is_binary(new_content):
                    continue
                new_node_info = (new_node.path, new_node.rev)
                new_path = new_node.path
                new_content = mimeview.to_unicode(new_content,
                                                  new_node.content_type)
            else:
                old_node_path = repos.normalize_path(old_node.path)
                diff_old_path = repos.normalize_path(data['old_path'])
                new_path = posixpath.join(data['new_path'],
                                          old_node_path[len(diff_old_path)+1:])

            if old_content != new_content:
                options = data['diff']['options']
                context = options.get('contextlines', 3)
                if context < 0:
                    context = 3 # FIXME: unified_diff bugs with context=None
                ignore_blank_lines = options.get('ignoreblanklines')
                ignore_case = options.get('ignorecase')
                ignore_space = options.get('ignorewhitespace')
                if not old_node_info[0]:
                    old_node_info = new_node_info # support for 'A'dd changes
                req.write('Index: ' + new_path + CRLF)
                req.write('=' * 67 + CRLF)
                req.write('--- %s (revision %s)' % old_node_info + CRLF)
                req.write('+++ %s (revision %s)' % new_node_info + CRLF)
                for line in unified_diff(old_content.splitlines(),
                                         new_content.splitlines(), context,
                                         ignore_blank_lines=ignore_blank_lines,
                                         ignore_case=ignore_case,
                                         ignore_space_changes=ignore_space):
                    req.write(line + CRLF)
        raise RequestDone

    def _render_zip(self, req, filename, repos, data):
        """ZIP archive with all the added and/or modified files."""
        new_rev = data['new_rev']
        req.send_response(200)
        req.send_header('Content-Type', 'application/zip')
        req.send_header('Content-Disposition', 'attachment;'
                        'filename=%s.zip' % filename)

        from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

        buf = StringIO()
        zipfile = ZipFile(buf, 'w', ZIP_DEFLATED)
        for old_node, new_node, kind, change in repos.get_changes(
            new_path=data['new_path'], new_rev=data['new_rev'],
            old_path=data['old_path'], old_rev=data['old_rev']):
            if kind == Node.FILE and change != Changeset.DELETE:
                assert new_node
                zipinfo = ZipInfo()
                zipinfo.filename = new_node.path.encode('utf-8')
                # Note: unicode filenames are not supported by zipfile.
                # UTF-8 is not supported by all Zip tools either,
                # but as some does, I think UTF-8 is the best option here.
                zipinfo.date_time = new_node.last_modified.utctimetuple()[:6]
                zipinfo.compress_type = ZIP_DEFLATED
                zipfile.writestr(zipinfo, new_node.get_content().read())
        zipfile.close()

        buf.seek(0, 2) # be sure to be at the end
        req.send_header("Content-Length", buf.tell())
        req.end_headers()

        req.write(buf.getvalue())
        raise RequestDone

    def title_for_diff(self, data):
        if data['new_path'] == data['old_path']: # ''diff between 2 revisions'' mode
            return 'Diff r%s:%s for %s' \
                   % (data['old_rev'] or 'latest', data['new_rev'] or 'latest',
                      data['new_path'] or '/')
        else:                              # ''generalized diff'' mode
            return 'Diff from %s@%s to %s@%s' \
                   % (data['old_path'] or '/', data['old_rev'] or 'latest',
                      data['new_path'] or '/', data['new_rev'] or 'latest')

    # ITimelineEventProvider methods

    def get_timeline_filters(self, req):
        if 'CHANGESET_VIEW' in req.perm:
            yield ('changeset', 'Repository checkins')

    def get_timeline_events(self, req, start, stop, filters):
        if 'changeset' in filters:
            show_files = self.timeline_show_files
            wiki_format = self.wiki_format_messages
            long_messages = self.timeline_long_messages
            
            repos = self.env.get_repository(req.authname)
            
            for chgset in repos.get_changesets(start, stop):
                shortlog = shorten_line(chgset.message or '')
                title = html('Changeset ', html.em('[%s]' % chgset.rev), ': ',
                             shortlog)
                if wiki_format:
                    message = chgset.message
                    markup = ''
                else:
                    message = None
                    markup = long_messages and chgset.message or shortlog
                    
                if show_files and 'BROWSER_VIEW' in req.perm:
                    files = []
                    for chg in chgset.get_changes():
                        if show_files > 0 and len(files) >= show_files:
                            files.append(html.LI(Markup('&hellip;')))
                            break
                        files.append(html.LI(html.DIV(class_=chg[2]),
                                             chg[0] or '/'))
                    markup = html(html.UL(files, class_="changes"), markup)

                event = TimelineEvent('changeset', title,
                                      req.href.changeset(chgset.rev), markup)
                event.set_changeinfo(chgset.date, chgset.author, True)
                event.set_context('changeset', chgset.rev, message)
                event.use_oneliner = not long_messages
                yield event

    # IWikiSyntaxProvider methods

    CHANGESET_ID = r"(?:\d+|[a-fA-F\d]{6,})" # only "long enough" hexa ids

    def get_wiki_syntax(self):
        yield (
            # [...] form: start with optional intertrac: [T... or [trac ...
            r"!?\[(?P<it_changeset>%s\s*)" % Formatter.INTERTRAC_SCHEME +
            # hex digits + optional /path for the restricted changeset
            r"%s(?:/[^\]]*)?\]|" % self.CHANGESET_ID +
            # r... form: allow r1 but not r1:2 (handled by the log syntax)
            r"(?:\b|!)r%s\b(?!:%s)" % ((self.CHANGESET_ID,)*2),
            lambda x, y, z:
            self._format_changeset_link(x, 'changeset',
                                        y[0] == 'r' and y[1:] or y[1:-1],
                                        y, z))

    def get_link_resolvers(self):
        yield ('changeset', self._format_changeset_link)
        yield ('diff', self._format_diff_link)

    def _format_changeset_link(self, formatter, ns, chgset, label,
                               fullmatch=None):
        intertrac = formatter.shorthand_intertrac_helper(ns, chgset, label,
                                                         fullmatch)
        if intertrac:
            return intertrac
        sep = chgset.find('/')
        if sep > 0:
            rev, path = chgset[:sep], chgset[sep:]
        else:
            rev, path = chgset, None
        try:
            changeset = self.env.get_repository().get_changeset(rev)
            return html.A(label, class_="changeset",
                          title=shorten_line(changeset.message),
                          href=formatter.href.changeset(rev, path))
        except NoSuchChangeset:
            return html.A(label, class_="missing changeset",
                          href=formatter.href.changeset(rev, path),
                          rel="nofollow")

    def _format_diff_link(self, formatter, ns, params, label):
        def pathrev(path):
            if '@' in path:
                return path.split('@', 1)
            else:
                return (path, None)
        if '//' in params:
            p1, p2 = params.split('//', 1)
            old, new = pathrev(p1), pathrev(p2)
            data = {'old_path': old[0], 'old_rev': old[1],
                    'new_path': new[0], 'new_rev': new[1]}
        else:
            old_path, old_rev = pathrev(params)
            new_rev = None
            if old_rev and ':' in old_rev:
                old_rev, new_rev = old_rev.split(':', 1)
            data = {'old_path': old_path, 'old_rev': old_rev,
                    'new_path': old_path, 'new_rev': new_rev}
        title = self.title_for_diff(data)
        href = formatter.href.changeset(new_path=data['new_path'] or None,
                                        new=data['new_rev'],
                                        old_path=data['old_path'] or None,
                                        old=data['old_rev'])
        return html.A(label, class_="changeset", title=title, href=href)

    # ISearchSource methods

    def get_search_filters(self, req):
        if 'CHANGESET_VIEW' in req.perm:
            yield ('changeset', 'Changesets')

    def get_search_results(self, req, terms, filters):
        if not 'changeset' in filters:
            return
        repos = self.env.get_repository(req.authname)
        db = self.env.get_db_cnx()
        sql, args = search_to_sql(db, ['rev', 'message', 'author'], terms)
        cursor = db.cursor()
        cursor.execute("SELECT rev,time,author,message "
                       "FROM revision WHERE " + sql, args)
        for rev, ts, author, log in cursor:
            if not repos.authz.has_permission_for_changeset(rev):
                continue
            yield (req.href.changeset(rev),
                   '[%s]: %s' % (rev, shorten_line(log)),
                   datetime.fromtimestamp(ts, utc), author,
                   shorten_result(log, terms))


class AnyDiffModule(Component):

    implements(IRequestHandler)

    # IRequestHandler methods

    def match_request(self, req):
        return re.match(r'/diff$', req.path_info)

    def process_request(self, req):
        repos = self.env.get_repository(req.authname)

        if req.get_header('X-Requested-With') == 'XMLHttpRequest':
            dirname, prefix = posixpath.split(req.args.get('q'))
            prefix = prefix.lower()
            node = repos.get_node(dirname)

            def kind_order(entry):
                def name_order(entry):
                    return embedded_numbers(entry.name)
                return entry.isfile, name_order(entry)

            html = tag.ul(
                [tag.li(is_dir and tag.b(path) or path)
                 for e in sorted(node.get_entries(), key=kind_order)
                 for is_dir, path in [(e.isdir, '/' + e.path.lstrip('/'))]
                 if e.name.lower().startswith(prefix)]
            )

            req.write(html.generate().render('xhtml'))
            return

        # -- retrieve arguments
        new_path = req.args.get('new_path')
        new_rev = req.args.get('new_rev')
        old_path = req.args.get('old_path')
        old_rev = req.args.get('old_rev')

        # -- normalize
        new_path = repos.normalize_path(new_path)
        if not new_path.startswith('/'):
            new_path = '/' + new_path
        new_rev = repos.normalize_rev(new_rev)
        old_path = repos.normalize_path(old_path)
        if not old_path.startswith('/'):
            old_path = '/' + old_path
        old_rev = repos.normalize_rev(old_rev)

        repos.authz.assert_permission_for_changeset(new_rev)
        repos.authz.assert_permission_for_changeset(old_rev)

        # -- prepare rendering
        data = {'new_path': new_path, 'new_rev': new_rev,
                'old_path': old_path, 'old_rev': old_rev}

        add_script(req, 'common/js/suggest.js')
        return 'diff_form.html', data, None
