from __future__ import print_function

import sys
import time
from pyVmomi import Vim, VmomiSupport
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
from pyVim import host, connect;
import os, time
import random
import atexit

class ExtentTest:
   def __init__(self, si):
      self._si = si
      self._hostSystem = host.GetHostSystem(si)
      self._configMgr = host.GetHostConfigManager(si)
      self._storageSystem = self._configMgr.GetStorageSystem()
      self._datastoreSystem = self._configMgr.GetDatastoreSystem()

   def runTest(self):
	availableDisks = self._datastoreSystem.QueryAvailableDisksForVmfs();
	availableDisk=availableDisks[0]
	assert(availableDisk)
	print("Using disk: %s" % availableDisk.deviceName)
	createOptions=self._datastoreSystem.QueryVmfsDatastoreCreateOptions(availableDisk.deviceName)
	for createOption in createOptions:
		if type(createOption.info) == Vim.Host.VmfsDatastoreOption.AllExtentInfo:
			break
	assert(createOption)
	createOption.info.layout.partition[0].end.block /= random.choice([2,3,4,5,6])
	diskPartInfo = self._storageSystem.ComputeDiskPartitionInfo(availableDisk.devicePath, createOption.info.layout)
	createOption.spec.vmfs.volumeName="testVmfs"
	createOption.spec.partition = diskPartInfo.spec
	try:
		targetDs = self._datastoreSystem.CreateVmfsDatastore(createOption.spec)
	except Exception as e:
		print("Unable to create Datastore. Error: %s " % e)
		return 0
	assert(targetDs)
	print("Create Vmfs volume successfully. Using the same disk to create another partition")
	try:
		extendOptions = self._datastoreSystem.QueryVmfsDatastoreExtendOptions(targetDs,availableDisk.devicePath, False);
	except Exception as e:
		print("Failed to get Extend Options: %s" % e)
		return 0
	extendOption = extendOptions[0]
	assert(extendOption)
	try:
		self._datastoreSystem.ExtendVmfsDatastore(targetDs, extendOption.spec);
	except Exception as e:
		print("Failed to extend Datastore: %s Error Msg: %s" % (targetDs, e))
		return 0
	print("Extended Vmfs volume successfully on initial disk: %s"
              % availableDisk.deviceName)
	availableExtendDisks = self._datastoreSystem.QueryAvailableDisksForVmfs(targetDs)
	for availableExtendDisk in availableExtendDisks:
		if availableExtendDisk.devicePath != availableDisk.devicePath:
			break
	assert(availableExtendDisk)
	print("Using disk: %s for extending the vmfs volume"
              % availableExtendDisk.deviceName)
	try:
		extendOptions = self._datastoreSystem.QueryVmfsDatastoreExtendOptions(targetDs,availableExtendDisk.devicePath, True);
	except Exception as e:
		print("Failed to get Extend Options: %s" % e)
		return 0
	extendOption = extendOptions[0]
	assert(extendOption)
	try:
		self._datastoreSystem.ExtendVmfsDatastore(targetDs, extendOption.spec);
	except Exception as e:
		print("Failed to extend Datastore: %s Error Msg: %s" % (targetDs, e))
		return 0
	print("Extended Vmfs volume successfully on disk: %s"
              % availableExtendDisk.deviceName)
	try:
		self._datastoreSystem.RemoveDatastore(targetDs);
	except Exception as e:
		print("Failed to remove Datastore: %s Error Msg: %s" % (targetDs, e))
		return 0
	print("Destroyed Vmfs volume successfully")
	partInfo=self._storageSystem.RetrieveDiskPartitionInfo(availableDisk.devicePath)
	if len(partInfo[0].spec.partition) != 0:
		print("Failed to delete all partitions for Datastore: %s" % targetDs)
		return 0
	print("All partitions for the Vmfs volume deleted successfully")
	return 1

def main():
   supportedArgs = [ (["h:", "host="], "10.112.184.217", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd")]

   supportedToggles = [(["usage", "help"], False, "Show usage information", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Connect
   si = connect.SmartConnect(host=args.GetKeyValue("host"),
                             user=args.GetKeyValue("user"),
                             pwd=args.GetKeyValue("pwd"))
   atexit.register(connect.Disconnect, si)

   Log("Connected to host " + args.GetKeyValue("host"))

   et = ExtentTest(si)
   et.__init__(si)
   ret = et.runTest()
   if ret == 1:
      Log ("test successful")
   else:
      Log ("test failed")
      return

# Start program
if __name__ == "__main__":
    main()
