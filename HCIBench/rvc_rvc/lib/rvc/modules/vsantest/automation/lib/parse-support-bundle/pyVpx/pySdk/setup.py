#!/usr/bin/env python
"""
Copyright 2010 VMware, Inc.  All rights reserved.

This module is the pySdk setup file to generate a distributable
"""

from distutils.core import setup

companyName = "VMware, Inc."
copyrightStr = "Copyright 2010 VMware, Inc.  All rights reserved."
regNameStr = '##{PACKAGENAME}##'
versionStr = '##{PACKAGEVERSION}##'
descStr = 'VMware vSphere Python SDK'
longDescStr = 'Public pyVmomi SDK containing pyVmomi types and some sample scripts'

setup(name=regNameStr,
      version=versionStr,
      license=copyrightStr,
      description=descStr,
      long_description=longDescStr,
      packages=['pyVmomi', 'pyVim', 'sample'],
     )
