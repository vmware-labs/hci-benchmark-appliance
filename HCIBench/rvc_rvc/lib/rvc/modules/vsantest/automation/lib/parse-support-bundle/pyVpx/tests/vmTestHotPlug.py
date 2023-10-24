#!/usr/bin/python

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

testFailedCount = 0

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
        time.sleep(1)
    except Exception as e:
        if not positive:
            Log("Hit an exception changing cpu count as expected")
            return
        else:
            raise
    if not positive:
        raise Exception("Did not hit an exception changing cpu count")


##
## Convenience routine that reconfigures a VM to change its memory size.
##
## @param vm1        [in] VM to invoke operation on
## @param memory     [in] New memory size of the VM
## @param positive   [in] Whether or not this is positive test case
##
def ChangeMemory(vm1, memory, positive):
    cspec = Vim.Vm.ConfigSpec()
    cspec.SetMemoryMB(long(memory))
    try:
        vm.Reconfigure(vm1, cspec)
    except Exception as e:
        if not positive:
            Log("Hit an exception changing memory as expected")
            return
        else:
            raise
    if not positive:
        raise Exception("Did not hit an exception changing memory")


##
## Test hot add of memory
##
## @param vm1        [in] VM to invoke operation on
## @param positive   [in] Whether or not this is positive test case
##
def TestHotPlugMemory(vm1, positive):
    Log("Testing memory hot add for VM " + vm1.GetConfig().GetName())
    curMB = vm1.GetConfig().GetHardware().GetMemoryMB()
    newMB = curMB + 30
    Log("Current memory: " + str(curMB) + " MB.")

    # Negative test case - changes memory when not allowed
    Log("Attempting to hot-add memory without setting enabled flag")
    ChangeMemory(vm1,newMB, False)

    # Enable memory hot add on VM
    Log("Powering off VM")
    vm.PowerOff(vm1)
    Log("Enabling memory hot add")
    cspec = Vim.Vm.ConfigSpec()
    cspec.SetMemoryHotAddEnabled(True)
    vm.Reconfigure(vm1, cspec)
    Log("Powering on the VM")
    vm.PowerOn(vm1)

    # Verify if memory values are reported correctly for the VM
    if positive:
        Log("Verifying if maxMemory and increment size are populated")
        cfgInfo = vm1.GetConfig()
        curMB = cfgInfo.GetHardware().GetMemoryMB()
        memGrow = cfgInfo.GetHotPlugMemoryIncrementSize()
        memLimit = cfgInfo.GetHotPlugMemoryLimit()
        memEnabled = cfgInfo.GetMemoryHotAddEnabled()
        Log("Memory enabled: " + str(memEnabled) + " Memory limit: " +
            str(memLimit) + " Memory grow step: " + str(memGrow))
        if not memEnabled or memLimit == None or memGrow == None:
            raise Exception("Memory values not being populated correctly.")
        newMB = curMB + memGrow

    # Test memory hot add
    Log("Testing hot add of memory")
    ChangeMemory(vm1, newMB, positive)
    if not positive:
        return
    curMB = vm1.GetConfig().GetHardware().GetMemoryMB()
    if curMB != newMB:
        raise Exception("Memory after hot-add: " + str(curMB) + " MB.")

    # Test some negative test cases
    Log("Testing invalid grow step")
    ChangeMemory(vm1, newMB + memGrow + 1, False)
    Log("Testing add of memory beyond published maximum")
    ChangeMemory(vm1, memLimit + 1, False)


##
## Test hot add and hot remove of virtual CPUs
##
## @param vm1        [in] VM to invoke operation on
## @param add        [in] Whether this is an add or a remove operation
## @param positive   [in] Whether or not this is positive test case
## @param opLabel    [in] Label for the operation type.
##
def TestHotPlugCpu(vm1, add, positive, opLabel):
    Log("Testing CPU hot " + opLabel + " for VM " + vm1.GetConfig().GetName())
    curCpu = vm1.GetConfig().GetHardware().GetNumCPU()
    newCpu = curCpu
    if add:
        newCpu += 1
    else:
        newCpu -= 1

    # Check for a valid CPU count
    if newCpu == 0:
        raise Exception("Cpu count cannot be zero")
    Log("Current cpu count : " + str(curCpu))

    # Making sure that hot plug cpu is not enabled
    Log("Powering off VM")
    vm.PowerOff(vm1)
    cspec = Vim.Vm.ConfigSpec()
    if add:
       cspec.SetCpuHotAddEnabled(False)
    else:
       cspec.SetCpuHotRemoveEnabled(False)
    vm.Reconfigure(vm1, cspec)
    Log("Powering on the VM")
    vm.PowerOn(vm1)

    # Negative test case - changing CPU count when not allowed
    Log("Attempting to change CPUs without setting enabled flag")
    ChangeCpu(vm1, newCpu, False)

    # Enabling CPU hot add/remove on the VM
    Log("Powering off VM")
    vm.PowerOff(vm1)
    Log("Enabling cpu hot plug")
    cspec = Vim.Vm.ConfigSpec()
    if add:
        cspec.SetCpuHotAddEnabled(True)
    else:
        cspec.SetCpuHotRemoveEnabled(True)
    vm.Reconfigure(vm1, cspec)
    Log("Powering on the VM")
    vm.PowerOn(vm1)

    # Verify reported CPU hot-plug enabled settings
    Log("Verifying if cpu hot plug enabled is populated")
    cfgInfo = vm1.GetConfig()
    if add and cfgInfo.GetCpuHotAddEnabled() != True or \
    (not add and cfgInfo.GetCpuHotRemoveEnabled() != True) :
        raise Exception("Cpu hot plug enabled not set correctly!")

    # Test CPU hot-plug
    ChangeCpu(vm1, newCpu, positive)
    if not positive:
        return
    curCpu = vm1.GetConfig().GetHardware().GetNumCPU()
    if curCpu != newCpu:
        raise Exception("Cpu count " + str(curCpu) + " not equal to " +
                        str(newCpu))


##
## Test hot add and hot remove for any virtual device.
##
## @param vm1        [in] VM to invoke operation on
## @param func       [in] Function that adds the device to the ConfigSpec
## @param label      [in] Label for the device
## @param devType    [in] Device type to check for in the VM's config
## @param positive   [in] Whether or not this is positive test case
## @param testRemove [in] Whether or not to test hotRemove
## @param leaveInVm  [in] Whether the device should be left behind in the VM
## @param fileOp     [in] File operation for the hot remove request
##
def TestHotPlugDevice(vm1, func, label, devType, positive,
                      testRemove = True, leaveInVm = False, fileOp = None,):
    Log("Testing " + label + " hot plug for VM " + vm1.GetConfig().GetName())
    failed = False
    Log("Add a new " + label + " to the VM")
    cspec = Vim.Vm.ConfigSpec()
    cspec = func(cspec, cfgInfo = vm1.GetConfig())
    devicesBefore = vmconfig.CheckDevice(vm1.GetConfig(), devType)

    # Hot-add the device
    try:
        vm.Reconfigure(vm1, cspec)
    except Exception as e:
        failed = True
        if not positive:
            Log("Caught exception as expected")
            return
        else:
            raise
    if not positive and not failed:
        raise Exception("Did not hit an exception as expected")

    # Check for device presence in VM's config
    devicesAfter = vmconfig.CheckDevice(vm1.GetConfig(), devType)
    if len(devicesAfter) == len(devicesBefore):
        raise Exception("Failed to find added " + label)

    if not testRemove:
        return

    # Hot-remove the device
    newDev = devicesAfter[len(devicesAfter) - 1]
    Log("Removing " + label + " from the VM")
    cspec = Vim.Vm.ConfigSpec()
    vmconfig.RemoveDeviceFromSpec(cspec, newDev, fileOp)
    vm.Reconfigure(vm1, cspec)
    devicesAfter = vmconfig.CheckDevice(vm1.GetConfig(), devType)

    # Check for device absence in the VM's config
    if len(devicesAfter) != len(devicesBefore):
        raise Exception(label + " still found in the VM")

    # Add device back into the VM if necessary
    if leaveInVm:
        cspec = Vim.Vm.ConfigSpec()
        cspec = func(cspec)
        vm.Reconfigure(vm1, cspec)


##
## Invoke all hot plug tests for positive and negative test cases
##
## @param vm1 [in] VM to invoke operation on
## @param positive [in] Whether or not this is positive test case
##
def TestDeviceHotPlugForVm(vm1, positive):
    global testFailedCount
    try:
        TestHotPlugMemory(vm1, positive)
    except Exception as e:
        testFailedCount += 1
        Log("Hot Plug Memory test - FAIL : " + str(e))

    try:
        TestHotPlugCpu(vm1, True, positive, "add")
    except Exception as e:
        testFailedCount += 1
        Log("Hot Plug CPU addition - FAIL : " + str(e))

    if positive:
        try:
            TestHotPlugCpu(vm1, False, positive, "remove")
        except Exception as e:
            testFailedCount += 1
            Log("Hot Plug CPU removal - FAIL : " + str(e))

    try:
        TestHotPlugDevice(vm1, vmconfig.AddScsiCtlr, "SCSI controller",
                          Vim.Vm.Device.VirtualSCSIController, positive, False, True)
    except Exception as e:
        testFailedCount += 1
        Log("Hot Plug SCSI Controller test - FAIL : " + str(e))

    try:
        TestHotPlugDevice(vm1, vmconfig.AddDisk, "SCSI disk",
                          Vim.Vm.Device.VirtualDisk, True,
                          fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy)
    except Exception as e:
        testFailedCount += 1
        Log("Hot Plug SCSI disk test - FAIL : " + str(e))

    try:
        TestHotPlugDevice(vm1, vmconfig.AddNic, "Ethernet card",
                          Vim.Vm.Device.VirtualEthernetCard, positive, False)
    except Exception as e:
        testFailedCount += 1
        Log("Hot Plug Ethernet Card test - FAIL : " + str(e))

    try:
        TestHotPlugDevice(vm1, vmconfig.AddUSBCtlr, "USB Controller",
                          Vim.Vm.Device.VirtualUSBController, positive, False)
    except Exception as e:
        testFailedCount += 1
        Log("Hot Plug USB Controller test - FAIL : " + str(e))

    try:
        TestHotPlugDevice(vm1, vmconfig.AddVMI, "VMI Rom",
                          Vim.Vm.Device.VirtualVMIROM, positive, False)
    except Exception as e:
        testFailedCount += 1
        Log("Hot Plug VMI Rom test - FAIL : " + str(e))

    #TestHotPlugDevice(vm1, vmconfig.AddSoundCard, "Sound card",
    #                  Vim.Vm.Device.VirtualEnsoniq1371, positive, False)


def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "vmname="], "HotPlugTest", "Name of the virtual machine", "vmname"),
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
       vm1 = folder.Find(vmname)
       try:
           if vm1:
              Log("Powering on VM " + vm1.GetConfig().GetName())
              if vm1.GetRuntime().GetPowerState() == Vim.VirtualMachine.PowerState.poweredOff:
                 vm.PowerOn(vm1)

              ## Positive test for the vm
              TestDeviceHotPlugForVm(vm1, True)

           else:
              Log("Did not specify a vmname or the VM was not found. Using the default name HotPlugTest")

              posVmName = vmname + "_Pos_" + str(i)
              negVmName = vmname + "_Neg_" + str(i)
              Log("Cleaning up VMs from previous runs...")

              vm.Delete(posVmName, True)
              vm.Delete(negVmName, True)

              ## Positive tests on a hwVersion 8 VM
              Log("Creating Hw8 VM..")
              vm1 = vm.CreateQuickDummy(posVmName, vmxVersion = "vmx-08",
                    memory = "1024", guest = "rhel5Guest")
              Log("Powering on VM " + vm1.GetConfig().GetName())
              vm.PowerOn(vm1)

              # Positive tests for hw8 VM
              TestDeviceHotPlugForVm(vm1, True)
              Log("Powering off and deleting VM " + vm1.GetName())
              vm.Delete(posVmName, True)

              ## Positive tests on a hwVersion 7 VM
              Log("Creating Hw7 VM..")
              vm1 = vm.CreateQuickDummy(posVmName, vmxVersion = "vmx-07",
                    memory = "1024", guest = "rhel5Guest")
              Log("Powering on VM " + vm1.GetConfig().GetName())
              vm.PowerOn(vm1)

              # Positive tests for hw7 VM
              TestDeviceHotPlugForVm(vm1, True)
              Log("Powering off and deleting VM " + vm1.GetName())
              vm.Delete(posVmName, True)

              Log("Creating Hw4 VM..")
              vm2 = vm.CreateQuickDummy(negVmName, 1, vmxVersion = "vmx-04")
              Log("Powering on VM " + negVmName)
              vm.PowerOn(vm2)

              # Negative tests for hw4 VM
              TestDeviceHotPlugForVm(vm2, False)
              Log("Powering off and deleting VM " + vm2.GetName())
              vm.Delete(negVmName, True)

           Log("Tests completed.")
           bigClock.finish("iteration " + str(i))
       except Exception as e:
           status = "FAIL"
           Log("Caught exception : " + str(e))

   if testFailedCount == 0:
       Log("TEST RUN COMPLETE: " + status)
   else:
       Log("TEST RUN COMPLETE: FAIL")
       Log("Number of total tests failed : " + str(testFailedCount))

# Start program
if __name__ == "__main__":
    main()
