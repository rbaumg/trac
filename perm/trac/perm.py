# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004, 2005 Edgewall Software
# Copyright (C) 2003, 2004 Jonas Borgstr�m <jonas@edgewall.com>
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
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
#         Christopher Lenz <cmlenz@gmx.de>

"""Management of permissions."""

from trac.core import *


__all__ = ['IPermissionRequestor', 'IPermissionStore',
           'IPermissionGroupProvider', 'PermissionError', 'PermissionSystem']

class PermissionError(StandardError):
    """Insufficient permissions to complete the operation"""

    def __init__ (self, action):
        StandardError.__init__(self)
        self.action = action

    def __str__ (self):
        return '%s privileges required to perform this operation' % self.action


class IPermissionRequestor(Interface):
    """Extension point interface for components that define actions."""

    def get_actions():
        """Return a list of actions defined by this component.
        
        The items in the list may either be simple strings, or
        `(string, sequence)` tuples. The latter are considered to be "meta
        permissions" that group several simple actions under one name for
        convenience.
        """


class IPermissionStore(Interface):
    """Extension point interface for components that provide storage and
    management of permissions."""

    def get_permissions(username):
        """Return all permissions for the user with the specified name.
        
        The permissions are returned as a dictionary where the key is the name
        of the permission, and the value is either `True` for granted
        permissions or `False` for explicitly denied permissions."""

    def grant_permission(username, action):
        """Grant a user permission to perform an action."""

    def revoke_permission(username, action):
        """Revokes the permission of the given user to perform an action."""


class PermissionSystem(Component):
    """Sub-system that manages user permissions."""

    implements(IPermissionRequestor)

    requestors = ExtensionPoint(IPermissionRequestor)
    stores = ExtensionPoint(IPermissionStore)

    # Public API

    def grant_permission(self, username, action):
        """Grant the user with the given name permission to perform to specified
        action."""
        # TODO: Validate that action is known, and that this permission doesn't
        # already exist
        self.store.grant_permission(username, action)

    def revoke_permission(self, username, action):
        """Revokes the permission of the specified user to perform an action."""
        # TODO: Validate that this permission does in fact exist
        self.store.revoke_permission(username, action)

    def get_permissions(self, username=None):
        """Return the permissions of the specified user.
        
        The return value is a dictionary containing all the actions as keys, and
        a boolean value. `True` means that the permission is granted, `False`
        means the permission is denied."""
        actions = []
        for requestor in self.requestors:
            actions += list(requestor.get_actions())
        permissions = {}
        if username:
            # Return all permissions that the given user has
            meta = {}
            for action in actions:
                if isinstance(action, tuple):
                    name, value = action
                    meta[name] = value
            def _expand_meta(action):
                permissions[action] = True
                if action in meta.keys():
                    [_expand_meta(perm) for perm in meta[action]]
            for perm in self.store.get_permissions(username):
                _expand_meta(perm)
        else:
            # Return all permissions available in the system
            for action in actions:
                if isinstance(action, tuple):
                    permissions[action[0]] = True
                else:
                    permissions[action] = True
        return permissions

    # IPermissionRequestor methods

    def get_actions(self):
        """Implement the global `TRAC_ADMIN` meta permission."""
        actions = []
        for requestor in [r for r in self.requestors if r is not self]:
            for action in requestor.get_actions():
                if isinstance(action, tuple):
                    actions.append(action[0])
                else:
                    actions.append(action)
        return [('TRAC_ADMIN', actions)]

    # Internal methods

    def _get_store(self):
        """Return the `IPermissionStore` implementation selected in the
        configuration."""
        selected_store = self.config.get('trac', 'permission_store')
        for store in self.stores:
            if store.__class__.__name__ == selected_store:
                return store
        raise TracError, 'Invalid permission store "%s"' % selected_store
    store = property(fget=lambda self: self._get_store())


class IPermissionGroupProvider(Interface):
    """
    Extension point interface for components that provide information about user
    groups.
    """

    def get_permission_groups(username):
        """Return a list of names of the groups that the user with the specified
        name is a member of."""


class DefaultPermissionStore(Component):
    """Default implementation of permission storage and simple group management.
    
    This component uses the `PERMISSION` table in the database to store both
    permissions and groups.
    """
    implements(IPermissionStore)

    group_providers = ExtensionPoint(IPermissionGroupProvider)

    def get_permissions(self, username):
        """Retrieve the permissions for the given user and return them in a
        dictionary.
        
        The permissions are stored in the database as (username, action)
        records. There's simple support for groups by using lowercase names for
        the action column: such a record represents a group and not an actual
        permission, and declares that the user is part of that group.
        """
        subjects = [username]
        for provider in self.group_providers:
            subjects += list(provider.get_permission_groups(username))

        actions = []
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT username,action FROM permission")
        rows = cursor.fetchall()
        while True:
            num_users = len(subjects)
            num_actions = len(actions)
            for user, action in rows:
                if user in subjects:
                    if not action.islower() and action not in actions:
                        actions.append(action)
                    if action.islower() and action not in subjects:
                        # action is actually the name of the permission group
                        # here
                        subjects.append(action)
            if num_users == len(subjects) and num_actions == len(actions):
                break
        return [action for action in actions if not action.islower()]

    def grant_permission(self, username, action):
        """Grants a user the permission to perform the specified action."""
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("INSERT INTO permission VALUES (%s, %s)",
                       (username, action))
        self.log.info('Granted permission for %s to %s' % (action, username))
        db.commit()

    def revoke_permission(self, username, action):
        """Revokes a users' permission to perform the specified action."""
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("DELETE FROM permission WHERE username=%s AND action=%s",
                       (username, action))
        self.log.info('Revoked permission for %s to %s' % (action, username))
        db.commit()


class DefaultPermissionGroupProvider(Component):
    """Provides the basic builtin permission groups 'anonymous' and
    'authenticated'."""

    implements(IPermissionGroupProvider)

    def get_permission_groups(self, username):
        groups = ['anonymous']
        if username and username != 'anonymous':
            groups.append('authenticated')
        return groups


class PermissionCache:
    """Cache that maintains the permissions of a single user."""

    def __init__(self, env, username):
        self.perms = PermissionSystem(env).get_permissions(username)

    def has_permission(self, action):
        return self.perms.has_key(action)

    def assert_permission(self, action):
        if action not in self.perms.keys():
            raise PermissionError(action)

    def permissions(self):
        return self.perms.keys()
