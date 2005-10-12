# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Edgewall Software
# Copyright (C) 2005 Jonas Borgström <jonas@edgewall.com>
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
# Author: Jonas Borgström <jonas@edgewall.com>

import re

from trac.core import *
from trac.perm import IPermissionRequestor
from trac.web import IRequestHandler
from trac.web.chrome import add_stylesheet, INavigationContributor, \
                            ITemplateProvider
from trac.web.href import Href

__all__ = ['IAdminPageProvider']


class IAdminPageProvider(Interface):
    """
    Extension point interface for adding pages to the admin module.
    """

    def get_admin_pages(self, req):
        """
        Return a list of available admin pages. The pages returned by
        this function must be a tuple of the form
        (category, category_label, page, page_label).
        """

    def process_admin_request(self, req, category, page, path_info):
        """
        Process the request for the admin `page`. This function should
        return a tuple of the form (template_name, content_type) where
        a content_type of `None` is assumed to be "text/html".
        """


class AdminModule(Component):

    implements(INavigationContributor, IRequestHandler, ITemplateProvider)
    page_providers = ExtensionPoint(IAdminPageProvider)
    
    # INavigationContributor methods

    def get_active_navigation_item(self, req):
        return 'admin'

    def get_navigation_items(self, req):
        """The 'Admin' navigation item is only visible if at least one
           admin page is available."""
        pages, providers = self._get_pages(req)
        if pages:
            yield 'mainnav', 'admin', '<a href="%s">Admin</a>' \
                  % (self.env.href.admin())

    # IRequestHandler methods

    def match_request(self, req):
        match = re.match('/admin(?:/([^/]+))?(?:/([^/]+))?(?:/(.*)$)?', req.path_info)
        if match:
            req.args['cat_id'] = match.group(1)
            req.args['page_id'] = match.group(2)
            req.args['path_info'] = match.group(3)
            return True

    def _get_pages(self, req):
        """Return a list of available admin pages."""
        pages = []
        providers = {}
        for provider in self.page_providers:
            p = list(provider.get_admin_pages(req))
            for page in p:
                providers[(page[0], page[2])] = provider
            pages += p
        pages.sort()
        return pages, providers

    def process_request(self, req):
        pages, providers = self._get_pages(req)
        if not pages:
            raise TracError('No admin pages available')
        cat_id = req.args.get('cat_id') or pages[0][0]
        page_id = req.args.get('page_id')
        path_info = req.args.get('path_info')
        if not page_id:
            page_id = filter(lambda page: page[0] == cat_id, pages)[0][2]
        
        provider = providers.get((cat_id, page_id), None)
        if not provider:
            raise TracError('Unknown Admin Page')
        
        template, content_type = provider.process_admin_request(req, cat_id,
                                                                page_id,
                                                                path_info)
        req.hdf['admin.pages'] = [{'cat_id': page[0],
                                   'cat_label': page[1],
                                   'page_id': page[2],
                                   'page_label': page[3],
                                   'href': self.env.href.admin(page[0], page[2])
                                   } for page in pages]
        req.hdf['admin.active_cat'] = cat_id
        req.hdf['admin.active_page'] = page_id
        req.hdf['admin.page_template'] = template
        add_stylesheet(req, 'admin/css/admin.css')
        return 'admin.cs', content_type

    # ITemplateProvider
    
    def get_htdocs_dirs(self):
        """Return the absolute path of a directory containing additional
        static resources (such as images, style sheets, etc).
        """
        from pkg_resources import resource_filename
        return [('admin', resource_filename(__name__, 'htdocs'))]

    def get_templates_dirs(self):
        """Return the absolute path of the directory containing the provided
        ClearSilver templates.
        """
        from pkg_resources import resource_filename
        return [resource_filename(__name__, 'templates')]
