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

from trac.core import *

import unittest


class ITest(Interface):
    def test():
        """Dummy function."""


class ComponentTestCase(unittest.TestCase):

    def setUp(self):
        from trac.core import ComponentManager, ComponentMeta
        self.compmgr = ComponentManager()

        # Make sure we have no external components hanging around in the
        # component registry
        self.old_components = ComponentMeta._components
        ComponentMeta._components = {}
        self.old_extension_points = ComponentMeta._extension_points
        ComponentMeta._extension_points = {}

    def tearDown(self):
        # Restore the original component registry
        from trac.core import ComponentMeta
        ComponentMeta._components = self.old_components
        ComponentMeta._extension_points = self.old_extension_points

    def test_unregistered_component(self):
        # FIXME: this is bogus
        self.assertRaises(TracError, self.compmgr.__getitem__, 'nada')

    def test__component_registration(self):
        class ComponentA(Component):
            pass
        assert self.compmgr['ComponentA']
        assert ComponentA(self.compmgr)

    def test_component_identity(self):
        class ComponentA(Component):
            pass
        c1 = ComponentA(self.compmgr)
        c2 = ComponentA(self.compmgr)
        assert c1 is c2, 'Expected same component instance'
        c2 = self.compmgr['ComponentA']
        assert c1 is c2, 'Expected same component instance'

    def test_component_initializer(self):
        class ComponentA(Component):
            def __init__(self):
                self.data = 'test'
        self.assertEqual('test', ComponentA(self.compmgr).data)
        ComponentA(self.compmgr).data = 'newtest'
        self.assertEqual('newtest', ComponentA(self.compmgr).data)

    def test_extension_point_with_no_extension(self):
        class ComponentA(Component):
            tests = ExtensionPoint(ITest)
        tests = ComponentA(self.compmgr).tests
        self.assertRaises(StopIteration, tests.next)

    def test_extension_point_with_one_extension(self):
        class ComponentA(Component):
            tests = ExtensionPoint(ITest)
        class ComponentB(Component):
            __extends__ = ['ComponentA.tests']
            def test(self): return 'x'
        tests = ComponentA(self.compmgr).tests
        self.assertEquals('x', tests.next().test())
        self.assertRaises(StopIteration, tests.next)

    def test_extension_point_with_two_extensions(self):
        class ComponentA(Component):
            tests = ExtensionPoint(ITest)
        class ComponentB(Component):
            __extends__ = ['ComponentA.tests']
            def test(self): return 'x'
        class ComponentC(Component):
            __extends__ = ['ComponentA.tests']
            def test(self): return 'y'
        tests = ComponentA(self.compmgr).tests
        self.assertEquals('x', tests.next().test())
        self.assertEquals('y', tests.next().test())
        self.assertRaises(StopIteration, tests.next)

    def test_inherited_extension_point(self):
        class BaseComponent(Component):
            tests = ExtensionPoint(ITest)
        class ConcreteComponent(BaseComponent):
            pass
        class ExtendingComponent(Component):
            __extends__ = ['BaseComponent.tests']
            def test(self): return 'x'
        tests = ConcreteComponent(self.compmgr).tests
        self.assertEquals('x', tests.next().test())
        self.assertRaises(StopIteration, tests.next)


def suite():
    return unittest.makeSuite(ComponentTestCase, 'test')

if __name__ == '__main__':
    unittest.main()
