from __future__ import print_function

from pyVmomi import Vim
from pyVim.task import WaitForTask
from pyVim import vm
from pyVim import vmconfig

###
### Implicit precondition: There has to be a floppy drive on the host.
###
VF = Vim.Vm.Device.VirtualFloppy
VFDEV = type(Vim.Vm.Device.VirtualFloppy.DeviceBackingInfo())
VFREMOTE = type(Vim.Vm.Device.VirtualFloppy.RemoteDeviceBackingInfo())
VFIMAGE = type(Vim.Vm.Device.VirtualFloppy.ImageBackingInfo())

def BasicCreateDelete(vm1):
   ## Test 1. Create and delete a basic floppy
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddFloppy(cspec)
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), VF)
   if len(devices) != 1:
      raise "Failed to find added floppy"

   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.RemoveDeviceFromSpec(cspec, devices[0])
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)
   devices = vmconfig.CheckDevice(vm1.GetConfig(), VF)
   if len(devices) != 0:
      raise "Found floppy even after delete"
   print("Basic create and delete of floppy works!")

def CreateFloppyDevWithAutoDetect(vm1, autodetectVal):
   ## Test 2. Create floppy device backing with auto detect set as specified and delete it
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddFloppy(cspec, autodetect=autodetectVal, type="device")
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), VF,
                                  {"backing": VFDEV,
                                   "backing.useAutoDetect": autodetectVal})
   if len(devices) != 1:
      raise "Failed to find added floppy"

   cspec2 = Vim.Vm.ConfigSpec()
   cspec2 = vmconfig.RemoveDeviceFromSpec(cspec2, devices[0])
   task2 = vm1.Reconfigure(cspec2)
   WaitForTask(task2)
   devices = vmconfig.CheckDevice(vm1.GetConfig(), VF)
   if len(devices) != 0:
      raise "Found floppy even after delete"
   print("Creating floppy (local)  with autodetect: %s works!" % autodetectVal)


def CreateFloppyRemoteWithAutoDetect(vm1, autodetectVal):
   ## Test 3. Create floppy remote backing with auto detect set as specified and delete it
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddFloppy(cspec, autodetect=autodetectVal, type="remote")
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), VF,
                                  {"backing": VFREMOTE,
                                   "backing.useAutoDetect": autodetectVal})
   if len(devices) != 1:
      raise "Failed to find added floppy"

   cspec2 = Vim.Vm.ConfigSpec()
   cspec2 = vmconfig.RemoveDeviceFromSpec(cspec2, devices[0])
   task2 = vm1.Reconfigure(cspec2)
   WaitForTask(task2)
   devices = vmconfig.CheckDevice(vm1.GetConfig(), VF)
   if len(devices) != 0:
      raise "Found floppy even after delete"
   print("Creating floppy (remote) with no autodetect works!")

def CreateFloppyWithNoDeviceAndAutoDetect(vm1):
   ## Test 7. Create a floppy with autodetect and no device name specified
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddFloppy(cspec, autodetect=True, backingName="")
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)
   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualFloppy,
                                  {"backing.useAutoDetect": True,
                                   "backing.deviceName": ""})
   if len(devices) != 1:
      raise "Failed to find added flopppy"

   cspec = Vim.Vm.ConfigSpec()
   vmconfig.RemoveDeviceFromSpec(cspec, devices[0])
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)
   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualFloppy)
   if len(devices) != 0:
      raise "Found floppy even after delete"

   print("Creating floppy with no device name and autodetect works")

def CreateFloppyWithNoDeviceAndNoAutoDetect(vm1):
   ## Test 8. Create a floppy with autodetect disabled and no device name specified
   success = False
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddFloppy(cspec, autodetect=False, backingName="")
   try:
      task = vm1.Reconfigure(cspec)
      WaitForTask(task)
   except Vim.Fault.InvalidDeviceBacking as e:
      success = True

   if success == True:
      print("Creating floppy with no device name and no autodetect failed as expected")
   else:
      print("Failed test: Created an audio card with no device and no autodetect")

def EditFloppySetAndUnsetAutodetect(vm1):
   # Test 9. Edit a floppy device and toggle the device autodetect setting
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddFloppy(cspec, autodetect=True)
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualFloppy,
                                  {"backing.useAutoDetect": True})
   if len(devices) != 1:
      raise "Failed to find added floppy"

   cspec = Vim.Vm.ConfigSpec()
   dev = devices[0]
   backing = dev.GetBacking()
   backing.SetUseAutoDetect(False)
   backing.SetDeviceName(vmconfig.GetDeviceName(None,
                                       vmconfig.GetCfgTarget(None).GetFloppy))
   dev.SetBacking(backing)
   vmconfig.AddDeviceToSpec(cspec, dev, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualFloppy,
                                  {"backing.useAutoDetect": False})
   if len(devices) != 1:
      raise "Failed to find added floppy"

   cspec = Vim.Vm.ConfigSpec()
   dev = devices[0]
   backing = dev.GetBacking()
   backing.SetUseAutoDetect(True)
   dev.SetBacking(backing)
   vmconfig.AddDeviceToSpec(cspec, dev, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualFloppy,
                                  {"backing.useAutoDetect": True})
   if len(devices) != 1:
      raise "Failed to find added floppy"
   print("Toggling floppy autodetect works!")
