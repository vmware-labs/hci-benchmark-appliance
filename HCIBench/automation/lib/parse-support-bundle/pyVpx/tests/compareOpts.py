#!/usr/bin/python

###
###  Simple script for comparing the options in host simulator and
###  the real host.
###

import sys
import atexit
from pyVmomi import vim, Hostd
from optparse import OptionParser
from pyVim import vm, host, folder, vmconfig, invt
from pyVim.task import WaitForTask
from pyVim.connect import Connect, Disconnect, GetStub
from pyVim.helpers import Log

def GetOptions():
    # Supports the command-line arguments listed below
    parser = OptionParser()
    parser.add_option("-H", "--host",
                      default="localhost",
                      help="Host to connect to.")
    parser.add_option("-u", "--user",
                      default="root",
                      help="User name to use when connecting to host.")
    parser.add_option("-p", "--password",
                      default="",
                      help="Password to use when connecting to host.")
    parser.add_option("-S", "--simHost",
                      default="localhost",
                      help="Simulator to connect to.")
    parser.add_option("-U", "--simUser",
                      default="root",
                      help="User name to use when connecting to simulator.")
    parser.add_option("-P", "--simPassword",
                      default="",
                      help="Password to use when connecting to simulator.")
    parser.add_option("-v", "--verbose",
                      default=False, action="store_true",
                      help="Log verbose")

    (options, _) = parser.parse_args()
    return options

def GetParams(hostName, userName, password):
   try:
      siHost = Connect(host=hostName, user=userName, pwd=password,
                       version="vim.version.version9")
   except vim.fault.HostConnectFault as e:
      Log("Failed to connect to %s" % hostName)
      raise

   atexit.register(Disconnect, siHost)
   hostSystem = host.GetHostSystem(siHost)
   advOpts = hostSystem.configManager.advancedOption
   return siHost, hostSystem, advOpts

def Main():
   status = "PASS"
   # Process command line
   options = GetOptions()

   si, hostSystem, advOpts = GetParams(options.host,
                                       options.user,
                                       options.password)
   simSi, simHostSystem, simAdvOpts = GetParams(options.simHost,
                                                options.simUser,
                                                options.simPassword)

   realOptions = []
   simOptions = []
   for opt in advOpts.supportedOption:
      realOptions.append(opt.key)
   for opt in simAdvOpts.supportedOption:
      simOptions.append(opt.key)

   # The option is hidden on the real host
   # but we don't have 'hidden' on the simulator yet.
   hiddenOpts = ['Mem.HostLocalSwapDirEnabled']
   for opt in hiddenOpts:
      if opt in simOptions:
         simOptions.remove(opt)

   for key in realOptions:
      try:
         simOptions.remove(key)
      except ValueError as e:
         Log("Failed to find %s in the simulator options" % key)
         status = "FAIL"

   if len(simOptions) > 0:
      status = "FAIL"
      Log("Remaining options in Simulator options:")
      for key in simOptions:
         Log("  %s" % key)

   Log("Test Status: %s" % status)
   if status != "PASS":
      return 1
   return 0

# Start program
if __name__ == "__main__":
  sys.exit(Main())
