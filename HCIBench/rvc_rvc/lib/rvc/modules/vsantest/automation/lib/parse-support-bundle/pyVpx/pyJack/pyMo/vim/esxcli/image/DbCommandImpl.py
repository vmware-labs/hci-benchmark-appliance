"""
Copyright 2010-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module implements the esxcli commands in the "imagex db" sub-namespace
 (in esxcli terminology, namespace = imagex, object = db)
"""
__author__ = "VMware, Inc"

import six
import sys
import logging
import textwrap

from MoManager import GetMoManager
from pyVmomi import Vim

from . import Defs
from . import DefsImpl

try:
   from vmware.esximage import HostImage
   HAVE_ESXIMAGE = True
except:
   HAVE_ESXIMAGE = False

log = logging.getLogger("esxcli-image-db")


LABEL_WIDTH = 25


#
# Class for implementing "esxcli imagex db" commands
#
class DbCommandImpl(Vim.EsxCLI.imagex.db):
   """ Implements all esxcli commands under 'esxcli imagex db'.
   """
   def __init__(self, moId):
      Vim.EsxCLI.imagex.db.__init__(self, moId)

   def ListVibs(self):
      """ esxcli imagex db listvibs """
      log.info("Invoking esxcli imagex db listvibs")

      #
      # Get the VIB inventory
      #
      h = HostImage.HostImage()
      vibs = h.GetInventory()
      viblist = []
      for vib in six.itervalues(vibs):
         vibinfo = Vim.EsxCLI.imagex.VibData()
         vibinfo.name = vib.name
         vibinfo.version = str(vib.version)
         vibinfo.vendor = vib.vendor
         vibinfo.summary = vib.summary
         vibinfo.releaseDate = DefsImpl.FormatDateString(vib.releasedate)
         vibinfo.installDate = DefsImpl.FormatDateString(vib.installdate)

         try:
            vibinfo.acceptanceLevel = Defs.ACCEPTANCE_LEVELS[getattr(vib,
                                         "acceptancelevel", "unknown")]
         except IndexError as e:
            vibinfo.acceptanceLevel = "<Unknown>"

         viblist.append(vibinfo)

      return viblist

   def ListProfile(self):
      """ esxcli imagex db listprofile """
      log.info("Invoking esxcli imagex db listprofile")
      lines = []
      h = HostImage.HostImage()
      hostaccept = Defs.ACCEPTANCE_LEVELS.get(h.GetHostAcceptance(), 'Unknown')
      lines.append("%s: %s" % ("Host Acceptance Level".ljust(LABEL_WIDTH),
                               hostaccept))
      lines.append('')
      prof = h.GetProfile()
      if not prof:
         lines.append('No image profile defined on this host.')
      else:
         lines.append("%s: %s" % ("Name".ljust(LABEL_WIDTH), prof.name))
         lines.append("%s: %s" % ("Creator".ljust(LABEL_WIDTH), prof.creator))
         lines.append("%s: %s" % ("Creation Time".ljust(LABEL_WIDTH),
                                  DefsImpl.FormatDateString(prof.creationtime)))
         lines.append("%s: %s" % ("Modification Time".ljust(LABEL_WIDTH),
                                  DefsImpl.FormatDateString(prof.modifiedtime)))
         label = "Description".ljust(LABEL_WIDTH) + ": "
         lines.extend(textwrap.wrap(prof.description, initial_indent=label,
                      subsequent_indent='  '))
         lines.append("%s:" % ("VIBs".ljust(LABEL_WIDTH)))

         vibs = h.GetInventory()
         for vib in six.itervalues(vibs):
            lines.append("  %-35s %-35s" % (vib.name, str(vib.version)))

      return '\n'.join(lines)

   def SetAcceptance(self, level):
      """ esxcli imagex db setacceptance """
      log.info("Invoking esxcli imagex db setacceptance")
      log.info("  Parameter level = %s" % (level))
      h = HostImage.HostImage()
      try:
         h.SetHostAcceptance(Defs.ACCEPTANCE_INPUT[level])
      except Exception as e:
         log.exception(e)
         DefsImpl.ReformatEsximageErr(e)

      return "Host acceptance level changed to %s." % (level)


#
# Register implementation managed object class
#
if HAVE_ESXIMAGE:
   GetMoManager().RegisterObjects([ DbCommandImpl("ha-pyesxcli-image-db")])
else:
   log.warning("Unable to import esximage library; esxcli image commands not available.")
