#!/usr/bin/env python

from setuptools import setup

PACKAGE = 'TracWebAdmin'
VERSION = '0.1'

setup(name=PACKAGE, version=VERSION, packages=['webadmin'],
      package_data={'webadmin': ['htdocs/css/*.css', 'htdocs/img/*.png',
                                 'htdocs/js/*.js', 'templates/*.cs']})
