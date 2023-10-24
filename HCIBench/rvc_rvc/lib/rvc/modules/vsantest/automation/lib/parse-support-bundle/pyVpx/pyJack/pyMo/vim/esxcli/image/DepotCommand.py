"""
Copyright 2010-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module defines esxcli commands in the "image depot" sub-namespace
 (in esxcli terminology, namespace = image, object = depot)
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
ESXCLI_IMAGE_DEPOT = Defs.ESXCLI_IMAGE + "." + "depot"


#
# esxcli command and parameter definitions
#
class DepotCommand:
   """ Defines all esxcli commands under 'esxcli image depot'.
   """
   _name = ESXCLI_IMAGE_DEPOT

   @CLIManagedType(name=_name, version=Defs._VERSION)
   def __init__(self):
      """Query, install, or update to an entire depot of VIBs and image profiles."""

   ##
   #  depot listprofiles
   @CLIMethod(parent=_name, displayName="listprofiles",
              hints={"formatter":"table",
                     "table-columns": "Name,Creator,Acceptance Level,"
                                      "Created,Modified"} )
   @CLIParam(name="meta", typ="string[]",
             help=Defs.HELP_META)
   @CLIReturn(typ=Defs.ESXCLI_IMAGE_IMGPROFDATA + "[]",
              flags=CLI_F_OPTIONAL)         # So empty list can be returned
   def ListProfiles(self, meta):
      """Lists all the image profiles defined in metadata files."""

#
# Register CLI methods and parameters defined by decorators above
#
RegisterCLITypes()
