#!/usr/bin/python

from __future__ import print_function

import sys
import time
import getopt
from pyVmomi import Vim
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm, folder
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import atexit

testName = "MULTICORE"

# Value for cores per socket to test with.
# It will be used to setup number of vCPUs for HotAdd tests
testCoresPerSocket = 2

##
## Convenience routine that reconfigures a VM to change its cores per socket count.
##
## @param vm1        [in] VM to invoke operation on
## @param cpu        [in] New cores per socket count of the VM
## @param positive   [in] Whether or not this is positive test case
##
def ChangeNumCoresPerSocket(vm1, cores, positive):
    cspec = Vim.Vm.ConfigSpec()
    cspec.SetNumCoresPerSocket(cores)
    try:
        vm.Reconfigure(vm1, cspec)
        time.sleep(5)
    except Exception:
        if not positive:
            Log("Hit an exception changing cores per socket count as expected")
            return
        else:
            raise
    if not positive:
        raise Exception("Did not hit an exception changing cores per socket count")


##
## Convenience routine that reconfigures a VM to change its CPU count.
##
## @param vm1        [in] VM to invoke operation on
## @param cpu        [in] New CPU count of the VM
## @param positive   [in] Whether or not this is positive test case
##
def ChangeCpu(vm1, cpu, positive):
    cspec = Vim.Vm.ConfigSpec()
    cspec.SetNumCPUs(cpu)
    try:
        vm.Reconfigure(vm1, cspec)
        time.sleep(5)
    except Exception:
        if not positive:
            Log("Hit an exception changing cpu count as expected")
            return
        else:
            raise
    if not positive:
        raise Exception("Did not hit an exception changing cpu count")


##
## Helper method to setup vms for online tests (i.e enable hotplug)
##
## @param vm1 [in] VM to invoke operation on
## @param positive [in] Whether or not this is positive test case
##
def HelperSetupOnlineTests(vm1):
    Log("Enabling cpu hot plug")
    cspec = Vim.Vm.ConfigSpec()

    # Enabling CPU hot add/remove on the VM
    cspec.SetCpuHotAddEnabled(True)

    # Set number of vCPUs to be equal to coresPerSocket
    # That's a prequisite for hot add to be available on multicore VM
    cspec.SetNumCPUs(testCoresPerSocket)

    vm.Reconfigure(vm1, cspec)
    Log("Powering on the VM")
    vm.PowerOn(vm1)

    # Verify reported CPU hot-plug enabled settings
    Log("Verifying if cpu hot plug enabled is populated")
    cfgInfo = vm1.GetConfig()
    if cfgInfo.GetCpuHotAddEnabled() != True:
        raise Exception("Cpu hot plug enabled not set correctly!")

##
## Test coresPerSocket capability
##
## @param vm1 [in] VM to invoke operation on
## @param positive [in] Whether or not this is positive test case
##
def TestMulticoreCapability(vm1, positive):
    supported = vm1.GetCapability().GetMultipleCoresPerSocketSupported()
    if supported != positive:
        raise Exception("Multicore support don't match expectations." +
                        "Expected: " + str(positive) + ", Have: " + str(supported))

##
## Test changing coresPerSocket (used in both powered on and powered off VMs)
##
## @param vm1 [in] VM to invoke operation on
## @param positive [in] Whether or not this is positive test case
##
def TestSetMulticore(vm1, newCoresPerSocket, positive):
    ChangeNumCoresPerSocket(vm1, newCoresPerSocket, positive)

    if positive:
        coresPerSocket = vm1.config.hardware.numCoresPerSocket
        if coresPerSocket != newCoresPerSocket:
            raise Exception("Cores per socket don't match set value.")

##
## Test changing vCPUs in multicore envirounment (used for HotAdd testing)
##
## @param vm1 [in] VM to invoke operation on
## @param positive [in] Whether or not this is positive test case
##
def TestSetCpus(vm1, correctArguments, expectedToWork):
    coresPerSocket = vm1.config.hardware.numCoresPerSocket

    if coresPerSocket % testCoresPerSocket != 0:
        raise Exception("Expecting coresPerSocket to be left as multiple of testCoresPerSocket from previous cases.")

    curCpu = vm1.config.hardware.numCPU
    if correctArguments:
        newCpu = curCpu + coresPerSocket
    else:
        newCpu = curCpu + coresPerSocket + 1

    ChangeCpu(vm1, newCpu, expectedToWork)

def mainTestMulticore():
   Log("---[ TEST " + testName + " ]---")

   vmname = "HwV8_Multicore"
   status = "PASS"

   bigClock = StopWatch()
   vm1 = None
   try:
       Hw4VmName = vmname + "_Hw4"
       Hw7VmName = vmname + "_Hw7"
       Hw8VmName = vmname + "_Hw8"
       Log("Cleaning up VMs from previous runs...")

       vm.Delete(Hw4VmName, True)
       vm.Delete(Hw7VmName, True)
       vm.Delete(Hw8VmName, True)

       ## Positive tests on a hwVersion 8 VM
       Log("Creating Hw8 VM..")
       Hw8vm = vm.CreateQuickDummy(Hw8VmName, vmxVersion = "vmx-08",
         memory = 4, guest = "windows7Server64Guest")

       Log("Creating Hw7 VM..")
       Hw7vm = vm.CreateQuickDummy(Hw7VmName, 1, vmxVersion = "vmx-07")

       Log("Creating Hw4 VM..")
       Hw4vm = vm.CreateQuickDummy(Hw4VmName, 1, vmxVersion = "vmx-04")

       Log("Tests with Offline VMs")
       Log("  Check capability reported:")
       Log("    Hardware V8")
       TestMulticoreCapability(Hw8vm, True)
       Log("    Hardware V7")
       TestMulticoreCapability(Hw7vm, True)
       Log("    Hardware V4")
       TestMulticoreCapability(Hw4vm, False)

       Log("  Set multicore")
       Log("    Hardware V8")
       TestSetMulticore(Hw8vm, testCoresPerSocket, True)
       Log("    Hardware V7")
       TestSetMulticore(Hw7vm, testCoresPerSocket, True)
       Log("    Hardware V4")
       TestSetMulticore(Hw4vm, testCoresPerSocket, False)

       Log("Tests with Online VMs")
       HelperSetupOnlineTests(Hw8vm)  # Setup for hot add
       TestSetMulticore(Hw8vm, testCoresPerSocket * 2, False)

       HelperSetupOnlineTests(Hw7vm)  # Setup for hot add
       TestSetMulticore(Hw7vm, testCoresPerSocket * 2, False)

       Log("  Hot add CPU")
       Log("    Hardware V8 Positive")
       TestSetCpus(Hw8vm, True, True)
       Log("    Hardware V8 Negative")
       TestSetCpus(Hw8vm, False, False)
       Log("    Hardware V7 Negative")
       TestSetCpus(Hw7vm, True, False)

       Log("Powering off and deleting VMs")
       vm.Delete(Hw8vm, True)
       vm.Delete(Hw7vm, True)
       vm.Delete(Hw4vm, True)

       bigClock.finish(testName)
   except Exception as e:
       status = "FAIL"
       Log("Caught exception : " + str(e))

   Log("TEST [" + testName + "] COMPLETE: " + status)
   return status

# Start program
if __name__ == "__main__":
    print("This test module is part of Hardware V8 tests.")
    print("Run it from the main script.")
