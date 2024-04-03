#!/usr/bin/python

from __future__ import print_function

import sys
import os
from pyVmomi import Vim
from pyVim import connect
from pyVim.connect import Connect, Disconnect
from pyVim import arguments
from pyVmomi import Vmodl
from pyVim.helpers import Log
from pyVmomi import Hostd
from pyVmomi import types, Vmodl, Vim, SoapStubAdapter
from pyVmomi import VmomiSupport
from pyVim import configSerialize
from pyVmomi import SoapAdapter
import time
import types
import atexit, traceback

def GetDebugManager(si):
   global DM
   if DM == None:
      hsi = Hostd.ServiceInstance("ha-internalsvc-service-instance", si._stub)
      DM = hsi.GetDebugManager()
   return DM

DM = None

def ToggleDispatcherFlag(si, flagName):
   debugMgr = GetDebugManager(si)
   print("Toggling flag " + repr(flagName))
   option = Vim.Option.OptionValue()
   option.SetKey(flagName);
   option.SetValue("1");
   debugMgr.UpdateDispatcherOption(option)

#
#
# main
#
def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
		     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["i:", "id="], "1", "ID of client", "id"),
                     (["f:", "flag="], None, "Toggle dispatcher flag", "flag")
                     ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage"),
                        ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      os._exit(1)

   host = args.GetKeyValue("host")

   status = "PASS"

   try:
      # Connect to hosts.
      si = connect.Connect(host=host,
                           user=args.GetKeyValue("user"),
                           pwd=args.GetKeyValue("pwd"),
                           version="vim.version.version9")

      atexit.register(Disconnect, si)

      id = args.GetKeyValue("id")
      if args.GetKeyValue("flag"):
         ToggleDispatcherFlag(si, args.GetKeyValue("flag"))

      Log("TEST RUN %s COMPLETE: %s" % (id, status))
   except Exception:
      (excType, excVal, excTB) = sys.exc_info()
      Log("Caught exception: ")
      traceback.print_exception(excType, excVal, excTB)
      status = "FAIL"

# Start program
if __name__ == "__main__":
   try:
      main()
   except:
      (excType, excVal, excTB) = sys.exc_info()
      Log("Test exiting on unhandled exception: ")
      traceback.print_exception(excType, excVal, excTB)
      sys.exit(42)

