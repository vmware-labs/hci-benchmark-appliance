#!/usr/bin/python

import sys
import time
import getopt
from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm, folder
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
from pyVim import invt
import atexit


##
## Helper routine to check if a device is present in the VM
##
## @param vm1 [in] VM to invoke operation on
## @param devType [in] Device type to check for
## @param label [in] Device label
##

def CheckDevice(vm1, devType, label):
    retry = 0
    devices = vmconfig.CheckDevice(vm1.GetConfig(), devType)
    while len(devices) != 1 and retry < 10:
       Log("Device not there yet...")
       devices = vmconfig.CheckDevice(vm1.GetConfig(), devType)
       retry += 1
    if len(devices) != 1:
        raise Exception("Failed to find added " + label)
    return devices[0]

##
## Helper routine to check a device is not present in the VM
##
## @param vm1 [in] VM to invoke operation on
## @param devType [in] Device type to check for
## @param label [in] Device label
##

def CheckNoDevice(vm1, devType, label):
    devices = vmconfig.CheckDevice(vm1.GetConfig(), devType)
    if len(devices) != 0:
        raise Exception("Failed to remove " + label)

## Test hot add and hot remove for any virtual device.
##
## @param vm1          [in] VM to invoke operation on
## @param device       [in] UsbInfo object for passthrough device on host
## @param allowVMotion [in] True if VM can VMotion while device is attached
## @param ctlr         [in] Type of controller to attach device to
##
def TestAddDevice(vm1, device, allowVMotion, ctlr):
    Log("Testing adding of device '" + device.description + "' for VM " +
        vm1.GetConfig().GetName() + " allowVmotion:" + str(allowVMotion))
    cspec = Vim.Vm.ConfigSpec()

    cspec = vmconfig.AddUSBDev(cspec, cfgInfo = vm1.GetConfig(), devName = device.name,
                               allowVMotion = allowVMotion, ctlr = ctlr)
    # Hot-add the devices
    vm.Reconfigure(vm1, cspec)

    # Check for device presence in VM's config
    usbDev = CheckDevice(vm1, Vim.Vm.Device.VirtualUSB, "USB device")
    ctlrDev = vmconfig.GetControllers(vmconfig.GetCfgOption(None), ctlr, vm1.GetConfig(), Vim.Vm.ConfigSpec())[0]
    if ctlrDev.key != usbDev.controllerKey:
       raise Exception("Wrong controller for USB device:" + str(usbDev.controllerKey))

def TestRemoveDevice(vm1, device):
    Log("Testing removing of device '" + device.description + "' for VM " +
        vm1.GetConfig().GetName())
    devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualUSB)
    cspec = Vim.Vm.ConfigSpec()
    for dev in devices:
       if dev.backing.deviceName == device.name:
          cspec = vmconfig.RemoveDeviceFromSpec(cspec, dev)

    # Hot-remove the devices
    vm.Reconfigure(vm1, cspec)

    # Check for device absence from VM's config
    CheckNoDevice(vm1, Vim.Vm.Device.VirtualUSB, "USB device")

def DoPlugTest(vm1, device, allowVMotion, ctlr):
   # Test hot plug of a device
   TestAddDevice(vm1, device, allowVMotion, ctlr)

   # Test hot unplug of a device
   TestRemoveDevice(vm1, device)

def DoBadPlugTest(vm1, allowVMotion, ctlr):
    # Test adding a device with bad backing
    Log("Testing adding of bad device for VM " +
        vm1.GetConfig().GetName() + " allowVmotion:" + str(allowVMotion))
    cspec = Vim.Vm.ConfigSpec()

    cspec = vmconfig.AddUSBDev(cspec, cfgInfo = vm1.GetConfig(), devName = "",
                               allowVMotion = allowVMotion, ctlr = ctlr)
    # add the device
    caught = False
    try:
       vm.Reconfigure(vm1, cspec)
    except Vim.fault.InvalidDeviceBacking as e:
       Log("Caught exception : " + str(e))
       caught = True

    if not caught:
        raise Exception("Failed to throw vim.fault.InvalidDeviceBacking for bad device")


def DoPlugTests(vm1, device, ctlr, doHot):
   # Test cold plug of a device
   DoPlugTest(vm1, device, False, ctlr)

   # Test cold plug of a device
   DoPlugTest(vm1, device, True, ctlr)

   DoBadPlugTest(vm1, False, ctlr)

   if not doHot:
      return

   Log("Powering on VM " + vm1.GetConfig().GetName())
   vm.PowerOn(vm1)

   # Test hot plug of a device
   DoPlugTest(vm1, device, False, ctlr)

   # Test hot plug of a device
   DoPlugTest(vm1, device, True, ctlr)

   Log("Powering off VM " + vm1.GetConfig().GetName())
   vm.PowerOff(vm1)


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
   si = SmartConnect(host=args.GetKeyValue("host"),
                     user=args.GetKeyValue("user"),
                     pwd=args.GetKeyValue("pwd"))
   atexit.register(Disconnect, si)


   # Process command line
   vmname = args.GetKeyValue("vmname")
   numiter = int(args.GetKeyValue("iter"))
   runall = args.GetKeyValue("runall")
   noDelete = args.GetKeyValue("nodelete")
   status = "PASS"

   # Find a USB device on the host to passthrough
   envBrowser = invt.GetEnv()
   cfgTarget = envBrowser.QueryConfigTarget(None)
   if len(cfgTarget.usb) < 1:
      Log("No USB devices available for passthrough on " + args.GetKeyValue("host"))
      return

   device = cfgTarget.usb[0]

   for i in range(numiter):
      bigClock = StopWatch()
      vm1 = None
      try:
         vmname7 = vmname + "_HwV7"
         vmname8 = vmname + "_HwV8"
         Log("Cleaning up VMs from previous runs...")
         vm.Delete(vmname7, True)
         vm.Delete(vmname8, True)

         ## Positive tests on a hwVersion 7 VM
         Log("Creating Hw7 VM..")
         vm1 = vm.CreateQuickDummy(vmname7, vmxVersion = "vmx-07",
                                   memory = 4, guest = "rhel5Guest")

         Log("Add a new USB controller to the VM")
         cspec = Vim.Vm.ConfigSpec()
         cspec = vmconfig.AddUSBCtlr(cspec)
         vm.Reconfigure(vm1, cspec)

         DoPlugTests(vm1, device, Vim.Vm.Device.VirtualUSBController, True)
         vm.Delete(vm1.name, True)

         ## Positive tests on a hwVersion 8 VM
         Log("Creating Hw8 VM..")
         vm1 = vm.CreateQuickDummy(vmname8, vmxVersion = "vmx-08",
                                   memory = 4, guest = "rhel5Guest")

         Log("Add a new xHCI USB controller to the VM")
         cspec = Vim.Vm.ConfigSpec()
         cspec = vmconfig.AddUSBXHCICtlr(cspec)
         vm.Reconfigure(vm1, cspec)
         xhciCtlr = CheckDevice(vm1, Vim.Vm.Device.VirtualUSBXHCIController, "xHCI controller")
         DoPlugTests(vm1, device, Vim.Vm.Device.VirtualUSBXHCIController, True)

         Log("Add a new USB controller to the VM")
         cspec = Vim.Vm.ConfigSpec()
         cspec = vmconfig.AddUSBCtlr(cspec)
         vm.Reconfigure(vm1, cspec)
         usbCtlr = CheckDevice(vm1, Vim.Vm.Device.VirtualUSBController, "USB controller")
         DoPlugTests(vm1, device, Vim.Vm.Device.VirtualUSBController, True)

         Log("Remove xHCI USB controller from the VM")
         cspec = vmconfig.RemoveDeviceFromSpec(Vim.Vm.ConfigSpec(), xhciCtlr)
         vm.Reconfigure(vm1, cspec)
         CheckNoDevice(vm1, Vim.Vm.Device.VirtualUSBXHCIController, "xHCI controller")

         Log("Remove USB controller from the VM")
         cspec = vmconfig.RemoveDeviceFromSpec(Vim.Vm.ConfigSpec(), usbCtlr)
         vm.Reconfigure(vm1, cspec)
         CheckNoDevice(vm1, Vim.Vm.Device.VirtualUSBController, "USB controller")

         vm.Delete(vm1.name, True)

         Log("Tests completed.")
         bigClock.finish("iteration " + str(i))
      except Exception as e:
         status = "FAIL"
         Log("Caught exception : " + str(e))
   Log("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()

