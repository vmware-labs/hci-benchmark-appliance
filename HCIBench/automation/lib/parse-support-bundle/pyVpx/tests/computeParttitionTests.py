import sys
import time
from pyVmomi import Vim, VmomiSupport
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
from pyVim import host, connect;
import os, time
import random
import atexit

volName = "vffsTest"


class PartTest:
   def __init__(self, si):
      self._si = si
      self._hostSystem = host.GetHostSystem(si)
      self._configMgr = host.GetHostConfigManager(si)
      self._storageSystem = self._configMgr.GetStorageSystem()
      self._datastoreSystem = self._configMgr.GetDatastoreSystem()

   def testPart(self):
	availableSsds = self._storageSystem.QueryAvailableSsds()
	assert(availableSsds)
	availableSsd = availableSsds[0]
	dspec=Vim.host.DiskPartitionInfo.Specification()
	Log("Reseting partition on disk: "  + availableSsd.deviceName)
	self._storageSystem.UpdateDiskPartitions(availableSsd.deviceName, dspec)
	Log("Reset partition done")
	time.sleep(5)
	createOptions=self._datastoreSystem.QueryVmfsDatastoreCreateOptions(availableSsd.deviceName);
	for createOption in createOptions:
        # Using only All Disk options for simplicity of creation
		if type(createOption.info) == Vim.Host.VmfsDatastoreOption.AllExtentInfo:
			createOp=createOption
	createOp.info.layout.partition[0].end.block /= random.choice([2,3,4,5,6]);
	part=createOption.info.layout.partition
	try:
		self._storageSystem.ComputeDiskPartitionInfo(availableSsd.deviceName, createOption.info.layout, "gpt");
	except:
		Log("Failed to ComputeDiskPartitionInfo with linuxNative partition type and target gpt")
		return 0
	Log("compute partition done for linuxNative with target gpt")
	part[0].type='vmfs'
	try:
		self._storageSystem.ComputeDiskPartitionInfo(availableSsd.deviceName, createOption.info.layout, "mbr");
	except:
		Log("Failed to ComputeDiskPartitionInfo with vmfs partition type and mbr target")
		return 0
	Log("compute partition done for vmfs partition type with target mbr")
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

   pt = PartTest(si)
   pt.__init__(si)
   ret = pt.testPart()
   if ret == 1:
      Log ("test successful")
   else:
      Log ("test failed")
      return

# Start program
if __name__ == "__main__":
    main()
