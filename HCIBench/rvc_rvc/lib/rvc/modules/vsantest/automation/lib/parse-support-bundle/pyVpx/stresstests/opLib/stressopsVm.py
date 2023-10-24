#!/usr/bin/env python
'''
ToggleOp implementation for VM power ops
'''
import threading
from operator import xor
from stresstest import ToggleOp
from pyVim import connect, vm

class vmPowerToggle(ToggleOp):
   """
   Toggles VM power on and power off functions
   """
   def __init__(self, args):
      ToggleOp.__init__(self, args)
      self.si = connect.Connect(args['host'])
      self.vmList = args['vmlist']

   def on(self):
      try:
         for vmIter in self.vmList:
            vm.PowerOn(vmIter)
         self.success = True
         print self.getClientId() + " on successful"
      except:
         print self.getClientId() + " on failed"
         self.success = False
   def off(self):
      try:
         for vmIter in self.vmList:
            vm.PowerOff(vmIter)
         self.success = True
         print self.getClientId() + " off successful"
      except:
         self.success = False
         print self.getClientId() + " off failed"
   def syncPreWait(self, barrier):
      """
      save the success flag in barrier.data
      """
      if barrier.data is None: barrier.data = [self.success]
      else: barrier.data.append(self.success)
   def syncPreOpen(self, barrier):
      """
      exactly one client must be successful, so xor over the success
      flags of all clients.
      """
      self.syncPreWait(barrier)
      xsuccess = False
      for success in barrier.data:
         xsuccess = xor(xsuccess, success)
      barrier.data = []
      return xsuccess


class vmPowerOn(vmPowerToggle):
   """
   Simply powers on, doesn't power off
   """
   def off(self):
      "do nothing"
      pass

class vmPowerOff(vmPowerToggle):
   """
   Simply powers off, doesn't power on
   """   
   def on(self):
      "do nothing"      
      pass

class vmPowerToggleVerify(vmPowerToggle):
   """
   Adds verification methods
   """      
   def onVerify(self):
      "makes sure all vms in my list are powered on"
      for vmIter in self.vmList:
         if vmIter.GetRuntime().GetPowerState() != vmIter.PowerState.POWEREDON:
            return False
   def offVerify(self):
      "makes sure all vms in my list are powered off"      
      for vmIter in self.vmList:
         if (vmIter.GetRuntime().GetPowerState()
             != vmIter.PowerState.POWEREDOFF):
            return False



