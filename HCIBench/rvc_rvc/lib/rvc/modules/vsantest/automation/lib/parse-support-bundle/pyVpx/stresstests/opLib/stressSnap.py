#!/usr/bin/env python
'''
ToggleOp implementation for VM power ops
'''
import threading
from operator import xor
from stresstest import ToggleOp
from pyVim import connect, vm
from pyVmomi import Vim
from pyVim.task import WaitForTask
from pyVim import folder

class vmSnapToggle(ToggleOp):

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
	   print "Creating snapshot on vm " + vmIter.GetName()
	   vm.CreateSnapshot(vmIter, "testSnapshot", "a"*3000, False, False)
   	self.success = True
        print self.getClientId() + " on successful"
     except:
        print self.getClientId() + " on failed"
        self.success = False
   
   def off(self):
      try:
	for vmIter in self.vmList:
	   print "Reverting to snapshot from vm " + vmIter.GetName()
	   vm.RevertToCurrentSnapshot(vmIter)
	   print "Removing all snapshots on vm " + vmIter.GetName()
	   vm.RemoveAllSnapshots(vmIter)
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
