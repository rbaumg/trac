# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Edgewall Software
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
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
# Author: Christopher Lenz <cmlenz@gmx.de>

import os

from trac.core import *
from webadmin.web_ui import IAdminPageProvider

__all__ = []


class LoggingAdminPage(Component):

    implements(IAdminPageProvider)

    # IAdminPageProvider methods

    def get_admin_pages(self, req):
        if req.perm.has_permission('TRAC_ADMIN'):
            yield ('general', 'General', 'logging', 'Logging')

    def process_admin_request(self, req, cat, page, path_info):
        log_type = self.config.get('logging', 'log_type')
        log_level = self.config.get('logging', 'log_level').upper()
        log_file = self.config.get('logging', 'log_file', 'trac.log')
        log_dir = os.path.join(self.env.path, 'log')

        log_types = [
            dict(name='', label=''),
            dict(name='stderr', label='Console', selected=log_type == 'stderr'),
            dict(name='file', label='File', selected=log_type == 'file'),
            dict(name='syslog', label='Syslog', disabled=os.name != 'posix',
                 selected=log_type in ('unix', 'syslog')),
            dict(name='eventlog', label='Windows event log',
                 disabled=os.name != 'nt',
                 selected=log_type in ('winlog', 'eventlog', 'nteventlog')),
        ]

        log_levels = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']

        if req.method == 'POST':
            changed = False

            new_type = req.args.get('log_type')
            if new_type and new_type not in ('stderr', 'file', 'syslog',
                                             'eventlog'):
                raise TracError('Unknown log type %s' % new_type,
                                'Invalid log type')
            if new_type != log_type:
                self.config.set('logging', 'log_type', new_type or 'none')
                changed = True
                log_type = new_type

            if log_type:
                new_level = req.args.get('log_level')
                if new_level and new_level not in log_levels:
                    raise TracError('Unknown log level %s' % new_level,
                                    'Invalid log level')
                if new_level and new_level != log_level:
                    self.config.set('logging', 'log_level', new_level)
                    changed = True
                    log_evel = new_level
            else:
                self.config.remove('logging', 'log_level')
                changed = True

            if log_type == 'file':
                new_file = req.args.get('log_file', 'trac.log')
                if new_file != log_file:
                    self.config.set('logging', 'log_file', new_file or '')
                    changed = True
                    log_file = new_file
                if log_type == 'file' and not log_file:
                    raise TracError('You must specify a log file',
                                    'Missing field')
            else:
                self.config.remove('logging', 'log_file')
                changed = True

            if changed:
                self.config.save()
            req.redirect(self.env.href.admin(cat, page))

        req.hdf['admin.log'] = {'type': log_type, 'types': log_types,
                                'level': log_level, 'levels': log_levels,
                                'file': log_file, 'dir': log_dir}

        return 'admin_log.cs', None
