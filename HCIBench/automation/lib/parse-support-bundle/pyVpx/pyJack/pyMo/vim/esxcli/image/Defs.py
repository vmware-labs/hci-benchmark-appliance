"""
Copyright 2010-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module defines VMODL definitions common to all "esxcli image" commands
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
from pyMo.vim.CLIApps import CLIInfo

#
# VMODL names
#
_VERSION = "vim.version.version9"
ESXCLI_IMAGE = CLIInfo.VIM_ESXCLI + ".imagex"
ESXCLI_IMAGE_VIBDATA = ESXCLI_IMAGE + ".VibData"
ESXCLI_IMAGE_IMGPROFDATA = ESXCLI_IMAGE + ".ImageProfileData"
ESXCLI_IMAGE_VALIDATEDATA = ESXCLI_IMAGE + ".ValidationData"


#
# Enums and other constants used by CLIs
#
ACCEPTANCE_LEVELS = {"certified": "VMware Certified",
                     "accepted":  "VMware Accepted",
                     "signed":    "Partner Supported",
                     "unsigned":  "Community Supported"}

ACCEPTANCE_INPUT = {"certified": "certified",
                    "accepted":  "accepted",
                    "partner":   "signed",
                    "community": "unsigned"}

#
# Help text for options
#
HELP_VIBURL = "Specifies a URL to a VIB package " \
              "to install.  May be repeated."
HELP_VIBNAME =    "Specifies a VIB name, name:version, vendor:name, or " \
                  "vendor:name:version.  May be repeated."
HELP_META =       "Specifies a URL or file path to a metadata.zip file. " \
                  "May be repeated."
HELP_PROFILENAME = "Specifies the name of an image profile."
HELP_LEVEL =      "Specifies the acceptance level to set.  Should be one of " \
                  "certified / accepted / partner / community."

HELP_FORCE = "Bypasses checks for package dependencies, conflicts, "  \
             "obsolescence, and acceptance levels.  Really not recommended " \
             "unless you know what you are doing."

HELP_NOLIVEINSTALL = "Forces an install to /altbootbank even if the VIBs are " \
                     "eligible for live installation or removal."

#
# VIB data type definitions
#
class VibData:
   """ VMODL data type for basic VIB package data """
   _name = ESXCLI_IMAGE_VIBDATA

   @CLIDataType(name=_name, version=_VERSION)
   def __init__(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def name(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def version(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def vendor(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def releaseDate(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def installDate(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def acceptanceLevel(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def summary(self): pass


#
# Image Profile data type definitions
#
class BasicImageProfile:
   """ VMODL data type for basic image profile data """
   _name = ESXCLI_IMAGE_IMGPROFDATA

   @CLIDataType(name=_name, version=_VERSION)
   def __init__(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def name(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def creator(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def acceptanceLevel(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def created(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def modified(self): pass

class ValidationData:
   """ VMODL data type for image profile validation """
   _name = ESXCLI_IMAGE_VALIDATEDATA

   @CLIDataType(name=_name, version=_VERSION)
   def __init__(self): pass

   @CLIAttribute(parent=_name, typ="boolean")
   def compliant(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def hostProfileName(self): pass

   @CLIAttribute(parent=_name, typ="string")
   def validationProfileName(self): pass

   @CLIAttribute(parent=_name, typ="string[]",
                 flags=CLI_F_OPTIONAL)
   def onlyInHost(self): pass

   @CLIAttribute(parent=_name, typ="string[]",
                 flags=CLI_F_OPTIONAL)
   def onlyInValidationProfile(self): pass

#
# Define help text for "esxcli image".  Note that the help text
# is defined in the docstring of the method decorated by @CLIManagedType()
#
class EsxcliImage:
   @CLIManagedType(name=ESXCLI_IMAGE)
   def __init__(self):
      """Manage the ESXi software image and install/remove VIB packages."""

#
# Register CLI methods and parameters defined by decorators above
#
RegisterCLITypes()
