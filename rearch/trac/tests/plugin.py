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
from trac.plugin import *

import unittest


class PluginTestCase(unittest.TestCase):

    def setUp(self):
        self.pluginManager = PluginManager()
        # Make sure we have no auto-registered plug-ins hanging around
        from trac.plugin import PluginRegistry
        PluginRegistry.plugins = {}
        PluginRegistry.extensionPoints = {}

    def testNoSuchPlugin(self):
        self.assertRaises(NoSuchPlugin,
                          lambda: self.pluginManager.plugin('one'))

    def testAutoNaming(self):
        class OnePlugin(Plugin):
            pass
        assert self.pluginManager.plugin('one')

    def testExplicitNaming(self):
        class OnePlugin(Plugin):
            _id = 'other'
        assert self.pluginManager.plugin('other')

    def testExtensionPointWithNoExtension(self):
        class ITest(Interface):
            def test(): pass
        class OnePlugin(Plugin):
            tests = ExtensionPoint(ITest)
        tests = [t.test() for t in self.pluginManager.plugin('one').tests]
        self.assertEquals(0, len(tests))

    def testExtensionPointWithOneExtension(self):
        class ITest(Interface):
            def test(): pass
        class OnePlugin(Plugin):
            tests = ExtensionPoint(ITest)
        class OtherPlugin(Plugin):
            _extends = ['one.tests']
            advise(instancesProvide=[ITest])
            def test(self): return 'x'
        tests = [t.test() for t in self.pluginManager.plugin('one').tests]
        self.assertEquals(1, len(tests))
        self.assertEquals('x', tests[0])

    def testExtensionPointWithTwoExtensions(self):
        class ITest(Interface):
            def test(): pass
        class OnePlugin(Plugin):
            tests = ExtensionPoint(ITest)
        class OtherPlugin(Plugin):
            _extends = ['one.tests']
            advise(instancesProvide=[ITest])
            def test(self): return 'x'
        class AnotherPlugin(Plugin):
            _extends = ['one.tests']
            advise(instancesProvide=[ITest])
            def test(self): return 'y'
        tests = [t.test() for t in self.pluginManager.plugin('one').tests]
        self.assertEquals(2, len(tests))
        self.assertEquals('x', tests[0])
        self.assertEquals('y', tests[1])

    def testExtensionProxyConstrained(self):
        class ITest(Interface):
            def test(): pass
        class OnePlugin(Plugin):
            tests = ExtensionPoint(ITest)
        class OtherPlugin(Plugin):
            _extends = ['one.tests']
            advise(instancesProvide=[ITest])
            def test(self): return 'x'
        class AnotherPlugin(Plugin):
            _extends = ['one.tests']
            advise(instancesProvide=[ITest])
            def test(self): return 'y'
        def f(x):
            return x == 'another'
        plugin = self.pluginManager.plugin('one')
        tests = [t.test() for t in plugin.tests(constrain=f)]
        self.assertEquals(1, len(tests))
        self.assertEquals('y', tests[0])

    def testExtensionProxyOrdering(self):
        class ITest(Interface):
            def test(): pass
        class OnePlugin(Plugin):
            tests = ExtensionPoint(ITest)
        class OtherPlugin(Plugin):
            _extends = ['one.tests']
            advise(instancesProvide=[ITest])
            def test(self): return 'x'
        class AnotherPlugin(Plugin):
            _extends = ['one.tests']
            advise(instancesProvide=[ITest])
            def test(self): return 'y'
        def f(a, b):
            return cmp(a, b)
        plugin = self.pluginManager.plugin('one')
        tests = [t.test() for t in plugin.tests(order=f)]
        self.assertEquals(2, len(tests))
        self.assertEquals('y', tests[0])
        self.assertEquals('x', tests[1])

    def testExtensionsProxyReversed(self):
        class ITest(Interface):
            def test(): pass
        class OnePlugin(Plugin):
            tests = ExtensionPoint(ITest)
        class OtherPlugin(Plugin):
            _extends = ['one.tests']
            advise(instancesProvide=[ITest])
            def test(self): return 'x'
        class AnotherPlugin(Plugin):
            _extends = ['one.tests']
            advise(instancesProvide=[ITest])
            def test(self): return 'y'
        plugin = self.pluginManager.plugin('one')
        tests = [t.test() for t in plugin.tests(reverse=1)]
        self.assertEquals(2, len(tests))
        self.assertEquals('y', tests[0])
        self.assertEquals('x', tests[1])

    def testExtensionsProxyReversedOrdering(self):
        class ITest(Interface):
            def test(): pass
        class OnePlugin(Plugin):
            tests = ExtensionPoint(ITest)
        class OtherPlugin(Plugin):
            _extends = ['one.tests']
            advise(instancesProvide=[ITest])
            def test(self): return 'x'
        class AnotherPlugin(Plugin):
            _extends = ['one.tests']
            advise(instancesProvide=[ITest])
            def test(self): return 'y'
        def f(a, b):
            return cmp(a, b)
        plugin = self.pluginManager.plugin('one')
        tests = [t.test() for t in plugin.tests(order=f, reverse=1)]
        self.assertEquals(2, len(tests))
        self.assertEquals('x', tests[0])
        self.assertEquals('y', tests[1])

    def testActivationListener(self):
        class OnePlugin(Plugin):
            pass
        class ActivationListener(Plugin):
            _id = 'listener'
            _extends = ['plugin.activationListeners']
            advise(instancesProvide=[IPluginActivationListener])
            activeCount = 0
            def pluginActivated(self, plugin):
                self.activeCount += 1
        listener = self.pluginManager.plugin('listener')
        self.assertEquals(1, listener.activeCount)
        self.pluginManager.plugin('one')
        self.assertEquals(2, listener.activeCount)

    def tearDown(self):
        from trac.plugin import PluginRegistry
        PluginRegistry.plugins = {}
        PluginRegistry.extensionPoints = {}


def suite():
    return unittest.makeSuite(PluginTestCase, 'test')

if __name__ == '__main__':
    unittest.main()
