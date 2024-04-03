from __future__ import print_function

from pyVmomi import Vim
from pyVim.task import WaitForTask
from pyVim import vm
from pyVim import vmconfig

###
### Implicit precondition: There has to be a sound card on the host.
###

def BasicCreateDelete(vm1):
   ## Test 1. Create and delete a basic sound card
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddSoundCard(cspec)
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualSoundCard)
   if len(devices) != 1:
      raise "Failed to find added sound card"

   cspec2 = Vim.Vm.ConfigSpec()
   cspec2 = vmconfig.RemoveDeviceFromSpec(cspec2, devices[0])
   task2 = vm1.Reconfigure(cspec2)
   WaitForTask(task2)
   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualSoundCard)
   if len(devices) != 0:
      raise "Found sound card even after delete"
   print("Basic create and delete of sound card works!")


def CreateEnsoniqWithAutoDetect(vm1):
   ## Test 2. Create an ensoniq with auto detect enabled and delete it
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddSoundCard(cspec, autodetect=True, type="ensoniq")
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualEnsoniq1371,
                                  {"backing.useAutoDetect": True})
   if len(devices) != 1:
      raise "Failed to find added sound card"

   cspec2 = Vim.Vm.ConfigSpec()
   cspec2 = vmconfig.RemoveDeviceFromSpec(cspec2, devices[0])
   task2 = vm1.Reconfigure(cspec2)
   WaitForTask(task2)
   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualSoundCard)
   if len(devices) != 0:
      raise "Found sound card even after delete"
   print("Creating ensoniq with autodetect works!")

def CreateEnsoniqWithNoAutoDetect(vm1):
   ## Test 3. Create an ensoniq with auto detect enabled and delete it
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddSoundCard(cspec, autodetect=False, type="ensoniq")
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualEnsoniq1371,
                                  {"backing.useAutoDetect": False})
   if len(devices) != 1:
      raise "Failed to find added sound card"

   cspec2 = Vim.Vm.ConfigSpec()
   cspec2 = vmconfig.RemoveDeviceFromSpec(cspec2, devices[0])
   task2 = vm1.Reconfigure(cspec2)
   WaitForTask(task2)
   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualSoundCard)
   if len(devices) != 0:
      raise "Found sound card even after delete"
   print("Creating ensoniq with no autodetect works!")

def CreateSB16WithAutoDetect(vm1):
   ## Test 4. Create an SB16 with autodetect enabled and delete it.
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddSoundCard(cspec, autodetect=True, type="sb16")
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualSoundBlaster16,
                                  {"backing.useAutoDetect": True})
   if len(devices) != 1:
      raise "Failed to find added sound card"

   cspec2 = Vim.Vm.ConfigSpec()
   cspec2 = vmconfig.RemoveDeviceFromSpec(cspec2, devices[0])
   task2 = vm1.Reconfigure(cspec2)
   WaitForTask(task2)
   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualSoundCard)
   if len(devices) != 0:
      raise "Found sound card even after delete"
   print("Creating sb16 with autodetect works!")

def CreateSB16NoAuto(vm1):
   ## Test 5. Create an SB16 with autodetect disabled and delete it.
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddSoundCard(cspec, autodetect=False, type="sb16")
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualSoundBlaster16,
                                  {"backing.useAutoDetect": False})
   if len(devices) != 1:
      raise "Failed to find added sound card"

   cspec2 = Vim.Vm.ConfigSpec()
   cspec2 = vmconfig.RemoveDeviceFromSpec(cspec2, devices[0])
   task2 = vm1.Reconfigure(cspec2)
   WaitForTask(task2)
   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualSoundCard)
   if len(devices) != 0:
      raise "Found sound card even after delete"
   print("Creating sb16 with no autodetect works!")

def CreateMultipleSoundCards(vm1):
   ## Test 6. Create two sound cards and verify the operation fails
   success=False
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddSoundCard(cspec, autodetect=False, type="ensoniq")
   cspec = vmconfig.AddSoundCard(cspec, autodetect=False, type="sb16")
   try:
      task = vm1.Reconfigure(cspec)
      WaitForTask(task)
   except Vim.Fault.TooManyDevices as e:
      success=True

   if success == True:
      success = False
      cspec = Vim.Vm.ConfigSpec()
      cspec = vmconfig.AddSoundCard(cspec, autodetect=False, type="ensoniq")
      try:
         task = vm1.Reconfigure(cspec)
         WaitForTask(task)
      except Vim.Fault.TooManyDevices as e:
         success=True

   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualSoundCard)
   if len(devices) != 0:
      raise "Found sound card though operation should have failed!!"

   if (success == True):
      print("Successful failing to create 2 sound devices")
   else:
      print("Apparently didnt see expected exceptions")

def CreateSoundCardWithNoDeviceAndAutoDetect(vm1):
   ## Test 7. Create a sound card with autodetect and no device name specified
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddSoundCard(cspec, autodetect=True, devName="")
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)
   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualSoundCard,
                                  {"backing.useAutoDetect": True,
                                   "backing.deviceName": ""})
   if len(devices) != 1:
      raise "Failed to find added sound card"

   cspec = Vim.Vm.ConfigSpec()
   vmconfig.RemoveDeviceFromSpec(cspec, devices[0])
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)
   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualSoundCard)
   if len(devices) != 0:
      raise "Found sound card even after delete"

   print("Creating audio with no device name and autodetect works")

def CreateSoundCardWithNoDeviceAndNoAutoDetect(vm1):
   ## Test 8. Create a sound card with autodetect disabled and no device name specified
   success = False
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddSoundCard(cspec, autodetect=False, devName="")
   try:
      task = vm1.Reconfigure(cspec)
      WaitForTask(task)
   except Vim.Fault.InvalidDeviceBacking as e:
      success = True

   if success == True:
      print("Creating audio with no device name and no autodetect failed as expected")
   else:
      print("Failed test: Created an audio card with no device and no autodetect")

def EditExistingEnsoniqToSetAndUnsetAutodetect(vm1):
   # Test 9. Edit an ensoniq device and toggle  the device autodetect setting
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddSoundCard(cspec, autodetect=True, type="ensoniq")
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualEnsoniq1371,
                                  {"backing.useAutoDetect": True})
   if len(devices) != 1:
      raise "Failed to find added sound card"

   cspec = Vim.Vm.ConfigSpec()
   dev = devices[0]
   backing = dev.GetBacking()
   backing.SetUseAutoDetect(False)
   backing.SetDeviceName(vmconfig.GetDeviceName(None,
                                       vmconfig.GetCfgTarget(None).GetSound))
   dev.SetBacking(backing)
   vmconfig.AddDeviceToSpec(cspec, dev, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualEnsoniq1371,
                                  {"backing.useAutoDetect": False})
   if len(devices) != 1:
      raise "Failed to find added sound card"

   cspec = Vim.Vm.ConfigSpec()
   dev = devices[0]
   backing = dev.GetBacking()
   backing.SetUseAutoDetect(True)
   dev.SetBacking(backing)
   vmconfig.AddDeviceToSpec(cspec, dev, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualEnsoniq1371,
                                  {"backing.useAutoDetect": True})
   if len(devices) != 1:
      raise "Failed to find added sound card"
   print("Toggling soundcard autodetect works!")

