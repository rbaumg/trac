# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Edgewall Software
# Copyright (C) 2005 Jonas Borgström <jonas@edgewall.com>
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
import re

from trac.core import *
from trac.util import TracError
from trac.perm import PermissionSystem
from webadmin.web_ui import IAdminPageProvider

__all__ = []


class PermAdminPage(Component):

    implements(IAdminPageProvider)

    # IAdminPageProvider
    def get_admin_pages(self, req):
        if req.perm.has_permission('TRAC_ADMIN'):
            yield ('security', 'Security', 'perm', 'Permissions')

    def process_admin_request(self, req, cat, page, path_info):
        perm = PermissionSystem(self.env)
        perms = perm.get_all_permissions()
        subject = req.args.get('subject')
        action = req.args.get('action')

        if req.args.get('add') and subject and action:
            if action not in perm.get_actions():
                raise TracError('Unknown action')
            perm.grant_permission(subject, action)
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
        
        req.hdf['admin.actions'] = perm.get_actions()
        req.hdf['admin.perms'] = [{'subject': p[0],
                                   'action': p[1],
                                   'key': '%s:%s' % p
                                  } for p in perms]
        
        return 'admin_perm.cs', None
