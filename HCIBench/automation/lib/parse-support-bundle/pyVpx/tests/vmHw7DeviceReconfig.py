#!/usr/bin/python

import sys
import getopt
from pyVmomi import Vim
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm, folder
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import atexit

## Cleanup existing VMs with given name
def CleanupVm(vmname):
    vm1 = folder.Find(vmname)
    if vm1 != None:
        Log("Cleaning up VM " + vmname)
        vm.Destroy(vm1)


## Test for existence and then removal of specified device
def TestDeviceRemove(vm1, devType, devLabel):
     devices = vmconfig.CheckDevice(vm1.GetConfig(), devType)
     if len(devices) != 1:
         raise Exception("Failed to find " + devLabel + " device.")
     cspec = Vim.Vm.ConfigSpec()
     cspec = vmconfig.RemoveDeviceFromSpec(cspec, devices[0])
     task = vm1.Reconfigure(cspec)
     WaitForTask(task)
     devices = vmconfig.CheckDevice(vm1.GetConfig(), devType)
     if len(devices) != 0:
         raise Exception("Found " + devLabel + " device even after delete.")


## Test for adding and removing a Vmxnet3 device
def TestAddRemoveVmxet3Device(vm1, positiveTest = True):
     Log("Testing add and remove of Vmxnet3 device...")
     cspec = Vim.Vm.ConfigSpec()
     cspec = vmconfig.AddNic(cspec, nicType = "vmxnet3")
     try:
         task = vm1.Reconfigure(cspec)
         WaitForTask(task)
     except Vim.Fault.DeviceUnsupportedForVmVersion as e:
         if not positiveTest:
             Log("Hit version exception adding Vmxnet3 device as expected.")
             return
         raise
     if not positiveTest:
         raise Exception("Did not hit excpetion as expected!")
     TestDeviceRemove(vm1, Vim.Vm.Device.VirtualVmxnet3, "Vmxnet3")
     Log ("Basic Vmxnet3 device tests passed.")


## Test for adding and removing an LsiLogic SAS controller
def TestAddRemoveLsiLogicSasDevice(vm1, positiveTest = True):
     Log("Testing add and remove of LsiSAS controller...")
     cspec = Vim.Vm.ConfigSpec()
     cspec = vmconfig.AddScsiCtlr(cspec, ctlrType = "lsisas")
     try:
         task = vm1.Reconfigure(cspec)
         WaitForTask(task)
     except Vim.Fault.DeviceUnsupportedForVmVersion as e:
         if not positiveTest:
             Log("Hit a version exception adding LsiLogicSAS device as expected.")
             return
         raise
     if not positiveTest:
         raise Exception("Did not hit excpetion as expected!")
     TestDeviceRemove(vm1, Vim.Vm.Device.VirtualLsiLogicSASController, "LsiLogicSAS")
     Log ("Basic LsiLogicSAS device tests passed.")


## Test toggling of VAsserts capability
def TestVAssertToggle(vm1, toggle):
    Log("Testing Vassert toggle to : " + str(toggle))
    cspec = Vim.Vm.ConfigSpec()
    cspec.SetVAssertsEnabled(toggle)
    task = vm1.Reconfigure(cspec)
    WaitForTask(task)
    if vm1.GetConfig().GetVAssertsEnabled() != toggle:
      raise Exception("Toggling Vasserts to " + str(toggle) + " failed!")
    Log ("Vasserts enable/disable tests passed.")


## Convenience routine to check status of VMCI device
def CheckVMCIDeviceStatus(vm1, toggle):
    devices = vmconfig.CheckDevice(vm1.GetConfig(),
                                   Vim.Vm.Device.VirtualVMCIDevice,
                                   {"allowUnrestrictedCommunication": toggle})
    if len(devices) < 1:
        raise Exception("Failed to find VMCI device with unrestricted set to " + str(toggle))
    elif len(devices) > 1:
        raise Exception("More than one VMCI device found.")
    return devices[0]

## Positive tests for VMCI device
def TestPosVMCIDevice(vm1):
    Log("Testing if VMCI device is present by default in the VM")
    dev = CheckVMCIDeviceStatus(vm1, False)

    Log("Toggling unrestricted communication for VMCI...")
    cspec = Vim.Vm.ConfigSpec()
    dev.SetAllowUnrestrictedCommunication(True)
    vmconfig.AddDeviceToSpec(cspec, dev,
                             Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
    task = vm1.Reconfigure(cspec)
    WaitForTask(task)
    CheckVMCIDeviceStatus(vm1, True)
    Log("Verified communication settings for VMCI")


## Negative tests for VMCI device
def TestNegVMCIDevice(vm1, isVMCIDefault):
    if not isVMCIDefault:
        devices = vmconfig.CheckDevice(vm1.GetConfig(),
                                       Vim.Vm.Device.VirtualVMCIDevice)
        if len(devices) != 0:
            raise Exception("VMCI device found by default in VM")
        return
    failure = False
    Log("Adding new VMCI device to a VM")
    try:
        cspec = Vim.Vm.ConfigSpec()
        cpsec = vmconfig.AddVMCI(cspec)
        task = vm1.Reconfigure(cspec)
        WaitForTask(task)
    except Exception as e:
        Log("Verified request was rejected as expected.")
        failure = True
    if not failure:
        raise Exception("Adding VMCI device to VM was allowed!")

    Log("Attempt to remove VMCI device from VM")
    devices = vmconfig.CheckDevice(vm1.GetConfig(),
                                   Vim.Vm.Device.VirtualVMCIDevice)
    cspec = Vim.Vm.ConfigSpec()
    cpsec = vmconfig.RemoveDeviceFromSpec(cspec, devices[0])
    try:
        task = vm1.Reconfigure(cspec)
        WaitForTask(task)
    except Exception as e:
        Log("Verified request was rejected as expected.")
        return
    raise Exception("Did not hit an exception as expected")


## Convenience routine for checking 3D support of VideoCard
def CheckVideoCard3DSupport(vm1, toggle):
    devices = vmconfig.CheckDevice(vm1.GetConfig(),
                                   Vim.Vm.Device.VirtualVideoCard,
                                   {"enable3DSupport": toggle})
    if len(devices) != 1:
        raise Exception ("Video card with 3D support set to " +
                         str(toggle) + " not found!")
    return devices[0]


## Test 3d support for Video card
def TestVideoCard3D(vm1):
    dev = CheckVideoCard3DSupport(vm1, False)
    supports3D = False
    cspec = Vim.Vm.ConfigSpec()
    dev.SetEnable3DSupport(True)
    vmconfig.AddDeviceToSpec(cspec, dev,
                             Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
    task = vm1.Reconfigure(cspec)
    WaitForTask(task)
    CheckVideoCard3DSupport(vm1, True)
    Log("Verified toggling 3d support for video card")


## Convenience routine to test a negative operation on a VM
def TestNegOpOnVm(opLabel, func, *args,  **kw):
    try:
        func(*args, **kw)
    except Exception as e:
        Log("Hit exception " + opLabel + " as expected")
        return
    raise Exception("Did not hit exception " + opLabel)


## Test PCI passthrough device support
def TestPCIPassthroughDevice(vm1, positive):
    failed = False
    # Test adding PCI passthrough device to VM
    Log("Adding PCI passthrough device to VM")
    cspec = Vim.Vm.ConfigSpec()
    curMem = vm1.GetConfig().GetHardware().GetMemoryMB()
    memAlloc = Vim.ResourceAllocationInfo()
    memAlloc.SetReservation(long(curMem))
    memAlloc.SetLimit(long(curMem))
    cspec = vmconfig.AddPCIPassthrough(cspec)
    try:
        task = vm.Reconfigure(vm1, cspec)
    except Vim.Fault.DeviceUnsupportedForVmVersion as e:
        if not positive:
            Log("Caught version exception adding PCI Passthrough device as expected")
            return
        raise
    if not positive:
        raise Exception("Did not hit exception adding PCI Passthrough device")
    Log("Checking for presencec of PCI Passthrough device in VM")
    devices = vmconfig.CheckDevice(vm1.GetConfig(),
                                   Vim.Vm.Device.VirtualPCIPassthrough)
    if len(devices) != 1:
        raise Exception("VM has " + str(len(devices)) + \
                        "PCI passthrough devices. Expected 1.")

    # Power on VM
    Log("Powering on the VM")
    vm.PowerOn(vm1)

    # Suspend VM with PCI passthru
    Log("Attempting to suspend the VM")
    TestNegOpOnVm("suspending VM", vm.Suspend, vm1)

    # Hot-add a device to VM with PCI passthru
    Log("Attempting to hot add a NIC to the VM")
    cspec = Vim.Vm.ConfigSpec()
    vmconfig.AddNic(cspec)
    TestNegOpOnVm("hot-adding a nic to the VM", vm.Reconfigure, vm1, cspec)

    # Change memory reservataion of VM with PCI passthru
    Log("Attempting to change memory reservation of the VM")
    curMem = vm1.GetConfig().GetHardware().GetMemoryMB()
    cspec = Vim.Vm.ConfigSpec()
    memAlloc = Vim.ResourceAllocationInfo()
    memAlloc.SetReservation(long(curMem - 1))
    cspec.SetMemoryAllocation(memAlloc)
    TestNegOpOnVm("changing mem reservataion of VM", vm.Reconfigure, vm1, cspec)

    Log("Powering off VM")
    vm.PowerOff(vm1)

    # Remove PCI passthru device.
    Log("Removing PCI Passthrough device from VM")
    cspec = Vim.Vm.ConfigSpec()
    cspec = vmconfig.RemoveDeviceFromSpec(cspec, devices[0])
    vm.Reconfigure(vm1, cspec)

    Log("Checking that device was removed")
    devices = vmconfig.CheckDevice(vm1.GetConfig(),
                                   Vim.Vm.Device.VirtualPCIPassthrough)
    if len(devices) != 0:
        raise Exception("PCI passthrough device not removed from VM!")
    Log("Done with PCI passthrough tests")


def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "vmname="], "Hw7ReconfigTest", "Name of the virtual machine", "vmname"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage"),
                        (["runall", "r"], True, "Run all the tests", "runall"),
                        (["nodelete"], False, "Dont delete vm on completion", "nodelete") ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Connect
   si = Connect(host=args.GetKeyValue("host"),
                user=args.GetKeyValue("user"),
                pwd=args.GetKeyValue("pwd"),
                version="vim.version.version9")
   atexit.register(Disconnect, si)

   # Process command line
   vmname = args.GetKeyValue("vmname")
   numiter = int(args.GetKeyValue("iter"))
   runall = args.GetKeyValue("runall")
   noDelete = args.GetKeyValue("nodelete")
   status = "PASS"

   for i in range(numiter):
       bigClock = StopWatch()
       vm1 = None
       try:
           ## Cleanup old VMs
           posVmName = vmname + "_Pos_" + str(i)
           negVmName = vmname + "_Neg_" + str(i)
           CleanupVm(posVmName)
           CleanupVm(negVmName)

           ## Positive tests on a hwVersion 7 VM
           Log("Creating Hw7 VM..")
           vm1 = vm.CreateQuickDummy(posVmName, 0, 1,
                                     vmxVersion = "vmx-07")

           # Test add & removal Vmxnet3 device to VM
           TestAddRemoveVmxet3Device(vm1)
           # Test add & removal of LsiLogicSAS controller to VM
           TestAddRemoveLsiLogicSasDevice(vm1)
           # Test enabling VAsserts in the VM.
           TestVAssertToggle(vm1, True)
           TestVAssertToggle(vm1, False)
           # Test VMCI device
           TestPosVMCIDevice(vm1)
           TestNegVMCIDevice(vm1, True)
           # Test PCI passthrough device
           TestPCIPassthroughDevice(vm1, True)

           ## Negative tests on a hwVersion 4 VM
           Log("Creating Hw4 VM..")
           vm2 = vm.CreateQuickDummy(vmname + "_Neg_" + str(i), 1)
           # Test add & removal Vmxnet3 device to VM
           TestAddRemoveVmxet3Device(vm2, False)
           # Test add & removal of LsiLogicSAS controller to VM
           TestAddRemoveLsiLogicSasDevice(vm2, False)
           # Test if VMCI device is present by default
           TestNegVMCIDevice(vm2, False)
           # Test adds of PCI passthrough device are disallowed
           TestPCIPassthroughDevice(vm2, False)
           Log("Destroying VMs")
           vm.Destroy(vm1)
           vm.Destroy(vm2)
           Log("Tests completed.")
           bigClock.finish("iteration " + str(i))
       except Exception as e:
           status = "FAIL"
           Log("Caught exception : " + str(e))

   Log("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()
