#!/usr/bin/python

import sys
import time
import getopt
import traceback
#import pyVmacore
from pyVmomi import Vim
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm
from pyVim import arguments
from pyVim import folder
from pyVim.helpers import Log

import atexit

status = "PASS"


## Helper routine to add extra config entries to a VM.
def AddExtraConfig(extraCfgs, key, value):
   opt = Vim.Option.OptionValue()
   opt.SetKey(key)
   opt.SetValue(value)
   extraCfgs.append(opt)


def CheckState(vm, state):
   curState = vm.GetRuntime().GetRecordReplayState()
   if curState != state:
      raise Exception("Runtime record/replay state not set to " + str(state))
   Log("Verified runtime record/replay state")

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "vmname="], "Replay-VM", "Name of the virtual machine", "vmname"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Connect
   si = Connect(host=args.GetKeyValue("host"),
                user=args.GetKeyValue("user"),
                pwd=args.GetKeyValue("pwd"))
   atexit.register(Disconnect, si)

   # Process command line
   vmname = args.GetKeyValue("vmname")
   numiter = int(args.GetKeyValue("iter"))
   global status

   for i in range(numiter):
      vm1 = None
      # Cleanup from previous runs
      vm1 = folder.Find(vmname)
      if vm1 != None:
        vm1.Destroy()

      # Create new VM
      vm1 = vm.CreateQuickDummy(vmname, guest = "winXPProGuest")
      Log("Using VM : " + vm1.GetName())

      extraCfgs = vm1.GetConfig().GetExtraConfig()
      AddExtraConfig(extraCfgs, "replay.allowBTOnly", "TRUE")
      #AddExtraConfig(extraCfgs, "monitor.needreplay", "TRUE")
      cSpec =  Vim.Vm.ConfigSpec()
      cSpec.SetFlags(Vim.vm.FlagInfo(recordReplayEnabled=True))
      cSpec.SetExtraConfig(extraCfgs)
      task = vm1.Reconfigure(cSpec)
      WaitForTask(task)

      try:
         Log("Powering on the VM...")
         vm.PowerOn(vm1)

         Log("Powering off the VM...")
         vm.PowerOff(vm1)

         # StartRecording on a powered-off VM
         Log("Attempt to record a powered-off VM")
         try:
            vm.StartRecording(vm1, "Recording1", "Test recording")
            status = "FAIL"
            return
         except Vim.Fault.InvalidState as e:
            Log("Received InvalidState exception")

         # Power on the VM
         vm.PowerOn(vm1)

         # Start recording
         Log("Starting recording...")
         task = vm1.StartRecording("Recording1", "Test recording")
         WaitForTask(task)
         snapshot = task.GetInfo().GetResult()
         if snapshot == None:
            raise Exception("Got null result from StartRecording!")
         CheckState(vm1, Vim.VirtualMachine.RecordReplayState.recording)

         # Stop recording
         time.sleep(5)
         Log("Stopping recording...")
         vm.StopRecording(vm1)
         CheckState(vm1, Vim.VirtualMachine.RecordReplayState.inactive)

         # Check if the VM's snapshot is replayable
         snapInfo = vm1.GetSnapshot()
         rootSnapshotList = snapInfo.GetRootSnapshotList()
         rootSnapshot = rootSnapshotList[0]
         if rootSnapshot.GetReplaySupported() == False:
            raise Exception("Recorded Snapshot does not support replay!")
         Log("Using recorded snapshot " + rootSnapshot.GetName())

         # Start replay
         Log("Initiating replay...")
         vm.StartReplaying(vm1, rootSnapshot.GetSnapshot())
         CheckState(vm1, Vim.VirtualMachine.RecordReplayState.replaying)
         time.sleep(1)

         # Stop replay
         Log("Stopping replay...")
         vm.StopReplaying(vm1)
         CheckState(vm1, Vim.VirtualMachine.RecordReplayState.inactive)

         # Replay an invalid snapshot
         Log("Creating a dummy snapshot for replay")
         vm.CreateSnapshot(vm1, "dummySnapshot", "Dummy Snapshot", False, False)
         snapInfo = vm1.GetSnapshot()
         curSnap = snapInfo.GetCurrentSnapshot()
         Log("Attempt to replay dummy snapshot...")
         try:
           vm.StartReplaying(vm1, curSnap)
         except Exception as e:
            Log("Verified that attempt to replay invalid snapshot was rejected. ")
         CheckState(vm1, Vim.VirtualMachine.RecordReplayState.inactive)

         Log("Powering off...")
         vm.PowerOff(vm1)

         # PR 773236, recordReplayEnabled=False means StartRecording should be
         # rejected.
         spec = Vim.vm.ConfigSpec(flags=Vim.vm.FlagInfo(recordReplayEnabled=False))
         WaitForTask(vm1.Reconfigure(spec))

         vm.PowerOn(vm1)
         try:
            WaitForTask(vm1.StartRecording("Recording2", "Test recording"))
         except Vim.Fault.RecordReplayDisabled as e:
            Log("Verified that attempt to start recording when disabled was rejected.")
            Log("%s" % e)
         else:
            vm.StopRecording(vm1)
            vm.PowerOff(vm1)
            status = "FAIL"
            Log("StartRecording was allowed")
            return
         vm.PowerOff(vm1)

      except Exception as e:
         stackTrace = " ".join(traceback.format_exception(
                               sys.exc_type, sys.exc_value, sys.exc_traceback))
         Log(stackTrace)
         status = "FAIL"
         return

      try:
         if vm1.GetRuntime().GetPowerState() == Vim.VirtualMachine.PowerState.poweredOn:
            Log("Powering off VM...")
            vm.PowerOff(vm1)
         Log("Deleting VM")
         vm.Destroy(vm1)
      except Exception as e:
         Log("Error deleting VM : " + str(e))
      if status == "FAIL":
         break
      Log("Test status : " + str(status))
      return


# Start program
if __name__ == "__main__":
    main()
    Log("Test status: " + status)
    Log("Record/Replay Tests completed")
