#!/usr/bin/python

from __future__ import print_function

import sys
from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm
from pyVim import invt
from pyVim import vmconfig
from pyVim import vimutil
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import time
import atexit

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd"),
                     (["v:", "vmname="], "t1", "Name of the virtual machine", "vmname"),
                     (["i:", "iter="], "1", "Num of iterations", "iter")]
   supportedToggles = [(["usage", "help"], False, "Show usage information", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Connect
   si = SmartConnect(host=args.GetKeyValue("host"), port=443,
                     user=args.GetKeyValue("user"), pwd=args.GetKeyValue("pwd"))
   atexit.register(Disconnect, si)

   # Process command line
   vmname = args.GetKeyValue("vmname")
   numiter = int(args.GetKeyValue("iter"))

   # Cleanup from previous runs.
   vm1 = folder.Find(vmname)
   if vm1 == None:
      print("VM not found.")
      sys.exit(0)

   for i in xrange(numiter) :
      try:
         Log("Create initial root snapshot")
         vm.CreateSnapshot(vm1, "gg", "old root", False, False)
         gg = vm1.snapshot.currentSnapshot

         Log("Create furture root snapshot R1")
         vm.CreateSnapshot(vm1, "R1", "new root 1", False, False)
         s = vm1.snapshot.currentSnapshot

         task = s.Revert()
         WaitForTask(task)

         Log("Create furture root snapshot R2")
         vm.CreateSnapshot(vm1, "R2", "new root 2", False, False)
         r2 = vm1.snapshot.currentSnapshot

         Log("Power On")
         vm.PowerOn(vm1)

         Log("Remove initial root snapshot and consolidate")
         vimutil.InvokeAndTrack(gg.Remove, False)
         gg = None

         if vm1.runtime.consolidationNeeded:
            raise "Consolidation failed while removing gg."

         Log("Remove the next root snapshot without consolidation")
         vimutil.InvokeAndTrack(s.Remove, False, False)
         s = None

         if vm1.runtime.consolidationNeeded == False:
            raise "Consolidation flag not raised correctly at 2nd root."

         Log("Consolidate snapshot")
         vimutil.InvokeAndTrack(vm1.ConsolidateDisks)

         if vm1.runtime.consolidationNeeded:
            raise "Consolidation flag not cleared after consolidate."

         # time.sleep(5)

         Log("Remove all snapshots without consolidation")
         vimutil.InvokeAndTrack(vm1.RemoveAllSnapshots, False)

         if vm1.runtime.consolidationNeeded == False:
            raise "Consolidation flag not raised correctly at removeall."

         Log("Create online snapshot after removeall")
         vm.CreateSnapshot(vm1, "R3", "new root 3", False, False)

         Log("Power off")
         vm.PowerOff(vm1)

         Log("Remove all snapshots and consolide")
         vm.RemoveAllSnapshots(vm1)

         if vm1.runtime.consolidationNeeded:
            raise "Consolidation flag not cleared after removeall."

         Log("Success: iter " + str(i))

      except Exception as e:
         Log("Caught exception at iter " + str(i) + ": " + str(e))

# Start program
if __name__ == "__main__":
    main()
