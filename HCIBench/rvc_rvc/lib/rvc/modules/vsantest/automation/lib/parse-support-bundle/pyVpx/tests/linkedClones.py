#!/usr/bin/env python

from __future__ import print_function

import sys
import time
import getopt
import copy
from pyVmomi import Vim
from pyVmomi import VmomiSupport
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm
from pyVim import vimutil
from pyVim import vmconfig
from pyVim.invt import *
import atexit

def usage():
   print("linkedClones.py [options]")
   print("options:")
   print("   --serverType   <hostd|vpxd>                 [Required: The type of server to connect to]")
   print("   --serverIp     <IP address or DNS name>     [Required: The address of either VC or host]")

def main():

   try:
      opts, args = getopt.getopt(sys.argv[1:],
                                 "",
	                         ["serverType=", "serverIp="])
   except getopt.GetoptError:
      usage()
      sys.exit(-1)

   serverType = None
   serverIp = None

   for o, a in opts:
      if o in ("--serverType"):
         serverType = a
      if o in ("--serverIp"):
         serverIp = a

   if (None in (serverType, serverIp)):
      usage()
      sys.exit(-1)

   if serverType == "vpxd":
      print("Connecting to VirtualCenter: " + serverIp)
      userName = "Administrator"
   elif serverType == "hostd":
      print("Connecting to HostAgent: " + serverIp)
      userName = "root"
   else:
      usage()
      sys.exit(0)

   si = Connect(serverIp, 443, userName, "ca$hc0w", serverType, "SOAP", "vim25/5.5")
   atexit.register(Disconnect, si)

   doCommonTests()


def findDisk(myVM):
   """
   Finds the first disk in a VM
   """

   devices = myVM.config.hardware.device
   for device in devices:
      if isinstance(device,Vim.Vm.Device.VirtualDisk):
	 return device

def doCommonTests():
   print("Running common tests")

   # parameterize if needed
   vmName = "linkedCloneTest"
   numDisks = 1

   print("Creating virtual machine with name " + vmName)
   myVM = vm.CreateQuickDummy(vmName, numDisks)

   try:
      # Add a delta disk on top of the base disk
      # using reconfigure()
      reconfigureTest(myVM)

      # Create a new VM which links up to the base disk
      # of the other VM
      vmDisk = findDisk(myVM)
      createTest(vmDisk.backing.parent.fileName)
   finally:
      myVM.Destroy()

def createTest(baseDiskFileName):
   """
   Creates a new VM with a delta disk
   pointing to an already existing base disk.
   Also checks the results.
   """

   print("Running create test")

   vmName = "linkedCloneTest2"
   cspec = vm.CreateDefaultSpec(vmName)

   vmconfig.AddScsiDisk(cspec)

   vmFolder = vm.GetVmFolder()
   resPool = vm.GetResourcePool()

   createTask = vmFolder.CreateVm(cspec,resPool)
   WaitForTask(createTask)

   print("createTest succeeded")

def reconfigureTest(myVM):
   """
   reconfigures a VM to add a delta disk
   and verifies the success of the operation
   """

   print("Running reconfigure test")

   oldDisk = findDisk(myVM)
   oldDiskBacking = oldDisk.backing

   # the new filename is the same as the old except for -delta shoved in the middle
   oldFileName = oldDiskBacking.fileName
   newFileName = oldFileName.split('.')[0] + "-delta" + oldFileName.split('.')[1]

   # the new backing is exactly the same as the old one except that it has
   # a different filename and has the old backing as its parent.
   newDiskBacking = copy.copy(oldDiskBacking)
   newDiskBacking.fileName = newFileName
   newDiskBacking.parent = oldDiskBacking

   # the new disk is exactly the same as the old one except for
   # the different backing
   newDisk = copy.copy(oldDisk)
   newDisk.backing = newDiskBacking

   devSpec = Vim.Vm.Device.VirtualDeviceSpec()
   devSpec.device = newDisk
   devSpec.operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   devSpec.fileOperation = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.create

   cspec = Vim.Vm.ConfigSpec()
   cspec.deviceChange = [devSpec]

   reconfigureTask = myVM.Reconfigure(cspec)
   WaitForTask(reconfigureTask)

   # check to see if both files exist
   dsBrowser = myVM.runtime.host.datastoreBrowser

   searchSpec = Vim.Host.DatastoreBrowser.SearchSpec()
   searchSpec.matchPattern = [oldFileName, newFileName]

   searchTask = dsBrowser.Search("["+myVM.datastore[0].info.name+"]/",searchSpec)
   WaitForTask(searchTask)

   searchResult = searchTask.info.result
   if len(searchResult.file) != 2:
      raise Exception("failed in reconfigureTest")

   # check to see if the VM's ConfigInfo is correct
   diskAfterReconfig = findDisk(myVM)
   if diskAfterReconfig.backing.fileName != newFileName:
      raise Exception("failed in reconfigureTest")

   if diskAfterReconfig.backing.parent.fileName != oldFileName:
      raise Exception("failed in reconfigureTest")

   print("reconfigureTest succeeded")

if __name__ == "__main__":
   main()
