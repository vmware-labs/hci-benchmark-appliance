#!/usr/bin/env python

import datetime
from contrib.vorb import RunVmomiOrb
from pyVmomi import Vpx
import logging

# Implementation of the Vpx.Vmprov.ActionHandler managed object interface
class DummyActionHandler(Vpx.Vmprov.ActionHandler):
   def __init__(self, moId='workflowActionHandler'):
      Vpx.Vmprov.ActionHandler.__init__(self, moId)

   def GetVmName(self, context):
      if isinstance(context, Vpx.Vmprov.CreateContext):
         return context.spec.name
      elif isinstance(context, Vpx.Vmprov.VmContext):
         return context.srcVmState.config.name
      return "[Unknown]"

   def PreExecute(self, actionName, actionInfo, actionInput):
      vmName = self.GetVmName(actionInput.context)
      logging.info(">>> Pre executing action %s, VM: %s" %
                   (actionName, vmName))

   def PostExecute(self, actionName, actionInfo, actionInput, actionResult):
      vmName = self.GetVmName(actionInput.context)
      logging.info(">>> Post executing action %s, VM: %s, next actions: \n%s" %
                   (actionName, vmName, actionResult.nextAction))

# Create and register managed objects
def RegisterManagedObjects(vorb):
   handler = DummyActionHandler()
   vorb.RegisterObject(handler)

# Create VORB server
RunVmomiOrb(RegisterManagedObjects)
