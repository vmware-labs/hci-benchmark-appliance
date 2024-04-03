"""
Copyright 2010-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module implements common classes.
"""
__author__ = "VMware, Inc"

import sys
import logging

from MoManager import GetMoManager
from pyVmomi import Vim
from pyVmomi import Vmodl


# Error class needs to be derived from an existing Vmodl fault
#
class EsxcliImageException(Vim.EsxCLI.CLIFault):
   pass


log = logging.getLogger()
#
# Reformat an Esximage Error class into a ESXCLIFault
#
def ReformatEsximageErr(e):
   """Reformats and throws a new exception based on an existing esximage error"""
   errmsg = []
   if hasattr(e, "msg"):
      errmsg.append(e.msg)
   elif hasattr(e, "problemset"):
      errmsg = [str(p) for p in e.problemset]
      for p in e.problemset:
         if hasattr(p, 'vibacceptlevel'):
            errmsg.append("To change the host acceptance level, use the "
                          "'esxcli image db setacceptance' command.")
            break
   elif hasattr(e, 'message'):
      # This must be last because exceptions based on BaseException all expose
      # the 'message' attr ... at least until it was deprecated in Py 2.6.
      # Also, make sure that what is appended is indeed a string, or
      # pyVmomi's type checking will fail
      errmsg.append(str(e.message))
   else:
      errmsg.append(str(e))
   raise EsxcliImageException(errMsg=errmsg)


#
#
def FormatDateString(dt, time=True):
   """Formats a DateTime object into a string for display.  If dt is not
      a DateTime, then the empty string is returned.
      Parameters:
         * dt    - An instance of DateTime.DateTime
         * time  - If True, displays the time. If False, only the date is
                   displayed.
      Returns:
         A formatted time string, or '' if the input cannot be parsed.
   """
   if hasattr(dt, 'isoformat'):
      datestr = dt.isoformat().replace('T', ' ')
      return datestr[:time and 19 or 10]
   else:
      return ''


#
# Check for existence of esximage library
#
def CheckEsximage(have_esximage):
   if not have_esximage:
      raise EsxcliImageException(errMsg=['esximage library not found, cannot continue'])
