#!/usr/bin/python

#
# Test the VProbes <-> hostd <-> foundry communication channel.
# VProbes has the following interfaces which we need to test:
#    - Load a script
#    - Unload a script
#    - Reset an instance
#    - Get the list of static probes
#    - Get the list of global variables
#

import sys
import getopt
from pyVmomi import Vim
from pyVmomi import Hostd
from pyVmomi import Vmodl # for the exceptions
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim.helpers import Log
from pyVim import vm
from pyVim import host
from pyVim import invt
from pyVim import folder
from pyVim import connect
from pyVim import arguments
import atexit


def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd"),
                     (["v:", "vmname="], "", "Name of the virtual machine", "vmname") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage")]

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

   vm1 = None
   try:
      # Find the VM
      vm1 = folder.Find(vmname)
      if vm1 == None:
         raise Exception("VM with name " + vmname + " cannot be found!")

      instanceId = "0"
      # Inspired by InternalCommand() in vim/py/tests/vmTestHbr.py!!
      vprobesMgr = Hostd.VprobesManager("ha-internalsvc-vprobesmgr",
                                        si._stub)

      # Print out the VProbes version in the VM domain
      task = vprobesMgr.GetVprobesVersion(vm1)
      WaitForTask(task)
      Log(str(task.info.result))

      # Print out the static probes in the VM domain
      task = vprobesMgr.ListVprobesStaticProbes(vm1)
      WaitForTask(task)
      Log("List of static probes:\n" + str(task.info.result))

      # Print out the global variables in the VM domain
      task = vprobesMgr.ListVprobesGlobals(vm1)
      WaitForTask(task)
      Log("List of globals:\n" + str(task.info.result))

      script = '''0
         (vprobe VMXLoad (printf \"Test script loaded\\n\"))
         (vprobe VMM1Hz (printf \"Hello World\\n\"))
         (vprobe VMMUnload (printf \"Test script unloaded\\n\"))
         '''
      task = vprobesMgr.LoadVprobes(vm1, script)
      WaitForTask(task)
      Log("Load instance id: " + str(task.info.result))

      task = vprobesMgr.ResetVprobes(vm1, instanceId)
      WaitForTask(task)
      Log("VProbes instance reset successfully")

      Log("SUCCESS: VProbes tests completed")

   except Vmodl.Fault.SystemError as e:
      Log("FAILURE: Failed: " + e.reason)
   except Vim.Fault.InvalidState as e:
      Log("FAILURE: VM in an invalid state")
   except Exception as e:
      Log("FAILURE: Caught exception : " + str(e))

# Start program
if __name__ == "__main__":
    main()
