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

class vmStressToggle(ToggleOp):

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
      diskDev.SetUnitNumber(2)
      diskDev.SetKey(-100)
      diskDev.SetControllerKey(1000)
      diskDev.SetBacking(diskBacking)
      diskDev.SetCapacityInKB(long(1024*1024))
      diskSpec = Vim.Vm.Device.VirtualDeviceSpec()
      diskSpec.SetOperation("add")
      diskSpec.SetFileOperation("create")
      diskSpec.SetDevice(diskDev)
      deviceChange.append(diskSpec)
      configspec.SetDeviceChange(deviceChange)
      self.addConfigSpec = configspec
 
   def on(self):
      try:
         vmName = "vm" + self.getClientId()
	 print "Creating vm" + vmName
	 self.vm = vm.CreateQuickDummy(vmName, 1)
	 if self.vm == None:
            print "** Error in creating vm"
	    self.success = False
	    print self.getClientId() + " on failed"
	    return
	 print "Adding VM disk"
         task = self.vm.Reconfigure(self.addConfigSpec)
	 WaitForTask(task)
         print "Powering On vm"
	 vm.PowerOn(self.vm)
         print "Creating snapshot"
	 vm.CreateSnapshot(self.vm, "testSnapshot", "Test snap", False, False)
	 self.success = True
         print self.getClientId() + " on successful"
      except:
         print self.getClientId() + " on failed"
         self.success = False
   
   def off(self):
      try:
	 if self.vm == None:
	    self.success = False
	    print self.getClientId() + " off failed"
	    return
	 print "Removing snapshot"
         vm.RemoveAllSnapshots(self.vm)
	 print "Powering off vm"
	 vm.PowerOff(self.vm)
	 print "Removing VM disk"
         self.delDisk()
	 print "Destroying VM"
	 vm.Destroy(self.vm)
         self.success = True
         print self.getClientId() + " off successful"
      except:
         self.success = False
         print self.getClientId() + " off failed"

   def delDisk(self):
	config =  self.vm.GetConfig()
    	for disk in config.GetHardware().GetDevice():
           if isinstance(disk, Vim.Vm.Device.VirtualDisk):
               break
	print "Disk to destroy is :", disk
        configspec = Vim.Vm.ConfigSpec()
        deviceChange = []
        diskSpec = Vim.Vm.Device.VirtualDeviceSpec()
        diskSpec.SetOperation("remove")
        diskSpec.SetFileOperation("destroy")
        diskSpec.SetDevice(disk)
        deviceChange.append(diskSpec) 
        configspec.SetDeviceChange(deviceChange)
	task = self.vm.Reconfigure(configspec)
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


