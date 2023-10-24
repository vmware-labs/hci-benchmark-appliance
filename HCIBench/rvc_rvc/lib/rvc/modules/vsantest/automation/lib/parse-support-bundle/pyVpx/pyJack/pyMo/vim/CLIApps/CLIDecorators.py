#!/usr/bin/env python

"""
Copyright 2008-2019 VMware, Inc.  All rights reserved.
-- VMware Confidential

This module provides decorators for dynamic command line types declaration
"""
__author__ = "VMware, Inc"

# import decorators
import six
import logging
from pyVmomi import Vim, VmomiSupport
from VmodlDecorators import \
    ManagedType, DataType, EnumType, \
    Attribute, Method, Param, Return, \
    F_LINK, F_LINKABLE, F_OPTIONAL, \
    VmodlDecoratorException, \
    RegisterVmodlTypes, FlushVmodlTypes
from .CLIInfo import VIM_CLI, VIM_ESXCLI
from . import CLIInfoMgr

# Flags
#CLI_F_LINK     = F_LINK
#CLI_F_LINKABLE = F_LINKABLE
CLI_F_OPTIONAL = F_OPTIONAL

# Version
_VERSION = VmomiSupport.oldestVersions.GetName('vim')

# Capitalization for ESXCLI is governed by the following conventions established
# in K/L and M/N:
#
# VMODL Name for Managed Object Methods:
# * Components of name are dot separated
# * prefix is "vim.EsxCLI."
# * ESXCLI namespaces are all lowercase (eg. "hardware.cpu")
# * Method starts with upper case (eg. "List")
#
# For example, vim.EsxCLI.hardware.cpu.List, vim.EsxCLI.esxcli.command.List
#
# WSDL Name for Managed Object Methods:
# * Components of name are joined without a separator
# * prefix is "VimEsxCLI"
# * ESXCLI namespaces are all lower case (eg. "hardwarecpu"
# * Method starts with lower case (eg. "list")
#
# For example, VimEsxCLIhardwarecpulist, VimEsxCLIesxclicommandlist
#
# As a result, convert the VMODL names into WSDL names by
# (1) capitalizing only the first name components
# (2) removing dots
# (3) uncapitalizing the method name
#
def GenerateClassWsdlName(dottedName):
   ret = dottedName.split(".")
   for i in range(len(ret)):
      if ret[i][0].isupper():
         break
      else:
         ret[i] = VmomiSupport.Capitalize(ret[i])
   return "".join(ret)

def GenerateMethodWsdlName(dottedName, methodName):
   return GenerateClassWsdlName(dottedName) + VmomiSupport.Uncapitalize(methodName)

## Base CLI Decorator exception
#
class CLIDecoratorException(VmodlDecoratorException):
   """ Base CLI Decorator exception """
   def __init__(self, *args, **kwargs):
      VmodlDecoratorException.__init__(self, *args, **kwargs)


## Get hints (convert dict to Vim.KeyValue[])
#
def GetHints(hints):
   """ Get hints suitable for CLI Info """
   paramHints = None
   if hints:
      if isinstance(hints, dict):
         paramHints = Vim.KeyValue.Array()
         for key, value in six.iteritems(hints):
            paramHints.append(Vim.KeyValue(key=key, value=value))
      else:
         paramHints = hints
   return paramHints


## CLI managed type decorator (extends VmodlDecorators.ManagedType)
#
# @param  name fully qualified vmodl name
# @param  version Version
# @param  displayName managed type display name
# @return CLI Managed type decorator
def CLIManagedType(name, version=_VERSION, displayName=None):
   """ CLI managed type decorator (extends VmodlDecorators.ManagedType) """
   def Decorate(f):
      wsdlName = GenerateClassWsdlName(name)

      # Create managed type
      managed = ManagedType(name=name, version=version, wsdlName=wsdlName)(f)

      if name.startswith(VIM_ESXCLI):
         cmdlineName = name[len(VIM_ESXCLI) + 1:]
      else:
         cmdlineName = name

      # Register managed info
      cliInfoMgr = CLIInfoMgr.GetCLIInfoMgr()
      cliManagedInfo = cliInfoMgr.CreateManagedInfo(name=name,
                                                    cliName=cmdlineName,
                                                    help=f.__doc__,
                                                    displayName=displayName)
      cliInfoMgr.Register(name, cliManagedInfo)

      return managed
   return Decorate


## CLI method decorator (extends VmodlDecorators.Method)
#
# @param  name fully qualified vmodl name
# @param  version Version. None => same as parent version
# @param  faults Method faults
# @param  privId Privilege Id
# @param  hints Parameter hints (dict or vim.KeyValue[])
# @param  displayName Method display name
# @return CLI Method decorator
def CLIMethod(parent, version=None, faults=None, privId=None, hints=None,
              displayName=None):
   """ CLI method decorator constructor """
   def Decorate(f):
      """ CLI method decorator (extends VmodlDecorators.Method) """
      wsdlName = GenerateMethodWsdlName(parent, f.__name__)

      # Call vmodl method decorator
      method = Method(parent, version=version, faults=faults, privId=privId, wsdlName=wsdlName)(f)

      cliParams = hasattr(f, "_cliParams") and f._cliParams or []
      cliReturns = hasattr(f, "_cliReturns") and f._cliReturns or None

      # Verify cli params
      aliases = {}
      for cliParam in cliParams:
         # Do not allow duplicated aliases
         for alias in cliParam.aliases:
            if alias in aliases:
               # Duplicated alias
               message = "@Param " + cliParam.name + " aliases " + alias + \
                         " already defined in @Param " + aliases[alias].name
               logging.error(message)
               raise CLIDecoratorException(message)
            else:
               aliases[alias] = cliParam
      del aliases

      # Get method hints
      methodHints = GetHints(hints)

      # Register CLI method
      cliInfoMgr = CLIInfoMgr.GetCLIInfoMgr()
      cliMethod = cliInfoMgr.CreateMethod(name=f.__name__, params=cliParams,
                                          returns=cliReturns, hints=methodHints,
                                          help=f.__doc__,
                                          displayName=displayName)
      cliInfoMgr.RegisterMethod(parent, cliMethod)
      return method
   return Decorate


## CLI method parameter decorator (extends VmodlDecorators.Param)
#
# @param  name fully qualified vmodl name
# @param  typ fully qualified vmodl type name
# @param  version Version. None => same as parent version
# @param  flags Param flags
# @param  aliases List of param aliases. e.g. ["-l", "--List"]
# @param  default Param val default
# @param  constraint List of constraint
#           e.g. ["min=-100", "max=100"], ["a", "b", "c"]
# @param  help Param help
# @param  displayName Parameter display name
# @return CLI Param decorator
def CLIParam(name, typ, version=None, flags=0,
             aliases=None, default=None, constraint=None,
             help=None, displayName=None):
   """ CLI param decorator constructor """
   def Decorate(f):
      """ CLI method parameter decorator (extends VmodlDecorators.Param) """
      # Call vmodl param decorator
      param = Param(name, typ, version=version, flags=flags)(f)

      # At least one alias => --{paramName}
      if aliases == None:
         # One short name, one long name
         paramAliases = ["-" + name[0], "--" + name]
      else:
         paramAliases = aliases

      # Create a cli param
      cliInfoMgr = CLIInfoMgr.GetCLIInfoMgr()
      cliParam = cliInfoMgr.CreateParam(name=name, aliases=paramAliases,
                                        default=default, constraint=constraint,
                                        help=help, displayName=displayName)

      # Insert cli param
      if not hasattr(f, "_cliParams"):
         f._cliParams = [cliParam]
      else:
         f._cliParams.insert(0, cliParam)
      return param
   return Decorate


## CLI method return decorator (extends VmodlDecorators.Return)
#
# @param  typ fully qualified vmodl type name
# @param  flags Return flags
# @param  help Return help
# @return CLI Return decorator
def CLIReturn(typ, flags=0, help=None):
   """ CLI return decorator constructor """
   def Decorate(f):
      """ CLI method return decorator (extends VmodlDecorators.Return) """
      # Call vmodl return decorator
      ret = Return(typ, flags=flags)(f)

      # Create a cli param
      cliInfoMgr = CLIInfoMgr.GetCLIInfoMgr()
      f._cliReturns = cliInfoMgr.CreateParam(name="return", help=help)
      return ret
   return Decorate


## CLIBase type
class CLIBaseObject(object):
   pass


## Convert class to vmodl based class
#
# @param classToVmodls an iterables tuples of (CLI class, vmodl base name)
def CLIConvertToVmodlClass(classToVmodls):
   """ Convert class to vmodl based class """
   for cls, vmodlName in classToVmodls:
      try:
         vmodlType = VmomiSupport.GetVmodlType(vmodlName)
      except AttributeError:
         # Failed to find vmodl name
         logging.error("CLIConvertToVmodlClass: vmodl type %s not found" %
                                                                     vmodlName)
         raise

      # Patch the base if the class is not already based on this vmodl type
      if vmodlType not in cls.__bases__:
         cls.__bases__ = tuple(list(cls.__bases__) +
                                       [VmomiSupport.GetVmodlType(vmodlName)])


## Register
#
# @param classToVmodls an iterables tuples of (CLI class, vmodl base name)
def RegisterCLITypes(classToVmodlMapping=None, doNotFlush=False):
   """ Register CLI types into system """
   registered = RegisterVmodlTypes(doNotFlush=doNotFlush)
   if classToVmodlMapping:
      CLIConvertToVmodlClass(classToVmodlMapping)
   return registered


## Simple function bypass
#
CLIDataType = DataType
CLIEnumType = EnumType
CLIAttribute = Attribute
FlushCLITypes = FlushVmodlTypes
