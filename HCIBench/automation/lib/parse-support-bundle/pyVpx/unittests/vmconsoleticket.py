#!/usr/bin/python

import sys
import time
from pyVmomi import Vim
from pyVim.connect import Connect
from pyVim import arguments
from pyVim import folder, vm
from pyVim.helpers import Log

def PowerOn(vm1):
   try:
      print "Power on"
      vm.PowerOn(vm1)
      time.sleep(5)
   except:
      pass

def PowerOff(vm1):
   try:
      print "Power off"
      vm.PowerOn(vm1)
      time.sleep(5)
   except:
      pass

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd") ]

   supportedToggles = [ (["burn", "use"], False, "Burn the ticket", "burn"),
                        (["usage", "help"], False, "usage", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      return

   # Connect
   si = Connect(host=args.GetKeyValue("host"),
                user=args.GetKeyValue("user"),
                pwd=args.GetKeyValue("pwd"),
                version="vim.version.version10")

   time.sleep(5)

   print "VMs found:"
   for vm1 in folder.GetVmAll():
      print "   " + str(vm1)

   print "Selecting VM:" + str(vm1)
   time.sleep(2)

   PowerOff(vm1)

   PowerOn(vm1)

   # Obtain a ticket
   print "Obtaining ticket from:" + str(vm1)
   ticket_ = vm1.AcquireTicket('vmconsole')
   time.sleep(2)
   print "Ticket: " + ticket_.ticket

# Start program
if __name__ == "__main__":
    main()
