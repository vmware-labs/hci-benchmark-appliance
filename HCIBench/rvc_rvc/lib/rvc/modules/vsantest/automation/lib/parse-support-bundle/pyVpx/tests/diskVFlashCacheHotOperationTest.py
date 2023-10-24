#!/usr/bin/python

#
# Example -
#  $VMTREE/vim/py/py.sh  $VMTREE/vim/py/tests/diskVFlashCacheHotOperationTest.py -h "10.112.187.15" -u "root" -p "" -v "VM01"
#

#
# VM should be poweredOn.
#
from __future__ import print_function

import sys
import getopt
import re
import copy

from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm, folder, invt, host
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import atexit

supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                  (["u:", "user="], "root", "User name", "user"),
                  (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                  (["v:", "vmname="], "VM", "Name of the virtual machine", "vmname"),
                  (["d:", "datastore="], "datastore1", "Datastore name", "datastore") ]

supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage") ]

args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
if args.GetKeyValue("usage") == True:
   args.Usage()
   sys.exit(0)

# Connect
si = SmartConnect(host=args.GetKeyValue("host"),
                  user=args.GetKeyValue("user"),
                  pwd=args.GetKeyValue("pwd"))
atexit.register(Disconnect, si)

vmname = args.GetKeyValue("vmname")
vm1 = folder.Find(vmname)
datastore = args.GetKeyValue("datastore");

configMgr = host.GetHostConfigManager(si)
vFlashManager = configMgr.GetVFlashManager()

def main():
   # regression test
   test1()

   # check hot-add / hot-delete operations on vFC enabled disks!
   test2()


#----------------------------------------------------------------------------------------------
# Test 1:
#
# Regression test
# Add a disk without specifying vFC info, delete the added disk.
#----------------------------------------------------------------------------------------------
def test1():
   Log("\nTEST 1 Start\n");
   try:
      #------------------------------------------------
      # Add a disk without VFlash Cache Reservation set
      #------------------------------------------------
      vmConfig = vm1.GetConfig();
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation before addition: " + str(vFlashCacheReservation) +
            "\nTotal VFlash Cache Allocation  before addition: " + str(vFlashCacheAllocation))
      print(vFlashCacheAllocation)

      cspec = Vim.Vm.ConfigSpec()

      # Get config options and targets
      cfgOption = vmconfig.GetCfgOption(None)
      cfgTarget = vmconfig.GetCfgTarget(None)

      p = re.compile("\[" + datastore + "\]");
      for device in vmConfig.hardware.device:
         try:
            if device.backing and device.backing.fileName and p.search(device.backing.fileName):
               diskDev = device
               break
         except Exception as e:
            Log("Checking disk..")

      backing = diskDev.GetBacking()
      backing.SetFileName("[" + datastore + "] " + str(vmname) + "/regressionCheckDisk.vmdk");
      backing.SetUuid(None)
      diskDev.SetBacking(backing);
      diskDev.SetVFlashCacheConfigInfo(None);

      ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, vm1.GetConfig(), cspec)

      for ctlrIdx in range(len(ctlrs)):
          freeSlot = vmconfig.GetFreeSlot(cspec, vm1.GetConfig(), cfgOption, ctlrs[ctlrIdx])
          if (freeSlot >= 0):
             diskDev.SetControllerKey(ctlrs[ctlrIdx].GetKey())
             diskDev.SetUnitNumber(-1)
             diskDev.SetCapacityInKB(long(4096))
             diskDev.SetCapacityInBytes(long(4096) * 1024)
             break

      vmconfig.AddDeviceToSpec(cspec, diskDev, \
                Vim.Vm.Device.VirtualDeviceSpec.Operation.add, \
                Vim.Vm.Device.VirtualDeviceSpec.FileOperation.create)

      Log("Calling Reconfigure...")
      vm.Reconfigure(vm1, cspec)
      Log("Finished Reconfiguring VM: " + str(vmname));

      vmConfig = vm1.GetConfig();
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation after addition: " + str(vFlashCacheReservation) +
            "\nTotal VFlash Cache Allocation  after addition: " + str(vFlashCacheAllocation))

      #--------------------------------------------------
      # check the virtual disk for VFlashCacheConfigInfo
      #--------------------------------------------------
      p = re.compile("regressionCheckDisk.vmdk");
      found = "false"
      for device in vmConfig.hardware.device:
         try:
            if device.backing and device.backing.fileName and p.search(device.backing.fileName):
               diskDev = device
               found = "true"
               break
         except Exception as e:
            Log("Checking disk..")

      if (found == "true"):
         Log("Added disk found")
      else:
         Log("Added disk not found")
         sys.exit("ERROR");

      #----------------------------------------------
      # delete the disk and check VFlash Reservation
      #----------------------------------------------
      Log("Deleting the disk now.")
      cspec = Vim.Vm.ConfigSpec()
      ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, vm1.GetConfig(), cspec)

      vmconfig.AddDeviceToSpec(cspec, diskDev, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.remove, \
                 Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy)

      Log("Calling Reconfigure...")
      vm.Reconfigure(vm1, cspec)
      Log("Finished Reconfiguring VM: " + str(vmname));

      vmConfig = vm1.GetConfig();
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation after deletion: " + str(vFlashCacheReservation) +
            "\nTotal VFlash Cache Allocation  after deletion: "+ str(vFlashCacheAllocation))

   except Exception as e:
           Log("Caught exception : " + str(e))

   Log("\nTEST 1 End\n");



#----------------------------------------------------------------------------------------------
# Test 2:
#
# Checks the hot-add operations of vFC enabled disks
#----------------------------------------------------------------------------------------------
def test2():
   Log("\nTEST 2 Start\n");
   try:

      #------------------------------
      # Hot-addition:
      # Disk 2: vFC 4MB
      #------------------------------
      vmConfig = vm1.GetConfig();

      cspec = Vim.Vm.ConfigSpec()
      cfgOption = vmconfig.GetCfgOption(None)

      # VFlash Cache Configuration
      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetReservationInMB(4);

      p = re.compile("\[" + datastore + "\]");
      for device in vmConfig.hardware.device:
         try:
            if device.backing and device.backing.fileName and p.search(device.backing.fileName):
               diskDev = device
               break
         except Exception as e:
            Log("Checking disk..")

      backing = diskDev.GetBacking()
      backing.SetFileName("[" + datastore + "] " + str(vmname) + "/VMVFlashCacheDisk_hot_01.vmdk");
      backing.SetUuid(None)

      diskDev.SetBacking(backing);
      diskDev.SetVFlashCacheConfigInfo(vfcInfo);

      Log("VFlash Cache Configuration to be set on the disk")
      print(diskDev.GetVFlashCacheConfigInfo())

      ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, vm1.GetConfig(), cspec)

      for ctlrIdx in range(len(ctlrs)):
          freeSlot = vmconfig.GetFreeSlot(cspec, vm1.GetConfig(), cfgOption, ctlrs[ctlrIdx])
          if (freeSlot >= 0):
             diskDev.SetControllerKey(ctlrs[ctlrIdx].GetKey())
             diskDev.SetUnitNumber(-1)
             diskDev.SetCapacityInKB(long(8192))
             diskDev.SetCapacityInBytes(long(8192) * 1024)
             break

      vmconfig.AddDeviceToSpec(cspec, diskDev, \
                Vim.Vm.Device.VirtualDeviceSpec.Operation.add, \
                Vim.Vm.Device.VirtualDeviceSpec.FileOperation.create)

      Log("Calling Reconfigure...")
      vm.Reconfigure(vm1, cspec)
      Log("Finished Reconfiguring VM: " + str(vmname));


      vmConfig = vm1.GetConfig();
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation after addition: " + str(vFlashCacheReservation) +
            "\nTotal VFlash Cache Allocation  after addition: " + str(vFlashCacheAllocation))

      #--------------------------------------------------
      # check the virtual disk for VFlashCacheConfigInfo
      #--------------------------------------------------
      p = re.compile("VMVFlashCacheDisk_hot_");
      found = "false"
      diskDev1 = None

      for device in vmConfig.hardware.device:
         try:
            if device.backing and device.backing.fileName and p.search(device.backing.fileName):
               diskDev1 = device
               print(diskDev1.GetVFlashCacheConfigInfo())
               found = "true"
         except Exception as e:
            Log("Checking disk..")

      if (found == "true"):
         Log("Added disk found")
      else:
         Log("Added disk not found")
         sys.exit("ERROR");


      #--------------------------------------------------
      # Try editing vFC configuration, it should not fail
      #--------------------------------------------------
      Log("Editing the disk now.")
      cspec = Vim.Vm.ConfigSpec()
      ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, vm1.GetConfig(), cspec)

      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetReservationInMB(8);
      vfcInfo.SetBlockSizeInKB(16);
      diskDev1.SetVFlashCacheConfigInfo(vfcInfo);

      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure...")
      vm.Reconfigure(vm1, cspec)
      Log("Finished Reconfiguring VM: " + str(vmname));


      vmConfig = vm1.GetConfig();
      found = "false"
      diskDev1 = None

      for device in vmConfig.hardware.device:
         try:
            if device.backing and device.backing.fileName and p.search(device.backing.fileName):
               diskDev1 = device
               print(diskDev1.GetVFlashCacheConfigInfo())
               found = "true"
         except Exception as e:
            Log("Checking disk..")


      if (found == "true"):
         Log("Added disk found")
      else:
         Log("Added disk not found")
         sys.exit("ERROR");

      vmConfig = vm1.GetConfig();
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation after edit: " + str(vFlashCacheReservation) +
            "\nTotal VFlash Cache Allocation  after edit: " + str(vFlashCacheAllocation))

      #----------------------------------------------
      # Try editing device with invalid params
      #----------------------------------------------

      # Invalid Module Name
      cspec = Vim.Vm.ConfigSpec()

      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetVFlashModule("abcd");
      diskDev1.SetVFlashCacheConfigInfo(vfcInfo);

      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure for invalid module name")
      try:
         vm.Reconfigure(vm1, cspec)
      except Exception as e:
         Log("As expected reconfig failed with exception: " + str(e));

      # Invalid reservation
      cspec = Vim.Vm.ConfigSpec()

      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetReservationInMB(1);
      diskDev1.SetVFlashCacheConfigInfo(vfcInfo);

      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure for invalid reservation")
      try:
         vm.Reconfigure(vm1, cspec)
      except Exception as e:
         Log("As expected reconfig failed with exception: " + str(e));


      # Invalid reservation (> available)a
      vffs = vFlashManager.GetVFlashConfigInfo().GetVFlashResourceConfigInfo().GetVffs();
      cspec = Vim.Vm.ConfigSpec()

      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetReservationInMB((vffs.GetCapacity() / 1024/1024) + 10);
      diskDev1.SetVFlashCacheConfigInfo(vfcInfo);

      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure for invalid reservation (> available)")
      try:
         vm.Reconfigure(vm1, cspec)
      except Exception as e:
         Log("As expected reconfig failed with exception: " + str(e));

      # Invalid reservation (> vmdk size)
      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetReservationInMB((diskDev1.GetCapacityInKB() / 1024)+ 10);
      diskDev1.SetVFlashCacheConfigInfo(vfcInfo);

      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure for invalid reservation (> vmdksize)")
      try:
         vm.Reconfigure(vm1, cspec)
      except Exception as e:
         Log("As expected reconfig failed with exception: " + str(e));

      # Invalid blockSize
      cspec = Vim.Vm.ConfigSpec()
      vfcInfo.SetReservationInMB(1);

      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetBlockSizeInKB(2);
      diskDev1.SetVFlashCacheConfigInfo(vfcInfo);

      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure for invalid block size")
      try:
         vm.Reconfigure(vm1, cspec)
      except Exception as e:
         Log("As expected reconfig failed with exception: " + str(e));


      # Invalid CacheMode
      cspec = Vim.Vm.ConfigSpec()

      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetCacheMode("abcd");
      diskDev1.SetVFlashCacheConfigInfo(vfcInfo);

      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure for invalid cache mode")
      try:
         vm.Reconfigure(vm1, cspec)
      except Exception as e:
         Log("As expected reconfig failed with exception: " + str(e));

      # write_back not supported! Should get exception.
      cspec = Vim.Vm.ConfigSpec()
      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetCacheMode("write_back");
      diskDev1.SetVFlashCacheConfigInfo(vfcInfo);
      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure for unsupported cache mode: \"write_back\"")
      try:
         vm.Reconfigure(vm1, cspec)
      except Exception as e:
         Log("As expected reconfig failed with exception: " + str(e));

      # Invalid Cache Consistency type
      cspec = Vim.Vm.ConfigSpec()

      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetCacheConsistencyType("abcd");
      diskDev1.SetVFlashCacheConfigInfo(vfcInfo);

      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure for invalid cache consistency type")
      try:
         vm.Reconfigure(vm1, cspec)
      except Exception as e:
         Log("As expected reconfig failed with exception: " + str(e));

      # weak is not supported! Should get exception.
      cspec = Vim.Vm.ConfigSpec()
      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetCacheConsistencyType("weak");
      diskDev1.SetVFlashCacheConfigInfo(vfcInfo);

      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure for unsupported cache consistency type: \"weak\"")

      try:
         vm.Reconfigure(vm1, cspec)
      except Exception as e:
         Log("As expected reconfig failed with exception: " + str(e));


      #------------------------
      # Set back default values
      #------------------------
      Log("Editing the disk now.")
      cspec = Vim.Vm.ConfigSpec()
      ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, vm1.GetConfig(), cspec)

      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      diskDev1.SetVFlashCacheConfigInfo(vfcInfo);

      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure...")
      vm.Reconfigure(vm1, cspec)
      Log("Finished Reconfiguring VM: " + str(vmname));


      vmConfig = vm1.GetConfig();
      found = "false"
      diskDev1 = None

      for device in vmConfig.hardware.device:
         try:
            if device.backing and device.backing.fileName and p.search(device.backing.fileName):
               diskDev1 = device
               print(diskDev1.GetVFlashCacheConfigInfo())
               found = "true"
         except Exception:
            Log("Checking disk..")


      if (found == "true"):
         Log("Added disk found")
      else:
         Log("Added disk not found")
         sys.exit("ERROR");

      vmConfig = vm1.GetConfig();
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation after edit: " + str(vFlashCacheReservation) +
            "\nTotal VFlash Cache Allocation  after edit: " + str(vFlashCacheAllocation))


      #----------------------------------
      # Set 0 as VFlash Cache reservation
      #----------------------------------
      Log("Editing the disk now.")
      cspec = Vim.Vm.ConfigSpec()
      ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, vm1.GetConfig(), cspec)

      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetReservationInMB(0);
      diskDev1.SetVFlashCacheConfigInfo(vfcInfo);

      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure...")
      vm.Reconfigure(vm1, cspec)
      Log("Finished Reconfiguring VM: " + str(vmname));


      vmConfig = vm1.GetConfig();
      found = "false"
      diskDev1 = None

      for device in vmConfig.hardware.device:
         try:
            if device.backing and device.backing.fileName and p.search(device.backing.fileName):
               diskDev1 = device
               print(diskDev1.GetVFlashCacheConfigInfo())
               found = "true"
         except Exception as e:
            Log("Checking disk..")


      if (found == "true"):
         Log("Added disk found")
      else:
         Log("Added disk not found")
         sys.exit("ERROR");

      vmConfig = vm1.GetConfig();
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation after edit: " + str(vFlashCacheReservation) +
            "\nTotal VFlash Cache Allocation  after edit: " + str(vFlashCacheAllocation))

      #-------------------------------------
      # Set NULL as VFlash Cache reservation
      #-------------------------------------
      Log("Editing the disk now.")
      cspec = Vim.Vm.ConfigSpec()
      ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, vm1.GetConfig(), cspec)

      diskDev1.SetVFlashCacheConfigInfo(None);

      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure...")
      vm.Reconfigure(vm1, cspec)
      Log("Finished Reconfiguring VM: " + str(vmname));


      vmConfig = vm1.GetConfig();
      found = "false"
      diskDev1 = None

      for device in vmConfig.hardware.device:
         try:
            if device.backing and device.backing.fileName and p.search(device.backing.fileName):
               diskDev1 = device
               print(diskDev1.GetVFlashCacheConfigInfo())
               found = "true"
         except Exception:
            Log("Checking disk..")


      if (found == "true"):
         Log("Added disk found")
      else:
         Log("Added disk not found")
         sys.exit("ERROR");

      vmConfig = vm1.GetConfig();
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation after edit: " + str(vFlashCacheReservation) +
            "\nTotal VFlash Cache Allocation  after edit: " + str(vFlashCacheAllocation))


      #----------------------------------------------
      # delete the disk and check VFlash Reservation
      #----------------------------------------------
      Log("Deleting the disk now.")
      cspec = Vim.Vm.ConfigSpec()
      ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, vm1.GetConfig(), cspec)

      vmconfig.AddDeviceToSpec(cspec, diskDev1, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.remove, \
                 Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy)

      Log("Calling Reconfigure...")
      vm.Reconfigure(vm1, cspec)
      Log("Finished Reconfiguring VM: " + str(vmname));

      vmConfig = vm1.GetConfig();
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation after deletion: " + str(vFlashCacheReservation) +
            "\nTotal VFlash Cache Allocation  after deletion: " + str(vFlashCacheAllocation))

   except Exception as e:
           Log("Caught exception : " + str(e))

   Log("\nTEST 2 End\n");



# Start program
if __name__ == "__main__":
    main()
