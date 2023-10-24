from __future__ import print_function

import sys
from pyVmomi import Vim, VmomiSupport
from pyVim import host, connect, vm, invt, vimhost
from pyVim import arguments
from pyVim.connect import SmartConnect, Disconnect
from pyVim.helpers import Log,StopWatch
import pickle
import random
import atexit

class Vmfs5:
   def __init__(self, si):
      self._si = si
      self._hostSystem = host.GetHostSystem(si)
      self._configMgr = host.GetHostConfigManager(si)
      self._storageSystem = self._configMgr.GetStorageSystem()
      self._datastoreSystem = self._configMgr.GetDatastoreSystem()

   def UpgradeDatastore(self, ds):
      if VmomiSupport.Type(ds.info) == Vim.Host.VmfsDatastoreInfo:
         self._storageSystem.UpgradeVmfs(ds.host[0].mountInfo.path)

   def CleanupExistingTestDatastores(self):
      for ds in self._datastoreSystem.datastore:
         if ds.name.startswith('vmfs5-test-ds:'):
            self._datastoreSystem.RemoveDatastore(ds)

   def TestCreateAndUpgradeVmfsDatastores(self):
      self.CleanupExistingTestDatastores()
      versions = set(self._hostSystem.capability.supportedVmfsMajorVersion)
      print("Host supports the following Vmfs versions %s" % versions)
      assert set([3,5]).issubset(versions)
      availableDisks = self._datastoreSystem.QueryAvailableDisksForVmfs()
      print("Available Disks are: %s"
            % [disk.deviceName for disk in availableDisks])
      for vmfsVersion in [0, 2, 3, 5, 6]:
         print("[ Vmfs Version: %s" % vmfsVersion)
         for availableDisk in availableDisks:
            print("[ Available Disk: %s" % availableDisk.deviceName)
            print(self._storageSystem.RetrieveDiskPartitionInfo(availableDisk.deviceName))
            print("[ Create Options: ")
            try:
		if vmfsVersion != 0:
		  createOptions = self._datastoreSystem.QueryVmfsDatastoreCreateOptions(availableDisk.deviceName, vmfsVersion)
	        else:
		  createOptions = self._datastoreSystem.QueryVmfsDatastoreCreateOptions(availableDisk.deviceName)
            except Exception as e:
               print(e)
            for createOption in createOptions:
               print("[ %s" % createOption)
               if type(createOption.info) == Vim.Host.VmfsDatastoreOption.AllExtentInfo:
                  createOption.spec.vmfs.volumeName="vmfs5-test-ds:%s" % random.randint(1,1000);
#                 Wait for fix for ComputePartitionFormat taking a clobber option
#                 for the AllExtentInfo case where non-vmware partitions shouldn't
#                 be a factor in computing partition format switch. Also modify
#                 the following assert to check for non-vmware partitions when
#                 mbr vmfs5 options are returned.
#                 assert (((createOption.spec.vmfs.majorVersion == 3) and (createOption.spec.partition.partitionFormat == 'mbr')) or ((createOption.spec.vmfs.majorVersion == 5) and (createOption.spec.partition.partitionFormat == 'gpt')))
                  try:
                     print("{ Creating: ")
                     ds = self._datastoreSystem.CreateVmfsDatastore(createOption.spec)
                     print(ds.info, ds.summary)
                     assert versions.__contains__(ds.info.vmfs.majorVersion)
                     print("}")
                     try:
                        print("{ Upgrading: ")
                        olderVmfsVersion = ds.info.vmfs.version
                        self.UpgradeDatastore(ds)
                        newerVmfsVersion = ds.info.vmfs.version
                        print(ds.info, ds.summary)
                        assert olderVmfsVersion < newerVmfsVersion
                        print("}")
		     except Exception as e:
                        print(e)
                        assert ds.info.vmfs.vmfsUpgradable == False
                        print("}")
		     try:
                        print("{ Removing: ")
                        print(ds.info, ds.summary)
                        dsName = ds.info.name
                        self._datastoreSystem.RemoveDatastore(ds)
                        assert [ds for ds in self._datastoreSystem.datastore if ds.summary.name == dsName].__len__() == 0
		     except Exception as e:
                        print(e)
                        print("}")
		  except Vim.Fault.PlatformConfigFault as f:
		     print(f)
		     if f.text == 'Failed to update disk partition information':
                        print("Most likely due to inability to clobber existing Msdos partition")
		     print("}")
		  except Exception as e:
		     print(e)
		     print("}")
	       print("]")
	    print("]")
	    print("]")
	 print("]")

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd")]

   supportedToggles = [(["usage", "help"], False, "Show usage information", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Connect
   si = SmartConnect(host=args.GetKeyValue("host"),
                     user=args.GetKeyValue("user"),
                     pwd=args.GetKeyValue("pwd"))
   atexit.register(Disconnect, si)

   Log("Connected to host " + args.GetKeyValue("host"))

   vmfs5 = Vmfs5(si)
   vmfs5.TestCreateAndUpgradeVmfsDatastores()
# Start program
if __name__ == "__main__":
    main()
