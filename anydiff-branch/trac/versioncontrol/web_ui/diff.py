# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003-2005 Edgewall Software
# Copyright (C) 2003-2005 Jonas Borgstr�m <jonas@edgewall.com>
# Copyright (C) 2004-2005 Christopher Lenz <cmlenz@gmx.de>
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
# Author: Jonas Borgstr�m <jonas@edgewall.com>
#         Christopher Lenz <cmlenz@gmx.de>
#         Christian Boos <cboos@neuf.fr>

from __future__ import generators
import time
import re
import posixpath
from urllib import urlencode

from trac import mimeview, util
from trac.core import *
from trac.perm import IPermissionRequestor
from trac.versioncontrol import Changeset, Node
from trac.versioncontrol.diff import get_diff_options, hdf_diff, unified_diff
from trac.web import IRequestHandler
from trac.web.chrome import add_link, add_stylesheet
from trac.wiki import wiki_to_html, IWikiSyntaxProvider

class DiffArgs(dict):
    def __getattr__(self,str):
        return self[str]
    

class ChangesPermission(Component):
    """Simple permission provider for changes related modules."""
    
    implements(IPermissionRequestor)
    
    def get_permission_actions(self):
        return ['CHANGESET_VIEW']
    

class AbstractDiffModule(Component):
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

    abstract = True

    implements(IRequestHandler)

    # IRequestHandler methods

    def match_request(self, req):
        raise NotImplementedError

    def process_request(self, req):
        """The appropriate mode of operation is inferred from
        the request parameters:
         * If `old` and `new` parameters are given, it will be an
           arbitrary set of differences: `chgset` is False.
           * If `old_path` is given and is different from `path`,
             it's a generalized diff, from `old_path@old`
             to `path@new`: `restricted` is False.
           * Otherwise those are differences between two arbitrary revisions
             of a given path: `restricted` is True.
         * Otherwise, we are dealing with a changeset only: `chgset` is True.
           * If the `path` is not empty or not the root, then only
             the changes affecting that path (i.e. itself, children or
             ancestors) will be considered: `restricted` is True.
           * Otherwise, it's the full changeset: `restricted` is False.
         
        In any case, the given path@rev pair must exist.
        """
        req.perm.assert_permission('CHANGESET_VIEW')
        
        # -- retrieve arguments
        path = req.args.get('path')
        rev = req.args.get('rev')
        old = req.args.get('old')
        new = req.args.get('new')
        old_path = req.args.get('old_path')

        # -- normalize and check for special case
        repos = self.env.get_repository(req.authname)
        path = repos.normalize_path(path)
        rev = repos.normalize_rev(rev)
        old_path = repos.normalize_path(old_path)
        
        if old_path == path and old and old == new: # revert to Changeset
            rev = old
            old_path = old = new = None

        diff_options = get_diff_options(req)

        # -- setup the `chgset` and `restricted` flags, see docstring above.
        chgset = not old and not new and not old_path
        if chgset:
            restricted = path != '' and path != '/' # (subset or not)
        else:
            restricted = old_path == path # (same path or not)

        # -- redirect if changing the diff options
        if req.args.has_key('update'):
            if chgset:
                if restricted:
                    req.redirect(self.env.href.diff(path, rev=rev))
                else:
                    req.redirect(self.env.href.changeset(rev))
            else:
                req.redirect(self.env.href.diff(path, new=new,
                                                old_path=old_path, old=old))

        # -- preparing the diff arguments
        if chgset:
            prev = repos.get_node(path, rev).get_previous()
            if prev:
                prev_path, prev_rev = prev[:2]
            else:
                prev_path, prev_rev = path, repos.previous_rev(rev)
            diff_args = DiffArgs(old_path=prev_path, old_rev=prev_rev,
                                 new_path=path, new_rev=rev)
        else:
            if not new:
                new = repos.youngest_rev
            elif not old:
                old = repos.youngest_rev
            if not old_path:
                old_path = path
            diff_args = DiffArgs(old_path=old_path, old_rev=old,
                                 new_path=path, new_rev=new)
        if chgset:
            chgset = repos.get_changeset(rev)
            req.check_modified(chgset.date,
                               diff_options[0] + ''.join(diff_options[1]))
        else:
            pass # FIXME: what date should we choose for a diff?

        req.hdf['diff'] = diff_args

        format = req.args.get('format')

        if format in ['diff', 'zip']:
            # choosing an appropriate filename
            rpath = path.replace('/','_')
            if chgset:
                if restricted:
                    filename = 'changeset_%s_r%s' % (rpath, rev)
                else:
                    filename = 'changeset_r%s' % rev
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
                self._render_diff(req, filename, repos, diff_args,
                                  diff_options)
                return
            elif format == 'zip':
                self._render_zip(req, filename, repos, diff_args)
                return

        # -- HTML format
        self._render_html(req, repos, chgset, restricted,
                          diff_args, diff_options)
        if chgset:
            diff_params = 'rev=%s' % rev
        else:
            diff_params = urlencode({'path': path,
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
        return 'diff.cs', None


    # Internal methods

    def _render_html(self, req, repos, chgset, restricted, diff, diff_options):
        """
        HTML version
        """
        req.hdf['diff'] = {
            'chgset': chgset and True,
            'restricted': restricted,
            'href': { 'new_rev': self.env.href.changeset(diff.new_rev),
                      'old_rev': self.env.href.changeset(diff.old_rev),
                      'new_path': self.env.href.browser(diff.new_path,
                                                        rev=diff.new_rev),
                      'old_path': self.env.href.browser(diff.old_path,
                                                        rev=diff.old_rev)
                      }
            }
        
        if chgset: # Changeset Mode (possibly restricted on a path)
            path, rev = diff.new_path, diff.new_rev

            # -- getting the deltas from the Changeset.get_changes method
            def get_deltas():
                old_node = new_node = None
                for npath, kind, change, opath, orev in chgset.get_changes():
                    if restricted and \
                           not (npath.startswith(path)      # npath is below
                                or path.startswith(npath)): # npath is above
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
            req.hdf['changeset'] = {
                'revision': chgset.rev,
                'time': time.strftime('%c', time.localtime(chgset.date)),
                'author': util.escape(chgset.author or 'anonymous'),
                'message': wiki_to_html(chgset.message or '--', self.env, req,
                                        escape_newlines=True)
                }
            oldest_rev = repos.oldest_rev
            if chgset.rev != oldest_rev:
                if restricted:
                    prev = repos.get_node(path, rev).get_previous()
                    if prev:
                        prev_path, prev_rev = prev[:2]
                        prev_href = self.env.href.changeset(prev_rev,
                                                            path=prev_path)
                    else:
                        prev_path = prev_rev = None
                else:
                    prev_path = diff.old_path
                    prev_rev = repos.previous_rev(chgset.rev)
                    add_link(req, 'first', self.env.href.changeset(oldest_rev),
                             'Changeset %s' % oldest_rev)
                    prev_href = self.env.href.changeset(prev_rev)
                if prev_rev:
                    add_link(req, 'prev', prev_href, _changeset_title(prev_rev))
            youngest_rev = repos.youngest_rev
            if str(chgset.rev) != str(youngest_rev):
                if restricted:
                    next_rev = next_href = None
                    # FIXME: find an effective way to find the next rev
                else:
                    next_rev = repos.next_rev(chgset.rev)
                    next_href = self.env.href.changeset(next_rev)
                    add_link(req, 'last',
                             self.env.href.diff(path, rev=youngest_rev),
                             'Changeset %s' % youngest_rev)
                if next_rev:
                    add_link(req, 'next', next_href, _changeset_title(next_rev))

        else: # Diff Mode
            # -- getting the deltas from the Repository.get_deltas method
            def get_deltas():
                for d in repos.get_deltas(**diff):
                    yield d
                    
            reverse_href = self.env.href.diff(diff.old_path,
                                              new=diff.old_rev,
                                              old_path=diff.new_path,
                                              old=diff.new_rev)
            req.hdf['diff.reverse_href'] = reverse_href
            if restricted:              # 'diff between 2 revisions' mode
                title = 'Diff r%s:%s for %s' % (diff.old_rev, diff.new_rev,
                                                diff.new_path)
            else:                       # 'arbitrary diff' mode
                title = 'Diff from %s @ %s to %s @ %s' % (diff.old_path,
                                                          diff.old_rev,
                                                          diff.new_path,
                                                          diff.new_rev)
        req.hdf['title'] = title

        def _change_info(old_node, new_node, change):
            info = {'change': change}
            if old_node:
                info['path.old'] = old_node.path
                info['rev.old'] = old_node.rev # this is the created rev.
                old_href = self.env.href.browser(old_node.path,
                                                 rev=diff.old_rev)
                # Reminder: old_node.path may not exist at old_node.rev
                info['browser_href.old'] = old_href
            if new_node:
                info['path.new'] = new_node.path
                info['rev.new'] = new_node.rev # created rev.
                new_href = self.env.href.browser(new_node.path,
                                                 rev=diff.new_rev)
                # (same remark as above)
                info['browser_href.new'] = new_href
            return info

        hidden_properties = [p.strip() for p
                             in self.config.get('browser', 'hide_properties',
                                                'svk:merge').split(',')]

        def _prop_changes(old_node, new_node):
            old_props = old_node.get_properties()
            new_props = new_node.get_properties()
            changed_props = {}
            if old_props != new_props:
                for k,v in old_props.items():
                    if not k in new_props:
                        changed_props[k] = {'old': v}
                    elif v != new_props[k]:
                        changed_props[k] = {'old': v, 'new': new_props[k]}
                for k,v in new_props.items():
                    if not k in old_props:
                        changed_props[k] = {'new': v}
                for k in hidden_properties:
                    if k in changed_props:
                        del changed_props[k]
            return changed_props

        def _content_changes(old_node, new_node):
            """
            Returns the list of differences.
            The list is empty when no differences between comparable files
            are detected, but the return value is None for non-comparable files.
            """
            default_charset = self.config.get('trac', 'default_charset')
            old_content = old_node.get_content().read()            
            if mimeview.is_binary(old_content):
                return None
            charset = mimeview.get_charset(old_node.content_type) or \
                      default_charset
            old_content = util.to_utf8(old_content, charset)

            new_content = new_node.get_content().read()
            if mimeview.is_binary(new_content):
                return None
            charset = mimeview.get_charset(new_node.content_type) or \
                      default_charset
            new_content = util.to_utf8(new_content, charset)

            if old_content != new_content:
                context = 3
                options = diff_options[1]
                for option in options:
                    if option.startswith('-U'):
                        context = int(option[2:])
                        break
                tabwidth = int(self.config.get('diff', 'tab_width',
                                               self.config.get('mimeviewer',
                                                               'tab_width')))
                return hdf_diff(old_content.splitlines(),
                                new_content.splitlines(),
                                context, tabwidth,
                                ignore_blank_lines='-B' in options,
                                ignore_case='-i' in options,
                                ignore_space_changes='-b' in options)
            else:
                return []

        idx = 0
        for old_node, new_node, kind, change in get_deltas():
            if change != Changeset.EDIT:
                show_entry = True
            else:
                show_entry = False
                assert old_node and new_node
                props = _prop_changes(old_node, new_node)
                if props:
                    req.hdf['diff.changes.%d.props' % idx] = props
                    show_entry = True
                if kind == Node.FILE:
                    diffs = _content_changes(old_node, new_node)
                    if diffs != []:
                        if diffs:
                            req.hdf['diff.changes.%d.diff' % idx] = diffs
                        # elif None (means: manually compare to (previous))
                        show_entry = True
            if show_entry:
                info = _change_info(old_node, new_node, change)
                req.hdf['diff.changes.%d' % idx] = info
            idx += 1 # the sequence should be immutable

    def _render_diff(self, req, filename, repos, diff, diff_options):
        """Raw Unified Diff version"""
        req.send_response(200)
        req.send_header('Content-Type', 'text/plain;charset=utf-8')
        req.send_header('Content-Disposition',
                        'filename=%s.diff' % filename)
        req.end_headers()

        for old_node, new_node, kind, change in repos.get_deltas(**diff):
            # TODO: Property changes

            # Content changes
            if kind == Node.DIRECTORY:
                continue

            default_charset = self.config.get('trac', 'default_charset')
            new_content = old_content = ''
            new_node_info = old_node_info = ('','')

            if old_node:
                charset = mimeview.get_charset(old_node.content_type) or \
                          default_charset
                old_content = util.to_utf8(old_node.get_content().read(),
                                           charset)
                old_node_info = (old_node.path, old_node.rev)
                if mimeview.is_binary(old_content):
                    continue

            if new_node:
                charset = mimeview.get_charset(new_node.content_type) or \
                          default_charset
                new_content = util.to_utf8(new_node.get_content().read(),
                                           charset)
                new_node_info = (new_node.path, new_node.rev)
                if mimeview.is_binary(new_content):
                    continue
                new_path = new_node.path
            else:
                old_node_path = repos.normalize_path(old_node.path)
                diff_old_path = repos.normalize_path(diff.old_path)
                new_path = posixpath.join(diff.new_path,
                                          old_node_path[len(diff_old_path)+1:])

            if old_content != new_content:
                context = 3
                options = diff_options[1]
                for option in options:
                    if option.startswith('-U'):
                        context = int(option[2:])
                        break
                if not old_node_info[0]:
                    old_node_info = new_node_info # support for 'A'dd changes
                req.write('Index: ' + new_path + util.CRLF)
                req.write('=' * 67 + util.CRLF)
                req.write('--- %s (revision %s)' % old_node_info +
                          util.CRLF)
                req.write('+++ %s (revision %s)' % new_node_info +
                          util.CRLF)
                for line in unified_diff(old_content.splitlines(),
                                         new_content.splitlines(), context,
                                         ignore_blank_lines='-B' in options,
                                         ignore_case='-i' in options,
                                         ignore_space_changes='-b' in options):
                    req.write(line + util.CRLF)

    def _render_zip(self, req, filename, repos, diff):
        """ZIP archive with all the added and/or modified files."""
        new_rev = diff.new_rev
        req.send_response(200)
        req.send_header('Content-Type', 'application/zip')
        req.send_header('Content-Disposition',
                        'filename=%s.zip' % filename)
        req.end_headers()

        try:
            from cStringIO import StringIO
        except ImportError:
            from StringIO import StringIO
        from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

        buf = StringIO()
        zipfile = ZipFile(buf, 'w', ZIP_DEFLATED)
        for old_node, new_node, kind, change in repos.get_deltas(**diff):
            if kind == Node.FILE and change != Changeset.DELETE:
                assert new_node
                zipinfo = ZipInfo()
                zipinfo.filename = new_node.path
                zipinfo.date_time = time.gmtime(new_node.last_modified)[:6]
                zipinfo.compress_type = ZIP_DEFLATED
                zipfile.writestr(zipinfo, new_node.get_content().read())
        zipfile.close()
        req.write(buf.getvalue())


class DiffModule(AbstractDiffModule):

    implements(IWikiSyntaxProvider)

    # (reimplemented) IRequestHandler methods

    def match_request(self, req):
        match = re.match(r'/diff(?:(/.*)|$)', req.path_info)
        if match:
            if match.group(1):
                req.args['path'] = match.group(1)
            return 1

    # IWikiSyntaxProvider methods
    
    def get_wiki_syntax(self):
        return []

    def get_link_resolvers(self):
        yield ('diff', self._format_link)

    def _format_link(self, formatter, ns, params, label):
        def pathrev(path):
            irev = path.find('#')
            if irev > 0:
                return (path[:irev], path[irev+1:])
            else:
                return (path, None)
        ianydiff = params.find('//')
        if ianydiff > 0:
            old_path, old_rev = pathrev(params[:ianydiff])
            new_path, new_rev = pathrev(params[ianydiff+2:])
        else: 
            old_path, old_rev = pathrev(params)
            new_path = old_path
            new_rev = None
            if old_rev:
                isep = old_rev.find(':')
                if isep > 0:
                    old_rev = old_rev[:isep]
                    new_rev = old_rev[isep+1:]
        href = formatter.href.diff(new_path, new=new_rev,
                                   old_path=old_path, old=old_rev)
        return '<a class="changeset" title="%s" href="%s">%s</a>' \
                   % ('Diff', href, label)


class AnyDiffModule(Component):

    implements(IRequestHandler)

    # IRequestHandler methods

    def match_request(self, req):
        return re.match(r'/anydiff$', req.path_info)

    def process_request(self, req):
        # -- retrieve arguments
        new_path = req.args.get('new_path')
        new_rev = req.args.get('new_rev')
        old_path = req.args.get('old_path')
        old_rev = req.args.get('old_rev')

        # -- normalize 
        repos = self.env.get_repository(req.authname)
        new_path = repos.normalize_path(new_path)
        new_rev = repos.normalize_rev(new_rev)
        old_path = repos.normalize_path(old_path)
        old_rev = repos.normalize_rev(old_rev)

        # -- prepare rendering
        req.hdf['anydiff'] = {
            'new_path': new_path,
            'new_rev': new_rev,
            'old_path': old_path,
            'old_rev': old_rev,
            'diff_href': self.env.href.diff(),
            }

        return 'anydiff.cs', None
