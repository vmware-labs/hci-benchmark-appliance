#!/usr/bin/python

import sys
import time
import getopt
from pyVmomi import Vim
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim.helpers import Log
from pyVim import vm
from pyVim import host
from pyVim import invt
from pyVim import connect
from pyVim import arguments
from pyVim import folder
import atexit

status = "PASS"
checkRRState = True

## Cleanup VMs with the given name on a host.
def CleanupVm(vmname, useLlpm = False):
    Log("Cleaning up VMs with name " + vmname)
    oldVms = folder.FindPrefix(vmname)
    for oldVm in oldVms:
	if oldVm.GetRuntime().GetPowerState() == \
	   Vim.VirtualMachine.PowerState.poweredOn:
		vm.PowerOff(oldVm)
        Log("Destroying VM")
        if useLlpm == True:
             vmConfig = oldVm.GetConfig()
             hw = vmConfig.GetHardware()
             hw.SetDevice([])
             vmConfig.SetHardware(hw)
             llpm = invt.GetLLPM()
             llpm.DeleteVm(vmConfig)
        else:
            vm.Destroy(oldVm)

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Secondary host name", "host"),
		     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "VM name="], "vmFT", "Name of the virtual machine", "vmname") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   vmname = args.GetKeyValue("vmname")

   try:
      si = Connect(host=args.GetKeyValue("host"),
                   user=args.GetKeyValue("user"),
		   pwd=args.GetKeyValue("pwd"))
      atexit.register(Disconnect, si)
      Log("Connected to host")
      CleanupVm(vmname, True)
      Log("Cleaned up secondary VM")
   except Exception as e:
      Log("Caught exception : " + str(e))

# Start program
if __name__ == "__main__":
   main()

