#!/usr/bin/env python
import unittest

import tests.wiki
import tests.href
import tests.environment

def suite():
    suite = unittest.TestSuite()
    suite.addTest(tests.wiki.suite())
    suite.addTest(tests.href.suite())
    suite.addTest(tests.environment.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
