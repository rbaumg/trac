# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.

import unittest

import trac.tests.compat
from trac.config import ConfigurationError
from trac.perm import PermissionCache, PermissionSystem
from trac.test import EnvironmentStub, Mock, MockRequest
from trac.ticket.api import TicketSystem
from trac.ticket.batch import BatchModifyModule
from trac.ticket.model import Ticket
from trac.ticket.default_workflow import ConfigurableTicketWorkflow


class ConfigurableTicketWorkflowTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()

    def test_ignores_other_operations(self):
        """Ignores operations not defined by ConfigurableTicketWorkflow.
        """
        self.env.config.set('ticket-workflow', 'review', 'assigned -> review')
        self.env.config.set('ticket-workflow', 'review.operations',
                            'CodeReview')
        ctw = ConfigurableTicketWorkflow(self.env)
        ticket = Ticket(self.env)
        ticket.populate({'summary': '#13013', 'status': 'assigned'})
        ticket.insert()
        req = MockRequest(self.env)

        self.assertNotIn((0, 'review'), ctw.get_ticket_actions(req, ticket))


class ResetActionTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(default_data=True)
        self.perm_sys = PermissionSystem(self.env)
        self.ctlr = TicketSystem(self.env).action_controllers[0]
        self.req1 = Mock(authname='user1', args={},
                         perm=PermissionCache(self.env, 'user1'))
        self.req2 = Mock(authname='user2', args={},
                         perm=PermissionCache(self.env, 'user2'))
        self.ticket = Ticket(self.env)
        self.ticket['status'] = 'invalid'
        self.ticket.insert()

    def tearDown(self):
        self.env.reset_db()

    def _reload_workflow(self):
        self.ctlr.actions = self.ctlr.get_all_actions()

    def test_default_reset_action(self):
        """Default reset action."""
        self.perm_sys.grant_permission('user2', 'TICKET_ADMIN')
        self._reload_workflow()

        actions1 = self.ctlr.get_ticket_actions(self.req1, self.ticket)
        actions2 = self.ctlr.get_ticket_actions(self.req2, self.ticket)
        chgs2 = self.ctlr.get_ticket_changes(self.req2, self.ticket, '_reset')

        self.assertEqual(1, len(actions1))
        self.assertNotIn((0, '_reset'), actions1)
        self.assertEqual(2, len(actions2))
        self.assertIn((0, '_reset'), actions2)
        self.assertEqual('new', chgs2['status'])

    def test_custom_reset_action(self):
        """Custom reset action in [ticket-workflow] section."""
        config = self.env.config['ticket-workflow']
        config.set('_reset', '-> review')
        config.set('_reset.operations', 'reset_workflow')
        config.set('_reset.permissions', 'TICKET_BATCH_MODIFY')
        config.set('_reset.default', 2)
        self.perm_sys.grant_permission('user2', 'TICKET_BATCH_MODIFY')
        self._reload_workflow()

        actions1 = self.ctlr.get_ticket_actions(self.req1, self.ticket)
        actions2 = self.ctlr.get_ticket_actions(self.req2, self.ticket)
        chgs2 = self.ctlr.get_ticket_changes(self.req2, self.ticket, '_reset')

        self.assertEqual(1, len(actions1))
        self.assertNotIn((2, '_reset'), actions1)
        self.assertEqual(2, len(actions2))
        self.assertIn((2, '_reset'), actions2)
        self.assertEqual('review', chgs2['status'])


class SetResolutionAttributeTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(default_data=True)
        for ctlr in TicketSystem(self.env).action_controllers:
            if isinstance(ctlr, ConfigurableTicketWorkflow):
                self.ctlr = ctlr

    def tearDown(self):
        self.env.reset_db()

    def _reload_workflow(self):
        self.ctlr.actions = self.ctlr.get_all_actions()

    def test_empty_set_resolution(self):
        config = self.env.config['ticket-workflow']
        config.set('resolve.set_resolution', '')
        self._reload_workflow()
        ticket = Ticket(self.env)
        ticket.populate({'summary': '#12882', 'status': 'new'})
        ticket.insert()
        req = MockRequest(self.env, path_info='/ticket/%d' % ticket.id)
        try:
            self.ctlr.render_ticket_action_control(req, ticket, 'resolve')
            self.fail('ConfigurationError not raised')
        except ConfigurationError, e:
            self.assertIn('but none is defined', unicode(e))

    def test_undefined_resolutions(self):
        config = self.env.config['ticket-workflow']
        ticket = Ticket(self.env)
        ticket.populate({'summary': '#12882', 'status': 'new'})
        ticket.insert()
        req = MockRequest(self.env, path_info='/ticket/%d' % ticket.id)

        config.set('resolve.set_resolution',
                   'fixed,invalid,wontfix,,duplicate,worksforme,,,,,')
        self._reload_workflow()
        self.ctlr.render_ticket_action_control(req, ticket, 'resolve')

        config.set('resolve.set_resolution', 'undefined,fixed')
        self._reload_workflow()
        try:
            self.ctlr.render_ticket_action_control(req, ticket, 'resolve')
            self.fail('ConfigurationError not raised')
        except ConfigurationError, e:
            self.assertIn('but uses undefined resolutions', unicode(e))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ConfigurableTicketWorkflowTestCase))
    suite.addTest(unittest.makeSuite(ResetActionTestCase))
    suite.addTest(unittest.makeSuite(SetResolutionAttributeTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
