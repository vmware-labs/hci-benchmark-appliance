#!/usr/bin/python

import atexit
import sys

from pyVim import arguments
from pyVim import vm
from pyVim import vmconfig
from pyVim.connect import SmartConnect, Disconnect
from pyVim.helpers import Log
from pyVim.task import WaitForTask
from pyVmomi import vim

WATCHDOGTIMER_DEV_KEY = 18000

def CreateVWDT(key, runOnBoot=None):
    wdt = vim.vm.device.VirtualWDT()
    wdt.key = key
    if runOnBoot != None:
        wdt.runOnBoot = runOnBoot
    return wdt

def CreateVD(key):
    vd = vim.vm.device.VirtualDevice()
    vd.key = key
    return vd

def AddVWDT(cspec, key=None, runOnBoot=None):
    if key is None:
        key = vmconfig.GetFreeKey(cspec)
    wdt = CreateVWDT(key, runOnBoot)
    vmconfig.AddDeviceToSpec(cspec, wdt,
                             vim.vm.device.VirtualDeviceSpec.Operation.add)

def CheckWDTNotPresent(vm1):
    """
    Confirm that watchdog timer is not present in a VM.
    """
    wdts = vmconfig.CheckDevice(vm1.config, vim.vm.device.VirtualWDT)
    if len(wdts) != 0:
        raise Exception("Watchdog timer found in a VM: " + str(wdts))

def CheckWDTPresent(vm1):
    """
    Validate watchdog timer presence.
    """
    wdts = vmconfig.CheckDevice(vm1.config, vim.vm.device.VirtualWDT)
    if len(wdts) != 1:
        raise Exception("Invalid watchdog timer configuration: " + str(wdts))
    wdt = wdts[0]
    if wdt.key != WATCHDOGTIMER_DEV_KEY:
        raise Exception("Watchdog timer has unexpected key: " + wdt.key)

def TestAdd2ndWDTKey(vm1, key):
    """
    Test add 2nd vWDT
    """
    Log("Adding 2nd vWDT using key=%s" % key)
    cspec = vim.vm.ConfigSpec()
    AddVWDT(cspec, key)
    try:
        vm.Reconfigure(vm1, cspec)
        raise Exception("Addition of 2nd vWDT did not fail with %s" % cspec)
    except vim.fault.TooManyDevices as e:
        pass
    CheckWDTPresent(vm1)

def TestAdd2ndWDT(vm1):
    """
    Test add 2nd vWDT
    """
    TestAdd2ndWDTKey(vm1, None)
    TestAdd2ndWDTKey(vm1, 100)
    TestAdd2ndWDTKey(vm1, WATCHDOGTIMER_DEV_KEY)
    TestAdd2ndWDTKey(vm1, -1)
    TestAdd2ndWDTKey(vm1, 1999999999)
    TestAdd2ndWDTKey(vm1, -1999999999)

def TestVWDTHotAdd(vm1):
    Log("Trying to hot-add vWDT")
    cspec = vim.vm.ConfigSpec()
    AddVWDT(cspec)
    try:
        vm.Reconfigure(vm1, cspec)
        raise Exception("Watchdog timer hot-add did not raise exception")
    except vim.fault.InvalidPowerState as e:
        pass
    CheckWDTNotPresent(vm1)

def TestVWDTRemoveDev(vm1, dev):
    cspec = vim.vm.ConfigSpec()
    vmconfig.AddDeviceToSpec(cspec, dev,
                             vim.vm.device.VirtualDeviceSpec.Operation.remove)
    vm.Reconfigure(vm1, cspec)
    CheckWDTNotPresent(vm1)

def TestNoVWDTRemoveDev(vm1, dev, fault=vim.fault.InvalidDeviceSpec):
    cspec = vim.vm.ConfigSpec()
    vmconfig.AddDeviceToSpec(cspec, dev,
                             vim.vm.device.VirtualDeviceSpec.Operation.remove)
    try:
        vm.Reconfigure(vm1, cspec)
        raise Exception("Reconfigure for vWDT %s did not raise exception" %
                        cspec)
    except fault as e:
        pass

def TestNoVWDTRemoveKey(vm1, key):
    Log("Trying to remove vWDT with key %s" % key)
    TestNoVWDTRemoveDev(vm1, CreateVWDT(key))

def TestNoVWDTRemoveVDKey(vm1, key):
    Log("Trying to remove virtual device with key %s" % key)
    TestNoVWDTRemoveDev(vm1, CreateVD(key))

def TestVWDTRemoveInvalid(vm1):
    TestNoVWDTRemoveKey(vm1, 18001)
    TestNoVWDTRemoveKey(vm1, -1)
    TestNoVWDTRemoveKey(vm1, 0)
    TestNoVWDTRemoveKey(vm1, 100)
    TestNoVWDTRemoveKey(vm1, 1000)
    TestNoVWDTRemoveVDKey(vm1, 18001)
    TestNoVWDTRemoveVDKey(vm1, -1)

def TestNoVWDTRemove(vm1):
    TestNoVWDTRemoveKey(vm1, 18000)
    TestNoVWDTRemoveVDKey(vm1, 18000)
    TestVWDTRemoveInvalid(vm1)
    CheckWDTNotPresent(vm1)

def TestVWDTReplaceKey(vm1, key):
    Log("Replacing vWDT with new key=%s" % key)
    cspec = vim.vm.ConfigSpec()
    vmconfig.AddDeviceToSpec(cspec, CreateVWDT(WATCHDOGTIMER_DEV_KEY),
                             vim.vm.device.VirtualDeviceSpec.Operation.remove)
    vmconfig.AddDeviceToSpec(cspec, CreateVWDT(key),
                             vim.vm.device.VirtualDeviceSpec.Operation.add)
    vm.Reconfigure(vm1, cspec)
    CheckWDTPresent(vm1)

def TestVWDTHotRemove(vm1):
    Log("Trying to hot-remove vWDT")
    TestNoVWDTRemoveDev(vm1,
                        CreateVWDT(WATCHDOGTIMER_DEV_KEY),
                        vim.fault.InvalidPowerState)
    CheckWDTPresent(vm1)

    Log("Trying to hot-remove virtual device with vWDT key")
    TestNoVWDTRemoveDev(vm1, CreateVD(WATCHDOGTIMER_DEV_KEY),
                        vim.fault.InvalidPowerState)
    CheckWDTPresent(vm1)

def TestNoVWDTRunning(vm1):
    TestVWDTHotAdd(vm1)
    TestNoVWDTRemove(vm1)

def TestNoVWDT(vm1):
    """
    Test that hot-add of vWDT fails
    """
    CheckWDTNotPresent(vm1)
    TestNoVWDTRemove(vm1)
    vm.PowerOn(vm1)
    try:
        TestNoVWDTRunning(vm1)
    finally:
        vm.PowerOff(vm1)

def TestVWDTReconfig(vm1):
    """
    Test add and remove for vWDT controller
    """
    Log("Adding vWDT")
    cspec = vim.vm.ConfigSpec()
    AddVWDT(cspec)
    vm.Reconfigure(vm1, cspec)
    CheckWDTPresent(vm1)
    TestAdd2ndWDT(vm1)
    TestVWDTRemoveInvalid(vm1)
    CheckWDTPresent(vm1)
    TestVWDTReplaceKey(vm1, -1)
    TestVWDTReplaceKey(vm1, WATCHDOGTIMER_DEV_KEY)
    TestVWDTReplaceKey(vm1, 100)

    vm.PowerOn(vm1)
    try:
        TestVWDTRemoveInvalid(vm1)
        TestVWDTHotRemove(vm1)
    finally:
        vm.PowerOff(vm1)
    # Remove vWDT controller from VM
    Log("Removing watchdog timer from VM")
    TestVWDTRemoveDev(vm1, CreateVWDT(WATCHDOGTIMER_DEV_KEY))

def TestVWDTRunning(vm1, running):
    """
    Test running field for vWDT controller
    """
    Log("Adding vWDT, runOnBoot=%u" % running)
    cspec = vim.vm.ConfigSpec()
    AddVWDT(cspec, key=WATCHDOGTIMER_DEV_KEY, runOnBoot=running)
    vm.Reconfigure(vm1, cspec)
    CheckWDTPresent(vm1)

    vm.PowerOn(vm1)
    try:
        wdts = vmconfig.CheckDevice(vm1.config, vim.vm.device.VirtualWDT)
        if len(wdts) != 1:
            raise Exception("Invalid vWDT configuration: " + str(wdts))
        wdt = wdts[0]
        if wdt.running != running:
            raise Exception("Watchdog timer running=%u" % wdt.running)
    finally:
        vm.PowerOff(vm1)
    # Remove vWDT controller from VM
    Log("Removing watchdog timer from VM")
    TestVWDTRemoveDev(vm1, CreateVWDT(WATCHDOGTIMER_DEV_KEY))

def TestVWDTRunOnBoot(vm1, runOnBoot):
    """
    Test runOnBoot field for vWDT controller
    """
    Log("Adding vWDT, runOnBoot=%u" % runOnBoot)
    cspec = vim.vm.ConfigSpec()
    AddVWDT(cspec, key=WATCHDOGTIMER_DEV_KEY, runOnBoot=runOnBoot)
    vm.Reconfigure(vm1, cspec)
    CheckWDTPresent(vm1)

    vm.PowerOn(vm1)
    try:
        wdts = vmconfig.CheckDevice(vm1.config, vim.vm.device.VirtualWDT)
        if len(wdts) != 1:
            raise Exception("Invalid vWDT configuration: " + str(wdts))
        wdt = wdts[0]
        if wdt.runOnBoot != runOnBoot:
            raise Exception("Watchdog timer runOnBoot=%u" % wdt.runOnBoot)
    finally:
        vm.PowerOff(vm1)
    # Remove vWDT controller from VM
    Log("Removing watchdog timer from VM")
    TestVWDTRemoveDev(vm1, CreateVWDT(WATCHDOGTIMER_DEV_KEY))

def TestVWDTRunOnBootAndRunning(vm1):
    """
    Test runOnBoot and running fields for vWDT controller
    """
    Log("Testing vWDT device running field")
    TestVWDTRunning(vm1, False)
    TestVWDTRunning(vm1, True)

    Log("Testing vWDT device runOnBoot field")
    TestVWDTRunOnBoot(vm1, False)
    TestVWDTRunOnBoot(vm1, True)

def TestVWDTVDRemove(vm1):
    """
    Test vWDT removal via key
    """
    Log("Adding vWDT with positive key")
    cspec = vim.vm.ConfigSpec()
    AddVWDT(cspec, key=WATCHDOGTIMER_DEV_KEY)
    vm.Reconfigure(vm1, cspec)
    CheckWDTPresent(vm1)

    Log("Removing vWDT device from VM using virtual device with vWDT key")
    TestVWDTRemoveDev(vm1, CreateVD(WATCHDOGTIMER_DEV_KEY))

def main():
    supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                      (["u:", "user="], "root", "User name", "user"),
                      (["p:", "pwd="], "", "Password", "pwd"),
                      (["v:", "vmname="], "VWDTTest",
                       "Name of the virtual machine", "vmname") ]

    supportedToggles = [ (["usage", "help"], False,
                           "Show usage information", "usage"),
                         (["runall", "r"], True, "Run all the tests", "runall"),
                         (["nodelete"], False,
                           "Dont delete vm on completion", "nodelete") ]

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

        ## vWDT requires hardware version 17.
        Log("Creating Hw17 VM...")
        cfg = vm.CreateQuickDummySpec(vmname, vmxVersion = "vmx-17",
                                      memory = 4, guest = "otherGuest")
        AddVWDT(cfg)
        vm1 = vm.CreateFromSpec(cfg)
        task = vm1.Destroy()
        WaitForTask(task)
        vm1 = None

        vm1 = vm.CreateQuickDummy(vmname, vmxVersion = "vmx-17",
                                  memory = 4, guest = "otherGuest")

        TestVWDTReconfig(vm1)
        TestNoVWDT(vm1)
        TestVWDTVDRemove(vm1)

        TestVWDTRunOnBootAndRunning(vm1)

        Log("Tests completed.")

    except Exception as e:
        status = "FAIL"
        Log("Caught exception : %s, %r" % (e, e))
        raise
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

