#!/usr/bin/python

#
# Basic tests for Vim::Vm::PauseManager
#
# These require the latest tools on a VM with a supported guest
#
import os
from pyVmomi import Vim, Vmodl
from pyVim import vm
from pyVim.helpers import Log
from pyVim.task import WaitForTask
from guestOpsUtils import *

#
# Wait for snapshot to enter the lazy phase
#

def waitForLazySnapshot(virtualMachine, snapTask):
   while snapTask.info.progress != 100 and snapTask.info.state not in ['success', 'error']:
      Log(">>> Current snapshot: state='%s', progress='%s'" % (snapTask.info.state, snapTask.info.progress))

      if virtualMachine.GetRuntime().GetSnapshotInBackground() is True:
         Log(">>> Entered lazy phase for snapshot")
         Log("-----------------------------------")
         break
      else:
         Log(">>> Snapshot still in eager phase...")
         Log("-----------------------------------")
      time.sleep(3)
   # check task status
   Log(">>> Current snapshot: state='%s', progress='%s'" % (snapTask.info.state, snapTask.info.progress))

def main():
   # process command line
   options = get_options()

   global svcInst
   global svcInstIntCont
   global virtualMachine
   global guestAdminAuth
   global guestAuth
   global guestAuthBad
   [svcInst, svcInstIntCont, virtualMachine,
    guestAdminAuth, guestAuth, guestAuthBad] = init(options.host, options.user, options.password, options.vmname,
                                    options.vmxpath, options.guestuser, options.guestpassword,
                                    options.guestrootuser, options.guestrootpassword,
                                    powerOn=False, getIntCont=True)

   # get the processManager object
   global procMgr
   procMgr = svcInst.content.guestOperationsManager.processManager
   global procDef
   procDef = Vim.Vm.Guest.ProcessManager

   # get the pauseManager object
   global pauseMgr
   pauseMgr = svcInstIntCont.pauseManager
   global pauseDef
   pauseDef = Vim.Vm.PauseManager

   Log("########################################")
   # power on the VM and pause it right away
   Log("Powering on and pausing VM...")
   WaitForTask(pauseMgr.PowerOnPaused(virtualMachine))

   # verify that the VM is paused
   if virtualMachine.GetRuntime().GetPaused() is True:
      Log("VM is paused successfully")
   else:
      Log("VM failed to pause (if you are connected to VC, this may take time to populate)")

   Log("########################################")
   # verify that "tools" is not running on paused VM
   testNotReady(procMgr, virtualMachine, guestAuth)

   Log("########################################")
   # unpause the VM
   try:
      Log("Unpausing VM...")
      pauseMgr.Unpause(virtualMachine)
   except Exception as e:
      Log("Error unpausing VM: %s" % e)

   # verify that the VM is unpaused
   if virtualMachine.GetRuntime().GetPaused() is False:
      Log("VM is unpaused successfully")
   else:
      Log("VM failed to unpause (if you are connected to VC, this may take time to populate)")

   # re-try to unpause a unpaused VM
   try:
      Log("Unpausing VM again...")
      pauseMgr.Unpause(virtualMachine)
   except Vim.Fault.InvalidState as il:
      Log("Got expected (InvalidState) fault")
      pass
   except Exception as e:
      Log("Error unpausing VM: %s" % e)

   Log("########################################")
   # wait for tools to come up
   waitForTools(virtualMachine)
   Log("Tools are up and running")

   Log("########################################")
   # verify that "tools" is running on unpaused VM
   testNotReady(procMgr, virtualMachine, guestAuth)

   Log("########################################")
   # pause the VM
   try:
      Log("Pausing VM...")
      pauseMgr.Pause(virtualMachine)
   except Exception as e:
      Log("Error pausing VM: %s" % e)

   # verify that the VM is paused
   if virtualMachine.GetRuntime().GetPaused() is True:
      Log("VM is paused successfully")
   else:
      Log("VM failed to pause (if you are connected to VC, this may take time to populate)")

   # re-try to pause a paused VM
   try:
      Log("Pausing VM again...")
      pauseMgr.Pause(virtualMachine)
   except Vim.Fault.InvalidState as il:
      Log("Got expected (InvalidState) fault")
      pass
   except Exception as e:
      Log("Error pausing VM: %s" % e)

   # verify that "tools" is not running on paused VM
   try:
      Log("########################################")
      Log("Trying a guest ops on a paused VM...")
      testNotReady(procMgr, virtualMachine, guestAuth)
   except Vmodl.Fault.SystemError as err:
      Log("Got expected (SystemError) fault")
      if "vix error codes = (3016, 0)" in err.reason:
         Log("Got expected VIX error: VIX_E_TOOLS_NOT_RUNNING (3016)")
         pass
      else:
         Log("Got unexpected VIX error")
         raise err
   except Exception as e:
      Log("Error doing guest ops on paused VM: %s" % e)

   Log("########################################")
   Log("Start creating a snapshot")
   # start creating a snapshot
   snapTask = virtualMachine.CreateSnapshot("test", "test snapshot", memory=True, quiesce=False)

   # wait for snapshot to enter the lazy mode
   Log("Waiting for snapshot to enter lazy phase")
   waitForLazySnapshot(virtualMachine, snapTask)

   Log("########################################")
   # unpause the VM
   try:
      Log("Unpausing VM...")
      pauseMgr.Unpause(virtualMachine)
   except Exception as e:
      Log("Error unpausing VM: %s" % e)

   # verify that the VM is unpaused
   if virtualMachine.GetRuntime().GetPaused() is False:
      Log("VM is unpaused successfully")
   else:
      Log("VM failed to unpause (if you are connected to VC, this may take time to populate)")

   Log("########################################")
   # wait for snapshot to finish
   Log("Waiting for snapshot to complete...")
   WaitForTask(snapTask)

   # check final task status
   Log("Snapshot complete.")
   Log("Final snapshot: state='%s', progress='%s'" % (snapTask.info.state, snapTask.info.progress))
   snapshot = snapTask.info.result
   if virtualMachine.snapshot is None:
      raise Exception("VM has no snapshot exposed")
   if len(virtualMachine.rootSnapshot) < 1:
      raise Exception("VM has no rootSnapshot exposed")
   if snapshot._GetMoId() != virtualMachine.snapshot.currentSnapshot._GetMoId():
      raise Exception("Current snapshot is not correct")

   Log("########################################")
   # remove the test snapshot
   Log("Waiting for snapshot to be removed...")
   WaitForTask(snapshot.Remove(True, True))
   Log("Snapshot removed.")

   Log("########################################")
   # power the VM off
   Log("Powering off VM...")
   powerOffVM(virtualMachine)

   Log("########################################")
   # try to pause/unpause a powered off VM
   try:
      Log("Pausing powered off VM...")
      pauseMgr.Pause(virtualMachine)
   except Vim.Fault.InvalidState as il:
      Log("Got expected (InvalidState) fault")
   except Exception as e:
      Log("Error pausing VM: %s" % e)

   try:
      Log("Unpausing powered off VM...")
      pauseMgr.Unpause(virtualMachine)
   except Vim.Fault.InvalidState as il:
      Log("Got expected (InvalidState) fault")
   except Exception as e:
      Log("Error unpausing VM: %s" % e)
   Log("########################################")


# Start program
if __name__ == "__main__":
   main()
   Log("pauseManager tests completed")
