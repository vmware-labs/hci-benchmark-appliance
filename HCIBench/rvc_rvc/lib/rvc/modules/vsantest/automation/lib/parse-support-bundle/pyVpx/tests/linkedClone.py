#!/usr/bin/python

# This test attempts to tests basic functions of linked clone in host agent,
# its frame is shamelessly copied from the qaUnitTests.
#
# Three VMs are created, VM1 on datastore DS1, VM2 & VM3 on datastore DS2,
# and whose disks are linked off snapshot points of VM1.
#
# The VMs relationship and snapshot points are illustrated in the following
# diagram.
#
# VM1 has snapshotS1, which has children
# S1C2 and S1C1 which further has a child S1C1C1. S1C1C1 is the VM1's current
# snapshot.
#
# VM2 has two disks, they are linked off S1C2 and VM3S2 respectively,
# VM3 is linked off S1C1C1. VM3 has a single snapshot VM3S1 and VM3S2.
#
#
#  VM1 on DS1           |               VM2 on DS2
#                       |
#  S1 <===== S1C2  <====|===== |----------|
#  /\      (1 is        |      | VM2 disk1|
#  ||       parentDisk1)|      |----------|
#  ||                   |
# S1C1                  |
#  /\                   |
#  ||                   |
#  || (2 is             |
#  ||  parentDisk2)     |      |----------|
#  ||       |---------| |      | VM2 disk2|
#  ||       |VM1disk 1| |      |----------|
# S1C1C1<===|VM1disk 2| |          ||
#  /\       |---------| |          ||
# -||----------------------------------------------
#  ||                              ||
#  ||          VM3  DS2            || (2 is
# VM3S1                            ||  parentDisk3)
#  /\                              ||
#  ||                              ||
#  \\                              \/
#   -=========================== VM3S2 <=== |-----------|
#                                           | VM3 disk2 |
#                                           |-----------|
#
#
# Then the following operation are performed on the above set up:
#
# (1) Delete snapshot S1C2 of VM1 (whose current snapshot is S1C1C1).
#     This tests SnapshotGenerateDeleteDisks to not attempt to delete
#     S1C2 disk. Power cycle VM2.
#
# (2) Delete VM VM2, make sure disks belong to VM1 are not deleted.
#     Power cycle VM1. Create the same VM2 again.
#
# (3) Delete snapshot VM3S2 of VM3 (which is its current snapshot).
#     Power cycle VM1, revert VM1 to snapshot S1C1. This tests disks
#     belong to VM1 are not consolidated.
#
# (4) Use internal method to do a VM2 disk refresh, then
#     its immediate parent. This tests VM1 disk are not deleted.
#     Power cycle VM1.
#
# (5) Delete VM1. This tests that shared disks are
#     not deleted. Power cycle VM3 and VM2.
#
# (6) Consolidate VM3 disk. Consolidate chain
#     (S1,S1C1, S1C1C1, VM3S1, VM3S2, VM3-disk) should throw an
#     invalid argument exception. Consolidate chain
#     (S1, S1C1, S1C1C1, VM3S1) (VM3S2, VM3-disk) should go
#     successfully.
#
# (7) Destroy VM3 and VM2, verify that their corresponding directories
#     are all empty, no orphaned disks left behind.
#
# Current Limitations:
#    After all VMs are destroyed, there would be orphaned disks left.
#    This would be fixed when the internal functions in LLPM are
#    implemented, at that time, an operation would be added to make
#    sure no orphaned disks left.
#

import sys
import getopt
from pyVmomi import Vim
from pyVmomi import Vmodl
from pyVim import connect
from pyVim.task import WaitForTask
from pyVim import vm
from pyVim import vmconfig
from pyVim import invt
from pyVim import vimutil
from pyVim import arguments
from pyVim import folder
from pyVim import host
from pyVim.helpers import Log,StopWatch
import time
import atexit

def GetBackingInfo(backingType):
   if backingType == 'flat':
      return Vim.Vm.Device.VirtualDisk.FlatVer2BackingInfo()
   if backingType == 'seSparse':
      return Vim.Vm.Device.VirtualDisk.SeSparseBackingInfo()

def PowerCycle(vm1):
   Log("Powercycle (on)")
   vm.PowerOn(vm1)
   time.sleep(2)
   Log("Powercycle (off)")
   vm.PowerOff(vm1)
   time.sleep(2)

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["d:", "d1="], "storage1", "Datastore 1", "ds1"),
                     (["q:", "d2="], "local", "Datastore 2", "ds2"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter"),
                     (["f:", "deltaDiskFormat="], "redoLogFormat", "Delta Disk Format: nativeFormat/seSparseFormat/redoLogFormat", "delta"),
                     (["b:", "backingType="], "flat", "Backing type of disk", "backing"),
                     (["v:", "vmxVersion="], "vmx-08", "The VMX version", "vmx") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Connect
   si = connect.SmartConnect(host=args.GetKeyValue("host"),
                user=args.GetKeyValue("user"),
                pwd=args.GetKeyValue("pwd"))
   atexit.register(connect.Disconnect, si)

   # Process command line
   numiter = int(args.GetKeyValue("iter"))
   ds1 = args.GetKeyValue("ds1")
   ds2 = args.GetKeyValue("ds2")
   deltaDiskFormat = args.GetKeyValue("delta")
   backingType = args.GetKeyValue("backing")
   vmxVersion = args.GetKeyValue("vmx")
   status = "PASS"

   resultsArray = []
   testLinkedClone(si, numiter, deltaDiskFormat, backingType, vmxVersion, ds1, ds2, status, resultsArray)

def testLinkedClone(si, numiter, deltaDiskFormat, backingType, vmxVersion, ds1, ds2, status, resultsArray):
   for i in range(numiter):
      bigClock = StopWatch()
      try:
         try:
            vm1Name = "LinkedParent_" + str(i)
            vm1 = folder.Find(vm1Name)
            if vm1 != None:
               Log("Cleaning up old vm with name: " + vm1Name)
               vm1.Destroy()

            # Create a simple vm with nothing but two disk on ds1
            vm1 = vm.CreateQuickDummy(vm1Name, numScsiDisks=2, \
                                      datastoreName=ds1, diskSizeInMB=1, \
                                      vmxVersion=vmxVersion, \
                                      backingType=backingType)
            Log("Created parent VM1 --" + vm1Name + "with Native snapshotting"
              + " capability set to " + str(vm1.IsNativeSnapshotCapable()))

            vm1DirName = vm1.config.files.snapshotDirectory

            # Create snapshots

            # S1, S1C1, S1C1C1 and S1C2
            vm.CreateSnapshot(vm1, "S1", "S1 is the first snaphost", \
                              False, False)
            snapshotInfo = vm1.GetSnapshot()
            S1Snapshot = snapshotInfo.GetCurrentSnapshot()
            Log("Create Snapshot S1 for VM1")

            vm.CreateSnapshot(vm1, "S1-C1", "S1-C1 is the first child of S1",\
                              False, False)

            snapshotInfo = vm1.GetSnapshot()
            S1C1Snapshot = snapshotInfo.GetCurrentSnapshot()
            Log("Create Snapshot S1C1 for VM1")

            vm.CreateSnapshot(vm1, "S1-C1-C1", \
                              "S1-C1-C1 is the grand child of S1", \
                              False, False)
            snapshotInfo = vm1.GetSnapshot()
            S1C1C1Snapshot = snapshotInfo.GetCurrentSnapshot()
            Log("Create Snapshot S1C1C1 for VM1")

            # revert to S1
            vimutil.InvokeAndTrack(S1Snapshot.Revert)
            Log("Reverted VM1 to Snapshot S1C1")

            vm.CreateSnapshot(vm1, "S1-C2", \
                              "S1-C2 is the second child of S1", False, False)

            snapshotInfo = vm1.GetSnapshot()
            S1C2Snapshot = snapshotInfo.GetCurrentSnapshot()
            Log("Create Snapshot S1C2 for VM1")

            # revert to S1C1C1, so it is the current snapshot
            vimutil.InvokeAndTrack(S1C1C1Snapshot.Revert)
            Log("Reverted VM1 to Snapshot S1C1C1")

            # Get the name of the parent disks
            disks = vmconfig.CheckDevice(S1C2Snapshot.GetConfig(), \
                                         Vim.Vm.Device.VirtualDisk)

            if len(disks) != 2:
               raise Exception("Failed to find parent disk1")

            parentDisk1 = disks[0].GetBacking().GetFileName()

            disks = vmconfig.CheckDevice(S1C1C1Snapshot.GetConfig(), Vim.Vm.Device.VirtualDisk)

            if len(disks) != 2:
               raise Exception("Failed to find parent disk2")

            parentDisk2 = disks[1].GetBacking().GetFileName()

            # Create a VM2 on ds2 that is linked off S1C2
            vm2Name = "LinkedChild1_" + str(i)
            configSpec = vmconfig.CreateDefaultSpec(name = vm2Name, datastoreName = ds2)
            configSpec = vmconfig.AddScsiCtlr(configSpec)
            configSpec = vmconfig.AddScsiDisk(configSpec, datastorename = ds2, capacity = 1024, backingType = backingType)
            configSpec.SetVersion(vmxVersion)
            childDiskBacking = configSpec.GetDeviceChange()[1].GetDevice().GetBacking()
            parentBacking = GetBackingInfo(backingType)
            parentBacking.SetFileName(parentDisk1)
            childDiskBacking.SetParent(parentBacking)
            childDiskBacking.SetDeltaDiskFormat(deltaDiskFormat)

            resPool = invt.GetResourcePool()
            vmFolder = invt.GetVmFolder()
            vimutil.InvokeAndTrack(vmFolder.CreateVm, configSpec, resPool)

            vm2 = folder.Find(vm2Name)
            Log("Created child VM2 --" + vm2Name)

            vm2DirName = vm2.config.files.snapshotDirectory

            # Create a VM3 on ds2 that is linked off S1C1C1
            vm3Name = "LinkedChild2_" + str(i)
            configSpec.SetName(vm3Name)
            parentBacking.SetFileName(parentDisk2)

            vimutil.InvokeAndTrack(vmFolder.CreateVm, configSpec, resPool)
            vm3 = folder.Find(vm3Name)
            Log("Created child VM3 --" + vm3Name)

            vm3DirName = vm3.config.files.snapshotDirectory

            # Create snapshot VM3S1 for VM3
            vm.CreateSnapshot(vm3, "VM3S1", "VM3S1 is VM3 snaphost", False, False)
            Log("Create Snapshot VM3S1 for VM3")

            # Create snapshot VM3S2 for VM3
            vm.CreateSnapshot(vm3, "VM3S2", "VM3S2 is VM3 snaphost", False, False)
            Log("Create Snapshot VM3S2 for VM3")
            snapshotInfo = vm3.GetSnapshot()
            VM3S2Snapshot = snapshotInfo.GetCurrentSnapshot()

            # get the disk name of VM3S2 so it can be configured as a
            # parent disk for VM2
            disks = vmconfig.CheckDevice(VM3S2Snapshot.GetConfig(), Vim.Vm.Device.VirtualDisk)

            if len(disks) != 1:
               raise Exception("Failed to find parent disk2")

            parentDisk3 = disks[0].GetBacking().GetFileName()

            # create a delta disk off VM3S2 on VM2
            Log("Adding delta disk off VM3S2 to VM2")
            configSpec = Vim.Vm.ConfigSpec()
            configSpec = vmconfig.AddScsiDisk(configSpec, \
                                              datastorename = ds2, \
                                              cfgInfo = vm2.GetConfig(), \
                                              backingType = backingType)
            childDiskBacking = configSpec.GetDeviceChange()[0].GetDevice().GetBacking()
            parentBacking = GetBackingInfo(backingType)
            parentBacking.SetFileName(parentDisk3)
            childDiskBacking.SetParent(parentBacking)
            childDiskBacking.SetDeltaDiskFormat(deltaDiskFormat)

            vimutil.InvokeAndTrack(vm2.Reconfigure, configSpec)

            Log("Power cycle VM1...")
            PowerCycle(vm1)
            Log("Power cycle VM2...")
            PowerCycle(vm2)
            Log("Power cycle VM3...")
            PowerCycle(vm3)

            Log("OP1: delete VM1.S1C2, then power cycle VM2")
            vimutil.InvokeAndTrack(S1C2Snapshot.Remove, True)
            PowerCycle(vm2)

            Log("OP2: destroy VM2, power cycle VM1")
            vimutil.InvokeAndTrack(vm2.Destroy)
            PowerCycle(vm1)

            Log("then recreate VM2 with just disk1")
            configSpec = vmconfig.CreateDefaultSpec(name = vm2Name, \
                                                    datastoreName = ds2)
            configSpec = vmconfig.AddScsiCtlr(configSpec)
            configSpec = vmconfig.AddScsiDisk(configSpec, datastorename = ds2, \
                                              capacity = 1024, \
                                              backingType = backingType)
            configSpec.SetVersion(vmxVersion)
            childDiskBacking = configSpec.GetDeviceChange()[1].GetDevice().GetBacking()
            parentBacking = GetBackingInfo(backingType)
            parentBacking.SetFileName(parentDisk1)
            childDiskBacking.SetParent(parentBacking)
            childDiskBacking.SetDeltaDiskFormat(deltaDiskFormat)

            resPool = invt.GetResourcePool()
            vmFolder = invt.GetVmFolder()
            vimutil.InvokeAndTrack(vmFolder.CreateVm, configSpec, resPool)
            vm2 = folder.Find(vm2Name)
            Log("ReCreated child VM2 --" + vm2Name)

            Log("OP3: delete VM3S2, power cycle VM1, revert to S1C1")
            vimutil.InvokeAndTrack(VM3S2Snapshot.Remove, True)
            vimutil.InvokeAndTrack(S1C1Snapshot.Revert)
            PowerCycle(vm1)

            llpm = si.RetrieveInternalContent().GetLlProvisioningManager()

            Log("OP4: refresh VM2 disk and destroy the disk and its parent")
            llpm.ReloadDisks(vm2, ['currentConfig', 'snapshotConfig'])

            disks = vmconfig.CheckDevice(vm2.GetConfig(), \
                                         Vim.Vm.Device.VirtualDisk)
            diskChain1 = disks[0]
            diskChain1.backing.parent.parent = None
            configSpec = Vim.Vm.ConfigSpec()
            configSpec = vmconfig.RemoveDeviceFromSpec(configSpec, \
                                                       diskChain1,
                                                       "destroy")
            configSpec.files = vm2.config.files
            llpm.ReconfigVM(configSpec)
            Log("verify only the immediate parent is deleted")
            PowerCycle(vm1)

            Log("OP5: destroy VM1, power cycle VM3")
            vimutil.InvokeAndTrack(vm1.Destroy)
            PowerCycle(vm3)

            Log("OP6: Consolidate VM3 disk chain")
            disks = vmconfig.CheckDevice(vm3.GetConfig(), \
                                         Vim.Vm.Device.VirtualDisk)

            shouldHaveFailed = 0
            try:
               task = llpm.ConsolidateDisks(vm3, disks)
               WaitForTask(task)
            except Exception as e:
               shouldHaveFailed = 1
               Log("Hit an exception when trying to consolidate cross " \
                   "snapshot point.")

            if shouldHaveFailed != 1:
               raise Exception("Error: allowed consolidation to merge snapshot")

            diskchain1 = disks[0]
            diskchain1.backing.parent.parent = None

            disks = vmconfig.CheckDevice(vm3.GetConfig(), \
                                         Vim.Vm.Device.VirtualDisk)
            diskchain2 = disks[0]
            diskchain2.backing = diskchain2.backing.parent.parent

            disks = []
            disks.append(diskchain1)
            disks.append(diskchain2)

            vimutil.InvokeAndTrack(llpm.ConsolidateDisks, vm3, disks)
            PowerCycle(vm3)

            Log("OP7: destroy VM2, no orphaned disks/files should have left")
            vimutil.InvokeAndTrack(vm2.Destroy)

            Log("Delete snapshot of VM3, and delete the disk with all parent."
                "then destroy vM3, no orphaned disks/files should have left")

            disks = vmconfig.CheckDevice(vm3.GetConfig(), \
                                         Vim.Vm.Device.VirtualDisk)
            diskChain1 = disks[0]
            configSpec = Vim.Vm.ConfigSpec()
            configSpec = vmconfig.RemoveDeviceFromSpec(configSpec, \
                                                       diskChain1,
                                                       "destroy")
            configSpec.files = vm3.config.files
            vimutil.InvokeAndTrack(llpm.ReconfigVM, configSpec)
            vimutil.InvokeAndTrack(vm3.Destroy)

            hostSystem = host.GetHostSystem(si)
            b = hostSystem.GetDatastoreBrowser()

            shouldHaveFailed = 0

            try:
               vimutil.InvokeAndTrack(b.Search, vm1DirName)
            except Vim.Fault.FileNotFound:
               Log("Caught " + vm1DirName + "Not found as expected")
               shouldHaveFailed += 1

            try:
               vimutil.InvokeAndTrack(b.Search, vm2DirName)
            except Vim.Fault.FileNotFound:
               Log("Caught " + vm2DirName + "Not found as expected")
               shouldHaveFailed += 1

            try:
               vimutil.InvokeAndTrack(b.Search, vm3DirName)
            except Vim.Fault.FileNotFound:
               Log("Caught " + vm3DirName + "Not found as expected")
               shouldHaveFailed += 1

            if shouldHaveFailed != 3:
               Log("Failed, orphaned disks left")
               raise Exception("orphaned disks")

            status = "PASS"

         finally:
            bigClock.finish("iteration " + str(i))

      except Exception as e:
         Log("Caught exception : " + str(e))
         status = "FAIL"

      Log("TEST RUN COMPLETE: " + status)
      resultsArray.append(status)

   Log("Results for each iteration: ")
   for i in range(len(resultsArray)):
      Log("Iteration " + str(i) + ": " + resultsArray[i])


# Start program
if __name__ == "__main__":
    main()
