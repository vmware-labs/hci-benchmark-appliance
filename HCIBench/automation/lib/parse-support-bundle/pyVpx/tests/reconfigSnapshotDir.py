#!/usr/bin/python

from __future__ import print_function

import sys
import logging
import re
from pyVmomi import Vim
from pyVim import vm, vmconfig
from pyVim import connect
from pyVim.connect import Connect, Disconnect
from optparse import OptionParser, make_option
from pyVim import arguments
import atexit, traceback


## Setup logger
logger = logging.getLogger('ReconfigSnapshotDirTest')
logger.setLevel(logging.INFO)
sh = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(asctime)s %(levelname)s] %(message)s")
sh.setFormatter(formatter)
logger.addHandler(sh)

## Routine that parses the command line arguments.
def ParseArgs(argv):
   _CMD_OPTIONS_LIST = [
      make_option("-h", "--host", dest="host", default="localhost",
                  help="Host name"),
      make_option("-u", "--user", dest="user", default="root",
                  help="User name"),
      make_option("-p", "--pwd", dest="pwd", default="",
                  help="Password"),
      make_option("-n", "--vmname", dest="vmname", default="ReconfigSnapshotDirTest",
                  help="Virtual machine name"),
      make_option("-d", "--dspath", dest="dspath", default="[storage1] ReconfigSnapshotDirTest",
                  help="Datastore Path"),
      make_option("-v", "--verbose", dest="verbose", action="store_true",
                  default=False, help="Enable verbose logging"),
      make_option("-?", "--help", action="store_true", help="Help"),
   ]
   _STR_USAGE = "%prog [options]"

   # Get command line options
   cmdParser = OptionParser(option_list=_CMD_OPTIONS_LIST,
                            usage=_STR_USAGE,
                            add_help_option=False)
   cmdParser.allow_interspersed_args = False
   usage = cmdParser.format_help()

   # Parse arguments
   (options, remainingOptions) = cmdParser.parse_args(argv)
   cmdParser.destroy()

   # Print usage
   if options.help:
      print(usage)
      sys.exit(0)
   return (options, remainingOptions)

#
#
# main
#
def main():

   options, remainingOptions = ParseArgs(sys.argv[1:])

   # Connect to hosts.
   si = connect.Connect(host=options.host,
                        user=options.user,
                        pwd=options.pwd)

   atexit.register(Disconnect, si)

   if options.verbose:
      logger.setLevel(logging.DEBUG)

   logger.info("Starting test run")
   vm1 = None
   status = "FAIL"
   try:
      logger.info("Retrieving vm: %s", options.vmname)
      vm1 = vm.CreateOrReturnExisting(options.vmname)
      config = vm1.GetConfig()
      cspec = Vim.Vm.ConfigSpec()
      files = config.files
      logger.info("Changing %s 's snapshotDir to %s", options.vmname, options.dspath)
      try:
         m = re.match('\[([^\]]+)\] .*', options.dspath)
      except:
         logger.error('path "%s" is not valid datastore path', options.dspath)
         raise Exception, "dspath is not valid"
      files.snapshotDirectory = options.dspath
      dsListOld = [ds for ds in vm1.datastore if ds.name == m.groups()[0]]
      if not dsListOld:
         cspec.SetFiles(files)
         vm.Reconfigure(vm1, cspec)
         dsListNew = [ds for ds in vm1.datastore if ds.name == m.groups()[0]]
         if dsListNew:
            logger.info("%s has been added to vm.datastore property", options.dspath)
            status = "PASS"
         else:
            logger.info("%s has not been added to vm.datastore property", options.dspath)
      else:
         logger.info("%s is already present in the vm.datastore property", options.dspath)

   except Exception as e:
      logger.error("Caught exception: " + str(e))
      status = "FAIL"

   logger.info("Test run complete: " + status)

# Start program
if __name__ == "__main__":
      main()
