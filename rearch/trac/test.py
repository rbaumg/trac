#!/usr/bin/env python
import unittest

import tests.wiki
import tests.href
import tests.ticket
import tests.perm_test
import tests.environment
import tests.diff
import tests.tracadmin
import tests.query
import tests.plugin
import tests.web.clearsilver
import tests.web.main


def suite():
    suite = unittest.TestSuite()
    suite.addTest(tests.wiki.suite())
    suite.addTest(tests.href.suite())
    suite.addTest(tests.ticket.suite())
    suite.addTest(tests.perm_test.suite())
    suite.addTest(tests.environment.suite())
    suite.addTest(tests.diff.suite())
    suite.addTest(tests.tracadmin.suite())
    suite.addTest(tests.query.suite())
    suite.addTest(tests.plugin.suite())
    suite.addTest(tests.web.clearsilver.suite())
    suite.addTest(tests.web.main.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
