"""
Copyright 2010-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module defines esxcli commands in the "image vib" sub-namespace
 (in esxcli terminology, namespace = image, object = vib)
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
ESXCLI_IMAGE_VIB = Defs.ESXCLI_IMAGE + "." + "vib"


#
# esxcli command and parameter definitions
#
class VibCommand:
   """ Defines all esxcli commands under 'esxcli image vib'.
   """
   _name = ESXCLI_IMAGE_VIB

   @CLIManagedType(name=_name, version=Defs._VERSION)
   def __init__(self):
      """Install, update, or remove individual VIB packages"""

   ##
   #  vib install
   @CLIMethod(parent=_name, displayName="install")
   @CLIParam(name="vib", typ="string[]",
             help=Defs.HELP_VIBURL)
   @CLIParam(name="force", typ="boolean",
             flags=CLI_F_OPTIONAL, help=Defs.HELP_FORCE)
   @CLIParam(name="noliveinstall", aliases=["--noliveinstall"],
             typ="boolean", flags=CLI_F_OPTIONAL, help=Defs.HELP_NOLIVEINSTALL)
   @CLIReturn(typ="string")
   def Install(self, vib, force=False, noliveinstall=False):
      """Installs VIB packages from URLs.  To install VIBs from a depot or an
offline bundle, use the depot install command instead."""

   ##
   #  vib remove
   @CLIMethod(parent=_name, displayName="remove")
   @CLIParam(name="vib", typ="string[]",
             help=Defs.HELP_VIBNAME)
   @CLIParam(name="force", typ="boolean",
             flags=CLI_F_OPTIONAL, help=Defs.HELP_FORCE)
   @CLIParam(name="noliveinstall", aliases=["--noliveinstall"],
             typ="boolean", flags=CLI_F_OPTIONAL, help=Defs.HELP_NOLIVEINSTALL)
   @CLIReturn(typ="string")
   def Remove(self, vib, force=False, noliveinstall=False):
      """Removes VIB packages from the host"""

#
# Register CLI methods and parameters defined by decorators above
#
RegisterCLITypes()
