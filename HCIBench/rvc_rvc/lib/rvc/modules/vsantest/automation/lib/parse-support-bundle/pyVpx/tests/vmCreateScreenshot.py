#!/usr/bin/python

from __future__ import print_function

import sys
import time
import getopt
#import pyVmacore
from pyVmomi import Vim
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm
from pyVim import arguments
from pyVim import folder
import atexit

status = "PASS"

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "vmname="], "CreateScreenshot-VM", "Name of the virtual machine", "vmname"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter") ]

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
   numiter = int(args.GetKeyValue("iter"))
   status = "PASS"

   for i in range(numiter):
      vm1 = None
      # Cleanup from previous runs
      vm1 = folder.Find(vmname)
      if vm1 != None:
        vm1.Destroy()

      # Create new VM
      vm1 = vm.CreateQuickDummy(vmname, guest = "winXPProGuest")
      print("Using VM : " + vm1.GetName())

      try:
         # CreateScreenshot when VM is powered off
         print("Attemp to CreateScreenshot for a powered-off VM")
         try:
            vm.CreateScreenshot(vm1)
            status = "FAIL"
            return
         except Exception as e:
            print("Verified negative test case and got an exception")
            print("Caught exception : " + str(e))

         print("Powering on the VM...")
         vm.PowerOn(vm1)

         # CreateScreenshot when VM is powered on
         print("Attempt to CreateScreenshot for a powered-on VM")

         for i in range(10):
            task = vm1.CreateScreenshot()
            WaitForTask(task)
            screenshotPath = task.GetInfo().GetResult()
            print("The datastore path of the screenshot is: " + screenshotPath)

         print("Suspending the VM...")
         vm.Suspend(vm1)

         # CreateScreenshot when VM is suspended
         print("Attempt to CreateScreenshot for a suspended VM")
         try:
            vm.CreateScreenshot(vm1)
            status = "FAIL"
            return
         except Exception as e:
            print("Verified negative test case and got an exception")
            print("Caught exception : " + str(e))

         # Delete the VM and check whether the screenshot files are deleted
         print("Deleting the VM...")
         delTask = vm1.Destroy()
         WaitForTask(delTask)

      except Exception as e:
         print("Caught exception : " + str(e))
         status = "FAIL"

      if status == "FAIL":
         break

   print("Test status : " + str(status))
   return

# Start program
if __name__ == "__main__":
    main()
    print("Test status: " + status)
    print("CreateScreenshot Tests completed")
