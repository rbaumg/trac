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

from trac.web.clearsilver import *

import unittest

class ClearSilverTemplateNodeTestCase(unittest.TestCase):

    def setUp(self):
        import neo_cgi, neo_util
        self.hdf = neo_util.HDF()
        self.data = HDFNode(self.hdf)

    def testAddTopLevelString(self):
        self.data['title'] = 'Test'
        self.assertEquals('Test', self.hdf.getValue('title', ''))

    def testAddTopLevelList(self):
        self.data['items'] = ['Item 1', 'Item 2']
        self.assertEquals('Item 1', self.hdf.getValue('items.0', ''))
        self.assertEquals('Item 2', self.hdf.getValue('items.1', ''))

    def testAddTopLevelDict(self):
        self.data['item'] = {'name': 'Item 1', 'value': '1'}
        self.assertEquals('Item 1', self.hdf.getValue('item.name', ''))
        self.assertEquals('1', self.hdf.getValue('item.value', ''))

    def testAddNestedString(self):
        self.data['test']['title'] = 'Test'
        self.assertEquals('Test', self.hdf.getValue('test.title', ''))

    def testAddNestedList(self):
        self.data['test']['items'] = ['Item 1', 'Item 2']
        self.assertEquals('Item 1', self.hdf.getValue('test.items.0', ''))
        self.assertEquals('Item 2', self.hdf.getValue('test.items.1', ''))

    def testAddNestedDict(self):
        self.data['test']['item'] = {'name': 'Item 1', 'value': '1'}
        self.assertEquals('Item 1', self.hdf.getValue('test.item.name', ''))
        self.assertEquals('1', self.hdf.getValue('test.item.value', ''))

    def testReplaceTopLevelString(self):
        self.data['title'] = 'Foobar'
        self.data['title'] = 'Test'
        self.assertEquals('Test', self.hdf.getValue('title', ''))

    def testReplaceTopLevelList(self):
        self.data['items'] = 'Foobar'
        self.data['items'] = ['Item 1', 'Item 2']
        self.assertEquals('Item 1', self.hdf.getValue('items.0', ''))
        self.assertEquals('Item 2', self.hdf.getValue('items.1', ''))

    def testReplaceTopLevelDict(self):
        self.data['item'] = 'Foobar'
        self.data['item'] = {'name': 'Item 1', 'value': '1'}
        self.assertEquals('Item 1', self.hdf.getValue('item.name', ''))
        self.assertEquals('1', self.hdf.getValue('item.value', ''))

    def testReplaceNestedString(self):
        self.data['test'] = 'Foo'
        self.data['test']['title'] = 'Bar'
        self.data['test']['title'] = 'Test'
        self.assertEquals('Test', self.hdf.getValue('test.title', ''))

    def testReplaceNestedList(self):
        self.data['test'] = 'Foo'
        self.data['test']['items'] = 'Bar'
        self.data['test']['items'] = ['Item 1', 'Item 2']
        self.assertEquals('Item 1', self.hdf.getValue('test.items.0', ''))
        self.assertEquals('Item 2', self.hdf.getValue('test.items.1', ''))

    def testReplaceNestedDict(self):
        self.data['test'] = 'Foo'
        self.data['test']['item'] = 'Bar'
        self.data['test']['item'] = {'name': 'Item 1', 'value': '1'}
        self.assertEquals('Item 1', self.hdf.getValue('test.item.name', ''))
        self.assertEquals('1', self.hdf.getValue('test.item.value', ''))

    def testReplaceItemInList(self):
        self.data['items'] = ['Item 1', 'Item 2']
        self.data['items'][0] = 'Item 0'
        self.assertEquals('Item 0', self.hdf.getValue('items.0', ''))
        self.assertEquals('Item 2', self.hdf.getValue('items.1', ''))

    def testReplaceItemInDict(self):
        self.data['item'] = {'name': 'Item 1', 'value': '1'}
        self.data['item']['value'] = '2'
        self.assertEquals('Item 1', self.hdf.getValue('item.name', ''))
        self.assertEquals('2', self.hdf.getValue('item.value', ''))

    def testRemoveString(self):
        self.data['title'] = 'Test'
        del self.data['title']
        self.assertEquals(None, self.hdf.getObj('title'))

    def testRemoveList(self):
        self.data['items'] = ['Item 1', 'Item 2']
        del self.data['items']
        self.assertEquals(None, self.hdf.getObj('items'))

    def testRemoveDict(self):
        self.data['item'] = {'name': 'Item 1', 'value': '1'}
        del self.data['item']
        self.assertEquals(None, self.hdf.getObj('item'))

    def testClearString(self):
        self.data['title'] = 'Test'
        self.data.clear()
        self.assertEquals(None, self.hdf.getObj('title'))

    def testClearList(self):
        self.data['items'] = ['Item 1', 'Item 2']
        self.data.clear()
        self.assertEquals(None, self.hdf.getObj('items'))

    def testClearDict(self):
        self.data['item'] = {'name': 'Item 1', 'value': '1'}
        self.data.clear()
        self.assertEquals(None, self.hdf.getObj('item'))


def suite():
    return unittest.makeSuite(ClearSilverTemplateNodeTestCase, 'test')

if __name__ == '__main__':
    unittest.main()
