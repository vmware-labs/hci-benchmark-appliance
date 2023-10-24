#!/usr/bin/env python

"""
Copyright 2008-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is an implementation for cli info object Vim.CLIManager
"""
__author__ = "VMware, Inc"

from pyVmomi import Vim
from MoManager import GetMoManager
from . import CLIInfoMgr

## The Vim.CLIManager implementation class
#
class CLIInfoImpl(Vim.CLIInfo):
   """
   Vim.CLIInfo implementation
   """

   # Fetch cli info for a type name
   def FetchCLIInfo(self, typeName):
      try:
         return CLIInfoMgr.GetCLIInfoMgr().FetchCLIInfo(typeName)
      except KeyError:
         message = str(typeName) + " not found"
         raise Vim.Fault.NotFound(message=message)

   # Fetch cli info form display name
   def FetchCLIInfoFromDisplayName(self, name):
      try:
         return CLIInfoMgr.GetCLIInfoMgr().FetchCLIInfoFromDisplayName(name)
      except KeyError:
         message = str(name) + " not found"
         raise Vim.Fault.NotFound(message=message)

# Add managed objects during import
GetMoManager().RegisterObjects([CLIInfoImpl("ha-cli-info-python")])
