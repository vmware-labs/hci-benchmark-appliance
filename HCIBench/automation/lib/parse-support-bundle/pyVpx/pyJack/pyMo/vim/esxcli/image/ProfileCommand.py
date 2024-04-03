"""
Copyright 2010-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module defines esxcli commands in the "image profile" sub-namespace
 (in esxcli terminology, namespace = image, object = profile)
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
ESXCLI_IMAGE_PROF = Defs.ESXCLI_IMAGE + "." + "profile"


#
# esxcli command and parameter definitions
#
class ProfileCommand:
   """ Defines all esxcli commands under 'esxcli image profile'.
   """
   _name = ESXCLI_IMAGE_PROF

   @CLIManagedType(name=_name, version=Defs._VERSION)
   def __init__(self):
      """Applies, updates, or validates image profiles"""

   ##
   #  profile install
   @CLIMethod(parent=_name, displayName="install")
   @CLIParam(name="meta", typ="string[]",
             help=Defs.HELP_META)
   @CLIParam(name="profile", typ="string",
             help=Defs.HELP_PROFILENAME)
   @CLIParam(name="force", typ="boolean",
             flags=CLI_F_OPTIONAL, help=Defs.HELP_FORCE)
   @CLIParam(name="noliveinstall", aliases=["--noliveinstall"],
             typ="boolean", flags=CLI_F_OPTIONAL, help=Defs.HELP_NOLIVEINSTALL)
   @CLIReturn(typ="string")
   def Install(self, meta, profile, force=False,
               noliveinstall=False):
      """Installs or applies an image profile from a depot to this host.
 WARNING: The new image profile will completely replace the current
 host image, and any VIBs that are in the current host and are
 not in the new profile will not be preserved."""

   ##
   #  profile validate
   # NOTE: list-header must be set to a string value not matching any field
   #       in order to turn off headers.  If set to None or not set, then all
   #       the fields will become headers!
   @CLIMethod(parent=_name, displayName="validate",
              hints={"formatter": "list",
                     "list-order": "Compliant,Host Profile Name,"
                                   "Validation Profile Name,"
                                   "Only In Host,"
                                   "Only In Validation Profile",
                     "list-header": "None"
                     } )
   @CLIParam(name="meta", typ="string[]",
             help=Defs.HELP_META)
   @CLIParam(name="profile", typ="string",
             help=Defs.HELP_PROFILENAME)
   @CLIReturn(typ=Defs.ESXCLI_IMAGE_VALIDATEDATA + "[]")
   def Validate(self, meta, profile):
      """Validates the current image profile on the host against an image
   profile in a depot."""


#
# Register CLI methods and parameters defined by decorators above
#
RegisterCLITypes()
