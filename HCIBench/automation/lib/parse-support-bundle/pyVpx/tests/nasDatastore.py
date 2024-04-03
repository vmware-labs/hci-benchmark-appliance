#!/usr/bin/python

from __future__ import print_function

import sys
import os
import time
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import Vim,VmomiSupport,Vmodl
from pyVim import vm, host
from pyVim import arguments
import atexit
from pyVim.task import WaitForTask
from pyVim import vmconfig
from pyVim import invt
from pyVim import vimutil

#
# Helper routine to create a NAS Datastore on the host
#
def CreateNasDs(dsName, remoteHost, remotePath, invalidType = False, accessMode=''):
    try:
        print("Creating NAS datastore " + dsName + " ...")
        spec = Vim.Host.NasVolume.Specification()
        if not accessMode:
            spec.SetAccessMode("readWrite")
        else:
            spec.SetAccessMode(accessMode)
        spec.SetLocalPath(dsName)
        spec.SetRemoteHost(remoteHost)
        spec.SetRemotePath(remotePath)
        if invalidType == True:
            spec.SetType("cifs")
        print(spec)

        nasDs = datastoreSystem.CreateNasDatastore(spec)
        if nasDs == None or nasDs.GetSummary().GetName() != dsName:
            print("Failed to create datastore")
            return None
        else:
            print("Successfully created datastore " + dsName)
            return nasDs
    except Exception as e:
        print("Failed to create datastore %s" % e)
        return None


#
# Helper routine to clean up dangling nfs mounts and datastores
#
def Cleanup(remoteHost, remotePath, localPath):
    os.system("umount " + localPath)
    url = remoteHost + ":" + remotePath
    for datastore in datastoreSystem.GetDatastore():
        if datastore.GetSummary().GetUrl() == url:
            datastore.Destroy()
            break

def TestCleanupLocks(dsName, remoteHost, remotePath):
    print("Create datastore ... ")
    ds = CreateNasDs(dsName, remoteHost, remotePath)
    if (not ds):
        raise Exception("TestCleanLocks datastore create failed with " + dsName)

    print("create vm")
    vmName = "testvm2"
    vm1 = vm.CreateQuickDummy(vmname=vmName, datastoreName=dsName)
    if (not vm1) :
        raise Exception("TestCleanLocks vm cannot be created " + vmName)
    print("create vm done")

    print("test remove file locks with vm ... ")
    try:
        vimutil.InvokeAndTrack(ds.CleanupLocks)
    except Vim.Fault.ResourceInUse as e:
        print("TestCleanupLocks with vm test succeeded with " + str(e))
    except Exception as e:
        print("TestCleanupLocks with vm failed with incorrect exception " + str(e))
    else:
        raise Exception("TestCleanupLocks with vm failed because write action is allowd on read-only volume")

    print("destroy vm")
    vm.Delete(vm1)
    print("destory vm done")

    print("test remove locks on datastore or subdirectory")
    try:
        vimutil.InvokeAndTrack(ds.CleanupLocks)
        print("TestCleanLocks positive test succeeds")
        vimutil.InvokeAndTrack(ds.CleanupLocks, "something")
        print("TestCleanLocks positive subdir test succeeds")
    except Exception as e:
        raise Exception("TestCleanLocks positive test failed " + str(e))
    finally:
        datastoreSystem.RemoveDatastore(ds)

    print("Create datastore ")
    ds = CreateNasDs(dsName, remoteHost, remotePath, accessMode="readOnly")
    if (not ds):
        raise Exception("TestCleanLocks readly datastore create failed with " + dsName)
    "Create datastore done"

    print("test remove locks with read permission")
    try:
        vimutil.InvokeAndTrack(ds.CleanupLocks)
    except Vim.Fault.InaccessibleDatastore as e:
        print("TestCleanupLocks readonly test succeeded, with exception " + str(e))
    except Exception as e:
        print("TestCleanupLocks readonly test failed with incorrect exception " + str(e))
    else:
        raise Exception("TestCleanupLocks readonly test failed because write action is allowd on read-only volume")
    finally:
        datastoreSystem.RemoveDatastore(ds)

    print("Test remove locks on vmfs")
    try:
        vmds = [ds for ds in datastoreSystem.datastore
                if isinstance(ds.info, Vim.Host.VmfsDatastoreInfo)]
        vimutil.InvokeAndTrack(vmds[0].CleanupLocks)
        print("TestCleanLocks positive test on vmfs " + vmds[0].summary.name + " succeeds")
    except Exception as e:
        raise Exception("TestCleanLocks positive test on vmfs failed " + str(e))

#
# Helper routine to mount an NFS volume on the host
#
def MountNFS(remoteHost, remotePath, localPath):
    mkdircmd = "mkdir -p "
    os.system(mkdircmd + localPath)
    os.system("mount " + remoteHost + ":" + remotePath + " " + localPath)
    print("Mounted NFS Volume")


def main():
    supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                      (["u:", "user="], "root", "User name", "user"),
                      (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                      (["d:", "dsName="], "nas", "Name for the NAS datastore", "dsName"),
                      (["r:", "remotePath="], "/vol/vol0/home/ISO-Images", "Remote volume backing for the Datastore", "remotePath"),
                      (["s:", "remoteHost="], "exit15.eng.vmware.com", "Remote server for the NAS mount", "remoteHost"),
                      (["l:", "localPath="], "/tmp", "Local directory for NAS mounts", "localPath"),
                      (["n:", "newName="], "foo", "Alternative name for the local datastore", "newName"),
                      (["i:", "numiter="], "1", "Number of iterations", "iter") ]

    supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage")]

    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
    if args.GetKeyValue("usage") == True:
        args.Usage()
        sys.exit(0)

    # Process command line
    dsName = args.GetKeyValue("dsName")
    numiter = int(args.GetKeyValue("iter"))
    remotePath = args.GetKeyValue("remotePath")
    localPath = args.GetKeyValue("localPath")
    remoteHost = args.GetKeyValue("remoteHost")
    newName = args.GetKeyValue("newName")

    # Connect
    si = SmartConnect(host=args.GetKeyValue("host"),
                      user=args.GetKeyValue("user"),
                      pwd=args.GetKeyValue("pwd"))
    atexit.register(Disconnect, si)

    hostSystem = host.GetHostSystem(si)
    hostConfigManager = hostSystem.GetConfigManager()
    global datastoreSystem
    datastoreSystem = hostConfigManager.GetDatastoreSystem()

    i = 0
    while i < numiter:
        print("Current Datastore list: ")
        datastoreList = hostSystem.GetDatastore()
        print(datastoreList)

        print("Running Positive tests for nas datastores")
        try:
            TestCleanupLocks(dsName, remoteHost, remotePath)

            # Add a NAS datastore
            MountNFS(remoteHost, remotePath, localPath)
            nasDs = CreateNasDs(dsName, remoteHost, remotePath)
            if nasDs == None:
                raise Exception("Failed to create datastore")

            # Print datastore information
            dsInfo = nasDs.GetInfo()
            print("Datastore info:")
            print(dsInfo)
            print("Datastore summary:")
            print(nasDs.GetSummary())
            dsPath = dsInfo.GetUrl()

            # Rename the datastore
            print("Renaming the datastore to " + newName)
            nasDs.Rename(newName)
            if nasDs.GetInfo().GetName() != newName:
                raise Exception("Failed to rename datastore")
            print("Datastore summary after rename: ")
            print(nasDs.GetSummary())

            # Refresh the datastore after unmounting it
            os.system("umount " + localPath)
            nasDs.Refresh()
            if nasDs.GetSummary().GetAccessible() != False:
                raise Exception("Failed to refresh datastore state as inaccessible")
            print("Refreshed Datastore state as inaccesible")
            print(nasDs.GetSummary())

            # Remove the datastore
            print("Removing datastore...")
            nasDs.Destroy()
            datastoreList = hostSystem.GetDatastore()
            for dsRef in datastoreList:
                if dsRef.GetSummary().GetName() == dsName:
                    raise Exception ("Failed to remove datastore")
            print("Datastore list after removal: ")
            print(datastoreList)

        except Exception as e:
            print(e)
            Cleanup(remoteHost, remotePath, localPath)
            return

        print("Positive tests for nas datastores: PASS")
        print("Negative tests for nas datastores")

        # Add a datastore with a name clash
        MountNFS(remoteHost, remotePath, localPath)
        nasDs = CreateNasDs(dsName, remoteHost, remotePath)
        if nasDs == None:
            return
        if CreateNasDs(dsName, remoteHost, remotePath) != None:
            print("Created datastore with clashing name")
            return
        print("Datastore with clashing name was rejected")

        # Add a datastore with a backing clash
        if CreateNasDs(newName, remoteHost, remotePath) != None:
            print("Created datastore with clashing backing")
            return
        print("Datastore with clashing backing was rejected")

        nasDs.Destroy()
        # Add a datastore with an invalid mount
        if CreateNasDs(dsName, "dummyServer", "dummyShare") != None:
            print("Created datastore with an invalid backing")
            return
        print("Datastore with invalid backing was rejected")


        # Add a datastore with an invalid filesystem type
        if CreateNasDs(dsName, remoteHost, remotePath, True) != None:
            print("Created datastore with an invalid file system type")
            return
        print("Datastore with invalid file system type was rejected")


        # Add a datastore with an invalid name
        invalidName = "[This is an invalid name]"
        if CreateNasDs(invalidName, remoteHost, remotePath) != None:
            print("Created datastore with invalid name")
            return
        print("Datastore with invalid name was rejected")

        # Cleanup
        Cleanup(remoteHost, remotePath, localPath)
        print("Negative tests for nas datastores: PASS")
        i = i+1

# Start program
if __name__ == "__main__":
    main()

