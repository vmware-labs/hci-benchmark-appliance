#!/usr/bin/python

import sys
import time
import getopt
from pyVmomi import vim, vmodl, VmomiSupport
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm
from pyVim import vmconfig
from pyVim import arguments
from pyVim import host
from pyVim.helpers import Log
import atexit

QAT_DEV_KEY = 17000
MAX_QAT_DEV = 4

def CreateVQAT(key, deviceType="C62XVF"):
   qat = vim.vm.device.VirtualQAT()
   qat.key = key
   backing = vim.vm.device.VirtualQAT.DeviceBackingInfo()
   backing.deviceName = ""
   backing.deviceType = deviceType
   qat.backing = backing
   return qat

def CreateVD(key):
   vd = vim.vm.device.VirtualDevice()
   vd.key = key
   return vd

def AddVQAT(cspec, key=None, deviceType="C62XVF"):
   if key is None:
      key = vmconfig.GetFreeKey(cspec)
   qat = CreateVQAT(key, deviceType)
   vmconfig.AddDeviceToSpec(cspec, qat,
                            vim.vm.device.VirtualDeviceSpec.Operation.add)

def RemoveDev(vm1, dev):
   cspec = vim.vm.ConfigSpec()
   vmconfig.AddDeviceToSpec(cspec, dev,
                            vim.vm.device.VirtualDeviceSpec.Operation.remove)
   vm.Reconfigure(vm1, cspec)

def CheckQATNotPresent(vm1):
   """
   Confirm that QAT is not present in a VM.
   """
   qatDevices = vmconfig.CheckDevice(vm1.config, vim.vm.device.VirtualQAT)
   if len(qatDevices) != 0:
      raise Exception("QAT found in a VM: " + str(qatDevices))

def CheckQATPresent(vm1, cnt):
   """
   Validate QAT presence.
   """
   qatDevices = vmconfig.CheckDevice(vm1.config, vim.vm.device.VirtualQAT)
   if len(qatDevices) != cnt:
      raise Exception("Unexpected number of QAT devices: " + len(qatDevices))
   off = 0
   # Is there a guarantee that the keys are in order? This seems to work.
   for qat in qatDevices:
      if qat.key != QAT_DEV_KEY + off:
         raise Exception("qat" + off + " device has unexpected key: " +
                         qat.key)
      off += 1
   return qat

def TestAdd5thQATKey(vm1, key):
   """
   Test add 5th VQAT
   """
   Log("Adding 5th VQAT using key=%s" % key)
   cspec = vim.vm.ConfigSpec()
   AddVQAT(cspec, key)
   try:
      vm.Reconfigure(vm1, cspec)
      raise Exception("Addition of 5th VQAT did not fail with %s" % cspec)
   except vim.fault.TooManyDevices as e:
      pass
   CheckQATPresent(vm1, MAX_QAT_DEV)

def TestAdd5thQAT(vm1):
   """
   Test add 5th VQAT
   """
   TestAdd5thQATKey(vm1, None)
   TestAdd5thQATKey(vm1, 100)
   TestAdd5thQATKey(vm1, QAT_DEV_KEY)
   TestAdd5thQATKey(vm1, QAT_DEV_KEY + MAX_QAT_DEV)
   TestAdd5thQATKey(vm1, -1)
   TestAdd5thQATKey(vm1, 1999999999)
   TestAdd5thQATKey(vm1, -1999999999)

def TestVQATHotAdd(vm1):
   Log("Trying to hot-add VQAT")
   cspec = vim.vm.ConfigSpec()
   AddVQAT(cspec)
   try:
      vm.Reconfigure(vm1, cspec)
      raise Exception("QAT hot-add did not raise exception")
   except vim.fault.InvalidPowerState as e:
      pass
   CheckQATNotPresent(vm1)

def TestNoVQATRemoveDev(vm1, dev, fault=vim.fault.InvalidDeviceSpec):
   cspec = vim.vm.ConfigSpec()
   vmconfig.AddDeviceToSpec(cspec, dev,
                            vim.vm.device.VirtualDeviceSpec.Operation.remove)
   try:
      vm.Reconfigure(vm1, cspec)
      raise Exception("Reconfigure for QAT %s did not raise exception" %
                      cspec)
   except fault as e:
      pass

def TestNoVQATRemoveKey(vm1, key):
   Log("Trying to remove VQAT with key %s" % key)
   TestNoVQATRemoveDev(vm1, CreateVQAT(key))

def TestNoVQATRemoveVDKey(vm1, key):
   Log("Trying to remove virtual device with key %s" % key)
   TestNoVQATRemoveDev(vm1, CreateVD(key))

def TestVQATRemoveInvalid(vm1):
   TestNoVQATRemoveKey(vm1, QAT_DEV_KEY + MAX_QAT_DEV)
   TestNoVQATRemoveKey(vm1, -1)
   TestNoVQATRemoveKey(vm1, 0)
   TestNoVQATRemoveKey(vm1, 100)
   TestNoVQATRemoveKey(vm1, 1000)
   TestNoVQATRemoveVDKey(vm1, QAT_DEV_KEY + MAX_QAT_DEV)
   TestNoVQATRemoveVDKey(vm1, -1)

def TestNoVQATRemove(vm1):
   TestNoVQATRemoveKey(vm1, QAT_DEV_KEY)
   TestNoVQATRemoveVDKey(vm1, QAT_DEV_KEY)
   TestVQATRemoveInvalid(vm1)
   CheckQATNotPresent(vm1)

def TestVQATMove(vm1, key):
   Log("Replacing VQAT device with new key=%s" % key)
   cspec = vim.vm.ConfigSpec()
   vmconfig.AddDeviceToSpec(cspec, CreateVQAT(QAT_DEV_KEY),
                            vim.vm.device.VirtualDeviceSpec.Operation.remove)
   vmconfig.AddDeviceToSpec(cspec, CreateVQAT(key),
                            vim.vm.device.VirtualDeviceSpec.Operation.add)
   vm.Reconfigure(vm1, cspec)
   CheckQATPresent(vm1, MAX_QAT_DEV)

def TestVQATHotRemove(vm1):
   Log("Trying to hot-remove VQAT")
   TestNoVQATRemoveDev(vm1, CreateVQAT(QAT_DEV_KEY),
                       vim.fault.InvalidPowerState)
   CheckQATPresent(vm1, MAX_QAT_DEV)

   Log("Trying to hot-remove virtual device with VQAT key")
   TestNoVQATRemoveDev(vm1, CreateVD(QAT_DEV_KEY),
                       vim.fault.InvalidPowerState)
   CheckQATPresent(vm1, MAX_QAT_DEV)

def TestNoVQATRunning(vm1):
   TestVQATHotAdd(vm1)
   TestNoVQATRemove(vm1)

def TestNoVQAT(vm1):
   """
   Test that hot-add of VQAT fails
   """
   CheckQATNotPresent(vm1)
   TestNoVQATRemove(vm1)
   vm.PowerOn(vm1)
   try:
      TestNoVQATRunning(vm1)
   finally:
      vm.PowerOff(vm1)

def TestVQATReconfig(vm1):
   """
   Test add and remove for VQAT controller
   """
   Log("Adding VQAT")
   cspec = vim.vm.ConfigSpec()
   for i in range(MAX_QAT_DEV):
      AddVQAT(cspec)
   vm.Reconfigure(vm1, cspec)
   CheckQATPresent(vm1, MAX_QAT_DEV)

   TestAdd5thQAT(vm1)
   TestVQATRemoveInvalid(vm1)
   CheckQATPresent(vm1, MAX_QAT_DEV)
   TestVQATMove(vm1, -1)
   TestVQATMove(vm1, QAT_DEV_KEY)
   TestVQATMove(vm1, 100)

   vm.PowerOn(vm1)
   try:
      TestVQATRemoveInvalid(vm1)
      TestVQATHotRemove(vm1)
   finally:
      vm.PowerOff(vm1)
   # Remove QAT controller from VM
   Log("Removing QAT devices from VM")
   for i in range(MAX_QAT_DEV):
      RemoveDev(vm1, CreateVQAT(QAT_DEV_KEY + i))
   CheckQATNotPresent(vm1)

def TestVQATDeviceType(vm1):
   """
   Test adding QAT devices with various deviceTypes
   """
   CheckQATNotPresent(vm1)
   Log("Adding VQAT with deviceType")
   cspec = vim.vm.ConfigSpec()
   # Add VQAT devices with a variety of deviceTypes to VM.
   deviceTypes = [ "C62XVF", "C62XVF-crypto", "C62XVF-compression" ]
   for deviceType in deviceTypes:
      AddVQAT(cspec, deviceType=deviceType)
   vm.Reconfigure(vm1, cspec)

   # Iterate through qatDevices and build both a remove spec
   # and a list of the QAT backing deviceTypes seen.
   qatDevices = vmconfig.CheckDevice(vm1.config, vim.vm.device.VirtualQAT)
   backingDeviceTypes = []
   cspec = vim.vm.ConfigSpec()
   for qat in qatDevices:
      deviceType = qat.backing.deviceType
      if deviceType is None:
         raise Exception("qat device with unset deviceType")
      backingDeviceTypes.append(deviceType)
      vmconfig.AddDeviceToSpec(cspec, qat,
                               vim.vm.device.VirtualDeviceSpec.Operation.remove)

   # Should see all of the configured deviceTypes in the returned
   # backing deviceTypes.
   if sorted(deviceTypes) != sorted(backingDeviceTypes):
      raise Exception("Invalid device types after reconfiguration: " +
                      ",".join(backingDeviceTypes))

   # Remove all QAT device and verify no QAT devices remain on VM.
   vm.Reconfigure(vm1, cspec)
   CheckQATNotPresent(vm1)

def TestVQATVDRemove(vm1):
   """
   Test VQAT removal via key
   """
   Log("Adding VQAT with positive key")
   cspec = vim.vm.ConfigSpec()
   AddVQAT(cspec, key=QAT_DEV_KEY)
   vm.Reconfigure(vm1, cspec)
   CheckQATPresent(vm1, 1)

   Log("Removing VQAT device from VM using virtual device with VQAT key")
   RemoveDev(vm1, CreateVD(QAT_DEV_KEY))
   CheckQATNotPresent(vm1)

 
def TestVQATDestroyVM(vm):
   """
   Destroy a VM.
   """
   Log("Destroying VM")
   task = vm.Destroy()
   WaitForTask(task)


def TestVQATCreateSpec(vmname, memSize):
   """
   Create a spec for a VQAT VM, with all memory reserved.
   """
   Log("Creating a spec")
   cfg = vm.CreateQuickDummySpec(vmname,
                                 vmxVersion = vmconfig.GetHWvFutureVmxString(),
                                 memory = memSize, guest = "otherGuest")

   memoryAlloc = vim.ResourceAllocationInfo()
   memoryAlloc.SetReservation(memSize)
   cfg.SetMemoryAllocation(memoryAlloc)
   return cfg


def TestVQATCreateVM(cfg):
   """
   Create a VM from a spec.
   """
   Log("Creating a VM")
   return vm.CreateFromSpec(cfg)


def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd"),
                     (["v:", "vmname="], "VQATTest",
                      "Name of the virtual machine", "vmname") ]

   supportedToggles = [ (["usage", "help"], False,
                          "Show usage information", "usage"),
                        (["runall", "r"], True, "Run all the tests", "runall"),
                        (["nodelete"], False,
                          "Dont delete vm on completion", "nodelete") ]

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

      cfg = TestVQATCreateSpec(vmname, memSize = 4)
      for i in range(MAX_QAT_DEV):
         AddVQAT(cfg)
      vm1 = TestVQATCreateVM(cfg)
      TestVQATDestroyVM(vm1)
      vm1 = None

      cfg = TestVQATCreateSpec(vmname, memSize = 8)
      vm1 = TestVQATCreateVM(cfg)
      TestVQATReconfig(vm1)
      TestVQATDeviceType(vm1)
      TestNoVQAT(vm1)
      TestVQATVDRemove(vm1)
      TestVQATDestroyVM(vm1)
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
            TestVQATDestroyVM(vm1)
         vm1 = None

   Log("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()

