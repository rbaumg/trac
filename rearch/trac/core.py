# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2003, 2004, 2005 Edgewall Software
# Copyright (C) 2003, 2004 Jonas Borgström <jonas@edgewall.com>
# Copyright (C) 2004, 2005 Christopher Lenz <cmlenz@gmx.de>
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
#         Christopher Lenz <cmlenz@gmx.de>

from __future__ import generators

from trac.util import TracError

__all__ = ['Component', 'ExtensionPoint', 'Interface', 'TracError']


class Interface(object):
    """
    Dummy base class for interfaces. Should use PyProtocols in the future.
    """
    __slots__ = []


class ExtensionPoint(object):
    """
    Marker class for extension points in components. Could be extended
    to hold the protocol/interface required.
    """

    __slots__ = ['interface', 'declaring_class']

    def __init__(self, interface):
        self.interface = interface
        self.declaring_class = None

    def __str__(self):
        return '<ExtensionPoint %s declared by %s>' \
               % (self.interface.__name__, self.declaring_class)


class ComponentMeta(type):
    """
    Meta class for components. Takes care of component and extension point
    registration.
    """

    _components = {}
    _extension_points = {}

    def __new__(cls, name, bases, d):
        xtnpts = {}
        declared_here = []
        for base in [b for b in bases
                     if hasattr(b, '_extension_points')]:
            xtnpts.update(base._extension_points)
        for key, value in d.items():
            if isinstance(value, ExtensionPoint):
                xtnpts[key] = value
                declared_here.append(value)
                del d[key]

        new_class = type.__new__(cls, name, bases, d)
        for xtnpt in declared_here:
            xtnpt.declaring_class = name
        new_class._extension_points = xtnpts

        # Allow components to have a no-argument initializer so that
        # they don't need to worry about accepting the component manager
        # as argument and invoking the super-class initializer
        def maybe_init(self, compmgr, init=d.get('__init__'), class_name=name):
            if not class_name in compmgr.components:
                compmgr.components[class_name] = self
                if init:
                    init(self)
        setattr(new_class, '__init__', maybe_init)

        ComponentMeta._components[name] = new_class
        for class_name, xtnpt_name in [ref.split('.')
                                       for ref in d.get('_extends', [])]:
            xtnpt = (class_name, xtnpt_name)
            if not xtnpt in ComponentMeta._extension_points:
                ComponentMeta._extension_points[xtnpt] = []
            ComponentMeta._extension_points[xtnpt].append(name)

        return new_class


class Component(object):
    """
    Base class for components. Every component must have an _id attribute that
    is a string that uniquely identifies the component. In addition, every
    component can declare what extension points it provides, as well as what
    extension points of other components it extends.
    """
    __metaclass__ = ComponentMeta
    __slots__ = ['compmgr']

    def __new__(cls, compmgr):
        if not cls.__name__ in compmgr.components:
            self = object.__new__(cls)
            self.compmgr = compmgr
            compmgr.component_activated(self)
            return self
        return compmgr[cls.__name__]

    def __getattr__(self, name):
        xtnpt = self._extension_points.get(name)
        if xtnpt:
            key = (xtnpt.declaring_class, name)
            extensions = ComponentMeta._extension_points.get(key, [])
            for extension in extensions:
                yield self.compmgr[extension]
            return
        raise AttributeError, name


class ComponentManager(object):
    """
    The component manager keeps a pool of active components.
    """
    __slots__ = ['components']

    def __init__(self):
        self.components = {}

    def __contains__(self, class_name):
        return class_name in self.components

    def __getitem__(self, class_name):
        component = self.components.get(class_name)
        if not component:
            try:
                component = ComponentMeta._components[class_name](self)
            except KeyError, e:
                raise TracError, 'Component "%s" not registered (%s)' \
                                 % (class_name, e)
            except TypeError, e:
                raise TracError, 'Unable to instantiate component "%s" (%s)' \
                                 % (class_name, e)
        return component

    def component_activated(self, component):
        """
        Can be overridden by sub-classes so that special initialization for
        components can be provided.
        """
