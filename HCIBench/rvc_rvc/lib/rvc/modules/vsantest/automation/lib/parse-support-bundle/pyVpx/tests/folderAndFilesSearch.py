#!/usr/bin/python

###
###  Simple script for testing DatastoreBrowser search functionality
###  for files and folders.
###
from __future__ import print_function

import sys
import getopt
from pyVim import arguments
from pyVim.connect import Connect, Disconnect
from pyVmomi import Vim,VmomiSupport
from pyVim import vm, host
import atexit

def main():
    supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
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
                 pwd=args.GetKeyValue("pwd"))
    atexit.register(Disconnect, si)

    hostSystem = host.GetHostSystem(si)
    datastoreBrowser = hostSystem.GetDatastoreBrowser()
    datastores = hostSystem.GetDatastore()

    # Find a suitable datastore to invoke the search on
    if datastores == None or len(datastores) == 0:
        print("No datastores found on this host. Exiting..")
        sys.exit(1)

    dsName = "[" + datastores[0].GetSummary().GetName() + "]"
    print("Using datastore " + dsName)

    # Construct the Search Spec
    searchSpec = Vim.Host.DatastoreBrowser.SearchSpec()
    queries = []
    query = Vim.Host.DatastoreBrowser.Query()
    folderQuery = Vim.Host.DatastoreBrowser.FolderQuery()

    queries.append(folderQuery)
    queries.append(query)

    searchSpec.SetQuery(queries)
    searchSpec.SetSearchCaseInsensitive(True)
    searchSpec.SetSortFoldersFirst(True)

    fileDetails = Vim.Host.DatastoreBrowser.FileInfo.Details()
    fileDetails.SetFileType(True)
    fileDetails.SetFileSize(True)
    fileDetails.SetModification(True)
    fileDetails.SetFileOwner(True)

    searchSpec.SetDetails(fileDetails)
    print("Search spec:")
    print(searchSpec)

    # Invoke the search
    searchTask = datastoreBrowser.Search(dsName, searchSpec)
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
