#!/usr/bin/env python

"""
Copyright 2008-2019 VMware, Inc.  All rights reserved.
-- VMware Confidential

This module defines type info for managed object CLI Info
"""

from VmodlDecorators import \
    ManagedType, DataType, EnumType, \
    Attribute, Method, Param, Return, \
    F_LINK, F_LINKABLE, F_OPTIONAL, \
    VmodlDecoratorException, RegisterVmodlTypes
from pyVmomi import Vmodl
from pyVmomi.VmomiSupport import oldestVersions

## Vmodl names
#
_VERSION = oldestVersions.GetName('vim')
VIM_CLI = "vim.CLIInfo"
VIM_CLI_INFO = VIM_CLI + ".Info"
VIM_CLI_METHOD = VIM_CLI + ".Method"
VIM_CLI_EXAMPLE = VIM_CLI + ".Example"
VIM_CLI_PARAM = VIM_CLI + ".Param"

VIM_ESXCLI = "vim.EsxCLI"
VIM_ESXCLI_FAULT = VIM_ESXCLI + ".CLIFault"

## Command line interface method parameter info
#
class CLIParam:
   _name = VIM_CLI_PARAM

   @DataType(name=_name, version=_VERSION)
   def __init__(self): pass

   # Parameter name
   @Attribute(parent=_name, typ="string")
   def name(self): pass

   # Parameter display name. Same as name if not present
   @Attribute(parent=_name, typ="string", flags=F_OPTIONAL)
   def displayName(self): pass

   # Parameter aliases
   @Attribute(parent=_name, typ="string[]", flags=F_OPTIONAL)
   def aliases(self): pass

   # Parameter default value
   @Attribute(parent=_name, typ="string", flags=F_OPTIONAL)
   def default(self): pass

   # Parameter constraints
   @Attribute(parent=_name, typ="string[]", flags=F_OPTIONAL)
   def constraint(self): pass

   # Parameter help
   @Attribute(parent=_name, typ="string", flags=F_OPTIONAL)
   def help(self): pass

   # Whether the parameter a flag
   # Valid only for boolean parameters
   @Attribute(parent=_name, typ="boolean", flags=F_OPTIONAL)
   def flag(self): pass

## Command line method examples
#
class CLIExample:
   _name = VIM_CLI_EXAMPLE

   @DataType(name=_name, version=_VERSION)
   def __init__(self): pass

   @Attribute(parent=_name, typ="string")
   def example(self): pass

   @Attribute(parent=_name, typ="string")
   def description(self): pass

## Command line interface method info
#
class CLIMethod:
   _name = VIM_CLI_METHOD

   @DataType(name=_name, version=_VERSION)
   def __init__(self): pass

   # Method name
   @Attribute(parent=_name, typ="string")
   def name(self): pass

   # Method display name. Same as name if not present
   @Attribute(parent=_name, typ="string", flags=F_OPTIONAL)
   def displayName(self): pass

   # Method help
   @Attribute(parent=_name, typ="string", flags=F_OPTIONAL)
   def help(self): pass

   # Method parameters
   @Attribute(parent=_name, typ=VIM_CLI_PARAM + "[]", flags=F_OPTIONAL)
   def param(self): pass

   # Method returns
   @Attribute(parent=_name, typ=VIM_CLI_PARAM, flags=F_OPTIONAL)
   def ret(self): pass

   # Parameter hints
   @Attribute(parent=_name, typ="vim.KeyValue[]", flags=F_OPTIONAL)
   def hints(self): pass

   # Method examples
   @Attribute(parent=_name, typ=VIM_CLI_EXAMPLE + "[]", flags=F_OPTIONAL)
   def examples(self): pass


## Command line interface data info
#
class CLIInfo:
   _name = VIM_CLI_INFO

   @DataType(name=_name, version=_VERSION)
   def __init__(self): pass

   # Cmdline app name
   @Attribute(parent=_name, typ="string")
   def name(self): pass

   # Cmdline app display name. Same as name if not present
   @Attribute(parent=_name, typ="string", flags=F_OPTIONAL)
   def displayName(self): pass

   # Cmdline app help
   @Attribute(parent=_name, typ="string", flags=F_OPTIONAL)
   def help(self): pass

   # Cmdline app methods
   @Attribute(parent=_name, typ=VIM_CLI_METHOD + "[]", flags=F_OPTIONAL)
   def method(self): pass


## Command line interface info managed type
#
class CLI:
   _name = VIM_CLI

   @ManagedType(name=_name, version=_VERSION)
   def __init__(self): pass

   @Method(parent=_name, faults=["vim.fault.NotFound"])
   @Param(name="typeName", typ="string")
   @Return(typ=VIM_CLI_INFO)
   def FetchCLIInfo(self, typeName): pass

   @Method(parent=_name, faults=["vim.fault.NotFound"])
   @Param(name="name", typ="string")
   @Return(typ=VIM_CLI_INFO)
   def FetchCLIInfoFromDisplayName(self, name): pass


## ESXCLI fault type
#
class ESXCLIFault:
   _name = VIM_ESXCLI_FAULT

   @DataType(name=_name, base="vmodl.RuntimeFault", version=_VERSION)
   def __init__(self):
      """
      To raise a ESXCLI fault, (subclass Vim.EsxCLI.CLIFault) and do:
         raise Vim.EsxCLI.CLIFault(errMsg=["Line 1 msg", "Line 2 msg", ...])
      """

   # ESXCLI error message
   @Attribute(parent=_name, typ="string[]")
   def errMsg(self): pass


# Register managed object types
RegisterVmodlTypes()
