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

from trac import ticket, util
from trac.core import *
from trac.perm import IPermissionRequestor
from webadmin.web_ui import IAdminPageProvider


__all__ = []


class ComponentAdminPage(Component):

    implements(IAdminPageProvider)

    # IAdminPageProvider
    def get_admin_pages(self, req):
        if req.perm.has_permission('TICKET_ADMIN'):
            yield ('ticket', 'Ticket System', 'components', 'Components')

    def process_admin_request(self, req, cat, page, component):
        req.perm.assert_permission('TICKET_ADMIN')
        
        # Detail view?
        if component:
            comp = ticket.Component(self.env, component)
            if req.method == 'POST':
                if req.args.get('save'):
                    comp.name = req.args.get('name')
                    comp.owner = req.args.get('owner')
                    comp.update()
                    req.redirect(self.env.href.admin(cat, page))
                elif req.args.get('cancel'):
                    req.redirect(self.env.href.admin(cat, page))

            req.hdf['admin.component'] = {
                'name': comp.name,
                'owner': comp.owner
            }
        else:
            if req.method == 'POST':
                # Add Component
                if req.args.get('add') and req.args.get('name'):
                    comp = ticket.Component(self.env)
                    comp.name = req.args.get('name')
                    if req.args.get('owner'):
                        comp.owner = req.args.get('owner')
                    comp.insert()
                    req.redirect(self.env.href.admin(cat, page))

                # Remove components
                elif req.args.get('remove') and req.args.get('sel'):
                    sel = req.args.get('sel')
                    sel = isinstance(sel, list) and sel or [sel]
                    if not sel:
                        raise TracError, 'No component selected'
                    db = self.env.get_db_cnx()
                    for name in sel:
                        comp = ticket.Component(self.env, name, db=db)
                        comp.delete(db=db)
                    db.commit()
                    req.redirect(self.env.href.admin(cat, page))

                # Set default component
                elif req.args.get('apply'):
                    if req.args.get('default'):
                        name = req.args.get('default')
                        self.log.info('Setting default component to %s', name)
                        self.config.set('ticket', 'default_component', name)
                        self.config.save()
                        req.redirect(self.env.href.admin(cat, page))

            default = self.config.get('ticket', 'default_component')
            req.hdf['admin.components'] = \
                [{'name': c.name, 'owner': c.owner,
                  'is_default': c.name == default,
                  'href': self.env.href.admin(cat, page, c.name)
                 } for c in ticket.Component.select(self.env)]
            

        restrict_owner = self.config.get('ticket', 'restrict_owner')
        if restrict_owner in util.TRUE:
            req.hdf['admin.owners'] = [username for username, name, email
                                       in self.env.get_known_users()]

        return 'admin_component.cs', None


class VersionsAdminPage(Component):

    implements(IAdminPageProvider)

    # IAdminPageProvider
    def get_admin_pages(self, req):
        if req.perm.has_permission('TICKET_ADMIN'):
            yield ('ticket', 'Ticket System', 'versions', 'Versions')

    def process_admin_request(self, req, cat, page, version):
        req.perm.assert_permission('TICKET_ADMIN')
        
        # Detail view?
        if version:
            ver = ticket.Version(self.env, version)
            if req.method == 'POST':
                if req.args.get('save'):
                    ver.name = req.args.get('name')
                    # FIXME: parse the "time" field
                    ver.description = req.args.get('description')
                    ver.update()
                    req.redirect(self.env.href.admin(cat, page))
                elif req.args.get('cancel'):
                    req.redirect(self.env.href.admin(cat, page))

            req.hdf['admin.version'] = {
                'name': ver.name,
                'time': ver.time,
                'description': ver.description
            }
        else:
            if req.method == 'POST':
                # Add Version
                if req.args.get('add') and req.args.get('name'):
                    ver = ticket.Version(self.env)
                    ver.name = req.args.get('name')
                    ver.insert()
                    req.redirect(self.env.href.admin(cat, page))
                         
                # Remove versions
                elif req.args.get('remove') and req.args.get('sel'):
                    sel = req.args.get('sel')
                    sel = isinstance(sel, list) and sel or [sel]
                    if not sel:
                        raise TracError, 'No version selected'
                    db = self.env.get_db_cnx()
                    for name in sel:
                        ver = ticket.Version(self.env, name, db=db)
                        ver.delete(db=db)
                    db.commit()
                    req.redirect(self.env.href.admin(cat, page))

                # Set default version
                elif req.args.get('apply'):
                    if req.args.get('default'):
                        name = req.args.get('default')
                        self.log.info('Setting default version to %s', name)
                        self.config.set('ticket', 'default_version', name)
                        self.config.save()
                        req.redirect(self.env.href.admin(cat, page))

            default = self.config.get('ticket', 'default_version')
            req.hdf['admin.versions'] = \
                [{'name': c.name, 'time': c.time,
                  'is_default': c.name == default,
                  'href': self.env.href.admin(cat, page, c.name)
                 } for c in ticket.Version.select(self.env)]
            
        return 'admin_version.cs', None


class EnumAdminPageBase(Component):

    _type = 'unknown'
    _enum_cls = None
    _label = ('(Undefined)', '(Undefined)')

    # IAdminPageProvider
    def get_admin_pages(self, req):
        if req.perm.has_permission('TICKET_ADMIN'):
            yield ('ticket', 'Ticket System', self._type, self._label[1])

    def process_admin_request(self, req, cat, page, path_info):
        req.perm.assert_permission('TICKET_ADMIN')
        req.hdf['admin.enum'] = {
            'label_singular': self._label[0],
            'label_plural': self._label[1]
        }
        # Detail view?
        if path_info:
            enum = self._enum_cls(self.env, path_info)
            if req.method == 'POST':
                if req.args.get('save'):
                    enum.name = req.args.get('name')
                    enum.update()
                    req.redirect(self.env.href.admin(cat, page))
                elif req.args.get('cancel'):
                    req.redirect(self.env.href.admin(cat, page))

            req.hdf['admin.enum'] = {
                'name': enum.name,
                'value': enum.value
            }
        else:
            default = self.config.get('ticket', 'default_%s' % self._type)

            if req.method == 'POST':
                # Add enum
                if req.args.get('add') and req.args.get('name'):
                    enum = self._enum_cls(self.env)
                    enum.name = req.args.get('name')
                    enum.insert()
                    req.redirect(self.env.href.admin(cat, page))
                         
                # Remove enums
                elif req.args.get('remove') and req.args.get('sel'):
                    sel = req.args.get('sel')
                    sel = isinstance(sel, list) and sel or [sel]
                    if not sel:
                        raise TracError, 'No enum selected'
                    db = self.env.get_db_cnx()
                    for name in sel:
                        enum = self._enum_cls(self.env, name, db=db)
                        enum.delete(db=db)
                    db.commit()
                    req.redirect(self.env.href.admin(cat, page))

                # Appy changes
                elif req.args.get('apply'):
                    # Set default value
                    if req.args.get('default'):
                        name = req.args.get('default')
                        if name != default:
                            self.log.info('Setting default %s to %s',
                                          self._type, name)
                            self.config.set('ticket', 'default_%s' % self._type,
                                            name)
                            self.config.save()

                    # Change enum values
                    order = dict([(key[6:], req.args.get(key)) for key
                                  in req.args.keys()
                                  if key.startswith('value_')])
                    values = dict([(val, True) for val in order.values()])
                    if len(order) != len(values):
                        raise TracError, 'Order numbers must be unique'
                    db = self.env.get_db_cnx()
                    for enum in self._enum_cls.select(self.env, db=db):
                        new_value = order[enum.value]
                        if new_value != enum.value:
                            enum.value = new_value
                            enum.update(db=db)
                    db.commit()

                    req.redirect(self.env.href.admin(cat, page))

            req.hdf['admin.enums'] = [
                {'name': e.name, 'value': e.value,
                 'is_default': e.name == default,
                 'href': self.env.href.admin(cat, page, e.name)
                } for e in self._enum_cls.select(self.env)]

        return 'admin_enum.cs', None


class PriorityAdminPage(EnumAdminPageBase):
    implements(IAdminPageProvider)

    _type = 'priority'
    _enum_cls = ticket.Priority
    _label = ('Priority', 'Priorities')


class SeverityAdminPage(EnumAdminPageBase):
    implements(IAdminPageProvider)

    _type = 'severity'
    _enum_cls = ticket.Severity
    _label = ('Severity', 'Severities')


class TicketTypeAdminPage(EnumAdminPageBase):
    implements(IAdminPageProvider)

    _type = 'type'
    _enum_cls = ticket.Type
    _label = ('Ticket Type', 'Ticket Types')
