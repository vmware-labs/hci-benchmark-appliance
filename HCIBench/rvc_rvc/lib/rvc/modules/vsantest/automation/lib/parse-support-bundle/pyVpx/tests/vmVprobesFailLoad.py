#!/usr/bin/python

#
# Test the VProbes <-> hostd <-> foundry communication channel.
# This test makes sure that if we load a bad script the client
# gets the result compilation error message.
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
      bad_script = '''0
         (vprobe VMXLoad (printf \"Test script loaded\\n\"))
         (vprobe VMM1Hz (printf \"Hello World\\n\"))
         (vprobe badProbeName (printf \"Test script unloaded\\n\"))
         '''
      task = vprobesMgr.LoadVprobes(vm1, bad_script)
      WaitForTask(task)

      Log("FAILURE: Failed to catch exception")

   except Vmodl.Fault.SystemError as e:
      Log("EXPECTED FAILURE: Load failed: " + e.reason)
      Log("SUCCESS: VProbes tests completed")
      return
   except Exception as e:
      Log("FAILURE: Caught exception : " + str(e))
      raise e

   return

# Start program
if __name__ == "__main__":
    main()
