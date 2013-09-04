# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2013 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.com/license.html.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/.

import unittest

from trac.versioncontrol.web_ui.tests import wikisyntax

def suite():
    suite = unittest.TestSuite()
    suite.addTest(wikisyntax.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
