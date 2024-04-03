#!/usr/bin/python

"""
Copyright 2013 VMware, Inc.  All rights reserved. -- VMware Confidential

A set of simple tests to add more disks using advanced maxTargets config.
"""

from optparse import OptionParser
import os
import sys
import atexit

from pyVim.connect import Connect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm
from pyVim import vmconfig
from pyVim import vimutil
from pyVim import invt
from pyVim.connect import SmartConnect, Disconnect, GetSi
from pyVim.helpers import Log,StopWatch
from pyVmomi import Vim


def SetExtraConfig(vm1, key, value):
   cspec = Vim.Vm.ConfigSpec(extraConfig=[Vim.Option.OptionValue(key=key, value=value)])
   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

def AddDisks(vm1, num, ctlrKeys, startingOffset = -1, datastore=None):
   cspec = Vim.Vm.ConfigSpec()
   dchange = cspec.GetDeviceChange()
   cspec.SetDeviceChange(dchange)
   for z in ctlrKeys:
      ctlrKey = z
      thisOffset = startingOffset
      for i in range(num):
         devSpec = Vim.Vm.Device.VirtualDeviceSpec()
         diskDev = Vim.Vm.Device.VirtualDisk()
         diskDev.SetKey(-i)
         diskDev.SetControllerKey(ctlrKey)
         if thisOffset < 0:
            diskDev.SetUnitNumber(-1)
         else:
            if thisOffset + i == 7:
               thisOffset += 1
            diskDev.SetUnitNumber(thisOffset + i)

         diskDev.capacityInKB = long(1024)
         devSpec.SetDevice(diskDev)
         devSpec.SetOperation("add")
         devSpec.SetFileOperation("create")
         dchange.append(devSpec)
         diskBacking = Vim.Vm.Device.VirtualDisk.FlatVer2BackingInfo()
         diskDev.SetBacking(diskBacking)
         if datastore != None:
            diskBacking.SetFileName("[" + datastore + "]")
         else:
            diskBacking.SetFileName("")
         diskBacking.SetDiskMode("persistent")
         Log("Adding disk " + str(i+1) + " to spec " + str(diskDev.unitNumber))

   task = vm1.Reconfigure(cspec)
   WaitForTask(task)

def RunTests(argv):
   # Can't use built-in help option because -h is used for hostname
   parser = OptionParser(add_help_option=False)

   parser.add_option('-h', '--host', dest='host', help='Host name', default='localhost')
   parser.add_option('-u', '--user', dest='user', help='User name', default='root')
   parser.add_option('-p', '--pwd', dest='pwd', help='Password')
   parser.add_option('-o', '--port', dest='port', help='Port',
                     default=443, type='int')
   parser.add_option('-v', '--vmname', dest='vmname', help='temporary vm name',
                     default="test-more-devices")
   parser.add_option('-n', '--numdisks', dest='numdisks', help='number of disks on each controller',
                     default = 27, type = 'int')
   parser.add_option('-c', '--numctlrs', dest='numCtlrs', help='number of controllers',
                     default = 1, type = 'int')
   parser.add_option('-d', '--datastore', dest='datastore', help='Datastore')
   parser.add_option('-s', '--scenario', dest='scenario', default=1,
                     help='1: normal; 2: VM suspended; 3: VM poweredOn',
                     type = 'int')
   parser.add_option('-?', '--help', '--usage', action='help', help='Usage information')

   (options, args) = parser.parse_args(argv)

   # Connect
   si = SmartConnect(host=options.host,
                     user=options.user,
                     pwd=options.pwd,
                     port=options.port)
   atexit.register(Disconnect, si)

   vm1 = vm.CreateQuickDummy(options.vmname, vmxVersion="vmx-11",
                             datastoreName = options.datastore);
   cspec = Vim.Vm.ConfigSpec()
   numCtlrs = options.numCtlrs
   if numCtlrs > 4 :
      numCtlrs = 4
   elif numCtlrs < 0 :
      numCtlrs = 1

   numdisks = options.numdisks
   if numdisks < 0 or numdisks > 254:
      Log("Invalid number of disks, use 16.")
      numdisk = 16

   # Scenarioes
   allScenario = {1: normalScene, 2: suspendedScene, 3: poweredOnScene}
   scene = options.scenario
   if scene not in allScenario:
      Log("Invalid scenario specified, use scenario 1.")
      scene = 1

   ctlrKeys = []
   for i in range(numCtlrs):
      cspec = vmconfig.AddScsiCtlr(cspec, ctlrType="pvscsi")
      ctlrKeys.append(1000 + i)

   vm.Reconfigure(vm1, cspec)
   Log("Created VM with PVSCSI controller")

   allScenario[scene](vm1, numdisks, ctlrKeys, options.datastore)

   vm.Destroy(vm1)
   Log("Success!")

def normalScene(vm1, numdisks, ctlrKeys, storage):
   AddDisks(vm1, 15, ctlrKeys)
   Log("Added 15 disks successfully")

   try:
      AddDisks(vm1, 16, ctlrKeys[:1])
   except Exception as e:
      Log("Hit an exception on add more than 15 disks as expected" + str(e))
   else:
      raise Exception("Error: should not allow more than 15 disks by default")

   numCtlrs = len(ctlrKeys)
   for i in range(numCtlrs):
      advCfgKey = "scsi" + str(i) + ".maxTargets"
      SetExtraConfig(vm1, advCfgKey, "255")

   Log("Update maxTargets successfully")

   if numdisks < 16:
      numdisk = 1 # add one more disks for fun
   else:
      numdisks = numdisks - 15

   AddDisks(vm1, numdisks, ctlrKeys, 16, datastore=storage)
   if vm1.runtime.powerState != Vim.VirtualMachine.PowerState.poweredOn:
      vm.PowerOn(vm1)
   Log("Successfully added all disks")

   vm.PowerOff(vm1)

def suspendedScene(vm1, numdisks, ctlrKeys, storage):
   numCtlrs = len(ctlrKeys)
   for i in range(numCtlrs):
      advCfgKey = "scsi" + str(i) + ".maxTargets"
      SetExtraConfig(vm1, advCfgKey, "255")
   Log("Update maxTargets successfully")

   vm.PowerOn(vm1)
   vm.Suspend(vm1)
   try:
      AddDisks(vm1, numdisks, ctlrKeys, 0, datastore=storage)
   except Exception as e:
      Log("Testing rollback hit an exception as expected" + str(e))
   else:
      raise Exception("Error: should not allow passing suspended scene")

def poweredOnScene(vm1, numdisks, ctlrKeys, storage):
   if numdisks > 15:
      numCtlrs = len(ctlrKeys)
      for i in range(numCtlrs):
         advCfgKey = "scsi" + str(i) + ".maxTargets"
         SetExtraConfig(vm1, advCfgKey, "255")
      Log("Update maxTargets successfully")

   vm.PowerOn(vm1)
   AddDisks(vm1, numdisks, ctlrKeys, -1, datastore=storage)
   vm.PowerOff(vm1)

# Start program
if __name__ == "__main__":
    sys.exit(RunTests(sys.argv[1:]))



