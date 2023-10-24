#!/usr/bin/python

# This test attempts to tests basic functionality of LLPM
# promoteDisks API in host agent,

from __future__ import print_function

import sys
import getopt
from pyVmomi import vim, vmodl
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


def SetDeltaDiskBacking(configSpec, idx, parentDisk):
   childDiskBacking = configSpec.GetDeviceChange()[idx].GetDevice().GetBacking()
   parentBacking = Vim.Vm.Device.VirtualDisk.FlatVer2BackingInfo()
   parentBacking.SetFileName(parentDisk)
   childDiskBacking.SetParent(parentBacking)
   childDiskBacking.SetDeltaDiskFormat('redoLogFormat')


def GetVirtualDisks(vm):
    return list(filter(lambda device: isinstance(device,
                                                 vim.vm.Device.VirtualDisk),
                       vm.GetConfig().GetHardware().GetDevice()))

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["d:", "d1="], "storage1", "Datastore 1", "ds1"),
                     (["q:", "d2="], "local", "Datastore 2", "ds2"),
                     (["i:", "numiter="], "1", "No. of iterations", "iter"),
                     (["b:", "backingType="], "flat", "Backing type", "backing"),
                     (["v:", "vmxVersion="], "vmx-08", "VMX version", "vmx"),
                     (["n:", "numDisks="], "3", "No. of Disks", "numDisks") ]

   supportedToggles = [ (["usage", "help"], False,
                         "Show usage information", "usage")]

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
   backingType = args.GetKeyValue("backing")
   vmxVersion = args.GetKeyValue("vmx")
   numDisks = int(args.GetKeyValue("numDisks"))
   status = "PASS"

   resultsArray = []
   testPromoteDisks(si, numDisks, numiter, backingType,
                    vmxVersion, ds1, ds2, status, resultsArray)

def testPromoteDisks(si, numDisks, numiter, backingType,
                     vmxVersion, ds1, ds2, status, resultsArray):
   for i in range(numiter):
      bigClock = StopWatch()
      try:
         try:
            vm1Name = "Parent" + str(i)
            vm1 = folder.Find(vm1Name)
            if vm1 != None:
               Log("Cleaning up old vm with name: " + vm1Name)
               vm1.Destroy()

            # Create a simple vm with numDisks on ds1
            vm1 = vm.CreateQuickDummy(vm1Name, numScsiDisks=numDisks, \
                                      datastoreName=ds1, diskSizeInMB=1, \
                                      vmxVersion=vmxVersion, \
                                      backingType=backingType)
            Log("Created parent VM1 --" + vm1Name)

            vm1DirName = vm1.config.files.snapshotDirectory

            # Create snapshot
            vm.CreateSnapshot(vm1, "S1", "S1 is the first snaphost", \
                              False, False)
            snapshotInfo = vm1.GetSnapshot()
            S1Snapshot = snapshotInfo.GetCurrentSnapshot()
            Log("Created Snapshot S1 for VM1")

            # Get the name of the parent disks
            disks = vmconfig.CheckDevice(S1Snapshot.GetConfig(), \
                                         Vim.Vm.Device.VirtualDisk)

            if len(disks) != numDisks:
               raise Exception("Failed to find parent disks")

            parentDisks = [None] * len(disks)
            for i in range(len(disks)):
               parentDisks[i] = disks[i].GetBacking().GetFileName()

            # Create a VM2 on ds2 that is linked off S1
            vm2Name = "LinkedClone" + str(i)
            configSpec = vmconfig.CreateDefaultSpec(name = vm2Name,
                                                    datastoreName = ds2)
            configSpec = vmconfig.AddScsiCtlr(configSpec)
            configSpec = vmconfig.AddScsiDisk(configSpec,
                                              datastorename = ds2,
                                              capacity = 1024,
                                              backingType = backingType)
            configSpec.SetVersion(vmxVersion)
            childDiskBacking = configSpec.GetDeviceChange()[1].\
                               GetDevice().GetBacking()
            parentBacking = GetBackingInfo(backingType)
            parentBacking.SetFileName(parentDisks[0])
            childDiskBacking.SetParent(parentBacking)
            childDiskBacking.SetDeltaDiskFormat("redoLogFormat")

            resPool = invt.GetResourcePool()
            vmFolder = invt.GetVmFolder()
            vimutil.InvokeAndTrack(vmFolder.CreateVm, configSpec, resPool)

            vm2 = folder.Find(vm2Name)
            Log("Created child VM2 --" + vm2Name)

            vm2DirName = vm2.config.files.snapshotDirectory

            # create delta disks off VM1 on VM2
            Log("Adding delta disks off VM1 to VM2")
            configSpec = Vim.Vm.ConfigSpec()
            for i in range(len(parentDisks)):
               configSpec = vmconfig.AddScsiDisk(configSpec, \
                                                 datastorename = ds2, \
                                                 cfgInfo = vm2.GetConfig(), \
                                                 backingType = backingType)
               SetDeltaDiskBacking(configSpec, i, parentDisks[i])

            vimutil.InvokeAndTrack(vm2.Reconfigure, configSpec)

            Log("Power (on) vm1")
            vm.PowerOn(vm1)
            time.sleep(5)

            Log("Power (on) vm2")
            vm.PowerOn(vm2)
            time.sleep(5)

            # prepare promoteDisksSpec
            diskList = GetVirtualDisks(vm2)
            promoteDisksSpec = [None] * len(diskList)
            for i in range(len(diskList)):
                promoteDisksSpec[i]=vim.host.LowLevelProvisioningManager.\
                                    PromoteDisksSpec()
                promoteDisksSpec[i].SetNumLinks(1)
                promoteDisksSpec[i].SetOffsetFromBottom(0)
                diskId = diskList[i].GetKey()
                promoteDisksSpec[i].SetDiskId(diskId)

            Log("Calling LLPM PromoteDisks")
            llpm = invt.GetLLPM()
            try:
                task = llpm.PromoteDisks(vm2, promoteDisksSpec)
                WaitForTask(task)
            except Exception as e:
                print(e)
                Log("Caught exception : " + str(e))
                status = "FAIL"

            status = "PASS"

            Log("Destroying VMs")
            vm.PowerOff(vm2)
            time.sleep(5)
            vm.PowerOff(vm1)
            time.sleep(5)

            vm2.Destroy()
            vm1.Destroy()

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
