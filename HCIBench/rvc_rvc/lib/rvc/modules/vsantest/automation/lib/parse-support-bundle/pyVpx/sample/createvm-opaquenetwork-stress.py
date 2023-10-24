#!/usr/bin/python
"""
Python program for creating vms on a host and connect to opaque network.
The VM reconfigure and VM destroy tasks are executed in parallel, and
can be used for stress test

Requirements:
 * pyVmomi, pyVim
 * Needs to be invoked with py.sh rather than regular python executable
 * The target host needs to be running hostd
"""

import sys
from optparse import OptionParser
from pyVim.connect import SmartConnect
from pyVim.task import WaitForTask
from pyVim import vm, vmconfig
from pyVim.helpers import StopWatch
from pyVim.invt import GetEnv
from pyVmomi import Vim
from pyVim import invt
from pyVmomi import SoapStubAdapter, Vpx
from pyVim.task import WaitForTasks, WaitForTask


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
                      default="",
                      help="Password to use when connecting to hostd")
    parser.add_option("-v",
                      "--vm_name",
                      "--vmname",
                      default="CreateTest",
                      help="Name of the virtual machine")
    parser.add_option("-o",
                      "--opaquenetwork_id",
                      default="ovs-testing",
                      help="Id of opaque network")
    parser.add_option("-t",
                      "--opaquenetwork_type",
                      default="nvp.network",
                      help="type of opaque network")
    parser.add_option("-n",
                      "--vnic_type",
                      default="vmxnet3",
                      help="type of vNIC device (e1000/vmxnet3, etc)")
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

    curSi = SmartConnect(host=options.host,
                         user=options.user,
                         pwd=options.password)

    # Create vms
    envBrowser = GetEnv()
    cfgOption = envBrowser.QueryConfigOption(None, None)
    cfgTarget = envBrowser.QueryConfigTarget(None)

    vmList = []
    tasks = []
    clock = StopWatch()
    for i in range(int(options.num_iterations)):
        vm1 = vm.CreateQuickDummy(options.vm_name + "_" + str(i),
                                  options.num_scsi_disks,
                                  options.num_ide_disks,
                                  datastoreName=options.datastore_name,
                                  cfgOption=cfgOption,
                                  cfgTarget=cfgTarget)
        vmList.append(vm1)
        if options.opaquenetwork_id:
            config = Vim.Vm.ConfigSpec()
            config = vmconfig.AddOpaqueNetwork(config, cfgOption, opaqueNetworkId=options.opaquenetwork_id, \
                                               opaqueNetworkType=options.opaquenetwork_type)
            task = vm1.Reconfigure(config)
            tasks.append(task)
    WaitForTasks(tasks)
    clock.finish("Reconfigure VMs done")

    # Delete the vm as cleanup
    if not options.dont_delete:
        clock = StopWatch()
        WaitForTasks([curVm.Destroy() for curVm in vmList])
        clock.finish("Destroy VMs done")


# Start program
if __name__ == "__main__":
    main()
