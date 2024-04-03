#!/usr/bin/env python

from __future__ import print_function

import sys
import logging
from pyVmomi import Vim, Vmodl
from pyVim.connect import SmartConnect, Disconnect
from pyVim import vm
from pyVim import vmconfig
from optparse import OptionParser, make_option
from pyVim.helpers import StopWatch
from pyVim import invt
from pyVim.task import WaitForTask
import atexit

## Setup logger
logger = logging.getLogger('VmciAccessMgrTest')
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
      make_option("-n", "--vmname", dest="vmname", default="ubuntu9.04_x64 (1)",
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


## Routine to verify whether a VM is present in a list of VMs (as
## identified by the name of the VM)
def VmInVmList(vm, vmList):
    for item in vmList:
        if vm.name == item.name:
            return True
    return False

## Grant access to a single VM
def GrantVmService(mgr, vm, serviceList):
    accessSpec = Vim.Host.VmciAccessManager.AccessSpec()
    accessSpec.SetVm(vm)
    accessSpec.SetServices(serviceList)
    accessSpec.SetMode(Vim.Host.VmciAccessManager.Mode.grant)
    mgr.UpdateAccess([ accessSpec ])

## Revoke access for a single VM
def RevokeVmService(mgr, vm, serviceList):
    accessSpec = Vim.Host.VmciAccessManager.AccessSpec()
    accessSpec.SetVm(vm)
    accessSpec.SetServices(serviceList)
    accessSpec.SetMode(Vim.Host.VmciAccessManager.Mode.revoke)
    mgr.UpdateAccess([ accessSpec ])


## Revoke access for multiple VMs
def RevokeMultiVmService(mgr, vmList, serviceList):
    accessSpecList = []
    for vm in vmList:
        accessSpec = Vim.Host.VmciAccessManager.AccessSpec()
        accessSpec.SetVm(vm)
        accessSpec.SetServices(serviceList)
        accessSpec.SetMode(Vim.Host.VmciAccessManager.Mode.revoke)
        accessSpecList.append(accessSpec);
    mgr.UpdateAccess(accessSpecList)

## Verify that invalid service tags throw the proper exceptions
def TestInvalidServiceTags(vm, serviceTagList, mgr):
    for serviceTag in serviceTagList:
        try:
            GrantVmService(mgr, vm, [serviceTag])
        except Vmodl.Fault.InvalidArgument as e:
            pass
        else:
            raise Exception("No exception thrown for invalid service tag " + serviceTag)

def main():
    options, remainingOptions = ParseArgs(sys.argv[1:])

    # Connect
    si = SmartConnect(host=options.host, user=options.user,
                      pwd=options.pwd)
    atexit.register(Disconnect, si)

    if options.verbose:
        logger.setLevel(logging.DEBUG)

    status = "PASS"

    # Get hold of the VMCI access manager through the host system
    # config manager

    rootFolder = si.content.GetRootFolder()
    dataCenter = rootFolder.GetChildEntity()[0]
    hostFolder = dataCenter.hostFolder
    host = hostFolder.childEntity[0]
    hostSystem = host.host[0]
    configManager = hostSystem.GetConfigManager()
    vmciAccessManager = si.RetrieveInternalContent().vmciAccessManager

    for i in range(options.iter):
        try:
            logger.info("Starting iteration %d." % (i + 1))

            vm.Delete("VmciAccessMgrTest1", True)
            vm1 = vm.CreateQuickDummy("VmciAccessMgrTest1", vmxVersion = "vmx-07",
                                      memory = 4, guest = "rhel5Guest")

            TestInvalidServiceTags(vm1,
                                   ["foo:", "", "foo:bar:", ":foo"],
                                   vmciAccessManager)

            GrantVmService(vmciAccessManager, vm1,
                           [ "foo:bar.foo", "foo:bar.bar", "foo:bar.bar", "bar:bar.bar", "foo" ])

            services = vmciAccessManager.RetrieveGrantedServices(vm1)
            if sorted(services) != ["bar:bar.bar", "foo", "foo:bar.bar", "foo:bar.foo"]:
                status = "FAIL"
                raise Exception("Mismatch in services granted to vm1")

            vm.Delete("VmciAccessMgrTest2", True)
            vm2 = vm.CreateQuickDummy("VmciAccessMgrTest2", vmxVersion = "vmx-07",
                                      memory = 4, guest = "rhel5Guest")

            GrantVmService(vmciAccessManager, vm2,
                           [ "foo:bar.foo", "foo:bar.bar", "bar:bar.bar" ])

            services = vmciAccessManager.RetrieveGrantedServices(vm2)
            if sorted(services) != ["bar:bar.bar", "foo:bar.bar", "foo:bar.foo"]:
                status = "FAIL"
                raise Exception("Mismatch in services granted to vm2")

            RevokeMultiVmService(vmciAccessManager, [vm1, vm2], [ "foo:bar.foo" ])

            services = vmciAccessManager.RetrieveGrantedServices(vm1)
            services2 = vmciAccessManager.RetrieveGrantedServices(vm2)
            if "foo:bar.foo" in services or "foo:bar.foo" in services2:
                status = "FAIL"
                raise Exception("Services foo:bar.foo still granted to a VM")

            vms = vmciAccessManager.QueryAccessToService(hostSystem, "foo:bar.bar")
            if  not VmInVmList(vm1, vms) or not VmInVmList(vm2, vms):
                status = "FAIL"
                raise Exception("Not all VMs reported as beeing a grantee of foo:bar.bar")

            RevokeVmService(vmciAccessManager, vm1, [])

            vms = vmciAccessManager.QueryAccessToService(hostSystem, "foo:bar.bar")
            if VmInVmList(vm1, vms):
                status = "FAIL"
                raise Exception("vm1 still reported as beeing a grantee of foo:bar.bar")

            if not VmInVmList(vm2, vms):
                status = "FAIL"
                raise Exception("vm2 not reported as beeing a grantee of foo:bar.bar")

            services = vmciAccessManager.RetrieveGrantedServices(vm1)
            if services != []:
                status = "FAIL"
                raise Exception("vm1 is still granted services")

            vm.Delete("VmciAccessMgrTest1", True)
            vm.Delete("VmciAccessMgrTest2", True)

            services = vmciAccessManager.RetrieveGrantedServices(vm2)
            if services != []:
                status = "FAIL"
                raise Exception("vm2 is still granted services after deletion")

            logger.info("End of iteration %d." % (i + 1))
        except Exception as e:
            logger.error("Caught exception : " + str(e))
            status = "FAIL"

    logger.info("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()
