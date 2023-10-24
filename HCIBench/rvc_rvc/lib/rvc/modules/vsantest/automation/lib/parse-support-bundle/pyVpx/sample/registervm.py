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
from pyVim.helpers import Log, StopWatch


def main():
    supportedArgs = [(["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "vmname="], "CreateTest",
                      "Name of the virtual machine", "vmname"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter")]

    supportedToggles = [
        (["usage", "help"], False, "Show usage information", "usage"),
        (["unregister"], False, "Do an unregister of all registered vms",
         "unregister")
    ]

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
    numiter = int(args.GetKeyValue("iter"))
    dounreg = int(args.GetKeyValue("unregister"))

    # The unregister case
    if (dounreg):
        for v in folder.GetAll():
            v.Unregister()
        sys.exit(0)

    # Create vms
    for i in range(numiter):
        clock = StopWatch()
        folder.Register("[storage1] " + vmname + "_" + str(i) + "/" + vmname +
                        "_" + str(i) + ".vmx")
        clock.finish("Register done")


# Start program
if __name__ == "__main__":
    main()
