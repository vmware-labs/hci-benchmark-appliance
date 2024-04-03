#!/usr/bin/python

# Copyright 2015-2020 VMware, Inc.  All rights reserved.
# -- VMware Confidential

#usage: $VMTREE/vim/py/py.sh $VMTREE/vim/py/tests/storagePerfBench/storageBenchPhyhost.py -h <hostIP/VCIP>  -p <password> -t <test>
#example:
#../../py.sh storageBenchPhyhost.py -h 10.133.251.5 -u 'Administrator@vsphere.local' -p 'Admin!23' -t storageSystem

#This is a performance test script
# The purpose of this script is to test the latency of following APIs
#2 datastoreSystem APIs
# datastoreSystem.CreateVmfsDatastore
# datastoreSystem.RemoveDatastore
#./vimbase/apiref/vim-apiref/vim.host.DatastoreSystem.html
#refer: datastoreSystem.RemoveDatastoreEX

#5 storageSystem APIs
# UnmountVmfsVolume (P0: Batch API: UnmountVmfsVolumeEx, P1: Non-batch API)
# MountVmfsVolume (P0: Batch API: MountVmfsVolumeEx, P1: Non-batch API)
# DetachScsiLun (P0: Batch API: DetachScsiLunEx, P1: Non-batch API)
# AttachScsiLun (P0: Batch API: AttachScsiLunEx, P1: Non-batch API)
# DeleteScsiLunState
# QueryUnresolvedVmfsVolume (LiveFsCheck disabled mode).

#2 defined in /storage-main.perforce.1666/bora/lib/vmkctl/storage/UnresolvedVmfsVolumeImpl.cpp
# ResolveVolume

from __future__ import print_function

import pyVmomi  #need export VMBLD=release
from pyVmomi import Vim, VmomiSupport, Vmodl
from pyVmomi.VmomiSupport import newestVersions
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import host, vm, folder, invt
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
from pyVim.invt import GetEnv
from pyVmomi.VmomiSupport import newestVersions
from datetime import datetime
import atexit
import sys, getopt, re, copy, random
import os, time

debug = 0

def RemoveDatastores():
    sw = StopWatch()
    for ds in vmfsDs:
        dsname = ds.info.name
#easy to fail, try multiple times, most QE try 12 times(PR1457852, PR1422995)
        retry = 0
        while retry < 1 : # can try 12 if needed
            bt = time.time()
            try:
                datastoreSystem.RemoveDatastore(ds)
            except Exception as obj:
                print("try %d Failed to delete datastore: %s : Error Msg: %s"
                      % (retry, ds, obj))
            else:
                print("remove " + dsname + " took " + str(time.time() - bt) + " sec.")
                break
            retry += 1
#note: calculate individual latency may affect the overall latency
    sw.finish(" removing all datastores")

def RemoveDatastoresEx():
    if len(vmfsDs) == 0:
        print("no interested datastore found!")
        return
    sw = StopWatch()
    #./vimbase/apiref/vim-apiref/vim.host.DatastoreSystem.html
    task = datastoreSystem.RemoveDatastoreEx(vmfsDs)
    #not sure if datastore is refreshing, it worked.
    WaitForTask(task)
    sw.finish(" remove VMFS datastoreEX")

#SideEffects : Creates Datastores on availableDisks
#so better make sure remove all datastore before begin
def CreateDatastores(availableDisks):
    i = 0;
    sw = StopWatch()
    for availableDisk in availableDisks:
        createOptions=datastoreSystem.QueryVmfsDatastoreCreateOptions(availableDisk.deviceName)
        for createOption in createOptions:
           if type(createOption.info) == Vim.Host.VmfsDatastoreOption.AllExtentInfo:
              i = i + 1
              createOption.info.layout.partition[0].end.block /= random.choice([2,3,4,5,6])
              diskPartInfo = storageSystem.ComputeDiskPartitionInfo(availableDisk.devicePath, createOption.info.layout);
#             Assign DS Name and Set the adjusted partition size
#              createOption.spec.vmfs.volumeName="ds_%s" % i
              createOption.spec.vmfs.volumeName="ds_%04d" % i
              print("Creating datastore %s" % createOption.spec.vmfs.volumeName)
              createOption.spec.partition = diskPartInfo.spec
              bt = time.time()
              try:
                  ds = datastoreSystem.CreateVmfsDatastore(createOption.spec)
              except Exception as e:
                  print("Unable to create Datastore. Error: %s " % e)
              print("create one datastore took " + str(time.time() - bt) + " sec.")
    sw.finish("  create all datastores")

def PrintDatastoreNames():
    for ds in datastoreSystem.datastore:
       print(ds.info.name)

def UnmountVolumes():
    sw = StopWatch()
    task = storageSystem.UnmountVmfsVolumeEx(volumeUUIDs)
    WaitForTask(task)
    sw.finish(" unmount VMFS volumes") #TODO add str(len(volumeUUIDs))
    time.sleep(60) # rest a bit, in case un-expected things happens to do next op

def DetachLuns():
    sw = StopWatch()
    task = storageSystem.DetachScsiLunEx(lunUUIDs)
    WaitForTask(task)
    sw.finish(" detach LUNs")
    time.sleep(60)

def AttachLuns():
    sw = StopWatch()
    task = storageSystem.AttachScsiLunEx(lunUUIDs)
    WaitForTask(task)
    sw.finish(" attach LUNs")
    time.sleep(360) # tried 180 still not enough

def MountVolumes():
    sw = StopWatch()
    task = storageSystem.MountVmfsVolumeEx(volumeUUIDs)
    WaitForTask(task)
    sw.finish(" mount VMFS volumes")
    time.sleep(60)

def RescanVmfs():
    sw = StopWatch()
    storageSystem.RescanVmfs()
    #task = storageSystem.RescanVmfs()
    #WaitForTask(task)  #if si is None:  si = Vim.ServiceInstance("ServiceInstance", task._stub)
    #AttributeError: 'NoneType' object has no attribute '_stub'
    #we cannot measure latency use task here. Jus measure directly.
    #This function call is helpful!
    #../py.sh storagePerfBench/storageBenchPhyhost.py -h 10.133.251.208  -u 'root' -p '' -t rescanVmfs

    sw.finish("rescan VMFS")
    time.sleep(60)

def RescanHBA():
    sw = StopWatch()
    storageSystem.RescanHba("vmhba2") #TODO: need pass in an adapater,let me hardcode first.
    sw.finish("rescan ")

def testVMSpec():
    sw = StopWatch()
    envBrowser = GetEnv()
    sw.finish("getEnv")

    sw = StopWatch()
    cfgOption = envBrowser.QueryConfigOption(None, None)
    sw.finish("queryConfigOption")

    sw = StopWatch()
    cfgTarget = envBrowser.QueryConfigTarget(None)
    sw.finish("queryConfigTarget")

    sw = StopWatch()
#    vmSpec = Vim.Vm.ConfigSpec()
#    vmSpec = vmconfig.AddScsiCtlr(vmSpec, cfgOption, cfgTarget)
#    print(vmSpec)
    sw.finish("testVMSpec")

def QueryUnresolvedVmfsVolume():
    if debug:
        print(" Calling QueryUnresolvedVmfsVolume() API")
    sw = StopWatch()
    vols[:] = storageSystem.QueryUnresolvedVmfsVolume()
    sw.finish(" query unresolved Vmfs Volumes")
    print("Found " + str(len(vols)) + " number of unresolved volumes.")

#### put functions for getlun, get mount, get disk in following ####
#lunUUIDs is used in detach/attach, volumeUUIDs used in unmount/mount
#scsiLunUUIDs just for research.
def getLuns():
    luns = storageSystem.storageDeviceInfo.scsiLun #'NoneType' object has no attribute 'scsiLun'    #after replace the host under VC, this issue solved
    print("1. Found " + str(len(luns)) + " number of Luns.")

    global lunUUIDs
    lunUUIDs = [] #global lunUUIDs = [] #Syntax error, so separate.
    for lun in luns:
        lunUUID = lun.GetUuid()    #where to find doc of GetUUID?
        if debug:
            print(lunUUID + "lunUUID\n")
          #02000500006006016027f02a006ba30d6e8c2ae5114449534b2020
        if lunUUID.find("6006") != -1:
            lunUUIDs.append(lunUUID)  #be careful when setup changes
    print("2. Found " + str(len(lunUUIDs)) + " number of interest LunUUIDs.")

    scsiLunUUIDs = []  #just test, haven't called elsewhere.
    for lun in luns:
        if type(lun) == Vim.Host.ScsiDisk:
            scsiLunUUIDs.append(lun.GetUuid())
    print("3. Found " + str(len(scsiLunUUIDs)) + " numer of scsiLunUUIDs.")

def getVolumes():
    mounts = storageSystem.GetFileSystemVolumeInfo().GetMountInfo()
    print("4. Found " + str(len(mounts)) + " number of mounts.")

    global volumeUUIDs
    volumeUUIDs = []
    for mount in mounts:
        volume = mount.GetVolume()
        #print(volume.GetUuid()) #will error, not all volume can GetUuid here
        if isinstance(volume, Vim.Host.VmfsVolume):
            volumeUUID = volume.GetUuid()
            if debug:
                print(volumeUUID)
            #like:4e3707d2-e59a92d5-e70b-d485644ad8d4-->storage1
            #if volumeUUID.find("4e3707d2") == -1:  #this not good, other host storage1 not this     name
            #if volumeUUID.find("00151716d56a") != -1:
            # must .find() != -1  or ==-1
            #the content to find will be changing everytime remove/create datastore
            # and datastore1 always have same value, trouble
            #TODO:research ways find volume according to datastore name
            if volumeUUID.find("d4ae52e93f79") != -1:
                volumeUUIDs.append(volumeUUID)
    print("5. Found " + str(len(volumeUUIDs)) + " number of interested VMFS volumes.")

def getDisks():
    availableDisks = datastoreSystem.QueryAvailableDisksForVmfs()
    print("6. Found " + str(len(availableDisks))+ " number of availableDisks.")
    global diskIDs
    diskIDs = []
    for availableDisk in availableDisks:
        #availableDisk.deviceName:
        #/vmfs/devices/disks/naa.6006016027f02a00e38a258e8c2ae5
        if debug:
            print("availableDisk.deviceName: " + availableDisk.deviceName)
        #specific to physical SAN setup, where naa.6006* is what we want, not naa.6005
        if availableDisk.deviceName.find("naa.6006") != -1:
            diskIDs.append(availableDisk)
    print("7. Found "+ str(len(diskIDs)) + " number of disks to create datastore.")

def getDS():
    allDS = datastoreSystem.datastore
    print("8. Found " + str(len(allDS)) + " number of all datastores.")
    global vmfsDs
    vmfsDs = []
    for ds in allDS:
        if debug:
            print("ds inforation:" + ds)
        if (ds.info.name[0:len("ds_")] == "ds_"):
            vmfsDs.append(ds)
    print("9. Found " + str(len(vmfsDs)) + " number of interested datrastores.")

    #TODO: we can implement more here
    #Following is temparory hack since current remove/create datastore too slow
    n = 4
    selectedDSname = ["ds_0001", "ds_0002", "ds_0003", "ds_0004"]
    selectedDS = []
    for ds in vmfsDs:
         if (ds.info.name in selectedDSname):
             selectedDS.append(ds)
    #vmfsDs = selectedDS #give back to vmfsDs, so they can call

def main():
    supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                    (["u:", "user="], "root", "User name", "user"),
                    (["p:", "pwd="], "", "password", "pwd"),
                    (("t:", "test="), "all", "test Options", "test")
                    ]

    supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage") ]

    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
    if args.GetKeyValue("usage") == True:
       args.Usage()
       sys.exit(0)

    '''
    si = Connect(host=args.GetKeyValue("host"),  #can be VC too
                 user=args.GetKeyValue("user"),
                 pwd=args.GetKeyValue("pwd"),
                 version=newestVersions.GetName('vim'))
                 '''
    si = SmartConnect(host=args.GetKeyValue("host"), user=args.GetKeyValue("user"), pwd=args.GetKeyValue("pwd"))

    atexit.register(Disconnect, si)

    global datastoreSystem
    datastoreSystem = host.GetHostConfigManager(si).GetDatastoreSystem()

    global storageSystem
    storageSystem = host.GetHostConfigManager(si).GetStorageSystem()
    test = args.GetKeyValue("test")
#    print(storageSystem.storageDeviceInfo)

    if test == "printDS":
        PrintDatastoreNames()

    if test == "getLuns":
        getLuns()
    if test == "getVolumes":
        getVolumes()
    if test == "getDisks":
        getDisks()
    if test == "getDS":
        getDS()
    if test == "getAll":
        getLuns()
        getVolumes()
        getDisks()
        getDS()
    if test == "testVMSpec":
        testVMSpec()

    if test == "datastoreSystem":
        getDS()
        RemoveDatastores()
        getDisks()
        CreateDatastores(diskIDs)
        if debug: PrintDatastoreNames()
        pass # for Syntax check in case uncommneted all the up function call
    #separate different API calls, error prone if test them all together.
    if test == "storageSystem":
        getLuns()
        getVolumes()
        UnmountVolumes()  # must run this twice to successfully do detach
        UnmountVolumes()
        UnmountVolumes()
        UnmountVolumes()
        UnmountVolumes()
        DetachLuns()
        AttachLuns()
        MountVolumes()#must run twice for the host really see the mounts, i.e.
#i.e.      able to see all  ls /vmfs/volume
        MountVolumes()
        pass

    if test == "all":
        getLuns()
        getVolumes()
        getDisks()
        RemoveDatastores()
        CreateDatastores(diskIDs)
        UnmountVolumes()  # must run this twice to successfully do detach
        UnmountVolumes()
        DetachLuns()
        AttachLuns()
        MountVolumes()#must run twice for the host really see the mounts
        MountVolumes()

    if test == "removeDS":
        getDS()
        RemoveDatastores()

    if test == "createDS":
        getDisks()
        CreateDatastores(diskIDs)

    if test == "unmount":
        getVolumes()
        UnmountVolumes()
        UnmountVolumes()
        pass
    if test == "detach":
        print("Going to detach, make sure the volumes are unmounted first.")
        getLuns()
        DetachLuns()
        pass
    if test == "attach":
        getLuns()
        AttachLuns()
        pass
    if test == "mount":
        getVolumes()
        MountVolumes()
        MountVolumes()
        pass
    if test == "rescanVmfs":
        RescanVmfs()
    if test == "rescanHBA":
        RescanHBA()

    if test == "extra":
        global vols
        vols = []
        QueryUnresolvedVmfsVolume()

#Start Program !!!
if __name__ == "__main__":
   main()
