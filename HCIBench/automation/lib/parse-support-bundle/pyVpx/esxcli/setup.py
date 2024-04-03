#!/usr/bin/env python
"""
Copyright (c) 2008-2021 VMware, Inc.  All rights reserved.
-- VMware Confidential

This module is the py2exe setup file
"""
__author__ = "VMware, Inc"

from distutils.core import setup
import py2exe

includes = [ "gzip"]

excludes = [ "MacOS", "macpath", "os2", "os2emxpath", "posixpath",
             "email", "gopherlib", "ftplib", "mimetypes", "macurl2path",
             "distutils", "doctest", "pdb", "pydoc",
             "gettext", "uu", "quopri",
             "getopt", "popen2",
             "pyVmomi.CimsfccTypes",
             "pyVmomi.DmsTypes",
             "pyVmomi.HbrReplicaTypes",
             "pyVmomi.HmoTypes",
             "pyVmomi.ImgFactTypes",
             "pyVmomi.OmsTypes",
             "pyVmomi.RbdTypes",
             "pyVmomi.VorbTypes",
           ]

packages = [ "lxml", "OpenSSL", "pyVim", "pyVmomi"]

setup(console=["esxcli.py"],
      # zipfile=None, # If separate zip file: zipfile="esxcli.zip",
      zipfile="esxcli.zip",
      options={ "py2exe": { # Bundle everything except Python interpreter
                            "bundle_files": 2,
                            "compressed": 1,
                            "optimize": 2,
                            "packages": packages,
                            "includes": includes,
                            "excludes": excludes } }
     )
