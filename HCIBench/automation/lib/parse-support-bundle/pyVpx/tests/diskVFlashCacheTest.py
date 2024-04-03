#!/usr/bin/python

#
# Example -
#  $VMTREE/vim/py/py.sh  $VMTREE/vim/py/tests/vFlashCache.py -h "10.112.187.15" -u "root" -p "" -v "VM01"
#

#
# Assumptions:
#     1. The name of the datastore is datastore1.
#     2. VM is poweredOff.
#
from __future__ import print_function

import sys
import getopt
import re
import copy

from pyVmomi import Vim
from pyVmomi import Vmodl
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm, folder, invt
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import atexit

supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                  (["u:", "user="], "root", "User name", "user"),
                  (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                  (["v:", "vmname="], "VM", "Name of the virtual machine", "vmname"),
                  (["d:", "datastore="], "datastore1", "Name of datatsore", "datastore"),
                  (["t:", "test="], "all", "Name of the test to run", "test") ]

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
datastore = args.GetKeyValue("datastore")
test = args.GetKeyValue("test")

def main():
   # Regression test
   if (test == "all" or test == "test1"):
      test1()

   # Basic vFC enabled disk add, edit and delete
   if (test == "all" or test == "test2"):
      test2()

   # Check vFC enabled disk (with reservation size 0) add edit and delete
   if (test == "all" or test == "test3"):
      test3()


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
      diskDev.SetBacking(backing);
      diskDev.SetVFlashCacheConfigInfo(None);

      ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, vm1.GetConfig(), cspec)
      diskDev.SetControllerKey(ctlrs[0].GetKey())
      diskDev.SetUnitNumber(-1)
      diskDev.SetCapacityInKB(long(4096))
      diskDev.SetCapacityInBytes(long(4096) * 1024)

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

      Log("VFlash Cache Configuration to be set on the disk")
      print(diskDev.GetVFlashCacheConfigInfo())

      #----------------------------------------------
      # delete the disk and check VFlash Reservation
      #----------------------------------------------
      Log("Deleting the disk now.")
      cspec = Vim.Vm.ConfigSpec()

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
            "\nTotal VFlash Cache Allocation  after deletion: " + str(vFlashCacheAllocation))

   except Exception as e:
           Log("Caught exception : " + str(e))

   Log("\nTEST 1 End\n");


#----------------------------------------------------------------------------------------------
# Test 2:
#
# Add a vFC enabled disk. After reconfig, check if added disk is present and check vm.config
# then edit the vFC reservation by calling reconfig_VM and check vm.config
# and finally delete the vFC enabled disk and check the vFC reservation in vm.config
#----------------------------------------------------------------------------------------------
def test2():
   Log("\nTEST 2 Start\n");
   try:
      #---------------------------------------------
      # Add a disk with VFlash Cache Reservation set
      #---------------------------------------------
      vmConfig = vm1.GetConfig()
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation before addition: " + str(vFlashCacheReservation) +
            "\nTotal VFlash Cache Allocation  before addition: " + str(vFlashCacheAllocation))

      cspec = Vim.Vm.ConfigSpec()

      # Get config options and targets
      cfgOption = vmconfig.GetCfgOption(None)
      cfgTarget = vmconfig.GetCfgTarget(None)

      # VFlash Cache Configuration
      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();

      p = re.compile("\[" + datastore + "\]");
      for device in vmConfig.hardware.device:
         try:
            if device.backing and device.backing.fileName and p.search(device.backing.fileName):
               diskDev = device
               break
         except Exception as e:
            Log("Checking disk..")

      backing = diskDev.GetBacking()
      backing.SetFileName("[" + datastore + "] " + str(vmname) + "/VMVFlashCacheDisk.vmdk");

      diskDev.SetBacking(backing);
      diskDev.SetVFlashCacheConfigInfo(vfcInfo);

      Log("VFlash Cache Configuration to be set on the disk")
      print(diskDev.GetVFlashCacheConfigInfo())

      ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, vm1.GetConfig(), cspec)
      diskDev.SetControllerKey(ctlrs[0].GetKey())
      diskDev.SetUnitNumber(-1)
      diskDev.SetCapacityInKB(long(65536))
      diskDev.SetCapacityInBytes(long(65536) * 1024)

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
      p = re.compile("VMVFlashCacheDisk.vmdk");
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
         Log("VFlash Cache Configuration set on the disk")
         print(diskDev.GetVFlashCacheConfigInfo())
      else:
         Log("Added disk not found")
         sys.exit("ERROR");

      #-----------------------------------------------
      # Try Edit the device with wrong blockSizeInKB
      #-----------------------------------------------
      Log("Editing the disk now.")
      cspec = Vim.Vm.ConfigSpec()

      vfcInfo = diskDev.GetVFlashCacheConfigInfo();
      vfcInfo.SetBlockSizeInKB(100);
      diskDev.SetVFlashCacheConfigInfo(vfcInfo);

      Log("Calling Reconfigure with below config info...")
      print(diskDev.GetVFlashCacheConfigInfo())

      vmconfig.AddDeviceToSpec(cspec, diskDev, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure...")
      try:
         vm.Reconfigure(vm1, cspec)
      except Exception as e:
         Log("As expected, got the exception." + str(e));


      #--------------------------------------------------------------------------
      # Try Edit the device with wrong blockSizeInKB and reservation combination
      #--------------------------------------------------------------------------
      Log("Editing the disk now.")
      cspec = Vim.Vm.ConfigSpec()

      vfcInfo = diskDev.GetVFlashCacheConfigInfo();
      vfcInfo.SetBlockSizeInKB(256);
      vfcInfo.SetReservationInMB(64);
      diskDev.SetVFlashCacheConfigInfo(vfcInfo);

      Log("Calling Reconfigure with below config info...")
      print(diskDev.GetVFlashCacheConfigInfo())

      vmconfig.AddDeviceToSpec(cspec, diskDev, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure...")
      try:
         vm.Reconfigure(vm1, cspec)
      except Exception as e:
         Log("As expected, got the exception." + str(e));

      #-------------------------------------------------------------
      # Try editing with unsupported CacheMode, CacheConsistencytype
      #-------------------------------------------------------------
      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetCacheMode("write_back");
      diskDev.SetVFlashCacheConfigInfo(vfcInfo);

      Log("Calling Reconfigure with below config info...")
      print(diskDev.GetVFlashCacheConfigInfo())

      vmconfig.AddDeviceToSpec(cspec, diskDev, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure...")

      try:
         vm.Reconfigure(vm1, cspec)
      except Exception as e:
         Log("As expected, got the exception." + str(e));

      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetCacheConsistencyType("weak");
      diskDev.SetVFlashCacheConfigInfo(vfcInfo);

      Log("Calling Reconfigure with below config info...")
      print(diskDev.GetVFlashCacheConfigInfo())

      vmconfig.AddDeviceToSpec(cspec, diskDev, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure...")
      try:
         vm.Reconfigure(vm1, cspec)

      except Exception as e:
         Log("As expected, got the exception." + str(e));

      #--------------------------------------------------
      # Try editing with supported reservation > diskSize
      #--------------------------------------------------
      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      diskSize = diskDev.GetCapacityInKB() / 1024
      vfcInfo.SetReservationInMB(diskSize + 10);
      diskDev.SetVFlashCacheConfigInfo(vfcInfo);

      Log("Calling Reconfigure with below config info...")
      print(diskDev.GetVFlashCacheConfigInfo())

      vmconfig.AddDeviceToSpec(cspec, diskDev, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure...")

      try:
         vm.Reconfigure(vm1, cspec)
      except Exception as e:
         Log("As expected, got the exception." + str(e));

      #----------------------------------------------
      # Edit the device
      #----------------------------------------------
      Log("Editing the disk now.")
      cspec = Vim.Vm.ConfigSpec()

      vfcInfo = diskDev.GetVFlashCacheConfigInfo();
      vfcInfo.SetReservationInMB(4);
      vfcInfo.SetBlockSizeInKB(4);
      # provide empty string for vFlashModule, mode and consistency type
      vfcInfo.SetVFlashModule("");
      vfcInfo.SetCacheMode(" ");
      vfcInfo.SetCacheConsistencyType("  ");

      diskDev.SetVFlashCacheConfigInfo(vfcInfo);

      Log("Calling Reconfigure with below config info...")
      print(diskDev.GetVFlashCacheConfigInfo())

      vmconfig.AddDeviceToSpec(cspec, diskDev, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure...")
      vm.Reconfigure(vm1, cspec)
      Log("Finished Reconfiguring VM: " + str(vmname));

      vmConfig = vm1.GetConfig();
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation after edit: " + str(vFlashCacheReservation) +
            "\nTotal VFlash Cache Allocation  after edit: " + str(vFlashCacheAllocation))


      #--------------------------------------------------
      # check the virtual disk for VFlashCacheConfigInfo
      #--------------------------------------------------
      found = "false"
      p = re.compile("VMVFlashCacheDisk.vmdk");
      for device in vmConfig.hardware.device:
         try:
            if device.backing and device.backing.fileName and p.search(device.backing.fileName):
               diskDev = device
               found = "true"
               break
         except Exception as e:
            Log("Checking disk..")

      if (found == "true"):
         Log("VFlash Cache Configuration set on the disk")
         print(diskDev.GetVFlashCacheConfigInfo())

         cacheInfo = diskDev.GetVFlashCacheConfigInfo()
         if cacheInfo.GetReservationInMB() != 4:
            Log("Unexpected value of Reservation!" +
                "\nReceived: " + str(cacheInfo.GetReservationInMB()) +
                "\nRequired: 4")
            sys.exit("ERROR");
         if cacheInfo.GetBlockSizeInKB() != 4:
            Log("Unexpected value of BlockSize!" +
                "\nReceived: " + str(cacheInfo.GetBlockSizeInKB()) +
                "\nRequired: 4")
            sys.exit("ERROR");
      else:
         Log("Edited disk not found!")
         sys.exit("ERROR");


      #----------------------------------------------
      # delete the disk and check VFlash Reservation
      #----------------------------------------------
      Log("Deleting the disk now.")
      cspec = Vim.Vm.ConfigSpec()

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
            "\nTotal VFlash Cache Allocation  after deletion: " + str(vFlashCacheAllocation))

   except Exception as e:
           Log("Caught exception : " + str(e))

   Log("\nTEST 2 End\n");


#----------------------------------------------------------------------------------------------
# Test 3:
#
# Check the vFC enabled disk with reservation set 0.
# In vmx file, enabled property should be set to disabled
#----------------------------------------------------------------------------------------------
def test3():
   Log("\nTEST 3 Start\n");
   try:
      #---------------------------------------------
      # Add a disk with VFlash Cache Reservation set
      #---------------------------------------------
      vmConfig = vm1.GetConfig()
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation before addition: " + str(vFlashCacheReservation) +
             "\nTotal VFlash Cache Allocation before addition: " + str(vFlashCacheAllocation))

      cspec = Vim.Vm.ConfigSpec()

      # Get config options and targets
      cfgOption = vmconfig.GetCfgOption(None)
      cfgTarget = vmconfig.GetCfgTarget(None)

      #------------------
      # Disk 1: vFC 4MB
      #------------------
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
      backing.SetFileName("[" + datastore + "] " + str(vmname) + "/VMVFlashCacheDisk_01.vmdk");

      diskDev.SetBacking(backing);
      diskDev.SetVFlashCacheConfigInfo(vfcInfo);

      Log("VFlash Cache Configuration to be set on the disk")
      print(diskDev.GetVFlashCacheConfigInfo())

      ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, vm1.GetConfig(), cspec)
      diskDev.SetControllerKey(ctlrs[0].GetKey())
      diskDev.SetUnitNumber(-1)
      diskDev.SetCapacityInKB(long(8192))
      diskDev.SetCapacityInBytes(long(8192) * 1024)

      vmconfig.AddDeviceToSpec(cspec, diskDev, \
                Vim.Vm.Device.VirtualDeviceSpec.Operation.add, \
                Vim.Vm.Device.VirtualDeviceSpec.FileOperation.create)

      Log("Calling Reconfigure...")
      vm.Reconfigure(vm1, cspec)
      Log("Finished Reconfiguring VM: " + str(vmname));

      #------------------
      # Disk 2: vFC 0
      #------------------
      cspec = Vim.Vm.ConfigSpec()

      # Get config options and targets
      cfgOption = vmconfig.GetCfgOption(None)
      cfgTarget = vmconfig.GetCfgTarget(None)

      # VFlash Cache Configuration
      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetReservationInMB(0);

      p = re.compile("\[" + datastore + "\]");
      for device in vmConfig.hardware.device:
         try:
            if device.backing and device.backing.fileName and p.search(device.backing.fileName):
               diskDev = device
               break
         except Exception as e:
            Log("Checking disk..")

      backing = diskDev.GetBacking()
      backing.SetFileName("[" + datastore + "] " + str(vmname) + "/VMVFlashCacheDisk_02.vmdk");

      diskDev.SetBacking(backing);
      diskDev.SetVFlashCacheConfigInfo(vfcInfo);

      Log("VFlash Cache Configuration to be set on the disk")
      print(diskDev.GetVFlashCacheConfigInfo())

      ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, vm1.GetConfig(), cspec)
      diskDev.SetControllerKey(ctlrs[0].GetKey())
      diskDev.SetUnitNumber(-1)
      diskDev.SetCapacityInKB(long(8192))
      diskDev.SetCapacityInBytes(long(8192) * 1024)

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
      p = re.compile("VMVFlashCacheDisk");
      for device in vmConfig.hardware.device:
         try:
            if device.backing and device.backing.fileName and p.search(device.backing.fileName):
               diskDev = device
               Log("VFlash Cache Configuration set on the disk")
               print(diskDev.GetVFlashCacheConfigInfo())
         except Exception as e:
            Log("Checking disk..")

      #----------------------------------------------
      # Edit the device
      #----------------------------------------------
      Log("Editing the disk now.")

      # Disk 1: set vFC to 0
      # Disk 2: set vFC to 8MB

      cspec = Vim.Vm.ConfigSpec()
      p = re.compile("VMVFlashCacheDisk_01");
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
         Log("VFlash Cache Configuration set on the disk")
         print(diskDev.GetVFlashCacheConfigInfo())
      else:
         Log("Added disk 1 not found")
         sys.exit("ERROR");

      vfcInfo = diskDev.GetVFlashCacheConfigInfo();
      vfcInfo.SetReservationInMB(0);
      diskDev.SetVFlashCacheConfigInfo(vfcInfo);

      vmconfig.AddDeviceToSpec(cspec, diskDev, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure... Setting vFC Reservation to 0")
      vm.Reconfigure(vm1, cspec)
      Log("Finished Reconfiguring VM: " + str(vmname));

      cspec = Vim.Vm.ConfigSpec()
      p = re.compile("VMVFlashCacheDisk_02");
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
         Log("VFlash Cache Configuration set on the disk")
         print(diskDev.GetVFlashCacheConfigInfo())
      else:
         Log("Added disk 2 not found")
         sys.exit("ERROR");

      vfcInfo = Vim.Vm.Device.VirtualDisk.VFlashCacheConfigInfo();
      vfcInfo.SetReservationInMB(8);
      diskDev.SetVFlashCacheConfigInfo(vfcInfo);

      vmconfig.AddDeviceToSpec(cspec, diskDev, \
                 Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

      Log("Calling Reconfigure... Setting vFC Reservation to 8")
      vm.Reconfigure(vm1, cspec)
      Log("Finished Reconfiguring VM: " + str(vmname));


      vmConfig = vm1.GetConfig()
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation after edit: " + str(vFlashCacheReservation) +
            "\nTotal VFlash Cache Allocation  after edit: " + str(vFlashCacheAllocation))


      #------------------------------------------------------------
      # check and delete the virtual disk for VFlashCacheConfigInfo
      #------------------------------------------------------------
      p = re.compile("VMVFlashCacheDisk");
      for device in vmConfig.hardware.device:
         try:
            if device.backing and device.backing.fileName and p.search(device.backing.fileName):
               diskDev = device
               Log("VFlash Cache Configuration set on the disk")
               print(diskDev.GetVFlashCacheConfigInfo())

               Log("Deleting the disk now.")
               cspec = Vim.Vm.ConfigSpec()

               vmconfig.AddDeviceToSpec(cspec, diskDev, \
                          Vim.Vm.Device.VirtualDeviceSpec.Operation.remove, \
                          Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy)
               vm.Reconfigure(vm1, cspec)

         except Exception as e:
            Log("Checking disk..")

      vmConfig = vm1.GetConfig();
      vmRuntime = vm1.GetRuntime()
      vFlashCacheReservation = vmConfig.GetVFlashCacheReservation()
      vFlashCacheAllocation = vmRuntime.GetVFlashCacheAllocation()
      Log("\n\nTotal VFlash Cache Reservation after deletion: " + str(vFlashCacheReservation) +
            "\nTotal VFlash Cache Allocation  after deletion: " + str(vFlashCacheAllocation))

   except Exception as e:
           Log("Caught exception : " + str(e))

   Log("\nTEST 3 End\n");


# Start program
if __name__ == "__main__":
    main()
