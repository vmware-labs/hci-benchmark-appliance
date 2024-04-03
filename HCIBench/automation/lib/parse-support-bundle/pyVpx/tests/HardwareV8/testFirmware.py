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

testName = "FIRMWARE"

##
## Convenience routine that reconfigures a VM to change its firmware.
##
## @param vm1        [in] VM to invoke operation on
## @param firmware   [in] "efi"/"bios" firmware type.
## @param positive   [in] Whether or not this is positive test case
##
def ChangeFirmware(vm1, firmware, positive):
    cspec = Vim.Vm.ConfigSpec()
    cspec.SetFirmware(firmware)
    try:
        vm.Reconfigure(vm1, cspec)
        time.sleep(5)
    except Exception:
        if not positive:
            Log("Hit an exception changing firmware as expected")
            return
        else:
            raise
    if not positive:
        raise Exception("Did not hit an exception changing firmware")


def mainTestFirmware():
   Log("---[ TEST " + testName + " ]---")

   vmname = "HwV8_Firmware"
   status = "PASS"

   bigClock = StopWatch()
   vm1 = None
   try:
       macosVmName = vmname + "_MacOS"
       Log("Cleaning up VMs from previous runs...")

       vm.Delete(macosVmName, True)

       Log("Creating Mac OS VM..")
       vm1 = vm.CreateQuickDummy(macosVmName, vmxVersion = "vmx-08",
		     memory = 4, guest = "darwin11Guest")

       firmware = "efi"
       ChangeFirmware(vm1, firmware, True)
       if firmware != vm1.config.firmware:
          raise Exception("Firmware don't match set value")

       firmware = "bios"
       ChangeFirmware(vm1, firmware, True)
       if firmware != vm1.config.firmware:
          raise Exception("Firmware don't match set value")

       Log("Deleting VM " + macosVmName)
       vm.Delete(macosVmName, True)

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

