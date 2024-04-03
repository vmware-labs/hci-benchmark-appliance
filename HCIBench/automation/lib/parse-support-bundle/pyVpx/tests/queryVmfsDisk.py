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

volName = "formatVffs-unit-test-1"

class QueryTest:
   def __init__(self, si):
      self._si = si
      self._hostSystem = host.GetHostSystem(si)
      self._configMgr = host.GetHostConfigManager(si)
      self._storageSystem = self._configMgr.GetStorageSystem()
      self._datastoreSystem = self._configMgr.GetDatastoreSystem()

   def test(self):
	print("Checking available disks for VMFS")
        disks = self._datastoreSystem.QueryAvailableDisksForVmfs();
        print("Total available disks for VMFS: %d" % len(disks))
	totalVmfsDisk = len(disks)
        for disk in disks:
                print("		disk:	%s" % disk.devicePath)
	print("Formatting VFFS now")
	availableSsds = self._storageSystem.QueryAvailableSsds()
	assert(availableSsds)
	availableSsd = availableSsds[0]
	spec = Vim.host.VffsVolume.Specification()
	spec.devicePath = availableSsd.deviceName
	spec.partition = None
	spec.majorVersion = 1
	spec.volumeName = volName
	try:
		vffs = self._storageSystem.FormatVffs(spec)
	except Exception:
		print("Formatting VFFS FAILED")
	print("successfully formated VFFS on disk: %s" % availableSsd.deviceName)
	print("Extending VFFS now")
	mountInfos = self._storageSystem.fileSystemVolumeInfo.mountInfo
	for mounts in mountInfos:
		if mounts.volume.type == "VFFS":
			mInfo = mounts.mountInfo
	availableSsds = self._storageSystem.QueryAvailableSsds(mInfo.path)
	assert(availableSsds)
	newSsd = availableSsds[0]
	devicePaths = []
	devicePaths.append(newSsd.devicePath)
	partitionInfos = self._storageSystem.RetrieveDiskPartitionInfo(devicePaths)
	assert(partitionInfos)
	try:
		self._storageSystem.ExtendVffs(mInfo.path, newSsd.deviceName, partitionInfos[0].spec)
	except Exception:
		print("Extending VFFS FAILED")
	print("successfully extended VFFS on disk: %s" % newSsd.deviceName)
	print("Checking available disks for VMFS again")
        disks = self._datastoreSystem.QueryAvailableDisksForVmfs();
        print("Total available disks for VMFS: %d"  % len(disks))
	totalVmfsDiskNow = len(disks)
        for disk in disks:
                print("		disk:	%s" % disk.devicePath)
	if totalVmfsDiskNow < totalVmfsDisk:
		ret = 0
	else:
		ret = 1
	print("Cleaning up")
	try:
		self._storageSystem.DestroyVffs(mInfo.path)
	except Exception:
		print("Failed to destroy the vffs volume: %s" % volName)
	print("Destroyed the VFFS volume successfully")
	return ret

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

   qt = QueryTest(si)
   qt.__init__(si)

   if qt.test() == 0:
	print("QueryAvailableDisksForVmfs test PASSED")
   else:
	print("QueryAvailableDisksForVmfs test FAILED")

# Start program
if __name__ == "__main__":
    main()
