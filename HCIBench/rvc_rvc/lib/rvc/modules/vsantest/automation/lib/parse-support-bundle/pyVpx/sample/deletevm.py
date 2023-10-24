#!/usr/bin/python

import sys
from pyVmomi import Vim
from pyVmomi import VmomiSupport
from pyVim.connect import Connect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm
from pyVim import vimutil
from pyVim import arguments


def main():
    supportedArgs = [(["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "vmname="], "",
                      "VM prefix (deletes everything by default)", "vmname")]

    supportedToggles = [(["usage",
                          "help"], False, "Show usage information", "usage")]

    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
    if args.GetKeyValue("usage") == True:
        args.Usage()
        sys.exit(0)

    # Connect
    si = Connect(host=args.GetKeyValue("host"),
                 user=args.GetKeyValue("user"),
                 pwd=args.GetKeyValue("pwd"))

    # Process command line
    vmname = args.GetKeyValue("vmname")

    vms = folder.FindPrefix(vmname)
    if len(vms) != 0:
        for vm in vms:
            try:
                vm.Destroy()
            except Exception, e:
                raise


# Start program
if __name__ == "__main__":
    main()
