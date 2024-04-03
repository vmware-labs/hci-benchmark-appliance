#!/usr/bin/python

import sys
import time
import getopt
from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log
import atexit

SECTOR_SIZE = 512

def TestWithSnapshot(vm1):
    """ Verify that it is not possible to extend delta disk by changing
        capacityInBytes.
    """
    cspec = Vim.Vm.ConfigSpec()
    vmconfig.AddScsiDisk(cspec, cfgInfo = vm1.config)
    vm.Reconfigure(vm1, cspec)
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)
    if len(devices) != 1:
       raise Exception("Failed to find new disk!")

    # attempt to extend a disk with a parent
    Log("Creating a snapshot on the VM for negative disk extend test.")
    vm.CreateSnapshot(vm1, "dummy snapshot", "dummy desc", False, False)
    Log("Attempting to extend disk size of delta disk.")
    disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[0]
    cspec = Vim.Vm.ConfigSpec()
    disk.capacityInBytes = disk.capacityInBytes + 1024
    vmconfig.AddDeviceToSpec(cspec, disk, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
    task = vm1.Reconfigure(cspec)
    try:
       WaitForTask(task)
    except Exception as e:
       Log("Hit an exception extending delta disk as expected" + str(e))
    else:
       raise Exception("Error: Extending delta disk was allowed!")

    Log("Removing all snapshots on the VM.")
    vm.RemoveAllSnapshots(vm1)

def TestEditDisk(vm1):
    """ Test reconfigures of capacityInBytes and capacityInKB when both are set
        and differ.
    """
    Log("Adding a new disk.")
    cspec = Vim.Vm.ConfigSpec()
    vmconfig.AddScsiDisk(cspec, cfgInfo = vm1.config)
    vm.Reconfigure(vm1, cspec)
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)
    if len(devices) != 1:
       raise Exception("Failed to find new disk!")

    disk = devices[0]
    Log("Increase disk size by 4MB setting capacityInBytes")
    cspec = Vim.Vm.ConfigSpec()
    newCapacity = disk.capacityInBytes + 4 * 1024 * 1024 + SECTOR_SIZE
    newCapacityKB = (newCapacity - SECTOR_SIZE) / 1024
    disk.capacityInBytes = newCapacity
    vmconfig.AddDeviceToSpec(cspec, disk, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
    vm.Reconfigure(vm1, cspec)
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk,
                                   {"capacityInBytes": newCapacity,
                                    "capacityInKB": newCapacityKB})
    if len(devices) != 1:
       raise Exception("Failed to find the disk with updated capacity: " +  str(len(devices)))

    Log("Atempt to increase only capacityInKB.")
    newCapacityKB = newCapacityKB + 4*1024
    disk.capacityInKB = newCapacityKB
    cspec = Vim.Vm.ConfigSpec()
    vmconfig.AddDeviceToSpec(cspec, disk, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
    vm.Reconfigure(vm1, cspec)
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk,
                                   {"capacityInKB": newCapacityKB})
    if len(devices) != 1:
       raise Exception("Failed to find the disk with updated capacity: " +  str(len(devices)))

    Log("Removing virtual disk from VM")
    cspec = Vim.Vm.ConfigSpec()
    fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
    vmconfig.RemoveDeviceFromSpec(cspec, devices[0], fileOp)
    vm.Reconfigure(vm1, cspec)

def TestCreateDisk(vm1):
    """ Creating disk with various combination of capacityInBytes and capacityInKB.
    """
    Log("Add a new disk with capacityInKB greater than capacityInBytes.")
    # server must consider capacityInBytes
    cspec = Vim.Vm.ConfigSpec()
    cspec = vmconfig.AddScsiCtlr(cspec, cfgInfo = vm1.config)
    capacityKB = 4 * 1024
    vmconfig.AddScsiDisk(cspec, cfgInfo = vm1.config,
                         capacity = capacityKB)
    vm.Reconfigure(vm1, cspec)
    # Server must always return "capacityInBytes"
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk,
                                   {"capacityInKB": capacityKB,
                                    "capacityInBytes": (capacityKB * 1024)})
    if len(devices) != 1:
       raise Exception("Failed to find new disk!")

    Log("Add a new disk with capacityInBytes bigger than capacityInKB.")
    cspec = Vim.Vm.ConfigSpec()
    capacityBytes = (capacityKB * 1024) + SECTOR_SIZE
    vmconfig.AddScsiDisk(cspec, cfgInfo = vm1.GetConfig(), capacity = capacityKB,
                         capacityInBytes = capacityBytes)
    vm.Reconfigure(vm1, cspec)
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk,
                                   {"capacityInKB": capacityKB,
                                    "capacityInBytes": capacityBytes})
    if len(devices) != 1:
       raise Exception("Capacity did not match expected values!")

    cspec = Vim.Vm.ConfigSpec()
    # server must consider capacityInBytes
    capacityBytes = 2*capacityKB*1024 - SECTOR_SIZE
    vmconfig.AddScsiDisk(cspec, cfgInfo = vm1.config, capacity = capacityKB,
                         capacityInBytes = capacityBytes)
    vm.Reconfigure(vm1, cspec)
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk,
                                   {"capacityInKB": (2 * capacityKB)-1,
                                    "capacityInBytes": capacityBytes})
    if len(devices) != 1:
       raise Exception("Capacity did not match expected values!")

    Log("Removing virtual disks from VM.")
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)
    fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
    cspec = Vim.Vm.ConfigSpec()
    for device in devices:
       vmconfig.RemoveDeviceFromSpec(cspec, device, fileOp)
    vm.Reconfigure(vm1, cspec)

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd"),
                     (["v:", "vmname="], "CapacityTest", "Name of the virtual machine", "vmname") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage"),
                        (["runall", "r"], True, "Run all the tests", "runall"),
                        (["nodelete"], False, "Don't delete VM on completion", "nodelete") ]

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

      Log("Creating Hw10 VM...")
      vm1 = vm.CreateQuickDummy(vmname, vmxVersion = "vmx-10",
                                memory = 4, guest = "otherGuest")

      TestCreateDisk(vm1)
      TestEditDisk(vm1)
      TestWithSnapshot(vm1)

      Log("Tests completed.")

   except Exception as e:
      status = "FAIL"
      Log("Caught exception : " + str(e))
   finally:
      # Delete the vm as cleanup
      if noDelete == False:
         if vm1 != None:
            task = vm1.Destroy()
            WaitForTask(task)
      vm1 = None

   Log("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()

