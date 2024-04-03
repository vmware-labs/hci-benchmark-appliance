#!/usr/bin/python
"""
Python program for creating vms on a host on which hostd is running

Requirements:
 * pyVmomi, pyVim
 * Needs to be invoked with py.sh rather than regular python executable
 * The target host needs to be running hostd
"""

from optparse import OptionParser
from pyVim.connect import Connect
from pyVim import vm
from pyVmomi import Vim
from pyVim import folder


def GetOptions():
    """
    Supports the command-line arguments listed below.
    """

    parser = OptionParser()
    parser.add_option("-s", "--server", help="remote host to connect to")
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
                      default="",
                      help="Prefix of name for the virtual machine")
    (options, _) = parser.parse_args()
    return options


def getNiceSize(size):
    unitTypes = ["KB", "MB", "GB"]
    units = "bytes"
    #return "%.2f %s" % (size, units)
    for unitType in unitTypes:
        if size >= 1024:
            size = float(size) / 1024.0
            units = unitType
        else:
            return "%.2f %s" % (size, units)
    return "%.2f %s" % (size, units)


def main():
    """
    Simple command-line program for creating virtual machines on a
    system managed by hostd.
    """

    options = GetOptions()

    Connect(host=options.server, user=options.user, pwd=options.password)

    dsList = {}
    vms = folder.FindPrefix(options.vm_name)
    print("")
    print("---------------------------- ")
    print("Virtual machine information: ")
    print("---------------------------- ")
    for vm1 in vms:
        print("")
        vm1.RefreshStorageInfo()
        name = vm1.GetName()
        layoutEx = vm1.GetLayoutEx()
        storageInfo = vm1.GetStorage()
        storageSummary = vm1.GetSummary().GetStorage()
        print("Virtual machine name: " + name)
        print("Layout: (retrieved at %s)" % (str(layoutEx.GetTimestamp())))
        files = layoutEx.GetFile()
        print ("%-40s %-20s %20s" \
           % ("File name", "File type", "File size"))
        print ("%-40s %-20s %20s" \
           % ("---------", "---------", "---------"))
        for file in files:
            size = getNiceSize(file.size)
            print ("%-40s %-20s %20s" \
               % (file.name, file.type, size))

        print("")
        print("Summary: (retrieved at %s)" %
              str(storageSummary.GetTimestamp()))
        print ("Committed: %s\tUncommitted: %s\tUnshared: %s" \
           % (getNiceSize(storageSummary.committed), \
              getNiceSize(storageSummary.uncommitted), \
              getNiceSize(storageSummary.unshared)))
        print("")
        print ("Storage information: (retrieved at %s)" \
           % str(storageInfo.GetTimestamp()))

        usages = storageInfo.GetPerDatastoreUsage()
        print ("%-30s %25s %25s %20s" % ("Datastore name", "Committed", \
                                           "Uncommitted", "Unshared"))
        print ("%-30s %25s %25s %20s" % ("--------------", "---------", \
                                           "-----------", "--------"))
        for dsUsage in usages:
            print ("%-30s %25s %25s %20s" \
               % (dsUsage.datastore.summary.name, getNiceSize(dsUsage.committed),
                  getNiceSize(dsUsage.uncommitted), getNiceSize(dsUsage.unshared)))
            dsList[dsUsage.datastore.summary.name] = dsUsage.datastore
        print("")

    print("---------------------------------------------- ")
    print("Datastore information for affected datastores: ")
    print("---------------------------------------------- ")
    for ds in dsList:
        print("")
        dsList[ds].RefreshStorageInfo()
        info = dsList[ds].info
        freeSpace = info.freeSpace
        summary = dsList[ds].summary
        name = summary.name
        print("Datastore: %s (retrieved at %s)" %
              (name, storageInfo.timestamp))
        print ("Capacity %s\tFreespace: %s\tUncommitted: %s" \
           % (getNiceSize(summary.capacity), getNiceSize(summary.freeSpace), \
              getNiceSize(summary.uncommitted)))
        print("")


# Start program
if __name__ == "__main__":
    main()
