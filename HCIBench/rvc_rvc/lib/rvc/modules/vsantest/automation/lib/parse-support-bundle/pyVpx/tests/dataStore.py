#!/usr/bin/python
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file vm.py --
# Integration Test Subsystem
# Virtual Machine Management Operations

from __future__ import print_function

__author__ = "VMware, Inc"

import sys
from pyVmomi import Vim, VmomiSupport
from pyVim import host, connect;
import os, time
import random
import atexit

RemoveAllDataStores = False;
RemoveTestDataStores = True;
RemoveLocalDataStores = False;
testStorageSystem = False;
testCompute = True;
testResize = False;
testCreate = True;
testExpand = False;
testExtend = False;
delayBeforeDiskUpdates = 0 #60

si = connect.Connect('mckinley187', 443, 'root', 'ca$hc0w', "hostd", "SOAP", "vim25/5.5");
atexit.register(connect.Disconnect, si)
hostSystem = host.GetHostSystem(si);
configMgr = host.GetHostConfigManager(si);
dataStoreSystem = configMgr.GetDatastoreSystem();
storageSystem = configMgr.GetStorageSystem();

def RemoveDataStores():
	for ds in dataStoreSystem.datastore:
		print(ds.info.name)
#		print(ds.host)
		vmfsFileSystemInfos = [ fileSystemMountInfo
		for host in ds.host
			for fileSystemMountInfo in storageSystem.fileSystemVolumeInfo.mountInfo
				if fileSystemMountInfo.mountInfo.path == host.mountInfo.path
					and fileSystemMountInfo.volume.type=='VMFS'
		];
#		print(vmfsFileSystemInfos)
#		Possible Duplicates in device paths for multiple extents on the same disk
		datastoreVmfsDevicePaths = [ "/vmfs/devices/disks/%s" % extent.diskName
			for mi in vmfsFileSystemInfos
				for extent in  mi.volume.extent
		];
		print(datastoreVmfsDevicePaths)
		datastoreDiskPartitionInfos = [
			storageSystem.RetrieveDiskPartitionInfo(datastoreVmfsDevicePath)
				for datastoreVmfsDevicePath in datastoreVmfsDevicePaths
		];
#		print(datastoreDiskPartitionInfos)
		try:
#			Remove Datastores based on the RemoveDatastore flags set
			if (RemoveAllDataStores or
			(RemoveLocalDataStores and len(vmfsFileSystemInfos) != 0) or
			(RemoveTestDataStores and (ds.info.name [0:len("ds:")] == "ds:"))):
				time.sleep(delayBeforeDiskUpdates);
				dataStoreSystem.RemoveDatastore(ds);
#			storageSystem.RescanVmfs();
#			storageSystem.Refresh();
#			print(os.popen ("ssh root@mckinley183 /usr/sbin/vmkfstools -V").read())
		except Exception as obj:
			print("Failed to delete datastore: %s : Error Msg: %s" % (ds, obj))
		else:
			pass;

#SideEffects : Creates Data stores on availableDisks
def CreateDataStores(availableDisks):
	i = 0;
	for availableDisk in availableDisks:
		createOptions=dataStoreSystem.QueryVmfsDatastoreCreateOptions(availableDisk.deviceName);
		for createOption in createOptions:
#			print("Create Option Obtained: %s" % createOption)
#			Using only All Disk options for simplicity of creation
			if type(createOption.info) == Vim.Host.VmfsDatastoreOption.AllExtentInfo:
				i = i+1;
				createOption.info.layout.partition[0].end.block /= random.choice([2,3,4,5,6]);
				diskPartInfo = storageSystem.ComputeDiskPartitionInfo(availableDisk.devicePath, createOption.info.layout);
#				diskPartInfo = storageSystem.ComputeDiskPartitionInfoForResize(createOption.spec.extent, createOption.info.vmfsExtent );
#				print(diskPartInfo)
#				Assign DS Name and Set the adjusted partition size
				createOption.spec.vmfs.volumeName="ds:%s" % i;
				createOption.spec.partition = diskPartInfo.spec;
#				print("Create Option being used: %s" % createOption)
				if testStorageSystem == True:
					for device in storageSystem.storageDeviceInfo.scsiLun:
#						print(device)
#						print(diskPartInfo)
						if device.deviceName == diskPartInfo.deviceName:
							try:
								time.sleep(delayBeforeDiskUpdates);
								storageSystem.UpdateDiskPartitions(device.deviceName, diskPartInfo.spec)
#								print(storageSystem.RetrieveDiskPartitionInfo(device.deviceName))
							except Exception as e:
								print("Failed to Update Disk Partition %s:%s. Skipping Create Datastore using StorageSystem API. Msg: %s" % (device.deviceName, diskPartInfo.partition.partition, e))
								continue;
							try:
								vmfsExtent = createOption.spec.vmfs.extent
								print("Formatting Extent on disk %s partition %d of Datastore: %s" % (vmfsExtent.diskName, vmfsExtent.partition, createOption.spec.vmfs.volumeName))
								vmfsvolume = storageSystem.FormatVmfs(createOption.spec.vmfs);
							except Exception as e:
								print("Failed to Format VMFS volume: %s" % e)
								continue;

					ds = [d for d in dataStoreSystem.datastore][0];
					for extent in createOption.spec.extent:
						try:
							storageSystem.AttachVmfsExtent(ds.host[0].mountInfo.path, extent);
						except Exception as e:
							print("Failed to Attach Extent: %s:%d on Datastore: %s Error Msg: %s" % (extent.diskName, extent.partition, ds,e))
				else:
					try:
						time.sleep(delayBeforeDiskUpdates);
						ds = dataStoreSystem.CreateVmfsDatastore(createOption.spec);
#						storageSystem.RescanVmfs();
					except Exception as e:
						print("Unable to create Datastore. Error: %s " % e)
						pass;

def PrintDataStoreNames():
	for ds in dataStoreSystem.datastore:
		print(ds.info.name)

def ExtendDataStores():
	for ds in dataStoreSystem.datastore:
	        if ds.info.name [0:len("ds:")] == "ds:":
			print("For Datastore : %s"  % ds.info.name)
			disks = dataStoreSystem.QueryAvailableDisksForVmfs(ds);
			for disk in disks:
				print("for Disk : %s" % disk.devicePath)
	#			print("Disk Layout Before Expansion: %s" % storageSystem.RetrieveDiskPartitionInfo(disk.deviceName))
				try:
					unsuppressedExtendOptions = dataStoreSystem.QueryVmfsDatastoreExtendOptions(ds,disk.devicePath, False);
#					print("Unsuppressed Extend Options : %s" % unsuppressedExtendOptions)
				except Exception as e:
					print("Failed to get Unsuppressed Extend Options: %s" % e)
				extendOptions = [];
				try:
					extendOptions = dataStoreSystem.QueryVmfsDatastoreExtendOptions(ds,disk.devicePath, True);
#					print("Suppressed Extend Options : %s" % extendOptions)
				except Exception as e:
					print("Failed to get Suppressed Extend Options: %s" % e)
				for extendOption in extendOptions:
					if testExtend == True:
						if testCompute == True:
							try:
								diskPartInfo = storageSystem.ComputeDiskPartitionInfo(disk.devicePath, extendOption.info.layout);
								extendOption.spec.partition = diskPartInfo.spec;
								print("Extend Option Used: %s" % extendOption)
							except Exception as e:
								print("Failed to Compute Disk Partition.")
								if testStorageSystem == True:
									print("Warning: Computing Disk Partition Essential for Testing StorageSystem API to extend")
									print("Warning: Skipping Extend Option")
									continue;
							else:
								print("Using the original Spec for Extension")

						print("Extending with Suppressed Extend Option Datastore: %s" % ds.info.name)
						if testStorageSystem == True:
							for device in storageSystem.storageDeviceInfo.scsiLun:
								if device.deviceName == diskPartInfo.deviceName:
									try:
										time.sleep(delayBeforeDiskUpdates);
										storageSystem.UpdateDiskPartitions(device.deviceName, diskPartInfo.spec)
#										print(storageSystem.RetrieveDiskPartitionInfo(device.deviceName))
									except Exception as e:
										print("Failed to Update Disk Partition. Skipping Attach Extent.")
										continue;
									for extent in extendOption.spec.extent:
										print("Attaching Extent on disk %s partition %d of Datastore: %s" % (extent.diskName, extent.partition, ds.info.name))
										try:
											storageSystem.AttachVmfsExtent(ds.host[0].mountInfo.path, extent);
										except Exception as e:
											print("Failed to Attach Extent: %s:%d on Datastore: %s Error Msg: %s" % (extent.diskName, extent.partition, ds,e))
						else:
							try:
								time.sleep(delayBeforeDiskUpdates);
								dataStoreSystem.ExtendVmfsDatastore(ds, extendOption.spec);
							except Exception as e:
								print("Failed to extend Datastore: %s Error Msg: %s" % (ds, e))


def ExpandDatastores():
	for ds in dataStoreSystem.datastore:
	        if ds.info.name [0:len("ds:")] == "ds:":
			print("For Datastore : %s"  % ds.info.name)
			disks = dataStoreSystem.QueryAvailableDisksForVmfs(ds);
			expandOptions = dataStoreSystem.QueryVmfsDatastoreExpandOptions(ds);
			for expandOption in expandOptions:
#				print("Expand Option Obtained: %s" % expandOption)

				if testResize == True:
					expandOption.info.vmfsExtent.end.block /= 2;
				if testCompute == True:
					try:
						diskPartInfo = storageSystem.ComputeDiskPartitionInfoForResize(expandOption.spec.extent, expandOption.info.vmfsExtent );
						expandOption.spec.partition = diskPartInfo.spec;
#						print("Expand Option Used: %s" % expandOption)
					except Exception as e:
						print("Failed to Compute Disk Partition.")
						if testStorageSystem == True:
							print("Warning: Skipping Expand Option")
							continue;
						else:
							print("Warning: Using the original Spec for Expansion")
				else:
					if testStorageSystem == True:
						print("Computing Disk Partition Essential for Testing StorageSystem API to extend")
						print("Skipping Expand option")
						continue;

				if testStorageSystem == True:
					for device in storageSystem.storageDeviceInfo.scsiLun:
						if device.deviceName == diskPartInfo.deviceName:
	#					print(device)
							if testExpand == True:
								try:
									time.sleep(delayBeforeDiskUpdates);
									storageSystem.UpdateDiskPartitions(device.deviceName, diskPartInfo.spec)
#									print(storageSystem.RetrieveDiskPartitionInfo(device.deviceName))
								except Exception as e:
									print("Failed to Update Disk Partition. Skipping Expand")
									continue;
								print("Expanding Extent on disk %s partition %d of Datastore: %s" % (expandOption.spec.extent.diskName, expandOption.spec.extent.partition, ds.info.name))
								try:
									storageSystem.ExpandVmfsExtent(ds.host[0].mountInfo.path, expandOption.spec.extent);
								except Exception as e:
									print("Failed to Expand Extent: %s:%d on Datastore: %s Error Msg: %s" % (expandOption.spec.extent.diskName, expandOption.spec.extent.partition, ds,e))
				else:
					if testExpand == True:
						print("Expanding Datastore: %s. Targetting Disk %s partition %d" % (ds.info.name,expandOption.spec.extent.diskName, expandOption.spec.extent.partition))
						try:
							time.sleep(delayBeforeDiskUpdates);
							dataStoreSystem.ExpandVmfsDatastore(ds, expandOption.spec);
						except Exception as e:
							print("Failed to Expand Datastore %s for %s:%d Error Msg: %s" % (ds,expandOption.spec.extent.diskName, expandOption.spec.extent.partition, e))

	#			print("Disk Layout After Expansion: %s" % storageSystem.RetrieveDiskPartitionInfo(expandOption.spec.extent.diskName))

def ExpandVsanddatastore():
       vmfsDisks = dataStoreSystem.QueryAvailableDisksForVmfs()
       count = 0 #creating only one vsand datastore
       for device in vmfsDisks:
                  spec = dataStoreSystem.QueryVmfsDatastoreCreateOptions(devicePath=device.devicePath,vmfsMajorVersion=53)
                  fb = int(spec[0].info.layout.partition[0].end.block / 2)
                  spec[0].info.layout.partition[0].end.block = fb
                  diskPartInfo = storageSystem.ComputeDiskPartitionInfo(device.devicePath, spec[0].info.layout);
                  name = "VSAND-%s" % count
                  count = count + 1
                  spec[0].spec.partition = diskPartInfo.spec
                  spec[0].spec.vmfs.volumeName = name
                  dataStoreSystem.CreateVmfsDatastore(spec=spec[0].spec)
                  break
       for ds in dataStoreSystem.datastore:
                  if "VSAND" in ds.name:
                             print("Trying to expand the Datastore : %s"  % ds.info.name)
                             specs = dataStoreSystem.QueryVmfsDatastoreExpandOptions(ds)
                             for spec in specs:
                                        try:
                                                   dataStoreSystem.ExpandVmfsDatastore(ds, spec.spec);
                                        except Exception as e:
                                                   print("Unable to expand vsand type Datastore. Error: %s " % e)

RemoveDataStores();
PrintDataStoreNames();
luns = storageSystem.storageDeviceInfo.scsiLun;
disks = [lun for lun in luns if (type(lun) == Vim.Host.ScsiDisk) ]
print("Disks:\n%s" % "\n".join([disk.deviceName for disk in disks]))
availableDisks = dataStoreSystem.QueryAvailableDisksForVmfs();
print("Disks available for VMFS:\n%s" % "\n".join([d.deviceName for d in availableDisks]))
CreateDataStores(availableDisks)
PrintDataStoreNames();
ExpandVsanddatastore();
#ExtendDataStores()
#ExpandDatastores()
RemoveDataStores();
