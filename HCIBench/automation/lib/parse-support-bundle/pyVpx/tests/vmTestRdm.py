#!/usr/bin/python

#
# Example -
#  $VMTREE/vim/py/py.sh  $VMTREE/vim/py/tests/vmTestRdm.py -h "localhost.eng.vmware.com" -u "root" -p "" -d "/vmfs/devices/naa.xxxx"
#

import sys
import getopt
from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm, folder, invt
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import atexit

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["d:", "disk="], "/vmfs/devices/", "Disk", "disk"),
                     (["s:", "ds="], "storage1", "Datastore 1", "ds"),
                     (["f:", "file="], "[datastore1] rdm/rdm.vmdk", "Virtual Disk", "file"),
                     (["v:", "vmname="], "RdmVM", "Name of the virtual machine", "vmname"),
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
   disk = args.GetKeyValue("disk")
   ds = args.GetKeyValue("ds")
   rdmDiskFile = args.GetKeyValue("file")


   status = "PASS"

   for i in range(numiter):
       bigClock = StopWatch()
       vm1 = None
       try:
           ## Cleanup old VMs
           vm1 = folder.Find(vmname)
           if vm1 != None:
               vm1.Destroy()

           Log("Creating VM: " + str(vmname))

           ## Add scsi disk
           Log("Adding a new rdm disk to VM: " + str(vmname))
           cspec = Vim.Vm.ConfigSpec()
           cspec = vmconfig.CreateDefaultSpec(name = vmname, datastoreName = ds)
           cspec = vmconfig.AddScsiCtlr(cspec)

           # Get config options and targets
           cfgOption = vmconfig.GetCfgOption(None)
           cfgTarget = vmconfig.GetCfgTarget(None)

           rdmBacking = Vim.Vm.Device.VirtualDisk.RawDiskMappingVer1BackingInfo()
           rdmBacking.SetFileName("");
           rdmBacking.SetDeviceName(disk);
           rdmBacking.SetCompatibilityMode("physicalMode");
           rdmBacking.SetDiskMode("");
           rdmBacking.SetParent(None);

           diskDev = Vim.Vm.Device.VirtualDisk()
           diskDev.SetKey(vmconfig.GetFreeKey(cspec))
           diskDev.SetBacking(rdmBacking)
           ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, None, cspec)

           # XXX Fix this up
           for ctlrIdx in range(len(ctlrs)):
              freeSlot = vmconfig.GetFreeSlot(cspec, None, cfgOption, ctlrs[ctlrIdx])
              if (freeSlot >= 0):
                 diskDev.SetControllerKey(ctlrs[ctlrIdx].GetKey())
                 diskDev.SetUnitNumber(-1)
                 diskDev.SetCapacityInKB(long(4096))
                 break


           vmconfig.AddDeviceToSpec(cspec, diskDev, \
                    Vim.Vm.Device.VirtualDeviceSpec.Operation.add, \
                    Vim.Vm.Device.VirtualDeviceSpec.FileOperation.create)

           Log("create VM: " + str(vmname) + " with the RDM disk")
           vmFolder = vm.GetVmFolder()
           resPool = vm.GetResourcePool()

           task = vmFolder.CreateVm(cspec, resPool)
           WaitForTask(task)
           Log("Finished Reconfiguring VM: " + str(vmname));
           vm1 = task.info.result

           Log("Now reconfiguring VM: " + str(vmname));

           cspec = Vim.Vm.ConfigSpec()

           rdmBacking = Vim.Vm.Device.VirtualDisk.RawDiskMappingVer1BackingInfo()
           rdmBacking.SetFileName(rdmDiskFile);
           rdmBacking.SetCompatibilityMode("physicalMode");
           rdmBacking.SetDiskMode("persistent");
           rdmBacking.SetParent(None);

           diskDev = Vim.Vm.Device.VirtualDisk()
           diskDev.SetKey(vmconfig.GetFreeKey(cspec))
           diskDev.SetBacking(rdmBacking)
           ctlrs = vmconfig.GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, vm1.GetConfig(), cspec)
           # XXX Fix this up
           for ctlrIdx in range(len(ctlrs)):
              freeSlot = vmconfig.GetFreeSlot(cspec, vm1.GetConfig(), cfgOption, ctlrs[ctlrIdx])
              if (freeSlot >= 0):
                 diskDev.SetControllerKey(ctlrs[ctlrIdx].GetKey())
                 diskDev.SetUnitNumber(-1)
                 diskDev.SetCapacityInKB(long(4096))
                 break


           vmconfig.AddDeviceToSpec(cspec, diskDev, \
                    Vim.Vm.Device.VirtualDeviceSpec.Operation.add, \
                    Vim.Vm.Device.VirtualDeviceSpec.FileOperation.create)
           vm.Reconfigure(vm1, cspec)
           task = vmFolder.ReconfigVm(cspec, resPool)
           WaitForTask(task)
           Log("Finished Reconfiguring VM: " + str(vmname));


       except Exception as e:
           status = "FAIL"
           Log("Caught exception : " + str(e))
   Log("TEST RUN COMPLETE: " + status)

# Start program
if __name__ == "__main__":
    main()
