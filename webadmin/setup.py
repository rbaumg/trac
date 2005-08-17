#!/usr/bin/env python

import ez_setup
ez_setup.use_setuptools()
from setuptools import setup, find_packages

PACKAGE = 'TracWebAdmin'
VERSION = '0.1'

setup(name=PACKAGE, version=VERSION,
      packages=find_packages(exclude=['ez_setup', '*.tests*']),
      package_data={'webadmin': ['htdocs/css/*.css', 'htdocs/img/*.png',
                                 'htdocs/js/*.js', 'templates/*.cs']})
