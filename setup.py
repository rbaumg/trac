#!/usr/bin/env python

from setuptools import setup

PACKAGE = 'TracWebAdmin'
VERSION = '0.1'

setup(name=PACKAGE, version=VERSION, packages=['webadmin'],
      package_data={'webadmin': ['templates/*.cs', 'htdocs/css/*.css']})

