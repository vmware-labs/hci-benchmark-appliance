#!/usr/bin/env python

"""
Copyright 2008-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is used to test CLI decorators
"""
__author__ = "VMware, Inc"

# import decorators
import sys
sys.path.append("..")
sys.path.append("../../../..")
from CLIDecorators import CLIManagedType, CLIDataType, CLIEnumType, \
                          CLIAttribute, CLIMethod, CLIParam, CLIReturn, \
                          CLI_F_OPTIONAL, \
                          CLIDecoratorException, \
                          RegisterCLITypes, FlushCLITypes

import unittest

class TestCLIDecorators(unittest.TestCase):
   ## Setup
   #
   def setUp(self):
      pass

   ## Test @CLIManagedType
   #
   def test_CLIManagedType(self):
      name = "vim.CLIManagedTest"
      class aCLI:
         @CLIManagedType(name=name)
         def __init__(self): pass

         @CLIMethod(parent=name,
                    hints={"formatter":"table", "table-columns":"Name,Type"})
         @CLIParam(name="arg0", typ="string", flags=CLI_F_OPTIONAL,
                   aliases=["-p", "--param"], default="test",
                   help="An array of string",
                   constraint=["testing", "1", "2", "3"])
         @CLIReturn(typ="string", help="Return value", flags=CLI_F_OPTIONAL)
         def aCLIMethod(self, arg0=None):
            """You want the help? Can you handle the help?!!"""

         @CLIMethod(parent=name, privId="System.Read")
         def aPrivilegeMethod(self):
            """A privilege method"""

      RegisterCLITypes()

   ## Test Duplicated aliases
   #
   def test_DuplicatedAliasesError(self):
      name = "vim.DuplicatedAliasesError"
      try:
         class aCLI:
            @CLIManagedType(name=name)
            def __init__(self): pass

            @CLIMethod(parent=name)
            @CLIParam(name="arg0", typ="string", aliases=["-p", "--param"])
            @CLIParam(name="arg1", typ="string", aliases=["-d", "--param"])
            def aCLIMethod(self, arg0, arg1):
               """A CLI method"""

         raise Exception("Failed to detect @CLIParam duplicate aliases")
      except CLIDecoratorException as err:
         pass


   ## The following should already been tested in VmodlDecorators unittests
   #

   ## Test @CLIEnumType
   def test_CLIEnum(self):
      pass

   ## Test @CLIDataType
   def test_CLIData(self):
      pass

   ## Test: Confirm decorators are simple pass-thru
   def test_ConfirmPassThru(self):
      from VmodlDecorators import ManagedType, DataType, EnumType, \
                                  Attribute, Method, Param, Return, \
                                  VmodlDecoratorException, \
                                  RegisterVmodlTypes, FlushVmodlTypes
      assert(CLIEnumType == EnumType)
      assert(CLIDataType == DataType)
      assert(CLIAttribute == Attribute)
      assert(FlushCLITypes == FlushVmodlTypes)


## Test main
#
if __name__ == "__main__":
   unittest.main()

