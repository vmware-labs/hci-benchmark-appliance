#!/usr/bin/python

import sys
import time
import getopt
from pyVmomi import Vim
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm, folder
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import atexit


## Test add and remove for Scsi controller
##
## @param vm1        [in] VM to invoke operation on
## @param numCtlrs   [in] Number of PvScsi controllers to check for in the VM
## @param testRemove [in] Whether or not to test remove of the controller
##
def TestScsiCtlrReconfig(vm1, numCtlrs, testRemove):
    Log("Adding SCSI controller to VM")
    cspec = Vim.Vm.ConfigSpec()
    cspec = vmconfig.AddScsiCtlr(cspec, cfgInfo = vm1.GetConfig(),
				 ctlrType = "pvscsi")

    # Reconfigure the VM to add the device
    vm.Reconfigure(vm1, cspec)

    # Check for device presence in VM's config
    ctlrs = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.ParaVirtualSCSIController)
    if len(ctlrs) != numCtlrs:
       raise Exception("Failed to find added SCSI controller :" + str(len(ctlrs)))

    if testRemove:
        # Remove SCSI controller from VM
	Log("Removing SCSI controller from VM")
	vm.RemoveDevice(vm1, ctlrs[numCtlrs - 1])



def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "vmname="], "PvScsiTest", "Name of the virtual machine", "vmname"),
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
           Log("Cleaning up VMs from previous runs...")
           vm.Delete(vmname, True)

           ## Positive tests on a hwVersion 7 VM
           Log("Creating Hw7 VM..")
           vm1 = vm.CreateQuickDummy(vmname, vmxVersion = "vmx-07",
				     memory = 4, guest = "rhel5Guest")

	   # Test add of PvScsi controller
	   TestScsiCtlrReconfig(vm1, 1, False)

	   Log("Powering on VM " + vm1.GetConfig().GetName())
           vm.PowerOn(vm1)

	   # Test hot plug of PvScsi controller
	   TestScsiCtlrReconfig(vm1, 2, True)

	   Log("Deleting VM")
	   vm.Delete(vmname, True)

           Log("Tests completed.")
           bigClock.finish("iteration " + str(i))
       except Exception as e:
           status = "FAIL"
           Log("Caught exception : " + str(e))
   Log("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()

