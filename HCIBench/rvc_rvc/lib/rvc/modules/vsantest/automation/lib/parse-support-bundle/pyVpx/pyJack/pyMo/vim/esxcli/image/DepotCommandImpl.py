"""
Copyright 2010-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module implements the esxcli commands in the "imagex depot" sub-namespace
 (in esxcli terminology, namespace = imagex, object = depot)
"""
__author__ = "VMware, Inc"

import sys
import logging

from MoManager import GetMoManager
from pyVmomi import Vim
from . import Defs
from . import DefsImpl
import six

try:
   from vmware.esximage.Transaction import Transaction
   HAVE_ESXIMAGE = True
except:
   HAVE_ESXIMAGE = False

log = logging.getLogger("esxcli-image-depot")


#
# Class for implementing "esxcli imagex depot" commands
#
class DepotCommandImpl(Vim.EsxCLI.imagex.depot):
   """ Implements all esxcli commands under 'esxcli imagex depot'.
   """
   def __init__(self, moId):
      Vim.EsxCLI.imagex.depot.__init__(self, moId)

   ##
   #  depot listprofiles
   def ListProfiles(self, meta):
      log.info("esxcli imagex depot listprofiles called")
      log.info("   meta parameter = %s" % (meta))
      try:
         meta = Transaction.DownloadMetadatas(meta)
      except Exception as e:
         log.exception(e)
         DefsImpl.ReformatEsximageErr(e)

      profiles = []
      for prof in six.itervalues(meta.profiles):
         imgprof = Vim.EsxCLI.imagex.ImageProfileData()
         imgprof.name = prof.name
         imgprof.creator = prof.creator
         imgprof.acceptanceLevel = Defs.ACCEPTANCE_LEVELS.get(
                                      prof.acceptancelevel, 'unknown')

         # creationtime and modifiedtime are always initialized to DateTime
         imgprof.created = DefsImpl.FormatDateString(prof.creationtime)
         imgprof.modified = DefsImpl.FormatDateString(prof.modifiedtime)
         profiles.append(imgprof)

      return profiles


#
# Register implementation managed object class
#
if HAVE_ESXIMAGE:
   GetMoManager().RegisterObjects([ DepotCommandImpl("ha-pyesxcli-image-depot")])
else:
   log.warning("Unable to import esximage library; esxcli image commands not available.")
