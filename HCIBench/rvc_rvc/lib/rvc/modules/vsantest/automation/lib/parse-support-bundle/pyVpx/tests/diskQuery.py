#!/usr/bin/python

###
###  Simple script for testing DatastoreBrowser search functionality
###  for virtual disks.
###

from __future__ import print_function

import sys
from pyVim import vm
from pyVim import host
from pyVim import arguments
from pyVim.connect import Connect, Disconnect
from pyVmomi import Vim,VmomiSupport
from pyVim import vm, host
import atexit

def main():
    supportedArgs = [(["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd") ]

    supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage") ]

    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
    if args.GetKeyValue("usage") == True:
        args.Usage()
        sys.exit(0)

    # Connect
    si = Connect(host=args.GetKeyValue("host"),
                 user=args.GetKeyValue("user"),
                 pwd=args.GetKeyValue("pwd"),
                 version="vim.version.version9")
    atexit.register(Disconnect, si)

    hostSystem = host.GetHostSystem(si)
    datastores = hostSystem.GetDatastore()
    datastoreBrowser = hostSystem.GetDatastoreBrowser()

    # Find a suitable datastore to invoke the search on
    if datastores == None or len(datastores) == 0:
        print("No datastores found on this host. Exiting..")
        sys.exit(1)

    dsName = "[" + datastores[0].GetSummary().GetName() + "]"
    print("Using datastore " + dsName)

    # Construct the search spec
    searchSpec = Vim.Host.DatastoreBrowser.SearchSpec()
    queries = []
    query = Vim.Host.DatastoreBrowser.VmDiskQuery()
    diskType = []
    diskType.append(Vim.Vm.Device.VirtualDisk.FlatVer2BackingInfo)
    diskType.append(Vim.Vm.Device.VirtualDisk.FlatVer1BackingInfo)
    hwVersion = []
    hwVersion.append(3)
    hwVersion.append(4)
    hwVersion.append(7)

    # Construct the disk filter
    diskFilter = Vim.Host.DatastoreBrowser.VmDiskQuery.Filter()
    diskFilter.SetDiskType(diskType)
    diskFilter.SetMatchHardwareVersion(hwVersion)
    query.SetFilter(diskFilter)

    # Specify the disk details requested
    diskDetails = Vim.Host.DatastoreBrowser.VmDiskQuery.Details()
    diskDetails.SetDiskType(True)
    diskDetails.SetCapacityKb(True)
    diskDetails.SetHardwareVersion(True)
    diskDetails.SetDiskExtents(True)
    diskDetails.SetControllerType(True)
    diskDetails.SetThin(True)
    query.SetDetails(diskDetails)

    queries.append(query)
    searchSpec.SetQuery(queries)
    searchSpec.SetSearchCaseInsensitive(True)
    searchSpec.SetSortFoldersFirst(True)

    # Specify disk patterns to match
    match = []
    match.append("*.vmdk")
    match.append("*.dsk")
    searchSpec.SetMatchPattern(match)

    # Specify the file details requested
    fileDetails = Vim.Host.DatastoreBrowser.FileInfo.Details()
    fileDetails.SetFileType(True)
    fileDetails.SetFileSize(True)
    fileDetails.SetModification(True)
    fileDetails.SetFileOwner(True)
    searchSpec.SetDetails(fileDetails)

    # Invoke the search
    searchTask = datastoreBrowser.SearchSubFolders(dsName, searchSpec)
    searchError = searchTask.GetInfo().GetError()
    if searchError != None:
        print("Error encountered during search: ")
        print(searchError)
    else:
        searchResults = searchTask.GetInfo().GetResult()
        print(searchResults)


# Start program
if __name__ == "__main__":
    main()
