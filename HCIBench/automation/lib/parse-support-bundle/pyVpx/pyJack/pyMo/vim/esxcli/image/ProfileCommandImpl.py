"""
Copyright 2010-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module implements the esxcli commands in the "imagex profile" sub-namespace
 (in esxcli terminology, namespace = imagex, object = profile)
"""
__author__ = "VMware, Inc"

import sys
import logging

from MoManager import GetMoManager
from pyVmomi import Vim
from . import DefsImpl

try:
   from vmware.esximage import Transaction
   from vmware.esximage import HostImage
   HAVE_ESXIMAGE = True
except:
   HAVE_ESXIMAGE = False

log = logging.getLogger("esxcli-image-profile")


#
# Class for implementing "esxcli imagex profile" commands
#
class ProfileCommandImpl(Vim.EsxCLI.imagex.profile):
   """ Implements all esxcli commands under 'esxcli imagex profile'.
   """
   def __init__(self, moId):
      Vim.EsxCLI.imagex.profile.__init__(self, moId)

   ##
   #  profile install
   def Install(self, meta, profile, force=False,
               noliveinstall=False):
      log.info("esxcli imagex profile install called")
      log.info("   meta parameter = %s" % (meta))
      log.info("   profile parameter = '%s'" % (profile))
      try:
         t = Transaction.Transaction()
         t.InstallProfile(meta, profile, skipvalidation=force,
                          forcebootbank=noliveinstall)
      except Exception as e:
         log.exception(e)
         DefsImpl.ReformatEsximageErr(e)

      return "Successfully installed '%s'" % (profile)

   ##
   #  profile validate
   def Validate(self, meta, profile):
      log.info("esxcli imagex profile validate called")
      log.info("   meta parameter = %s" % (meta))
      log.info("   profile parameter = '%s'" % (profile))
      try:
         vprof = Transaction.Transaction.GetProfileFromSources(
                                                   profile, metadataUrls=meta)
         h = HostImage.HostImage()
         prof = h.GetProfile()
      except Exception as e:
         log.exception(e)
         DefsImpl.ReformatEsximageErr(e)

      # error out if no host image profile defined
      if not prof:
         msg = "No host image profile defined, cannot continue"
         raise DefsImpl.EsxcliImageException(errMsg=[msg])

      vdata = Vim.EsxCLI.imagex.ValidationData()
      onlyhost, onlyvprof = prof.Diff(vprof)
      vdata.compliant = len(onlyhost)==0 and len(onlyvprof)==0
      vdata.hostProfileName = prof.name
      vdata.validationProfileName = vprof.name
      vdata.onlyInHost = list(onlyhost)
      vdata.onlyInValidationProfile = list(onlyvprof)
      return [vdata]

#
# Register implementation managed object class
#
if HAVE_ESXIMAGE:
   GetMoManager().RegisterObjects([ ProfileCommandImpl("ha-pyesxcli-image-profile")])
else:
   log.warning("Unable to import esximage library; esxcli image commands not available.")
