# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Edgewall Software
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
# Author: Christopher Lenz <cmlenz@gmx.de>

from protocols import *


class __PluginRegistry(object):

    plugins = {}
    extensionPoints = {}

    def getPluginsExtending(self, extensionPoint):
        plugins = []
        for plugin in self.extensionPoints.get(extensionPoint, []):
            plugins.append(plugin)
        return plugins

    def register(self, pluginId, pluginClass):
        self.plugins[pluginId] = pluginClass
        for extensionPoint in pluginClass._extends:
            if not self.extensionPoints.has_key(extensionPoint):
                self.extensionPoints[extensionPoint] = []
            self.extensionPoints[extensionPoint].append(pluginId)

PluginRegistry = __PluginRegistry()


class NoSuchPlugin(Exception): pass


class PluginManager(object):
    """
    Keeps track of which plugins are active, and instantiate plugins on
    demand.
    """

    activePlugins = None

    def __init__(self):
        self.activePlugins = {}

    def plugin(self, pluginId):
        """
        Return a plugin by name. If not already active, the plugin gets
        instantiated. Subsequent calls will return the already instantiated
        plugin.
        """
        plugin = self.activePlugins.get(pluginId)
        if not plugin:
            pluginClass = PluginRegistry.plugins.get(pluginId)
            if not pluginClass:
                raise NoSuchPlugin, 'No plugin with ID "%s" registered' % pluginId
            if pluginClass == self.__class__:
                return self
            try:
                plugin = pluginClass()
            except TypeError, e:
                raise TypeError, 'Unable to instantiate plugin "%s" (%s)' % (pluginId, e)
            plugin.pluginManager = self
            self.activePlugins[pluginId] = plugin
            for listener in plugin.activationListeners:
                listener.pluginActivated(plugin)
        return plugin


class ExtensionPoint(object):

    plugin = None
    name = None
    id = property(fget=lambda self: '%s.%s' % (self.plugin, self.name))

    def __init__(self, protocol):
        self.protocol = protocol

    def __repr__(self):
        return id


class PluginMeta(type):

    def __new__(cls, name, bases, d):

        pluginId = d.get('_id')
        if not pluginId:
            if name.endswith('Plugin'):
                pluginId = name[:-6].lower()
            else:
                pluginId = name.lower()
            d['_id'] = pluginId

        d.setdefault('_extends', [])

        extensionPoints = {}
        for base in [b for b in bases
                     if hasattr(b, '_extensionPoints')]:
            extensionPoints.update(base._extensionPoints)
        for attr, value in d.items():
            if isinstance(value, ExtensionPoint):
                value.plugin = pluginId
                value.name = attr
                extensionPoints[attr] = value
                del d[attr]

        newClass = type.__new__(cls, name, bases, d)
        newClass._extensionPoints = extensionPoints

        if pluginId:
            PluginRegistry.register(pluginId, newClass)

        return newClass


class ExtensionsProxy(object):

    pluginManager = None
    extensionPoint = None
    pluginIds = None

    def __init__(self, pluginManager, extensionPoint, pluginIds=None):
        self.pluginManager = pluginManager
        self.extensionPoint = extensionPoint
        if not pluginIds:
            self.pluginIds = PluginRegistry.getPluginsExtending(extensionPoint.id)
        else:
            self.pluginIds = pluginIds

    def __call__(self, constrain=None, order=None, reverse=0):
        if constrain:
            pluginIds = filter(constrain, self.pluginIds)
        else:
            pluginIds = self.pluginIds[:]        
        if order:
            pluginIds.sort(order)
        if reverse:
            pluginIds.reverse()
        # TODO: Should we cache nested proxies here?
        return ExtensionsProxy(self.pluginManager, self.extensionPoint,
                               pluginIds)

    def __getitem__(self, name):
        if not name in self.pluginIds:
            return None
        plugin = self.pluginManager.plugin(name)
        return adapt(plugin, self.extensionPoint.protocol)

    def __iter__(self):
        self.pos = 0
        return self

    def next(self):
        if self.pos == len(self.pluginIds):
            raise StopIteration
        plugin = self.pluginManager.plugin(self.pluginIds[self.pos])
        self.pos += 1
        return adapt(plugin, self.extensionPoint.protocol)


class IPluginActivationListener(Interface):

    def pluginActivated(plugin):
        """Called by the plugin manager after a plugin has been activated."""


class Plugin(object):
    __metaclass__ = PluginMeta

    _id = 'plugin'
    activationListeners = ExtensionPoint(IPluginActivationListener)

    pluginManager = None # set by the plugin manager on activation

    def __getattr__(self, name):
        extensionPoint = self._extensionPoints.get(name)
        if extensionPoint:
            # TODO Should we cache the proxy here?
            return ExtensionsProxy(self.pluginManager, extensionPoint)
        raise AttributeError, name

    def __str__(self):
        return self._id


__all__ = ['Plugin', 'PluginManager', 'NoSuchPlugin', 'ExtensionPoint',
           'IPluginActivationListener']
