#!/usr/bin/env python

"""
Copyright 2008-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is the CLIInfo manager
"""

# import CLIInfo to bring CLIInfo in Vim namespace
from . import CLIInfo
from pyVmomi import Vim, VmomiSupport
import six


## CLI info container
#
class CLIInfoContainer:
   """ CLI Info container """

   ## Constructor
   def __init__(self, name, cliName, help, displayName):
      """ CLI Info constructor """
      self.name = name
      self.cliName = cliName
      self.help = help
      self.displayName = displayName
      self.method = {}


## CLI info manager
#
class CLIInfoMgr:
   """ CLI info manager """

   ## CLI Info manager constructor
   def __init__(self):
      """ CLI Info manager constructor """
      self._info = {}

   ## Fetch CLI info from vmodl name
   #
   # @param  name Vmodl name
   # @return Vim.CLIInfo
   def FetchCLIInfo(self, name):
      """ Get CLI info from vmodl name """
      info = self._info[name]
      return self._BuildVimCLIInfo(info)

   ## Fetch CLI info from cli display name
   #
   # @param  name CLI display name
   # @return Vim.CLIInfo
   def FetchCLIInfoFromDisplayName(self, name):
      """ Get CLI info from vmodl name """
      for info in six.itervalues(self._info):
         if info.displayName == name:
            return self._BuildVimCLIInfo(info)
      raise KeyError("Error: " + str(name) + " not found")

   ## Register CLI managed type
   #
   # @param  info Managed info
   def Register(self, name, managedInfo):
      assert(isinstance(managedInfo, CLIInfoContainer))
      info = self._info.get(name)
      self._info[name] = managedInfo

   ## Register CLI method
   #
   # @param  parent Parent's vmodl name
   # @param  method Vim.CLIInfo.Method object
   def RegisterMethod(self, parent, method):
      """ Register CLI method """
      assert(isinstance(method, Vim.CLIInfo.Method))
      info = self._info.get(parent)
      info.method[method.name] = method

   ## Create CLI managed type info container
   #
   # @param  name Managed vmodl name
   # @param  cliName Name appear on command line
   # @param  help Parameter help
   # @return CLIInfoContainer
   def CreateManagedInfo(self, name, cliName=None, help=None, displayName=None):
      if not cliName:
         cliName = name
      if not displayName:
         displayName = cliName.rsplit('.', 1)[-1]
      info = CLIInfoContainer(name, cliName, help, displayName)
      return info

   ## Create CLI parameter container
   #
   # @param  name Parameter name
   # @param  aliases Parameter aliases
   # @param  default Default value
   # @param  constraint Value constraint
   # @param  help Parameter help
   # @return Vim.CLIInfo.Param object
   def CreateParam(self, name, aliases=None, default=None, constraint=None,
                   help=None, displayName=None):
      """ Create CLI parameter container """
      param = Vim.CLIInfo.Param()
      param.name = name
      if displayName:
         param.displayName = displayName
      else:
         param.displayName = name
      param.aliases = aliases
      param.default = default
      param.constraint = constraint
      param.help = help
      return param

   ## Create CLI method container
   #
   # @param  name Method name
   # @param  params Method parameters (a list of Vim.CLIInfo.Param)
   # @param  returns Method returns
   # @param  hints Parameter hints (vim.KeyValue[])
   # @param  help Method help
   # @return Vim.CLIInfo.Method object
   def CreateMethod(self, name, params=None, returns=None, hints=None,
                    help=None, displayName=None):
      """ Create CLI method container """
      method = Vim.CLIInfo.Method()
      if displayName:
         method.displayName = displayName
      else:
         method.displayName = name
      method.name = name
      method.param = params
      method.ret = returns
      method.hints = hints
      method.help = help
      return method

   ## Buld vim.CLIInfo from cli info
   #
   # @param  info CLI info
   # @return Vim.CLIInfo
   def _BuildVimCLIInfo(self, info):
      """ Build vim cli info """
      cliInfo = Vim.CLIInfo.Info()
      cliInfo.name = info.cliName
      cliInfo.displayName = info.displayName
      cliInfo.help = info.help
      cliInfo.method = list(info.method.values())
      return cliInfo


## Get CLI info manager
#
_gCLIInfoMgr = CLIInfoMgr()
def GetCLIInfoMgr():
   """ Get the vmomi type manager """
   return _gCLIInfoMgr
