#!/usr/bin/python

# Exercises the virtual disk manager code in multi-host environment.
#
# Tests takes two hosts, which are assumed to have the same connection
# parameters, and have a shared datastore with about 200MB of free space.
#
# Test will create a VM with disk, take a snapshot, keep the VM powered
# in a host while performing virtual disk manager operations in another
# host.
#
# Does not touch existing files/directories in the datastore.

from __future__ import print_function

import os
import sys
from pyVmomi import Vim
from pyVmomi import Vmodl
from pyVim.connect import SmartConnect
from pyVim.task import WaitForTask
from pyVim import host
from pyVim import vm
from pyVim import invt
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import time

class Phase:
   def __init__(self):
      self.phaseNumber = 0
      self.phaseClock = StopWatch()

   def SetPhase(self, msg):
      Log("Phase " + str(self.phaseNumber) + ": " + msg + " completed")
      self.phaseClock.finish("phase " + str(self.phaseNumber))
      self.phaseClock = StopWatch()
      self.phaseNumber = self.phaseNumber + 1

class OtherHostSetup:
   def __init__(self, args):
      self._host = args.GetKeyValue("otherhost")
      self._user = args.GetKeyValue("user")
      self._pwd = args.GetKeyValue("otherpwd")
      self._ds = args.GetKeyValue("ds")
      self._vmName = args.GetKeyValue("vm")

   def SetupOtherHost(self):
      print(self._host + " " + self._user + " " + self._pwd)
      siOther = SmartConnect(host=self._host,
                             user=self._user,
                             pwd=self._pwd)
      self._vm = vm.CreateQuickDummy(self._vmName, numScsiDisks=1,
                                     datastoreName=self._ds)
      if self._vm == None:
         raise "Failed to create VM with specified video ram size"

      Log("Other Host: Power On VM")
      vm.PowerOn(self._vm)
      Log("Other Host: Take Snapshot (no memory)")
      vm.CreateSnapshot(self._vm, "pre vdm snap", "Pre VDM snapshot", False, False)

   def CleanupOtherHost(self):
      Log("Other Host: Power off")
      vm.PowerOff(self._vm)
      Log("Other Host: Deleting VM")
      self._vm.Destroy()

# Tests for VirtualDiskManager managed object
class VirtualDiskManagerTest:

   def __init__(self, si, virtualDiskManager, args):
      self._si = si
      self._vdm = virtualDiskManager
      self._dc = invt.GetDatacenter()
      self._ds = args.GetKeyValue("ds")
      self._vmName = args.GetKeyValue("vm")

   def MonitorTask(self, task):
      WaitForTask(task, True, si=self._si)

   def MakeDsPath(self, name, subdir=""):
      if subdir != "" and subdir[-1] != '/':
         subdir = subdir + "/"
      path = "[" + self._ds + "] " + subdir + name + ".vmdk"
      return path

   def DeleteSingle(self, path):
      Log("Deleting disk (" + path + ").")
      task = self._vdm.DeleteVirtualDisk(path, None)
      self.MonitorTask(task)
      Log("Deleting disk (" + path + ") Done.")

   def TestCopyDisksOfRunningVM(self, targetDiskType="thin", targetAdapterType="lsiLogic"):
      Log("VirtualDiskManager: Copy disks of a running virtual machine.")
      spec = Vim.VirtualDiskManager.FileBackedVirtualDiskSpec()
      spec.capacityKb = long(10000)
      spec.diskType = targetDiskType
      spec.adapterType = targetAdapterType

      pathWriteLocked = self.MakeDsPath(self._vmName + "-000001", self._vmName)
      pathReadLocked = self.MakeDsPath(self._vmName, self._vmName + "/")
      pathCopy = self.MakeDsPath(self._vmName + "_copy", self._vmName)

      success = 0
      try:
         print("Copying " + pathWriteLocked + " to " + pathCopy)
         task = self._vdm.CopyVirtualDisk(pathWriteLocked, self._dc,
                                          pathCopy, self._dc, spec, True)
         self.MonitorTask(task)
      except Vmodl.Fault.SystemError as e:
         if e.reason.find("ailed to lock") != -1:
            success = 1
      if success == 1:
         print("Copying write-locked failed as expected")
      else:
         raise "Copying write-locked disk did not fail as expected"

      print("Copying " + pathReadLocked + " to " + pathCopy)
      task = self._vdm.CopyVirtualDisk(pathReadLocked, self._dc,
                                       pathCopy, self._dc, spec, True)
      self.MonitorTask(task)
      self.DeleteSingle(pathCopy)


   def RunTests(self):
      Log("VirtualDiskManager: Run tests")
      self.TestCopyDisksOfRunningVM()

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["o:", "otherhost="], "", "Host name of other host", "otherhost"),
                     (["q:", "otherpwd="], "ca$hc0w", "Password of other host", "otherpwd"),
                     (["d:", "ds="], None, "Datastore name", "ds"),
                     (["v:", "vm="], "vdm_multihost", "VM name", "vm"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage"),
                        (["cleanup", "c"], True, "Try to cleanup test vms from previous runs", "cleanup")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   si = SmartConnect(host=args.GetKeyValue("host"),
                     user=args.GetKeyValue("user"),
                     pwd=args.GetKeyValue("pwd"))
   Log("Connected to host " + args.GetKeyValue("host"))

   # Process command line
   numiter = int(args.GetKeyValue("iter"))
   doCleanup = args.GetKeyValue("cleanup")
   status = "PASS"

   resultsArray = []

   serviceInstanceContent = si.RetrieveContent()
   vdiskMgr = serviceInstanceContent.GetVirtualDiskManager()
   if vdiskMgr == None:
      Log("Virtual Disk Manager not found")
      sys.exit(0)

   otherHostSetup = OtherHostSetup(args)
   otherHostSetup.SetupOtherHost();
   for i in range(numiter):
      bigClock = StopWatch()
      try:
         try:
            ph = Phase()

            vdiskMgrTest = VirtualDiskManagerTest(si, vdiskMgr, args)
            vdiskMgrTest.RunTests()

            ph.SetPhase("Virtual Disk Manager Tests")
            status = "PASS"

         finally:
            bigClock.finish("iteration " + str(i))

      except Exception as e:
         Log("Caught exception : " + str(e))
         status = "FAIL"

      Log("TEST RUN COMPLETE: " + status)
      resultsArray.append(status)

   otherHostSetup.CleanupOtherHost();

   Log("Results for each iteration: ")
   for i in range(len(resultsArray)):
      Log("Iteration " + str(i) + ": " + resultsArray[i])

# Start program
if __name__ == "__main__":
    main()
