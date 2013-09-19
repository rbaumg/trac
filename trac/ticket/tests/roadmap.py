# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2013 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.

from trac.test import EnvironmentStub
from trac.ticket.roadmap import *
from trac.core import ComponentManager

import unittest

class TicketGroupStatsTestCase(unittest.TestCase):

    def setUp(self):
        self.stats = TicketGroupStats('title', 'units')

    def test_init(self):
        self.assertEqual('title', self.stats.title, 'title incorrect')
        self.assertEqual('units', self.stats.unit, 'unit incorrect')
        self.assertEqual(0, self.stats.count, 'count not zero')
        self.assertEqual(0, len(self.stats.intervals), 'intervals not empty')

    def test_add_iterval(self):
        self.stats.add_interval('intTitle', 3, {'k1': 'v1'}, 'css', 0)
        self.stats.refresh_calcs()
        self.assertEqual(3, self.stats.count, 'count not incremented')
        int = self.stats.intervals[0]
        self.assertEqual('intTitle', int['title'], 'title incorrect')
        self.assertEqual(3, int['count'], 'count incorrect')
        self.assertEqual({'k1': 'v1'}, int['qry_args'], 'query args incorrect')
        self.assertEqual('css', int['css_class'], 'css class incorrect')
        self.assertEqual(100, int['percent'], 'percent incorrect')
        self.stats.add_interval('intTitle', 3, {'k1': 'v1'}, 'css', 0)
        self.stats.refresh_calcs()
        self.assertEqual(50, int['percent'], 'percent not being updated')

    def test_add_interval_no_prog(self):
        self.stats.add_interval('intTitle', 3, {'k1': 'v1'}, 'css', 0)
        self.stats.add_interval('intTitle', 5, {'k1': 'v1'}, 'css', 0)
        self.stats.refresh_calcs()
        interval = self.stats.intervals[1]
        self.assertEqual(0, self.stats.done_count, 'count added for no prog')
        self.assertEqual(0, self.stats.done_percent, 'percent incremented')

    def test_add_interval_prog(self):
        self.stats.add_interval('intTitle', 3, {'k1': 'v1'}, 'css', 0)
        self.stats.add_interval('intTitle', 1, {'k1': 'v1'}, 'css', 1)
        self.stats.refresh_calcs()
        self.assertEqual(4, self.stats.count, 'count not incremented')
        self.assertEqual(1, self.stats.done_count, 'count not added to prog')
        self.assertEqual(25, self.stats.done_percent, 'done percent not incr')

    def test_add_interval_fudging(self):
        self.stats.add_interval('intTitle', 3, {'k1': 'v1'}, 'css', 0)
        self.stats.add_interval('intTitle', 5, {'k1': 'v1'}, 'css', 1)
        self.stats.refresh_calcs()
        self.assertEqual(8, self.stats.count, 'count not incremented')
        self.assertEqual(5, self.stats.done_count, 'count not added to prog')
        self.assertEqual(62, self.stats.done_percent,
                         'done percnt not fudged downward')
        self.assertEqual(62, self.stats.intervals[1]['percent'],
                         'interval percent not fudged downward')
        self.assertEqual(38, self.stats.intervals[0]['percent'],
                         'interval percent not fudged upward')


class DefaultTicketGroupStatsProviderTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(default_data=True)

        self.milestone1 = Milestone(self.env)
        self.milestone1.name = 'Test'
        self.milestone1.insert()
        self.milestone2 = Milestone(self.env)
        self.milestone2.name = 'Test2'
        self.milestone2.insert()

        tkt1 = Ticket(self.env)
        tkt1.populate({'summary': 'Foo', 'milestone': 'Test', 'owner': 'foman',
                        'status': 'new'})
        tkt1.insert()
        tkt2 = Ticket(self.env)
        tkt2.populate({'summary': 'Bar', 'milestone': 'Test',
                        'status': 'closed', 'owner': 'barman'})
        tkt2.insert()
        tkt3 = Ticket(self.env)
        tkt3.populate({'summary': 'Sum', 'milestone': 'Test', 'owner': 'suman',
                        'status': 'reopened'})
        tkt3.insert()
        self.tkt1 = tkt1
        self.tkt2 = tkt2
        self.tkt3 = tkt3

        prov = DefaultTicketGroupStatsProvider(ComponentManager())
        prov.env = self.env
        prov.config = self.env.config
        self.stats = prov.get_ticket_group_stats([tkt1.id, tkt2.id, tkt3.id])

    def tearDown(self):
        self.env.reset_db()

    def test_stats(self):
        self.assertEqual(self.stats.title, 'ticket status', 'title incorrect')
        self.assertEqual(self.stats.unit, 'tickets', 'unit incorrect')
        self.assertEqual(2, len(self.stats.intervals), 'more than 2 intervals')

    def test_closed_interval(self):
        closed = self.stats.intervals[0]
        self.assertEqual('closed', closed['title'], 'closed title incorrect')
        self.assertEqual('closed', closed['css_class'], 'closed class incorrect')
        self.assertTrue(closed['overall_completion'],
                        'closed should contribute to overall completion')
        self.assertEqual({'status': ['closed'], 'group': ['resolution']},
                         closed['qry_args'], 'qry_args incorrect')
        self.assertEqual(1, closed['count'], 'closed count incorrect')
        self.assertEqual(33, closed['percent'], 'closed percent incorrect')

    def test_open_interval(self):
        open = self.stats.intervals[1]
        self.assertEqual('active', open['title'], 'open title incorrect')
        self.assertEqual('open', open['css_class'], 'open class incorrect')
        self.assertFalse(open['overall_completion'],
                         "open shouldn't contribute to overall completion")
        self.assertEqual({'status':
                          [u'assigned', u'new', u'accepted', u'reopened']},
                         open['qry_args'], 'qry_args incorrect')
        self.assertEqual(2, open['count'], 'open count incorrect')
        self.assertEqual(67, open['percent'], 'open percent incorrect')


def in_tlist(ticket, list):
    return len([t for t in list if t['id'] == ticket.id]) > 0

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TicketGroupStatsTestCase, 'test'))
    suite.addTest(unittest.makeSuite(DefaultTicketGroupStatsProviderTestCase,
                                      'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
