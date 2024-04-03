#!/usr/bin/python
'''
The goal of this test is verify Msg_Post will not cause hostd to disconnect with VMX
and lost track of power on status. PR 998381.
This test purposely adds a bad vmx.log.filename parameter to generate an early Msg_Post from VMX.
To verify fix for PR 998381, please run at least 20 power cycle iterations.

'''
from __future__ import print_function

import sys
from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm
from pyVim import vmconfig
from pyVim import arguments
from pyVim import path
from pyVim.helpers import Log
import atexit
import datetime

## Helper routine to edit extra config entries in a VM
def EditExtraConfig(extraCfg, key, value):
    for item in extraCfg:
        if item.key == key:
            item.SetValue(value)
            return True
    return False

## Helper routine to add extra config entries to a VM.
def AddExtraConfig(extraCfg, key, value):
    extraCfg += [Vim.Option.OptionValue(key=key, value=value)]

##
## Helper routine to verify if a given key, value pair exists in the
## list of extraconfig entries
##
def VerifyInExtraConfig(extraCfg, key, value):
    for item in extraCfg:
        if item.key == key and item.value == value:
            return True
    return False

## Helper routine that edits/add an extraConfig entry to a VM
def SetExtraConfig(vm1, key, value, positive = True):
    success = False
    extraCfg = vm1.config.extraConfig
    if not EditExtraConfig(extraCfg, key, value):
        AddExtraConfig(extraCfg, key, value)

    try:
        cspec = Vim.Vm.ConfigSpec()
        cspec.SetExtraConfig(extraCfg)
        vm.Reconfigure(vm1, cspec)
        Log("Reconfigured VM")
        success = True
    except Exception as e:
        if not positive:
            Log("Expected exception %s in negative test case" % e)
            return
        else:
            raise

    if success and not positive:
        raise Exception("Did not hit exception for negative test case.")

    if not VerifyInExtraConfig(vm1.config.extraConfig, key, value):
        raise Exception("Could not find entry in VM's extraConfig")
    else:
        Log("Validated entry in VM's extraConfig")


def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd"),
                     (["v:", "vmname="], "", "Name of the virtual machine", "vmname"),
                     (["d:", "datastore="], None, "datastore", "datastore"),
                     (["v:", "volume="], None, "VMFS volume", "volume"),
                     (["i:", "iter="], "1", "Num of iterations", "iter")]
   supportedToggles = [(["usage", "help"], False, "Show usage information", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Connect
   si = SmartConnect(host=args.GetKeyValue("host"),
                     user=args.GetKeyValue("user"),
                     pwd=args.GetKeyValue("pwd"),
                     port=443)
   atexit.register(Disconnect, si)

   # Process command line
   # Process command line
   vmname = args.GetKeyValue("vmname")
   numiter = int(args.GetKeyValue("iter"))
   datastore = args.GetKeyValue("datastore")
   volume = args.GetKeyValue("volume")

   # Determine the datastore name
   if datastore and volume:
      Log("Cannot specify both datastore and volume")
      sys.exit(-1)
   elif datastore:
      Log("Using specified datastore: '%s'" % datastore)
   elif volume:
      # Convert absolute volume path to (dsName, relPath) tuple to get dsName
      Log("Trying to determine datastore name for volume: '%s'" % volume)
      try:
         datastore = path.FsPathToTuple(volume)[0]
         Log("Using datastore: '%s'" % datastore)
      except path.FilePathError as e:
         Log("Could not determine datastore name for volume: '%s'" % volume)
         sys.exit(-1)
   else:
      Log("No datastore or volume specified, test will choose one")
      datastore = None

   start = datetime.datetime.now()

   vmcleanup = False
   # Cleanup from previous runs.
   # If defined VM exists, run power cycle test on it.
   # If not, create dummy VM to run test.
   testVMName = "PowerCycleTestVM"
   if vmname:
      # Cleanup from previous runs.
      vm1 = folder.Find(vmname)
      if vm1 == None:
         Log("VM not found, Let's create a dymmy VM to run power-on cycle tests.")
         # Create a simple vm
         try:
            vm1 = vm.CreateQuickDummy(testVMName, 1, datastoreName=datastore)
         except Exception as e:
            Log("Failed to create quick dummy VM %s: %s" % (testVMName, e))
            sys.exit(-1)
         vmcleanup = True
         Log("Dummy VM %s is created." % testVMName)
      else:
         Log("Found VM %s to perform test, verify it is in power off state." % vm1.config.name)
         if (vm1.runtime.powerState != Vim.VirtualMachine.PowerState.poweredOff):
            try:
               WaitForTask(vm1.PowerOff())
            except:
               Log("Problem power off %s VM. exit" % vm1.config.name)
               sys.exit(-1)
   else:
      vm1 = folder.Find(testVMName)
      if vm1 == None:
         # Create a simple vm
         try:
            vm1 = vm.CreateQuickDummy(testVMName, 1, datastoreName=datastore)
         except Exception as e:
            Log("Failed to create quick dummy VM %s: %s" % (testVMName, e))
            sys.exit(-1)
         vmcleanup = True
         Log("Dummy VM %s is created." % testVMName)
      else:
         if (vm1.runtime.powerState != Vim.VirtualMachine.PowerState.poweredOff):
            try:
               WaitForTask(vm1.PowerOff())
            except:
               Log("Problem power off %s VM. exit" % vm1.config.name)
               sys.exit(-1)

   print("This test purposely adds a bad vmx.log.filename parameter to generate an early Msg_Post from VMX.")
   print("The goal of this test is verify Msg_Post will not cause hostd to disconnect with VMX and lost track of power on status.")
   print("To verify fix for PR 998381, please run at least 20 power cycle iterations.")
   # Add extra config key value to set the vmx logging path to a non-existed file.
   # e.g. vmx.log.filename = "testpowercycle-vmware.log"
   # This line will config the vmx log file to "testpowercycle-vmware.log" instead of the default "vmware.log"
   # Msg_Post will not be triggered in this case.
   optionKey = "vmx.log.filename"
   # Let's use log file that is pretty much guaranteed to not exist.
   # e.g. "/vmfs/volumes/badpathname/vmware.log" PR 998381
   # Msg_Post will be triggered in this case.
   optionValue = "/vmfs/volumes/badpathname/vmware.log"
   Log("Add %s = %s to %s VM config before power cycle test." % (optionKey, optionValue, vm1.config.name))
   SetExtraConfig(vm1, optionKey, optionValue)

   teststatus = "PASS"
   Log("Start Power Cycle tests for %s iterations on %s VM." % (numiter, vm1.config.name))

   for i in xrange(numiter) :
      try:

         Log("Power On Cycle %s" % i)
         vm.PowerOn(vm1)

         Log("Power off")
         vm.PowerOff(vm1)

      except Exception as e:
         Log("Caught exception at iter %s: %s" % (i, e))
         teststatus = "FAIL"

   end = datetime.datetime.now()
   print("Power Cycle Test Result: %s" % teststatus)
   duration = end - start
   print("Total time taken: %s" % duration)

   if vmcleanup:
      Log("Delete created dummy test VM %s after test completes." % vm1.config.name)
      vm.Delete(vm1.config.name)

# Start program
if __name__ == "__main__":
    main()
