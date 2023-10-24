"""
Copyright 2010-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module defines esxcli commands in the "image db" sub-namespace
 (in esxcli terminology, namespace = image, object = db)
"""
__author__ = "VMware, Inc"

import sys
import logging

# import decorators
# there should be a better alternative to this
from pyMo.vim.CLIApps.CLIDecorators import \
                          CLIManagedType, CLIDataType, CLIEnumType, \
                          CLIAttribute, CLIMethod, CLIParam, CLIReturn, \
                          CLI_F_OPTIONAL, \
                          CLIDecoratorException, \
                          RegisterCLITypes, FlushCLITypes

from . import Defs

#
# VMODL namespace definitions
#
ESXCLI_IMAGE_DB = Defs.ESXCLI_IMAGE + "." + "db"


#
# esxcli command and parameter definitions
#
class DbCommand:
   """ Defines all esxcli commands under 'esxcli image db'.
   """
   _name = ESXCLI_IMAGE_DB

   @CLIManagedType(name=_name, version=Defs._VERSION)
   def __init__(self):
      """Query installed vibs and image profile; Export VIBs"""

   #
   # esxcli image db listvibs
   #
   @CLIMethod(parent=_name,
              hints={"formatter":"table",
                     "table-columns":"Name,Version,Vendor,,Install Date,,Summary"},
              displayName="listvibs")
   @CLIReturn(typ=Defs.ESXCLI_IMAGE_VIBDATA + "[]",
              flags=CLI_F_OPTIONAL)
   def ListVibs(self):
      """List the installed VIB packages"""

   #
   # esxcli image db listprofile
   #
   @CLIMethod(parent=_name, displayName="listprofile")
   @CLIReturn(typ="string")
   def ListProfile(self):
      """Display the installed image profile and host acceptance level"""

   #
   # esxcli image db setacceptance
   #
   @CLIMethod(parent=_name, displayName="setacceptance")
   @CLIParam(name="level", typ="string", help=Defs.HELP_LEVEL,
             constraint=list(Defs.ACCEPTANCE_INPUT.keys()))
   @CLIReturn(typ="string")
   def SetAcceptance(self, level):
      """Sets the host acceptance level. This controls what VIBs will be allowed
on a host."""

#
# Register CLI methods and parameters defined by decorators above
#
RegisterCLITypes()
