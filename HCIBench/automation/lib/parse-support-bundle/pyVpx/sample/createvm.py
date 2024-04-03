#!/usr/bin/python
"""
Python program for creating vms on a host on which hostd is running

Requirements:
 * pyVmomi, pyVim
 * Needs to be invoked with py.sh rather than regular python executable
 * The target host needs to be running hostd
"""

import sys
from optparse import OptionParser
from pyVim.connect import Connect
from pyVim.task import WaitForTask
from pyVim import vm
from pyVim.helpers import StopWatch
from pyVim.invt import GetEnv


def GetOptions():
    """
   Supports the command-line arguments listed below.
   """

    parser = OptionParser(add_help_option=False)
    parser.add_option("-h",
                      "--host",
                      default="127.0.0.1",
                      help="remote host to connect to")
    parser.add_option("-u",
                      "--user",
                      default="root",
                      help="User name to use when connecting to hostd")
    parser.add_option("-p",
                      "--password",
                      "--pwd",
                      default="ca$hc0w",
                      help="Password to use when connecting to hostd")
    parser.add_option("-v",
                      "--vm_name",
                      "--vmname",
                      default="CreateTest",
                      help="Name of the virtual machine")
    parser.add_option("--datastore-name", help="Name of the datastore")
    parser.add_option("-i",
                      "--num-iterations",
                      "--numiter",
                      default=1,
                      help="Number of iterations")
    parser.add_option("--num-scsi-disks",
                      default=1,
                      help="Number of SCSI disks")
    parser.add_option("--num-ide-disks", default=0, help="Number of IDE disks")
    parser.add_option("-c",
                      "--num-power-cycles",
                      "--powercycles",
                      default=0,
                      help="Number of power cycles to perform before delete")
    parser.add_option("-d",
                      "--dont-delete",
                      "--no-delete",
                      "--dontDelete",
                      default=False,
                      help="Don't delete created vm")
    parser.add_option("-?", "--help", action="store_true", help="Help")
    (options, _) = parser.parse_args()
    if options.help:
        print parser.format_help()
        sys.exit(0)
    return options


def main():
    """
   Simple command-line program for creating virtual machines on a
   system managed by hostd.
   """

    options = GetOptions()

    Connect(host=options.host, user=options.user, pwd=options.password)

    # Create vms
    envBrowser = GetEnv()
    cfgOption = envBrowser.QueryConfigOption(None, None)
    cfgTarget = envBrowser.QueryConfigTarget(None)
    for i in range(int(options.num_iterations)):
        vm1 = vm.CreateQuickDummy(options.vm_name + "_" + str(i),
                                  options.num_scsi_disks,
                                  options.num_ide_disks,
                                  datastoreName=options.datastore_name,
                                  cfgOption=cfgOption,
                                  cfgTarget=cfgTarget)

        for _ in range(int(options.num_power_cycles)):
            clock = StopWatch()
            vm.PowerOn(vm1)
            clock.finish("PowerOn done")
            clock = StopWatch()
            vm.PowerOff(vm1)
            clock.finish("PowerOff done")

        # Delete the vm as cleanup
        if not options.dont_delete:
            task = vm1.Destroy()
            WaitForTask(task)


# Start program
if __name__ == "__main__":
    main()
