#!/usr/bin/env python

from __future__ import print_function

import sys
import logging
from pyVmomi import Vim
from pyVim.connect import Connect, Disconnect
from pyVim import vm
from pyVim import vmconfig
from optparse import OptionParser, make_option
from pyVim.helpers import StopWatch
from pyVim import invt
import atexit

## Setup logger
logger = logging.getLogger('ExtraConfigTest')
logger.setLevel(logging.INFO)
sh = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(asctime)s %(levelname)s] %(message)s")
sh.setFormatter(formatter)
logger.addHandler(sh)

## Helper routine to edit extra config entries in a VM
def EditExtraConfig(extraCfg, key, value):
    for item in extraCfg:
        if item.key == key:
            item.SetValue(value)
            return True
    return False

## Helper routine to add extra config entries to a VM.
def AddExtraConfig(extraCfg, key, value):
    extraCfg += [Vim.Option.OptionValue(key=key, value=value)]

##
## Helper routine to verify if a given key, value pair exists in the
## list of extraconfig entries
##
def VerifyInExtraConfig(extraCfg, key, value):
    for item in extraCfg:
        if item.key == key and item.value == value:
            return True
    return False

## Helper routine that edits/add an extraConfig entry to a VM
def SetExtraConfig(vm1, key, value, positive = True):
    success = False
    extraCfg = vm1.config.extraConfig
    if not EditExtraConfig(extraCfg, key, value):
        AddExtraConfig(extraCfg, key, value)

    try:
        cspec = Vim.Vm.ConfigSpec()
        cspec.SetExtraConfig(extraCfg)
        vm.Reconfigure(vm1, cspec)
        logger.debug("Reconfigured VM")
        success = True
    except Exception as e:
        if not positive:
            logger.debug("Valided exception %s in negative test case" % e)
            return
        else:
            raise

    if success and not positive:
        raise Exception("Did not hit exception for negative test case.")

    if not VerifyInExtraConfig(vm1.config.extraConfig, key, value):
        raise Exception("Could not find entry in VM's extraConfig")
    else:
        logger.debug("Validated entry in VM's extraConfig")


## Routine that parses the command line arguments.
def ParseArgs(argv):
   _CMD_OPTIONS_LIST = [
      make_option("-h", "--host", dest="host", default="localhost",
                  help="Host name"),
      make_option("-u", "--user", dest="user", default="root",
                  help="User name"),
      make_option("-p", "--pwd", dest="pwd", default="",
                  help="Password"),
      make_option("-n", "--vmname", dest="vmname", default="ExtraCfgTest",
                  help="Virtual machine name"),
      make_option("-v", "--verbose", dest="verbose", action="store_true",
                  default=False, help="Enable verbose logging"),
      make_option("-i", "--iterations", dest="iter", type="int",
                  default=1, help="Number of iterations"),
      make_option("-k", "--extraConfigKey", dest="key",
                  default="replay.allowBTOnly", help="Extra Config Key"),
      make_option("-1", "--extraConfigVal1", dest="val1",
                  default="TRUE", help="Extra Config Value 1"),
      make_option("-2", "--extraConfigVal2", dest="val2",
                  default="FALSE", help="Extra Config Value 2"),
      make_option("-3", "--extraConfigInvalidKey", dest="invalidKey",
                  default="#@#@!!", help="Invalid Extra Config Key"),
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
    si = Connect(host=options.host, user=options.user,
                 pwd=options.pwd, version="vim.version.version9")
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

            logger.debug("Creating Hw7 VM..")
            vm1 = vm.CreateQuickDummy(options.vmname, vmxVersion = "vmx-07",
                                      memory = 4, guest = "rhel5Guest")

            logger.debug("Adding an extra config setting to the VM")
            SetExtraConfig(vm1, options.key, options.val1)

            logger.debug("Editing an extra config setting on the VM")
            SetExtraConfig(vm1, options.key, options.val2)

            logger.debug("Adding a bogus extra config setting on the VM")
            SetExtraConfig(vm1, options.invalidKey, "", False)

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
