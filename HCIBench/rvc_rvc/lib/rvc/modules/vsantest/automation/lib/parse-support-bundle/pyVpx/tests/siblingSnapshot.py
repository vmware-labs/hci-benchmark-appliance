#!/usr/bin/python

from __future__ import print_function

import sys
from pyVmomi import Vim, Vmodl, VmomiSupport, SoapAdapter
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm, connect
from pyVim import invt
from pyVim import vmconfig
from pyVim import vimutil
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import time
import atexit

debug = True

def printDebug(foo):
   if debug:
      print(foo)

def backings(config):
   return [device.backing for device in config.hardware.device if type(device.backing) == Vim.Vm.Device.VirtualDisk.FlatVer2BackingInfo or type(device.backing) == Vim.Vm.Device.VirtualDisk.SeSparseBackingInfo]

def findMatchingSnaps(snapshotTreeList, snapName, matchingSnaps):
   for snap in snapshotTreeList:
      if (snap.name == snapName):
         matchingSnaps.append(snap)
      if snap.childSnapshotList == []:
         findMatchingSnaps(snap.childSnapshotList, snapName, matchingSnaps)

def snapshotTest(virtualMachine, snapName, quiesced, memory, deltaDiskFormat):
   Log("{ Creating " + deltaDiskFormat + " based snapshot")
   if deltaDiskFormat == "nativeFormat":
      printDebug ("Skipping nativeFormat based Snapshot")
      return
   task = virtualMachine.CreateSnapshot(snapName, snapName, quiesced, memory)
   WaitForTask(task)

   snapInfo = virtualMachine.GetSnapshot()
   printDebug(snapInfo)
   printDebug(backings(virtualMachine.config))
   matchingSnaps=[]
   findMatchingSnaps(virtualMachine.GetSnapshot().rootSnapshotList, snapName, matchingSnaps)
   printDebug(matchingSnaps)
   for matchingSnap in matchingSnaps:
      snapShotBackings = backings(matchingSnap.snapshot.config)
      for backing in snapShotBackings:
         assert backing.deltaDiskFormat == None or backing.deltaDiskFormat == deltaDiskFormat or (not virtualMachine.IsNativeSnapshotCapable() and deltaDiskFormat == "redoLogFormat")
      try:
         task = matchingSnap.snapshot.Revert()
         WaitForTask(task)
      except Exception as e:
         printDebug(e)
      vm.RemoveSnapshot(matchingSnap.snapshot, False)

   printDebug(backings(virtualMachine.config))
   Log("End Creating " + deltaDiskFormat + " based snapshot }")

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "vmname="], "t1", "Name of the virtual machine", "vmname"),
                     (["i:", "iter="], "1", "Num of iterations", "iter")]
   supportedToggles = [(["usage", "help"], False, "Show usage information", "usage")]

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
   numiter = int(args.GetKeyValue("iter"))

   # Cleanup from previous runs.
   vm1 = folder.Find(vmname)
   printDebug(vm1.config)
   if vm1 == None:
      printDebug("VM not found.")
      sys.exit(0)

   for i in xrange(numiter) :
      try:
         printDebug(("Native Snapshot Capable?", vm1.IsNativeSnapshotCapable()))
         memoryOptions = [True, False]
         quiescedOptions = [True, False]
         deltaDiskFormatOptions = ["redoLogFormat", "nativeFormat"]
         for deltaDiskFormatOption in deltaDiskFormatOptions:
            for memoryOption in memoryOptions:
               for quiescedOption in quiescedOptions:
                  snapshotTest(vm1, deltaDiskFormatOption, quiescedOption,
                               memoryOption, deltaDiskFormatOption)
         time.sleep(5)

         Log("Remove all snapshots")
         vm.RemoveAllSnapshots(vm1)

         Log("Success: iter " + str(i))

         printDebug(vm1.config)

      except Exception as e:
         Log("Caught exception at iter " + str(i) + ": " + str(e))

# Start program
if __name__ == "__main__":
    main()
