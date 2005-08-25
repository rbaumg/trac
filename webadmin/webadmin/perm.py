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
from trac.util import TracError
from trac.perm import PermissionSystem
from webadmin.web_ui import IAdminPageProvider

__all__ = []


class PermissionAdminPage(Component):

    implements(IAdminPageProvider)

    # IAdminPageProvider
    def get_admin_pages(self, req):
        if req.perm.has_permission('TRAC_ADMIN'):
            yield ('general', 'General', 'perm', 'Permissions')

    def process_admin_request(self, req, cat, page, path_info):
        perm = PermissionSystem(self.env)
        perms = perm.get_all_permissions()
        subject = req.args.get('subject')
        action = req.args.get('action')
        group = req.args.get('group')

        if req.method == 'POST':
            # Grant permission to subject
            if req.args.get('add') and subject and action:
                if action not in perm.get_actions():
                    raise TracError('Unknown action')
                perm.grant_permission(subject, action)
                req.redirect(self.env.href.admin(cat, page))

            # Add subject to group
            elif req.args.get('add') and subject and group:
                perm.grant_permission(subject, group)
                req.redirect(self.env.href.admin(cat, page))

            # Remove permissions action
            elif req.args.get('remove') and req.args.get('sel'):
                sel = req.args.get('sel')
                sel = isinstance(sel, list) and sel or [sel]
                for key in sel:
                    subject, action = key.split(':', 1)
                    if (subject, action) in perms:
                        perm.revoke_permission(subject, action)
                req.redirect(self.env.href.admin(cat, page))
        
        perms.sort(lambda a, b: cmp(a[0], b[0]))
        req.hdf['admin.actions'] = perm.get_actions()
        req.hdf['admin.perms'] = [{'subject': p[0],
                                   'action': p[1],
                                   'key': '%s:%s' % p
                                  } for p in perms]
        
        return 'admin_perm.cs', None
