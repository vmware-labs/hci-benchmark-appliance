"""
Copyright 2010-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module implements the esxcli commands in the "imagex vib" sub-namespace
 (in esxcli terminology, namespace = imagex, object = vib)
"""
__author__ = "VMware, Inc"

import sys
import logging

from MoManager import GetMoManager
from pyVmomi import Vim
from . import DefsImpl

try:
   from vmware.esximage import Transaction
   from vmware.esximage import Errors
   HAVE_ESXIMAGE = True
except:
   HAVE_ESXIMAGE = False

log = logging.getLogger("esxcli-image-vib")


#
# Class for implementing "esxcli imagex vib" commands
#
class VibCommandImpl(Vim.EsxCLI.imagex.vib):
   """ Implements all esxcli commands under 'esxcli imagex vib'.
   """
   def __init__(self, moId):
      Vim.EsxCLI.imagex.vib.__init__(self, moId)

   ##
   #  vib install
   def Install(self, vib, force=False, noliveinstall=False):
      log.info("esxcli imagex vib install called")
      log.info("   vib parameter = %s" % (vib))
      log.info("   force parameter = %s" % (str(force)))
      log.info("   noliveinstall parameter = %s" % (str(noliveinstall)))

      try:
         t = Transaction.Transaction()
         res = t.InstallVibsFromSources(vib, [], [],
                                        skipvalidation=force,
                                        forcebootbank=noliveinstall)
      except Exception as e:
         log.exception(e)
         DefsImpl.ReformatEsximageErr(e)

      return "Successfully installed %s" % (', '.join(res.installed))

   ##
   #  vib remove
   def Remove(self, vib, force=False, noliveinstall=False):
      log.info("esxcli imagex vib remove called")
      log.info("   vib parameter = %s" % (vib))
      log.info("   force parameter = %s" % (str(force)))

      try:
         t = Transaction.Transaction()
         profile = t.GetProfile()

         # Each <name> string must match only one VIB.  Throw an error if no
         # matches are found.
         vibs = list()
         for nameid in vib:
            match = profile.vibs.FindVibsByColonSpec(nameid)
            if len(match) == 0:
               raise Errors.NoMatchError(nameid, "No VIB matching '%s' is installed."
                                         % (nameid))
            elif len(match) > 1:
               raise Errors.NoMatchError(nameid, "More than one VIB matches '%s'. "
                                         "Please try specifying <vendor>:<name> "
                                         "to narrow down to one VIB." % (nameid))
            vibs.append(match.pop())

         t.RemoveVibs(vibs, skipvalidation=force,
                      forcebootbank=noliveinstall)
      except Exception as e:
         log.exception(e)
         DefsImpl.ReformatEsximageErr(e)

      return "Successfully removed %s" % (', '.join(vibs))

#
# Register implementation managed object class
#
if HAVE_ESXIMAGE:
   GetMoManager().RegisterObjects([ VibCommandImpl("ha-pyesxcli-image-vib")])
else:
   log.warning("Unable to import esximage library; esxcli image commands not available.")
