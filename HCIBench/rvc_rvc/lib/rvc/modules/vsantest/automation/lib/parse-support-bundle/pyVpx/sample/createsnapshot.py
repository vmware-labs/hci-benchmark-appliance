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
                     (["v:", "vmname="], "", "Name of the virtual machine",
                      "vmname"),
                     (["d:", "snapshotdesc="], "Quick Dummy",
                      "Snapshot description", "snapshotdesc"),
                     (["s:", "snapshotname="], "TestSnapshot",
                      "Name of the snapshot", "snapshotname")]

    supportedToggles = [(["usage",
                          "help"], False, "Show usage information", "usage"),
                        (["dontDelete",
                          "d"], False, "Dont delete created snapshot", "del")]

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
    snapshotname = args.GetKeyValue("snapshotname")
    snapshotdesc = args.GetKeyValue("snapshotdesc")
    doDelete = not args.GetKeyValue("del")
    if len(vmname) == 0 or len(snapshotname) == 0:
        args.Usage()
        sys.exit(0)

    aVm = folder.FindPrefix(vmname)[0]
    task = aVm.CreateSnapshot(snapshotname,
                              snapshotdesc,
                              memory=False,
                              quiesce=False)
    snap = aVm.GetSnapshot().currentSnapshot
    print "Snapshot: %s" % repr(snap)
    if doDelete:
        print "Waiting for snapshot to be created: %s ..." % repr(snap)
        WaitForTask(task)
        print "Snapshot created. Removing ..."
        vm.RemoveSnapshot(snap)


# Start program
if __name__ == "__main__":
    main()
