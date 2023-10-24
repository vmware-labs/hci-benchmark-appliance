#!/usr/bin/python

import sys
import getopt
from pyVmomi import Vim
from pyVim.connect import Connect, Disconnect
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
                     (["v:", "vmname="], "Hw7ReconfigTest", "Name of the virtual machine", "vmname"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage"),
                        (["runall", "r"], True, "Run all the tests", "runall"),
                        (["nodelete"], False, "Dont delete vm on completion", "nodelete") ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Connect
   si = Connect(host=args.GetKeyValue("host"),
                user=args.GetKeyValue("user"),
                pwd=args.GetKeyValue("pwd"),
                version="vim.version.version9")
   atexit.register(Disconnect, si)


   # Process command line
   vmname = args.GetKeyValue("vmname")
   numiter = int(args.GetKeyValue("iter"))
   runall = args.GetKeyValue("runall")
   noDelete = args.GetKeyValue("nodelete")
   status = "PASS"

   for i in range(numiter):
       bigClock = StopWatch()
       vm1 = None
       try:
           ## Cleanup old VMs
	   vm1 = folder.Find(vmname)
	   if vm1 != None:
	      vm1.Destroy()

	   Log("Creating virtual machine")
	   vm1 = vm.CreateQuickDummy(vmname, 1, diskSizeInMB = 4096)

	   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualDisk)
	   if len(devices) < 1:
	         raise Exception("Failed to find added disk!")
	   cspec = Vim.Vm.ConfigSpec()
	   for i in range(0, len(devices)) :
	       disk = devices[i]
	       backing = disk.GetBacking()
	       backing.SetEagerlyScrub(True)
	       disk.SetBacking(backing)
	       vmconfig.AddDeviceToSpec(cspec, disk, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)

	   Log("Scrubbing existing disks of the VM")
	   task = vm1.Reconfigure(cspec)
	   WaitForTask(task)

	   Log("Add a new scrubbed disk to the VM")
	   cspec = Vim.Vm.ConfigSpec()
	   cspec = vmconfig.AddScsiCtlr(cspec)
	   vmconfig.AddScsiDisk(cspec, capacity = 128 * 1024, scrub = True)
	   #task = vm1.Reconfigure(cspec)
	   #WaitForTask(task)

       except Exception as e:
           status = "FAIL"
           Log("Caught exception : " + str(e))
   Log("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()
