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

import os

from trac import Environment, perm
from trac.util import TracError

modules = {
#    name           (module_name, class_name)
    'browser'     : ('Browser', 'BrowserModule'),
    'log'         : ('Browser', 'LogModule'),
    'file'        : ('Browser', 'FileModule'),
    'wiki'        : ('Wiki', 'WikiModule'),
    'about_trac'  : ('About', 'About'),
    'search'      : ('Search', 'Search'),
    'report'      : ('Report', 'Report'),
    'ticket'      : ('Ticket', 'TicketModule'),
    'timeline'    : ('Timeline', 'Timeline'),
    'changeset'   : ('Changeset', 'Changeset'),
    'newticket'   : ('Ticket', 'NewticketModule'),
    'query'       : ('Query', 'QueryModule'),
    'attachment'  : ('attachment', 'AttachmentModule'),
    'roadmap'     : ('Roadmap', 'Roadmap'),
    'settings'    : ('Settings', 'Settings'),
    'milestone'   : ('Milestone', 'Milestone')
    }

def module_factory(env, db, req):
    mode = req.args.get('mode', 'wiki')
    module_name, constructor_name = modules[mode]
    module = __import__(module_name, globals(),  locals())
    constructor = getattr(module, constructor_name)
    module = constructor()
    module._name = mode

    module.env = env
    module.log = env.log
    module.db = db
    module.perm = perm.PermissionCache(module.db, req.authname)

    return module

def open_environment(env_path=None):
    if not env_path:
        env_path = os.getenv('TRAC_ENV')
    if not env_path:
        raise EnvironmentError, \
              'Missing environment variable "TRAC_ENV". Trac ' \
              'requires this variable to point to a valid Trac Environment.'

    env = Environment.Environment(env_path)
    version = env.get_version()
    if version < Environment.db_version:
        raise TracError('The Trac Environment needs to be upgraded. '
                        'Run "trac-admin %s upgrade"' % env_path)
    elif version > Environment.db_version:
        raise TracError('Unknown Trac Environment version (%d).' % version)
    return env
