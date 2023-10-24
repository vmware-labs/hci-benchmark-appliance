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
from invt import *

class vmReconfigToggle(ToggleOp):

   """
   Toggles VM power on and power off functions
   """
   def __init__(self, args):
      ToggleOp.__init__(self, args)
      self.si = connect.Connect(args['host'])
      self.vmList = args['vmlist']
      self.setConfigSpec()

   def setConfigSpec(self):
      envBrowser =  GetEnv()
      cfgTarget = envBrowser.QueryConfigTarget(None)
      datastore = cfgTarget.GetDatastore()[0]	
      configspec = Vim.Vm.ConfigSpec()
      deviceChange = []
      diskBacking = Vim.Vm.Device.VirtualDisk.FlatVer2BackingInfo()
      diskBacking.SetDiskMode("persistent")
      diskBacking.SetFileName("[" + datastore.GetName() + "]")
      diskDev = Vim.Vm.Device.VirtualDisk()
      diskDev.SetUnitNumber(4)
      diskDev.SetKey(-100)
      diskDev.SetControllerKey(1000)
      diskDev.SetBacking(diskBacking)
      diskDev.SetCapacityInKB(long(4*1024))
      diskSpec = Vim.Vm.Device.VirtualDeviceSpec()
      diskSpec.SetOperation("add")
      diskSpec.SetFileOperation("create")
      diskSpec.SetDevice(diskDev)
      deviceChange.append(diskSpec)
      configspec.SetDeviceChange(deviceChange)
      self.addConfigSpec = configspec
 
   def on(self):
      try:
	for vmIter in self.vmList:
         print "Adding disk to vm " + vmIter.GetName()
         task = vmIter.Reconfigure(self.addConfigSpec)
	 WaitForTask(task)
   	 self.success = True
         print self.getClientId() + " on successful"
      except:
         print self.getClientId() + " on failed"
         self.success = False
   
   def off(self):
      try:
	for vmIter in self.vmList:
	 print "Removing disk from vm " + vmIter.GetName()
         self.delDisk(vmIter)
         self.success = True
         print self.getClientId() + " off successful"
      except:
         self.success = False
         print self.getClientId() + " off failed"

   def delDisk(self, vm):
	config =  vm.GetConfig()
	configspec = Vim.Vm.ConfigSpec()
        deviceChange = []
    	for disk in config.GetHardware().GetDevice():
           if isinstance(disk, Vim.Vm.Device.VirtualDisk):
	      if disk.GetUnitNumber() == 4:
	     	break
        diskSpec = Vim.Vm.Device.VirtualDeviceSpec()
        diskSpec.SetOperation("remove")
        diskSpec.SetFileOperation("destroy")
        diskSpec.SetDevice(disk)
        deviceChange.append(diskSpec) 
	configspec.SetDeviceChange(deviceChange)
	print "Reconfigure spec: ", configspec
	task = vm.Reconfigure(configspec)
        WaitForTask(task)
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


class vmAddDisk(vmReconfigToggle):
   """
   Simply adds disk, doesn't delete
   """
   def off(self):
      "do nothing"
      pass

class vmDelDisk(vmReconfigToggle):
   """
   Simply deletes a disk, doesn't add
   """   
   def on(self):
      "do nothing"      
      pass




