from trac.Ticket import Ticket

import unittest


class TicketTestCase(unittest.TestCase):

    def setUp(self):
        from trac.test import InMemoryDatabase
        self.db = InMemoryDatabase()
        # taken from trac/tests/wiki.py, hum...
        from trac import Mimeview, Logging
        from trac.web.href import Href
        class Environment:
            def __init__(self):
                self.log = Logging.logger_factory('null')
                self.get_config = lambda x,y,z=None: z
                self.href = Href('/')
                self.abs_href = Href('http://www.example.com/')
                self._wiki_pages = {}
                self.path = ''
                self.mimeview = Mimeview.Mimeview(self)
        self.env = Environment()

    def test_create_ticket(self):
        """Testing Ticket.insert()"""
        # Multiple test in one method, this sucks
        # 1. Creating ticket
        ticket = Ticket()
        ticket['reporter'] = 'santa'
        ticket['summary'] = 'Foo'
        ticket['custom_foo'] = 'This is a custom field'
        self.assertEqual('santa', ticket['reporter'])
        self.assertEqual('Foo', ticket['summary'])
        self.assertEqual('This is a custom field', ticket['custom_foo'])
        ticket.insert(self.env, self.db)

        # Retrieving ticket
        ticket2 = Ticket(self.db, 1)
        self.assertEqual(1, ticket2['id'])
        self.assertEqual('santa', ticket2['reporter'])
        self.assertEqual('Foo', ticket2['summary'])
        self.assertEqual('This is a custom field', ticket2['custom_foo'])

        # Modifying ticket
        ticket2['summary'] = 'Bar'
        ticket2['custom_foo'] = 'New value'
        ticket2.save_changes(self.env, self.db, 'santa', 'this is my comment')

        # Retrieving ticket
        ticket3 = Ticket(self.db, 1)
        self.assertEqual(1, ticket3['id'])
        self.assertEqual(ticket3['reporter'], 'santa')
        self.assertEqual(ticket3['summary'], 'Bar')
        self.assertEqual(ticket3['custom_foo'], 'New value')

        # Testing get_changelog()
        log = ticket3.get_changelog(self.db)
        self.assertEqual(len(log), 3)
        ok_vals = ['foo', 'summary', 'comment']
        self.failUnless(log[0][2] in ok_vals)
        self.failUnless(log[1][2] in ok_vals)
        self.failUnless(log[2][2] in ok_vals)

def suite():
    return unittest.makeSuite(TicketTestCase,'test')


if __name__ == '__main__':
    unittest.main()
