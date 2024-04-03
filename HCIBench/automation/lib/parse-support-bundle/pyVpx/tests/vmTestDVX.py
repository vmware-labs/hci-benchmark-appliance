#!/usr/bin/env python
# Copyright 2021-2022 VMware, Inc.  All rights reserved. -- VMware Confidential

import atexit
import inspect
from pyVmomi import vim, vmodl, VmomiSupport
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm
from pyVim import vmconfig
from pyVim import arguments
from pyVim import host
from pyVim.helpers import Log
import subprocess
import sys

# from vim/lib/vigorVim/devicekeys.txt
DVX_DEV_KEY = 13000          # shared with pciPassthru since DVX is a subtype
MAX_DVX_DEV = 16

DVXCLASS = "com.vmware.dvxsample"

def CreateDVX(key, deviceClass=DVXCLASS):
   dvx = vim.vm.device.VirtualPCIPassthrough()
   dvx.key = key
   backing = vim.vm.device.VirtualPCIPassthrough.DvxBackingInfo()
   backing.deviceClass = deviceClass
   dvx.backing = backing
   return dvx

def CreateVD(key):
   vd = vim.vm.device.VirtualDevice()
   vd.key = key
   return vd

def AddDVX(cspec, key=None, deviceClass=DVXCLASS):
   if key is None:
      key = vmconfig.GetFreeKey(cspec)
   dvx = CreateDVX(key, deviceClass)
   vmconfig.AddDeviceToSpec(cspec, dvx,
                            vim.vm.device.VirtualDeviceSpec.Operation.add)

def RemoveDev(vm1, dev):
   cspec = vim.vm.ConfigSpec()
   vmconfig.AddDeviceToSpec(cspec, dev,
                            vim.vm.device.VirtualDeviceSpec.Operation.remove)
   vm.Reconfigure(vm1, cspec)

def CheckDVXNotPresent(vm1):
   """
   Confirm that DVX is not present in a VM.
   """
   dvxDevices = vmconfig.CheckDevice(vm1.config,
                                     vim.vm.device.VirtualPCIPassthrough)
   if len(dvxDevices) != 0:
      raise Exception("DVX found in a VM: " + str(dvxDevices))

def CheckDVXPresent(vm1, cnt):
   """
   Validate DVX presence.
   """
   dvxDevices = vmconfig.CheckDevice(vm1.config,
                                     vim.vm.device.VirtualPCIPassthrough)
   if len(dvxDevices) != cnt:
      raise Exception("Unexpected number of DVX devices: " + len(dvxDevices))
   offset = 0
   for dvx in dvxDevices:
      if dvx.key != DVX_DEV_KEY + offset:
         raise Exception("dvx" + offset + " device has unexpected key: " +
                         dvx.key)
      offset += 1
   return dvx

def TestDVXHotAdd(vm1):
   Log("Trying to hot-add DVX (should fail)")
   cspec = vim.vm.ConfigSpec()
   AddDVX(cspec)
   try:
      vm.Reconfigure(vm1, cspec)
   except vim.fault.InvalidVmConfig:
      pass
   else:
      raise Exception("DVX hot-add did not raise exception")
   CheckDVXNotPresent(vm1)

def TestNoDVXRemoveDev(vm1, dev):
   cspec = vim.vm.ConfigSpec()
   vmconfig.AddDeviceToSpec(cspec, dev,
                            vim.vm.device.VirtualDeviceSpec.Operation.remove)
   try:
      vm.Reconfigure(vm1, cspec)
   except vim.fault.InvalidVmConfig:
      pass
   else:
      raise Exception("Reconfigure for DVX %s did not raise exception" % cspec)

def TestNoDVXRemoveKey(vm1, key):
   Log("Trying to remove DVX with key %s" % key)
   TestNoDVXRemoveDev(vm1, CreateDVX(key))

def TestNoDVXRemoveVDKey(vm1, key):
   Log("Trying to remove virtual device with key %s" % key)
   TestNoDVXRemoveDev(vm1, CreateVD(key))

def TestDVXRemoveInvalid(vm1):
   TestNoDVXRemoveKey(vm1, DVX_DEV_KEY + MAX_DVX_DEV)
   TestNoDVXRemoveKey(vm1, -1)
   TestNoDVXRemoveKey(vm1, 0)
   TestNoDVXRemoveKey(vm1, 100)
   TestNoDVXRemoveKey(vm1, 1000)
   TestNoDVXRemoveVDKey(vm1, DVX_DEV_KEY + MAX_DVX_DEV)
   TestNoDVXRemoveVDKey(vm1, -1)

def TestNoDVXRemove(vm1):
   TestNoDVXRemoveKey(vm1, DVX_DEV_KEY)
   TestNoDVXRemoveVDKey(vm1, DVX_DEV_KEY)
   TestDVXRemoveInvalid(vm1)
   CheckDVXNotPresent(vm1)

def TestDVXMove(vm1, key):
   Log("Replacing DVX device with new key=%s" % key)
   cspec = vim.vm.ConfigSpec()
   vmconfig.AddDeviceToSpec(cspec, CreateDVX(DVX_DEV_KEY),
                            vim.vm.device.VirtualDeviceSpec.Operation.remove)
   vmconfig.AddDeviceToSpec(cspec, CreateDVX(key),
                            vim.vm.device.VirtualDeviceSpec.Operation.add)
   vm.Reconfigure(vm1, cspec)
   CheckDVXPresent(vm1, MAX_DVX_DEV)

def TestNoDVXRunning(vm1):
   TestDVXHotAdd(vm1)
   TestNoDVXRemove(vm1)

def TestNoDVX(vm1):
   """
   Test that hot-add of DVX fails
   """
   CheckDVXNotPresent(vm1)
   TestNoDVXRemove(vm1)
   vm.PowerOn(vm1)
   try:
      TestNoDVXRunning(vm1)
   finally:
      vm.PowerOff(vm1)

def TestDVXReconfig(vm1):
   """
   Test add and remove for DVX device
   """
   Log("Adding DVX")
   cspec = vim.vm.ConfigSpec()
   for i in range(MAX_DVX_DEV):
      AddDVX(cspec)
   vm.Reconfigure(vm1, cspec)
   CheckDVXPresent(vm1, MAX_DVX_DEV)

   TestDVXRemoveInvalid(vm1)
   CheckDVXPresent(vm1, MAX_DVX_DEV)
   TestDVXMove(vm1, -1)
   TestDVXMove(vm1, DVX_DEV_KEY)
   TestDVXMove(vm1, 100)

   vm.PowerOn(vm1)
   try:
      TestDVXRemoveInvalid(vm1)
   finally:
      vm.PowerOff(vm1)
   Log("Removing DVX devices from VM")
   for i in range(MAX_DVX_DEV):
      RemoveDev(vm1, CreateDVX(DVX_DEV_KEY + i))
   CheckDVXNotPresent(vm1)

def TestDVXVDRemove(vm1):
   """
   Test DVX removal via key
   """
   Log("Adding DVX with positive key")
   cspec = vim.vm.ConfigSpec()
   AddDVX(cspec, key=DVX_DEV_KEY)
   vm.Reconfigure(vm1, cspec)
   CheckDVXPresent(vm1, 1)

   Log("Removing DVX device from VM using virtual device with DVX key")
   RemoveDev(vm1, CreateVD(DVX_DEV_KEY))
   CheckDVXNotPresent(vm1)

def TestDVXDestroyVM(vm):
   """
   Destroy a VM.
   """
   Log("Destroying VM")
   task = vm.Destroy()
   WaitForTask(task)

def TestDVXCreateSpec(vmname, memSize):
   """
   Create a spec for a DVX VM, with all memory reserved.
   """
   Log("Creating a spec")
   cfg = vm.CreateQuickDummySpec(vmname,
                                 vmxVersion = "vmx-20",
                                 memory=memSize, guest="otherGuest")

   memoryAlloc = vim.ResourceAllocationInfo()
   memoryAlloc.SetReservation(memSize)
   cfg.SetMemoryAllocation(memoryAlloc)
   return cfg


def TestDVXCreateVM(cfg):
   """
   Create a VM from a spec.
   """
   Log("Creating a VM")
   return vm.CreateFromSpec(cfg)

def LoadKernelModule(moduleName):
   # Adapted from esxUtils.py
   """Load the named kernel module."""
   cmd = ['/sbin/vmkload_mod', moduleName]
   process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
   stdout, stderr = process.communicate()
   retcode = process.wait()

   if retcode == 0:
      return

   # Non-zero retcode. We don't consider "already loaded" to be
   # an error, so double-check for that.

   i = stdout.find('already loaded')
   if i == -1:
      raise Exception("Error loading module '%s'." % moduleName)

def ExpectValue(a, b):
   if a != b:
      frame = inspect.stack()[1]
      msg = '{}:{}: ERROR: Unexpected value: Got {} Wanted {}'. \
            format(frame.filename, frame.lineno, a, b)
      Log(msg)
      raise Exception(msg)

def main():
   Log(str(vim.vm.device))
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd"),
                     (["v:", "vmname="], "DvxVMODLTest",
                      "Name of the virtual machine", "vmname") ]

   supportedToggles = [ (["usage", "help"], False,
                          "Show usage information", "usage"),
                        (["runall", "r"], True, "Run all the tests", "runall"),
                        (["nodelete"], False,
                          "Don't delete vm on completion", "nodelete") ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Connect
   si = SmartConnect(host=args.GetKeyValue("host"),
                     user=args.GetKeyValue("user"),
                     pwd=args.GetKeyValue("pwd"))
   atexit.register(Disconnect, si)

   # Process command line
   vmname = args.GetKeyValue("vmname")
   runall = args.GetKeyValue("runall")
   noDelete = args.GetKeyValue("nodelete")
   status = "PASS"
   vm1 = None

   try:
      Log("Cleaning up VMs from previous runs...")
      vm.Delete(vmname, True)

      Log("Loading dvxsample...")
      LoadKernelModule("/usr/lib/vmware/vmkmod/dvxsample")

      cfg = TestDVXCreateSpec(vmname, memSize = 4)
      for i in range(MAX_DVX_DEV):
         AddDVX(cfg)
      vm1 = TestDVXCreateVM(cfg)
      TestDVXDestroyVM(vm1)
      vm1 = None

      cfg = TestDVXCreateSpec(vmname, memSize = 8)
      vm1 = TestDVXCreateVM(cfg)
      TestDVXReconfig(vm1)
      TestNoDVX(vm1)
      TestDVXVDRemove(vm1)
      TestDVXDestroyVM(vm1)
      vm1 = None

      Log('Testing suspend/resume')
      cfg = TestDVXCreateSpec(vmname, memSize = 4)
      for i in range(MAX_DVX_DEV):
         AddDVX(cfg)
      vm1 = TestDVXCreateVM(cfg)
      vm.PowerOn(vm1)
      vm.Suspend(vm1)
      ExpectValue(vm1.runtime.powerState,
                  vim.VirtualMachine.PowerState.suspended)
      vm.PowerOn(vm1)
      vm.PowerOff(vm1)
      TestDVXDestroyVM(vm1)
      vm1 = None

      Log("Tests completed.")

   except Exception as e:
      status = "FAIL"
      Log("Caught exception : %s, %r" % (e, e))
      raise
   finally:
      # Delete the vm as cleanup
      if noDelete == False:
         if vm1 != None:
            TestDVXDestroyVM(vm1)
         vm1 = None

   Log("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()

