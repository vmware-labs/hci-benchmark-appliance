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


def Diff(lhs, rhs):
   diff = []
   lhs = sorted(lhs, key=lambda object: object.key)
   rhs = sorted(rhs, key=lambda object: object.key)
   for i in range(len(lhs)):
      if str(lhs[i]) != str(rhs[i]):
         diff.append([lhs[i], rhs[i]])
   return diff

def TestMoveDevice(vm1, device, ctlr):
    cspec = Vim.Vm.ConfigSpec()
    newCtlrKey = ctlr.key
    cfgOption = vmconfig.GetCfgOption(None)
    unitNumber = vmconfig.GetFreeSlot(cspec, vm1.config, cfgOption, ctlr)
    device.unitNumber = unitNumber;
    device.controllerKey = newCtlrKey
    vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
    vm.Reconfigure(vm1, cspec)
    devices = vmconfig.CheckDevice(vm1.config, type(device),
                                   {"controllerKey": newCtlrKey})

    if len(devices) != 1:
       raise Exception("Failed to move device!")

def TestExtendDisk(vm1):
    disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[0]
    # increase disk size
    Log("Increase disk size by 8 MB")
    cspec = Vim.Vm.ConfigSpec()
    newCapacity = disk.capacityInKB + 8192
    disk.capacityInKB = newCapacity
    vmconfig.AddDeviceToSpec(cspec, disk, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
    vm.Reconfigure(vm1, cspec)
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk,
                                   {"capacityInKB": newCapacity})
    if len(devices) != 1:
       raise Exception("Failed to find the disk with updated capacity")

def TestReconfigDeltaDisk(vm1):
      # attempt to extend a disk with a parent
    Log("Creating a snapshot on the VM for negative disk extend test")
    vm.CreateSnapshot(vm1, "dummy snapshot", "dummy desc", False, False)
    Log("Attempting to extend disk size of delta disk")
    disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[0]
    cspec = Vim.Vm.ConfigSpec()
    disk.capacityInKB = disk.capacityInKB + 4096
    vmconfig.AddDeviceToSpec(cspec, disk, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
    task = vm1.Reconfigure(cspec)
    try:
       WaitForTask(task)
    except Exception as e:
       Log("Hit an exception extending delta disk as expected" + str(e))
    else:
       raise Exception("Error: Extending delta disk was allowed!")

    Log("Removing all snapshots on the VM")
    vm.RemoveAllSnapshots(vm1)

def TestReconfigCdromBacking(vm1):
    cdrom = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualCdrom)[0]
    cspec = Vim.Vm.ConfigSpec()
    backing = Vim.Vm.Device.VirtualCdrom.IsoBackingInfo(fileName="[]")
    cdrom.backing = backing
    vmconfig.AddDeviceToSpec(cspec, cdrom, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
    vm.Reconfigure(vm1, cspec)
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualCdrom,
                                  {"backing.fileName": "[]"})
    if len(devices) != 1:
       raise Exception("Failed to find edited cdrom!")

def TestSnapshotCdrom(vm1):
    cdrom = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualCdrom)[0]
    Log("Creating a snapshot on the VM")
    vm.CreateSnapshot(vm1, "dummy snapshot", "dummy desc", False, False)
    snap = vm1.snapshot.currentSnapshot
    if len(Diff(vm1.config.hardware.device, snap.config.hardware.device)):
        Log("Mismatch between config and snapshot")
        raise Exception("Snapshot hardware differ VM hardware list!")

    Log("Revert to current snapshot")
    vm.RevertToCurrentSnapshot(vm1)
    propList = {"key": cdrom.key, "controllerKey": cdrom.controllerKey}
    Log("Check if cdrom is present after reverting to snapshot.")
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualCdrom, propList)
    if len(devices) != 1:
       raise Exception("Failed to find cdrom after revert to snapshot.")

    Log("Removing all snapshots on the VM.")
    vm.RemoveAllSnapshots(vm1)

def AddSataDisk(vm1):
    cspec = Vim.Vm.ConfigSpec()
    vmconfig.AddSataDisk(cspec, cfgInfo = vm1.config)
    vm.Reconfigure(vm1, cspec)

    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)
    if len(devices) < 1:
       raise Exception("Failed to find SATA disk!")
    ctlrKey = devices[0].controllerKey
    ctlrs = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualSATAController,
                                 {"key": ctlrKey})
    if len(ctlrs) != 1:
       raise Exception("Failed to find SATA controller!")

def AddSataCdrom(vm1):
    cfgInfo = vm1.config
    cspec = Vim.Vm.ConfigSpec()
    vmconfig.AddSataCdrom(cspec, cfgInfo = vm1.config)
    vm.Reconfigure(vm1, cspec)
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualCdrom)
    if len(devices) < 1:
       raise Exception("Failed to find SATA cdrom!")

    cdrom = devices[0]
    ctlrKey = cdrom.controllerKey
    ctlrs = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualSATAController,
                                   {"key": ctlrKey})
    if len(ctlrs) != 1:
       raise Exception("Failed to find SATA controller!")

def RemoveSataDisk(vm1):
    disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[0]
    cspec = Vim.Vm.ConfigSpec()
    fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
    vmconfig.RemoveDeviceFromSpec(cspec, disk, fileOp)
    vm.Reconfigure(vm1, cspec)
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)
    if len(devices) != 0:
       raise Exception("Found disk after delete")

def RemoveSataCdrom(vm1):
    cdrom = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualCdrom)[0]
    vm.RemoveDevice(vm1, cdrom)
    devices = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualCdrom)
    if len(devices) != 0:
       raise Exception("Found cdrom after delete")

def TestEditSataCdrom(vm1):
    """
    Test reconfigures of SATA cdroms
    """
    cspec = Vim.Vm.ConfigSpec()
    cspec = vmconfig.AddSataCtlr(cspec)
    vm.Reconfigure(vm1, cspec)

    Log("Add SATA cdrom.")
    AddSataCdrom(vm1)

    Log("Reconfigure cdrom backing.")
    TestReconfigCdromBacking(vm1)

    Log("Snapshot VM and revert to snapshot.")
    TestSnapshotCdrom(vm1)

    Log("Moving cdrom from SATA to IDE controller.")
    ideCtlrs = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualIDEController)
    cdrom = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualCdrom)[0]
    TestMoveDevice(vm1, cdrom, ideCtlrs[0])

    Log("Remove cdrom.")
    RemoveSataCdrom(vm1)

    Log("Testing hot-add and hot-remove of SATA cdrom.")
    vm.PowerOn(vm1)
    AddSataCdrom(vm1)
    RemoveSataCdrom(vm1)
    vm.PowerOff(vm1)

    ctlrs = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualSATAController)
    vm.RemoveDevice(vm1, ctlrs[0])

def TestEditSataDisk(vm1):
    """
    Test reconfigures of SATA disks
    """
    cspec = Vim.Vm.ConfigSpec()
    cspec = vmconfig.AddSataCtlr(cspec)
    cspec = vmconfig.AddScsiCtlr(cspec)
    vm.Reconfigure(vm1, cspec)

    Log("Add SATA disk.")
    AddSataDisk(vm1)

    Log("Reconfigure disk capacity.")
    TestExtendDisk(vm1)

    Log("Snapshot and reconfigure delta disk.")
    TestReconfigDeltaDisk(vm1)

    Log("Move SATA disk to SCSI controller.")
    scsiCtlrs = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualSCSIController)
    if len(scsiCtlrs) < 1:
       raise Exception("Failed to find SCSI controller!")
    disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[0]
    TestMoveDevice(vm1, disk, scsiCtlrs[0])

    Log("Move SCSI disk to SATA controller.")
    ctlrs = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualSATAController)
    disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[0]
    TestMoveDevice(vm1, disk, ctlrs[0])
    vm.RemoveDevice(vm1, scsiCtlrs[0])

    Log("Remove SATA disk.")
    RemoveSataDisk(vm1);

    Log("Testing hot-add and hot-remove of SATA disk.")
    vm.PowerOn(vm1)
    AddSataDisk(vm1)
    RemoveSataDisk(vm1);
    vm.PowerOff(vm1)

    vm.RemoveDevice(vm1, ctlrs[0])

def TestSataCtlrReconfig(vm1):
    """
    Test add and remove for SATA controller
    """
    Log("Adding SATA controller to VM")
    cspec = Vim.Vm.ConfigSpec()
    cspec = vmconfig.AddSataCtlr(cspec, cfgInfo = vm1.config)
    vm.Reconfigure(vm1, cspec)

    # Check for controller presence in VM's config
    ctlrs = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualAHCIController)
    if len(ctlrs) != 1:
       raise Exception("Failed to find added SATA controller :" + str(len(ctlrs)))

    Log("Powering on VM " + vm1.config.GetName())
    vm.PowerOn(vm1)

    Log("Hot-add SATA controller to VM")
    cspec = Vim.Vm.ConfigSpec()
    cspec = vmconfig.AddSataCtlr(cspec, cfgInfo = vm1.config)
    vm.Reconfigure(vm1, cspec)

    ctlrs = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualAHCIController)
    if len(ctlrs) != 2:
       raise Exception("Failed to find added SATA controller :" + str(len(ctlrs)))

    vm.PowerOff(vm1)
    # Remove SATA controller from VM
    Log("Removing SATA controllers from VM")
    cspec = Vim.Vm.ConfigSpec()
    vmconfig.AddDeviceToSpec(cspec, ctlrs[0], Vim.Vm.Device.VirtualDeviceSpec.Operation.remove)
    vmconfig.AddDeviceToSpec(cspec, ctlrs[1], Vim.Vm.Device.VirtualDeviceSpec.Operation.remove)
    vm.Reconfigure(vm1, cspec)

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd"),
                     (["v:", "vmname="], "SATATest", "Name of the virtual machine", "vmname") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage"),
                        (["runall", "r"], True, "Run all the tests", "runall"),
                        (["nodelete"], False, "Dont delete vm on completion", "nodelete") ]

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

      ## Positive tests on a hwVersion 10 VM
      Log("Creating Hw10 VM..")
      vm1 = vm.CreateQuickDummy(vmname, vmxVersion = "vmx-10",
                                memory = 4, guest = "otherGuest")

      # Test add of SATA controller
      TestSataCtlrReconfig(vm1)

      # Mess with SATA disks
      TestEditSataDisk(vm1)

      # Mess with SATA cdroms
      TestEditSataCdrom(vm1)

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

