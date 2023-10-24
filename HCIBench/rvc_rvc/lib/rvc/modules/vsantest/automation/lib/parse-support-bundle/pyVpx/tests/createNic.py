#!/usr/bin/python

from __future__ import print_function

import sys
from pyVmomi import Vim
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm
from pyVim import invt
from pyVim import vmconfig
from pyVim import vimutil
from pyVim import arguments
import atexit

def printNicUnitNumbers(vm1, prefix):
   devices = vm1.GetConfig().GetHardware().GetDevice()
   nics = []
   nicNums = []
   for device in devices:
      if isinstance(device, Vim.Vm.Device.VirtualEthernetCard):
         nicNums.append(device.GetUnitNumber())
         nics.append(device)
   print("%s Unit numbers for nics: %s" % (prefix, nicNums))
   return nics

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "vmname="], "CreateTest", "Name of the virtual machine", "vmname")]
   supportedToggles = [(["usage", "help"], False, "Show usage information", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Connect
   si = Connect(args.GetKeyValue("host"), 443,
                args.GetKeyValue("user"), args.GetKeyValue("pwd"))
   atexit.register(Disconnect, si)

   # Process command line
   vmname = args.GetKeyValue("vmname")

   # Cleanup from previous runs.
   vm1 = folder.Find(vmname)
   if vm1 != None:
      vm1.Destroy()

   # Create vms
   envBrowser = invt.GetEnv()
   config = vm.CreateQuickDummySpec(vmname)
   cfgOption = envBrowser.QueryConfigOption(None, None)
   cfgTarget = envBrowser.QueryConfigTarget(None)
   NIC_DIFFERENCE = 7

   config = vmconfig.AddNic(config, cfgOption, cfgTarget, unitNumber = NIC_DIFFERENCE + 0)
   config = vmconfig.AddNic(config, cfgOption, cfgTarget, unitNumber = NIC_DIFFERENCE + 2)
   config = vmconfig.AddNic(config, cfgOption, cfgTarget, unitNumber = NIC_DIFFERENCE + 3)
   config = vmconfig.AddNic(config, cfgOption, cfgTarget, unitNumber = NIC_DIFFERENCE + 4)
   config = vmconfig.AddNic(config, cfgOption, cfgTarget)
   config = vmconfig.AddNic(config, cfgOption, cfgTarget, unitNumber = NIC_DIFFERENCE + 6)
   config = vmconfig.AddNic(config, cfgOption, cfgTarget, unitNumber = NIC_DIFFERENCE + 7)
   config = vmconfig.AddNic(config, cfgOption, cfgTarget, unitNumber = NIC_DIFFERENCE + 8)
   config = vmconfig.AddNic(config, cfgOption, cfgTarget, unitNumber = NIC_DIFFERENCE + 9)
   config = vmconfig.AddScsiCtlr(config, cfgOption, cfgTarget, unitNumber = 3)
   config = vmconfig.AddScsiDisk(config, cfgOption, cfgTarget, unitNumber = 0)
   isofile = "[] /usr/lib/vmware/isoimages/linux.iso"
   config = vmconfig.AddCdrom(config, cfgOption, cfgTarget, unitNumber = 0, isoFilePath=isofile)
   image = "[] /vmimages/floppies/vmscsi.flp"
   config = vmconfig.AddFloppy(config, cfgOption, cfgTarget, unitNumber = 0, type="image", backingName=image)
   config = vmconfig.AddFloppy(config, cfgOption, cfgTarget, unitNumber = 1, type="image", backingName=image)
   backing = Vim.Vm.Device.VirtualSerialPort.FileBackingInfo()
   backing.SetFileName("[]")
   config = vmconfig.AddSerial(config, backing)

   try:
      vmFolder = invt.GetVmFolder()
      vimutil.InvokeAndTrack(vmFolder.CreateVm, config, invt.GetResourcePool(), None)
   except Exception as e:
      raise

   vm1 = folder.Find(vmname)
   printNicUnitNumbers(vm1, "Test 1: Creating a vm with lots of nics")

   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddNic(cspec, cfgOption, cfgTarget)
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)
   printNicUnitNumbers(vm1, "Test 2: Added a nic")


   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddNic(cspec, cfgOption, cfgTarget)
   task = vm1.Reconfigure(cspec)
   try:
      WaitForTask(task)
   except Vim.Fault.TooManyDevices as e:
      print("Caught too many devices as expected")
   nics = printNicUnitNumbers(vm1, "Test 3: Added too many nics")


   cspec = Vim.Vm.ConfigSpec()
   uni = nics[4].GetUnitNumber()
   cspec = vmconfig.RemoveDeviceFromSpec(cspec, nics[0])
   cspec = vmconfig.RemoveDeviceFromSpec(cspec, nics[2])
   cspec = vmconfig.RemoveDeviceFromSpec(cspec, nics[4])
   cspec = vmconfig.RemoveDeviceFromSpec(cspec, nics[5])
   cspec = vmconfig.RemoveDeviceFromSpec(cspec, nics[6])
   cspec = vmconfig.AddNic(cspec, cfgOption, cfgTarget)
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)
   printNicUnitNumbers(vm1, "Test 4: Removed a bunch of nics")

   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddNic(cspec, cfgOption, cfgTarget, unitNumber = NIC_DIFFERENCE - 2)
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)
   printNicUnitNumbers(vm1, "Test 5: Added a nic with slot incorrectly specified")

   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddNic(cspec, cfgOption, cfgTarget, unitNumber = uni)
   cspec = vmconfig.AddScsiCtlr(cspec, cfgOption, cfgTarget, unitNumber = 4)
   cspec = vmconfig.AddScsiDisk(cspec, cfgOption, cfgTarget, unitNumber = 1)
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)
   printNicUnitNumbers(vm1, "Test 6: Added a nic with a slot correctly specified")

   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddNic(cspec, cfgOption, cfgTarget, unitNumber = uni)
   task = vm1.Reconfigure(cspec)
   try:
      WaitForTask(task)
   except Vim.Fault.InvalidDeviceSpec as e:
      print("Exception caught for adding same nic twice")
   printNicUnitNumbers(vm1, "Test 7: Added a nic with s slot specified to be an occupied slot")
   vm1.Destroy()


# Start program
if __name__ == "__main__":
    main()
