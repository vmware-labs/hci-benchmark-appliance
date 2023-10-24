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

class Vffs:
   def __init__(self, si):
      self._si = si
      self._hostSystem = host.GetHostSystem(si)
      self._configMgr = host.GetHostConfigManager(si)
      self._storageSystem = self._configMgr.GetStorageSystem()
      self._vFlashManager = self._configMgr.GetVFlashManager()
      self._datastoreSystem = self._configMgr.GetDatastoreSystem()

   def getVffsFsMountInfo(self):
      mountInfos = self._storageSystem.fileSystemVolumeInfo.mountInfo
      for mountInfo in mountInfos:
           if mountInfo.volume.type == "VFFS":
                return mountInfo
      return None

   def getVffs(self):
      fsMountInfo = self.getVffsFsMountInfo()
      if fsMountInfo:
           return fsMountInfo.volume
      return None

   def getVffsMountInfo(self, vffs):
      fsMountInfo = self.getVffsFsMountInfo()
      if fsMountInfo:
           if vffs and fsMountInfo.volume.uuid == vffs.uuid:
                return fsMountInfo.mountInfo
      return None

   def formatVffs(self, volName):
      temp = self.getVffs()
      if temp:
           print("VFFS volume already exists.")
           if temp.name == "vffs":
                print("volume name is vffs. proceeding further")
                return temp
           mountInfo = self.getVffsMountInfo(temp)
           assert(mountInfo)
           try:
                 self._storageSystem.DestroyVffs(mountInfo.path)
           except Exception:
                print("Failed to destroy existing vffs volume. Can't proceed")
                return None
           availableSsds = self._storageSystem.QueryAvailableSsds()
           assert(availableSsds)
           availableSsd = availableSsds[0]
           devicePaths = []
           devicePaths.append(availableSsd.devicePath)
           partitionInfos = self._storageSystem.RetrieveDiskPartitionInfo(devicePaths)
           assert(partitionInfos)
           spec = Vim.host.VffsVolume.Specification()
           spec.devicePath = availableSsd.deviceName
           spec.partition = partitionInfos[0].spec
           spec.majorVersion = 1
           spec.volumeName = volName
           try:
   	      vffs = self._storageSystem.FormatVffs(spec)
              print("Created vffs volume")
              return vffs
	   except Exception:
              print("Failed to create vffs volume")
              return None

   def testHostCache(self, uuid):
      resSpec = Vim.host.VFlashManager.VFlashResourceConfigSpec()
      print(uuid)
      resSpec.vffsUuid = uuid
      self._vFlashManager.ConfigureVFlashResource(resSpec)
      cacheSpec = Vim.host.VFlashManager.VFlashCacheConfigSpec()
      defaultVFlashModule = "vfc"
      cacheSpec.defaultVFlashModule = defaultVFlashModule

      cacheSpec.swapCacheReservationInGB = 1;
      self._vFlashManager.ConfigureHostVFlashCache(cacheSpec)
      cacheInfo = self._vFlashManager.GetVFlashConfigInfo()
      if (cacheInfo.vFlashCacheConfigInfo.swapCacheReservationInGB != 1):
           print("Configured cache with 1GB but did not retrieve cache size 1GB as expected")
           return 0
      else:
           print("Configured cache with 1GB and retrieve cache size 1GB as expected")

      cacheSpec.swapCacheReservationInGB = 10;
      try:
           self._vFlashManager.ConfigureHostVFlashCache(cacheSpec)
           return 0
      except Exception:
           print("expected exception while configuring cache with reservation exceeding available memory")

      cacheSpec.swapCacheReservationInGB = 5;
      self._vFlashManager.ConfigureHostVFlashCache(cacheSpec)
      cacheInfo = self._vFlashManager.GetVFlashConfigInfo()
      if (cacheInfo.vFlashCacheConfigInfo.swapCacheReservationInGB != 5):
           print("Configured cache with 5GB but did not retrieve cache size 5GB as expected")
           return 0
      else:
           print("Configured cache with 5GB and retrieve cache size 5GB as expected")

      cacheSpec.swapCacheReservationInGB = 0;
      self._vFlashManager.ConfigureHostVFlashCache(cacheSpec)
      cacheInfo = self._vFlashManager.GetVFlashConfigInfo()
      if (cacheInfo.vFlashCacheConfigInfo.swapCacheReservationInGB != 0):
           print("Configured cache with 0 but did not retrieve cache size 0 as expected")
           return 0
      else:
           print("Configured cache with 0 and retrieve cache size 0 as expected")

      cacheSpec.swapCacheReservationInGB = -1;
      try:
           self._vFlashManager.ConfigureHostVFlashCache(cacheSpec)
           return 0
      except Exception:
           print("expected exception while configuring cache with -ve reservation value")

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

   vffs = Vffs(si)
   vffs.__init__(si)
   fs = vffs.formatVffs("vffs")
   if fs == None:
      print("XXX::HostCacheConfig test FAILED")
   else:
      if vffs.testHostCache(fs.uuid) == 1:
           print("***::HostCacheConfig test PASSED")
      else:
           print("XXX::HostCacheConfig test FAILED")

if __name__ == "__main__":
    main()
