#!/usr/bin/python

import sys
import getopt
from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm, folder, invt
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log, StopWatch
import pyVmomi
import atexit
import uuid

class Options(object):
   def __init__(self):
      disk = None
      datastore = None
      hostname = None
      username = None
      password = None

VirtualDisk = Vim.Vm.Device.VirtualDisk
VirtualDiskOption = Vim.Vm.Device.VirtualDiskOption
VirtualDeviceSpec = Vim.Vm.Device.VirtualDeviceSpec

def getUniqueVmName():
   return "test-disk-sharing-%s" % str(uuid.uuid4())

def addFlatDisk(options, machine, shared):
   cspec = Vim.Vm.ConfigSpec()
   diskDev = VirtualDisk()
   diskDev.key = vmconfig.GetFreeKey(cspec)
   diskDev.controllerKey = 1000
   diskDev.capacityInKB = long(1024)
   diskDev.unitNumber = -1

   diskBacking = VirtualDisk.FlatVer2BackingInfo()
   diskBacking.fileName = "[" + options.datastore + "]"
   diskBacking.diskMode = VirtualDiskOption.DiskMode.persistent
   if shared:
      diskBacking.sharing = VirtualDisk.Sharing.sharingMultiWriter
   diskBacking.thinProvisioned = False
   diskBacking.eagerlyScrub = True
   diskDev.backing = diskBacking

   vmconfig.AddDeviceToSpec(cspec, diskDev,
                            VirtualDeviceSpec.Operation.add,
                            VirtualDeviceSpec.FileOperation.create)

   vm.Reconfigure(machine, cspec)
   Log("Reconfigure(%s) -> add flat disk" % machine.name)

def addRdmDisk(options, machine, shared):
   cspec = Vim.Vm.ConfigSpec()
   diskDev = VirtualDisk()
   diskDev.key = vmconfig.GetFreeKey(cspec)
   diskDev.controllerKey = 1000
   diskDev.capacityInKB = long(1024)
   diskDev.unitNumber = -1

   diskBacking = VirtualDisk.RawDiskMappingVer1BackingInfo()
   diskBacking.fileName = ""
   diskBacking.diskMode = VirtualDiskOption.DiskMode.persistent
   diskBacking.deviceName = options.disk
   if shared:
      diskBacking.sharing = VirtualDisk.Sharing.sharingMultiWriter
   diskBacking.compatibilityMode = VirtualDiskOption.CompatibilityMode.physicalMode
   diskDev.backing = diskBacking

   vmconfig.AddDeviceToSpec(cspec, diskDev,
                            VirtualDeviceSpec.Operation.add,
                            VirtualDeviceSpec.FileOperation.create)

   vm.Reconfigure(machine, cspec)
   Log("Reconfigure(%s) - add RDM disk" % machine.name)

def editDisk(options, machine, diskDev, shared):
   cspec = Vim.Vm.ConfigSpec()
   if shared:
      diskDev.backing.sharing = VirtualDisk.Sharing.sharingMultiWriter
   else:
      diskDev.backing.sharing = VirtualDisk.Sharing.sharingNone

   vmconfig.AddDeviceToSpec(cspec, diskDev, VirtualDeviceSpec.Operation.edit)

   vm.Reconfigure(machine, cspec)
   Log("Reconfigure(%s) - edit disk" % machine.name)

def testAddDisk(options, online, shared):
   name = getUniqueVmName()
   machine = folder.Find(name)
   if machine: vm.Destroy(machine)
   machine = vm.CreateQuickDummy(name,
                                 datastoreName=options.datastore,
                                 scsiCtlrs=1)
   Log("CreateVM(%s, %s)" % (name, options.datastore))

   if online:
      vm.PowerOn(machine)
      Log("PowerOn(%s)" % machine.name)

   addFlatDisk(options, machine, shared)
   addRdmDisk(options, machine, shared)

   if online:
      vm.PowerOff(machine)
      Log("PowerOff(%s)" % machine.name)

   vm.Destroy(machine)

def testEditDisk(options):
   name = getUniqueVmName()
   machine = folder.Find(name)
   if machine: vm.Destroy(machine)
   machine = vm.CreateQuickDummy(name,
                                 datastoreName=options.datastore,
                                 scsiCtlrs=1)
   Log("CreateVM(%s, %s)" % (name, options.datastore))

   addFlatDisk(options, machine, shared=False)
   diskDev = vmconfig.CheckDevice(machine.config, VirtualDisk)[0]
   editDisk(options, machine, diskDev, shared=True)

   vm.Destroy(machine)

def run(options):
   si = SmartConnect(host=options.hostname,
                     user=options.username,
                     pwd=options.password)
   atexit.register(Disconnect, si)

   try:
      testAddDisk(options, online=False, shared=False)
      testAddDisk(options, online=False, shared=True)
      testAddDisk(options, online=True, shared=False)
      testAddDisk(options, online=True, shared=True)
      testEditDisk(options)
   except Exception as e:
      Log("Caught exception : " + str(e))

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd"),
                     (["d:", "disk="], "/vmfs/devices/", "Disk", "disk"),
                     (["s:", "ds="], "datastore1", "Datastore 1", "ds") ]
   supportedToggles = [
         (["usage", "help"], False, "Show usage information", "usage")
      ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage"):
      args.Usage()
      sys.exit(0)

   options = Options()
   options.disk = args.GetKeyValue("disk")
   options.datastore = args.GetKeyValue("ds")
   options.hostname = args.GetKeyValue("host")
   options.username = args.GetKeyValue("user")
   options.password = args.GetKeyValue("pwd")
   run(options)

if __name__ == "__main__":
    main()

