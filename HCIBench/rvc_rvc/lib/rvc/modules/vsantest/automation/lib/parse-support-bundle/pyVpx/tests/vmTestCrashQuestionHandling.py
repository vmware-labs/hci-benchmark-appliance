#!/usr/bin/env python

from __future__ import print_function

import sys
import logging
from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim import vm
from pyVim import vmconfig
from optparse import OptionParser, make_option
from pyVim.helpers import StopWatch
from pyVim import invt
import atexit
import time

## Setup logger
logger = logging.getLogger('QuestionTest')
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
      make_option("-n", "--vmname", dest="vmname", default="QuestionTest",
                  help="Virtual machine name"),
      make_option("-v", "--verbose", dest="verbose", action="store_true",
                  default=False, help="Enable verbose logging"),
      make_option("-i", "--iterations", dest="iter", type="int",
                  default=1, help="Number of iterations"),
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


def main():
    options, remainingOptions = ParseArgs(sys.argv[1:])

    # Connect
    si = SmartConnect(host=options.host,
                      user=options.user,
                      pwd=options.pwd)
    atexit.register(Disconnect, si)

    if options.verbose:
        logger.setLevel(logging.DEBUG)

    status = "PASS"
    for i in range(options.iter):
        try:
            logger.info("Starting iteration %d." % (i + 1))
            vm1 = None
            logger.debug("Cleaning up VMs from previous runs...")
            vm.Delete(options.vmname, True)

            logger.debug("Creating VM")
            vm1 = vm.CreateQuickDummy(options.vmname, memory = 4,
                                      vmxVersion = "vmx-07",
                                      guest = "rhel5Guest")

            logger.debug("Reconfiguring VM to have a serial port")
            cspec = Vim.Vm.ConfigSpec()
            backing = Vim.Vm.Device.VirtualSerialPort.FileBackingInfo()
            backing.SetFileName(vm1.config.files.logDirectory + "/serial.log")
            vmconfig.AddSerial(cspec, backing)
            vm.Reconfigure(vm1, cspec)

            logger.debug("Powering on VM")
            vm.PowerOn(vm1)

            logger.debug("Resetting VM")
            vm.Reset(vm1)

            if vm1.runtime.question == None:
                raise Exception("VM did not post a question")

            logger.debug("VM posted a question. Terminating VM")
            vm1.Terminate()

            #
            # The Terminate API sends a hard kill to the VMX. It takes
            # a few seconds after that for the VMX to be re-mounted in
            # Hostd.
            #
            time.sleep(5)
            if vm1.runtime.question != None:
                raise Exception("VM question was not cleared.")

            logger.debug("Verified VM question was cleared.")
            logger.debug("Destroying VM")
            vm.Delete(options.vmname, True)

            logger.info("End of iteration %d." % (i + 1))
        except Exception as e:
            logger.error("Caught exception : " + str(e))
            status = "FAIL"

    logger.info("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()
