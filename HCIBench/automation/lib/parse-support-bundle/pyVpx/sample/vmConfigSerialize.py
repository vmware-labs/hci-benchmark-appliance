#!/usr/bin/python

# Required to make pyVim.connect.Connection work on Python 2.5
from __future__ import with_statement

import sys
from pyVmomi import Vim
from pyVim import arguments
from pyVim import folder
from pyVim.connect import Connection
from pyVim.configSerialize import SerializeToConfig


def main():
    supportedArgs = [
        (["h:", "host="], "localhost", "Host name", "host"),
        (["u:", "user="], "root", "User name", "user"),
        (["p:", "pwd="], None, "Password", "pwd"),
        (["v:", "vmname="], None, "Name of the virtual machine", "vmname"),
    ]
    supportedToggles = [
        (["usage", "help"], False, "Show usage information", "usage"),
    ]
    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
    if args.GetKeyValue("usage") == True:
        args.Usage()
        sys.exit(0)

    # Connect
    connection = Connection(host=args.GetKeyValue("host"),
                            user=args.GetKeyValue("user"),
                            pwd=args.GetKeyValue("pwd"),
                            namespace="vim25/5.5")
    with connection as si:
        # Process command line
        vmname = args.GetKeyValue("vmname")
        vm = folder.Find(vmname)
        if vm == None:
            print "Could not find VM", vmname
            sys.exit(1)
        print SerializeToConfig(vm.config, tag="configInfo")


# Start program
if __name__ == "__main__":
    main()
