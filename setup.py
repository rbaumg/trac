#!/usr/bin/env python

import os
from distutils.core import setup
import trac

VERSION = str(trac.__version__)
URL = trac.__url__
LICENSE = trac.__license__

setup(name="trac",
      description="",
      version=VERSION,
      license=LICENSE,
      url=URL,
      packages=['trac'],
      scripts=[os.path.join('scripts', 'trac-admin')])

