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

volName1 = "formatVffs-unit-test-1"
volName2 = "formatVffs-unit-test-2"

def restartHost(pscmd, startcmd, stopcmd):
	print("		Restarting hostd")
	os.system(stopcmd)
	time.sleep(2)
	retval = os.system(pscmd)
	if retval == 0:
		print("		Failed to stop hostd. retVal %s" % retval)
	else:
		print("		Successfully stoped hostd")
	os.system(startcmd)
	time.sleep(10)
	retval2 = os.system(pscmd)
	time.sleep(5)
	if retval2 == 0:
		print("		Restarted hostd")
	else:
		print("		Restart hostd failed. retVal %s" % retval2)
		return 0
	return 1


class Vffs:
   def __init__(self, si):
      self._si = si
      self._hostSystem = host.GetHostSystem(si)
      self._configMgr = host.GetHostConfigManager(si)
      self._storageSystem = self._configMgr.GetStorageSystem()
      self._datastoreSystem = self._configMgr.GetDatastoreSystem()

   def resetSystem(self, sshcmd):
	print("		Reset ESX host storage")
	devInfo = self._storageSystem.GetStorageDeviceInfo()
	scsiLuns = devInfo.scsiLun
	for lun in scsiLuns:
		devPath = lun.devicePath
        	resertCmd = "partedUtil delete " + devPath + " 1"
		rstCmd = sshcmd
		rstCmd += " \" "
		rstCmd += resertCmd
		rstCmd += " \""
		os.system(rstCmd)

   def getVffsFsMountInfo(self):
   	mountInfos = self._storageSystem.fileSystemVolumeInfo.mountInfo
   	for mountInfo in mountInfos:
      		if mountInfo.volume.type == "VFFS":
       			return mountInfo
   	return None
	#end getVffsFsMountInfo

   def getVffs(self):
   		fsMountInfo = self.getVffsFsMountInfo()
   		if fsMountInfo:
      			return fsMountInfo.volume
   		return None
	#end getVffs

   def getVffsMountInfo(self, vffs):
   		fsMountInfo = self.getVffsFsMountInfo()
   		if fsMountInfo:
      			if vffs and fsMountInfo.volume.uuid == vffs.uuid:
         			return fsMountInfo.mountInfo
   		return None
	 #end getVffsMountInfo

   def querySsd(self, path):
		availableSsds = self._storageSystem.QueryAvailableSsds(path)
   		for availableSsd in availableSsds:
			return availableSsd
		return None

   def formatVffsNullPartition(self, volName):
   		if self.getVffs():
			print(" 			VFFS volume already exists")
      			return None
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
   			return vffs
   		except Exception as e:
			return None
	#end formatVffs

   def formatVffs(self, volName):
   		if self.getVffs():
			print(" 			VFFS volume already exists")
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
   			return vffs
   		except Exception as e:
			return None
	#end formatVffs

   def extendVffsNullSpec(self,  path, newSsd):
   		self._storageSystem.ExtendVffs(path, newSsd.deviceName, None)
	#end extendVffsNullSpec

   def extendVffs(self,  path, newSsd):
   		devicePaths = []
   		devicePaths.append(newSsd.devicePath)
   		partitionInfos = self._storageSystem.RetrieveDiskPartitionInfo(devicePaths)
   		assert(partitionInfos)
   		self._storageSystem.ExtendVffs(path, newSsd.deviceName, partitionInfos[0].spec)
	#end extendVffs

   def FormatNoPartition(self, volName):
   		try:
      			vffs = self.getVffs()
      			if not vffs:
      				vffs = self.formatVffsNullPartition(volName)
      			else:
				return 1
      			if vffs:
				return 0
      			else:
				return 1
   		except Exception as failure:
			return 1

   def Format(self, volName):
   		try:
      			vffs = self.getVffs()
      			if not vffs:
      				vffs = self.formatVffs(volName)
      			else:
				return 1
      			if vffs:
				return 0
      			else:
				return 1
   		except Exception as failure:
			return 1

   def Extend(self):
   		try:
      			vffs = self.getVffs()
      			assert(vffs)
      			mountInfo = self.getVffsMountInfo(vffs)
			diskAvailable = self.querySsd(mountInfo.path)
			if diskAvailable:
      				self.extendVffs(mountInfo.path, diskAvailable)
				print("			disk available: %s"
                                      % diskAvailable.devicePath)
				return 0
			else:
				print("			No disk available to extend VFFS partition")
				return 2
   		except Exception as failure:
			return 1

   def ExtendNullSpec(self):
   		try:
      			vffs = self.getVffs()
      			assert(vffs)
      			mountInfo = self.getVffsMountInfo(vffs)
			diskAvailable = self.querySsd(mountInfo.path)
			if diskAvailable:
      				self.extendVffsNullSpec(mountInfo.path, diskAvailable)
				print("			disk available: %s"
                                      % diskAvailable.devicePath)
				return 0
			else:
				print("			No disk available to extend VFFS partition")
				return 2
   		except Exception as failure:
			return 1

   def Mount(self):
   		try:
      			vffs = self.getVffs()
      			assert(vffs)
      			self._storageSystem.MountVffsVolume(vffs.GetUuid())
			self._storageSystem.Refresh()
      			mountInfo = self.getVffsMountInfo(vffs)
      			assert(mountInfo)
      			if mountInfo.mounted:
				return 0
      			else:
				return 1
   		except Exception as failure:
			return 1

   def Unmount(self):
   		try:
      			vffs = self.getVffs()
      			assert(vffs)
      			self._storageSystem.UnmountVffsVolume(vffs.GetUuid())
			self._storageSystem.Refresh()
      			mountInfo = self.getVffsMountInfo(vffs)
      			assert(mountInfo)
      			if not mountInfo.mounted:
				return 0
      			else:
				return 1
   		except Exception as failure:
			return 1

   def GetDisk(self):
   		try:
      			mountInfo = self.getVffsFsMountInfo()
      			assert(mountInfo)
			disk =  mountInfo.volume.extent[0].diskName
			return disk
   		except Exception as failure:
			return None

   def AttachDisk(self, disk):
   		try:
      			self._storageSystem.AttachScsiLun(disk)
			return 0
   		except Exception as failure:
			return 1

   def DetachDisk(self, disk):
   		try:
      			vffs = self.getVffs()
      			assert(vffs)
      			self._storageSystem.DetachScsiLun(disk)
			return 0
   		except Exception as failure:
			return 1

   def DetachDiskAndDeleteState(self, disk):
   		try:
      			vffs = self.getVffs()
      			assert(vffs)
      			self._storageSystem.DetachScsiLun(disk)
      			self._storageSystem.DeleteVffsVolumeState(vffs.GetUuid())
      			self._storageSystem.DeleteScsiLunState(disk)
			return 0
   		except Exception as failure:
			return 1

   def Destroy(self):
   		try:
      			vffs = self.getVffs()
      			assert(vffs)
      			mountInfo = self.getVffsMountInfo(vffs)
      			assert(mountInfo)
      			self._storageSystem.DestroyVffs(mountInfo.path)
      			vffs = self.getVffs()
      			if not vffs:
				return 0
      			else:
				return 1
   		except Exception as failure:
			return 1

   def Rescan(self):
		try:
      			self._storageSystem.RescanVffs()
			return 0
   		except Exception as failure:
			return 1

   def QueryExistingPartitions(self):
	availableSsds = self._storageSystem.QueryAvailableSsds()
	for availableSsd in availableSsds:
		partInfo=self._storageSystem.RetrieveDiskPartitionInfo(availableSsds[0].deviceName)
		if len(partInfo[0].spec.partition) != 0:
			return 1
	return 0

   def test1(self):
		print("TEST1 START")
		if self.Format(volName1) == 1:
			print("		Format disk failed.")
			return 1
		else:
			print("		Formatted new Vffs volume")
		if self.Mount() == 0:
			print("		MountVffs passed on a mounted volume.")
			return 1
		else:
			print("		Mount not possible on already mounted volume")
		if self.Unmount() == 1:
			print("		UnmountVffs failed on a mounted volume.")
			return 1
		else:
			print("		Unmount successful")
		if self.Destroy() == 0:
			print("		DestroyVffs passed on an unmounted volume.")
			return 1
		else:
			print("		Destroy volume not possible on unmounted volume")
		if self.Mount() == 1:
			print("		MountVffs failed on an unmounted volume.")
			return 1
		else:
			print("		Mount volume successful")
		if self.Destroy() == 1:
			print("		DestroyVffs failed on a mounted volume.")
			return 1
		else:
			print("		Destroy volume successful")
		if self.QueryExistingPartitions() == 1:
			print("		DestroyVffs failed to delete all partitions.")
			return 1
		else:
			print("		DestroyVffs successfully deleted all partitions")
		if self.Format(volName1) == 1:
			print("		Format disk failed.")
			return 1
		else:
			print("		Format volume successful")
		if self.Format(volName2) == 0:
			print("		Format disk passed on host already having a VFFS volume.")
			return 1
		else:
			print("		Format volume failed as host already has a VFFS volume")
		if self.Destroy() == 1:
			print("		DestroyVffs failed on a mounted volume.")
			return 1
		else:
			print("		Destroy volume successful")
		if self.QueryExistingPartitions() == 1:
			print("		DestroyVffs failed to delete all partitions.")
			return 1
		else:
			print("		DestroyVffs successfully deleted all partitions")
		if self.FormatNoPartition(volName1) == 1:
			print("		Format disk without partition failed.")
			return 1
		else:
			print("		Format volume without partition successful")
		if self.FormatNoPartition(volName2) == 0:
			print("		Format disk without partition passed on host already having a VFFS volume.")
			return 1
		else:
			print("		Format volume without partition failed as host already has a VFFS volume")
		if self.Destroy() == 1:
			print("		DestroyVffs failed on a mounted volume.")
			return 1
		else:
			print("		Destroy volume successful")
		if self.QueryExistingPartitions() == 1:
			print("		DestroyVffs failed to delete all partitions.")
			return 1
		else:
			print("		DestroyVffs successfully deleted all partitions")
		print("TEST1 END.")
		return 0

   # format-extend-unmount-extend(x)-mount-extend-destroy-query and check all partitions are deleted
   def test2(self):
		print("TEST2 START.")
		if self.Format(volName1) == 1:
			print("		Format disk failed.")
			return 1
		else:
			print("		Format volume successful")
		if self.Unmount() == 1:
			print("		UnmountVffs failed on a mounted volume.")
			return 1
		else:
			print("		Unmount successful")
		ret = self.Extend()
		if ret == 0:
			print("		ExtendVolume succeeded on an unmounted volume.")
			return 1
		elif ret == 2:
			print("		ExtendVolume not possible as no disk available.")
		else:
			print("		ExtendVolume not possible on an unmounted volume")
		if self.Mount() == 1:
			print("		MountVffs failed on an unmounted volume.")
			return 1
		else:
			print("		Mount volume successful")
		ret = self.Extend()
		if ret == 1:
			print("		ExtendVolume failed on a mounted volume.")
			return 1
		elif ret == 2:
			print("		ExtendVolume not possible as no disk available.")
		else:
			print("		ExtendVolume passed based on disk availability")
		ret = self.ExtendNullSpec()
		if ret == 1:
			print("		ExtendVolume with null spec failed on a mounted volume.")
			return 1
		elif ret == 2:
			print("		ExtendVolume not possible as no disk available.")
		else:
			print("		ExtendVolume with null spec passed based on disk availability")
		ret = self.Extend()
		if ret == 1:
			print("		ExtendVolume failed on a mounted volume.")
			return 1
		elif ret == 2:
			print("		ExtendVolume not possible as no disk available.")
		else:
			print("		ExtendVolume passed based on disk availability")
		if self.Destroy() == 1:
			print("		DestroyVffs failed on a mounted volume.")
			return 1
		else:
			print("		Destroy volume successful")
		if self.QueryExistingPartitions() == 1:
			print("		DestroyVffs failed to delete all partitions.")
			return 1
		else:
			print("		DestroyVffs successfully deleted all partitions")
		print("TEST2 END.")
		return 0

   def test5_part0(self):
   		fsMountInfo = self.getVffsFsMountInfo()
		if fsMountInfo:
			print("		Found Vffs volume %s" % fsMountInfo.mountInfo.path)
			return 0
		else:
			print("		Vffs volume not found")
			return 1

   # format-unmount-deleteState-rescan-query-unmount-mount-destroy
   def test3(self):
		print("TEST3 START.")
		if self.Format(volName1) == 1:
			print("		Format disk failed.")
			return 1
		else:
			print("		Format volume successful")
		disk = self.GetDisk()
		if self.Unmount() == 1:
			print("		UnmountVffs failed on a mounted volume.")
			return 1
		else:
			print("		Unmount successful")
		if self.DetachDiskAndDeleteState(disk) == 1:
			print("		DetachDiskAndDeleteState call failed.")
			return 1
		else:
			print("		DetachDiskAndDeleteState successful")
		if self.Rescan() == 1:
			print("		RescanVffs call failed.")
			return 1
		else:
			print("		RescanVffs successful")
		if self.AttachDisk(disk) == 1:
			print("		AttachDisk call failed.")
			return 1
		else:
			print("		AttachDisk successful")
		time.sleep(5)
		if self.test5_part0() == 1:
			return 1
		if self.Unmount() == 1:
			print("		UnmountVffs failed on a rescaned volume.")
			return 1
		else:
			print("		Unmount successful")
		if self.Mount() == 1:
			print("		MountVffs failed on an unmounted volume.")
			return 1
		else:
			print("		Mount volume successful")
		if self.Destroy() == 1:
			print("		DestroyVffs failed on a mounted volume.")
			return 1
		else:
			print("		Destroy volume successful")
		if self.QueryExistingPartitions() == 1:
			print("		DestroyVffs failed to delete all partitions.")
			return 1
		else:
			print("		DestroyVffs successfully deleted all partitions")
		print("TEST3 END.")
		return 0

   # format-unmount-rescan-query(x)
   def test4(self):
		print("TEST4 START.")
		if self.Format(volName1) == 1:
			print("		Format disk failed.")
			return 1
		else:
			print("		Format volume successful")
		disk = self.GetDisk()
		if self.Unmount() == 1:
			print("		UnmountVffs failed on a mounted volume.")
			return 1
		else:
			print("		Unmount successful")
		if self.DetachDisk(disk) == 1:
			print("		DetachDisk call failed.")
			return 1
		else:
			print("		DetachDisk successful")
		if self.Rescan() == 1:
			print("		RescanVffs call failed.")
			return 1
		else:
			print("		RescanVffs successful")
		if self.AttachDisk(disk) == 1:
			print("		AttachDisk call failed.")
			return 1
		else:
			print("		AttachDisk successful")
		time.sleep(5)
		if self.test5_part0() == 1:
			return 1
		if self.Unmount() == 0:
			print("		UnmountVffs successful on an unmounted volume.")
			return 1
		else:
			print("		Unmount call failed on an unmounted volume")
		if self.Mount() == 1:
			print("		MountVffs failed on an unmounted volume.")
			return 1
		else:
			print("		Mount call successful on an unmounted volume")
		if self.Destroy() == 1:
			print("		DestroyVffs failed on a mounted volume.")
			return 1
		else:
			print("		Destroy volume successful")
		if self.QueryExistingPartitions() == 1:
			print("		DestroyVffs failed to delete all partitions.")
			return 1
		else:
			print("		DestroyVffs successfully deleted all partitions")
		print("TEST4 END.")
		return 0

   # format-restart-unmount-extend(x)-mount-restart-extend-extend-extend(x)-destroy
   def test5_part1(self):
		print("TEST5 START.")
		if self.Format(volName1) == 1:
			print("		Format disk failed.")
			return 1
		else:
			print("		Format volume successful")
		return 0

   def test5_part2(self):
		if self.test5_part0() == 1:
			return 1
		if self.Unmount() == 1:
			print("		Unmount call failed on a mounted volume")
			return 1
		else:
			print("		UnmountVffs successful.")
		ret = self.Extend()
		if ret == 0:
			print("		ExtendVolume succeeded on an unmounted volume.")
			return 1
		elif ret == 2:
			print("		ExtendVolume not possible as no disk available.")
		else:
			print("		ExtendVolume not possible on an unmounted volume")
		if self.Mount() == 1:
			print("		MountVffs failed on an unmounted volume.")
			return 1
		else:
			print("		Mount volume successful")
		ret = self.Extend()
		if ret == 1:
			print("		ExtendVolume failed on a mounted volume.")
			return 1
		elif ret == 2:
			print("		ExtendVolume not possible as no disk available.")
		else:
			print("		ExtendVolume passed based on disk availability")
		return 0

   def test5_part3(self):
		if self.test5_part0() == 1:
			return 1
		ret = self.Extend()
		if ret == 1:
			print("		ExtendVolume failed on a mounted volume.")
			return 1
		elif ret == 2:
			print("		ExtendVolume not possible as no disk available.")
		else:
			print("		ExtendVolume passed based on disk availability")
		ret = self.Extend()
		if ret == 1:
			print("		ExtendVolume failed on a mounted volume.")
			return 1
		elif ret == 2:
			print("		ExtendVolume not possible as no disk available.")
		else:
			print("		ExtendVolume passed based on disk availability")
		if self.Destroy() == 1:
			print("		DestroyVffs failed on a mounted volume.")
			return 1
		else:
			print("		Destroy volume successful")
		if self.QueryExistingPartitions() == 1:
			print("		DestroyVffs failed to delete all partitions.")
			return 1
		else:
			print("		DestroyVffs successfully deleted all partitions")
		print("TEST5 END.")
		return 0

   # format-unmount-restart-query
   def test6(self):
		print("TEST6 START.")
		if self.Format(volName1) == 1:
			print("		Format disk failed.")
			return 1
		else:
			print("		Format volume successful")
		if self.Unmount() == 1:
			print("		UnmountVffs failed on a mounted volume.")
			return 1
		else:
			print("		Unmount successful")
		return 0

   def test6_(self):
                time.sleep(5)
                if self.test5_part0() == 1:
                        return 1
                if self.Mount() == 1:
                        print("		MountVffs failed on an unmounted volume.")
                        return 1
                else:
                        print("		Mount call successful on an unmounted volume")
                if self.Destroy() == 1:
                        print("		DestroyVffs failed on a mounted volume.")
                        return 1
                else:
                        print("		Destroy volume successful")
		if self.QueryExistingPartitions() == 1:
			print("		DestroyVffs failed to delete all partitions.")
			return 1
		else:
			print("		DestroyVffs successfully deleted all partitions")
                print("TEST6 END.")
                return 0

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

   cmd = "ssh "
   cmd += args.GetKeyValue("user")
   cmd += "@"
   cmd += args.GetKeyValue("host")
   pscmd = cmd
   startcmd = cmd
   stopcmd = cmd
   pscmd += " \"ps | grep -q hostd\""
   stopcmd += " \"/etc/init.d/hostd stop >/dev/null 2>&1\""
   startcmd += " \"/etc/init.d/hostd start >/dev/null 2>&1\""

   vffs = Vffs(si)
   #vffs.resetSystem(cmd)
   restartHost(pscmd, startcmd, stopcmd)
   si = connect.SmartConnect(host=args.GetKeyValue("host"),
                             user=args.GetKeyValue("user"),
                             pwd=args.GetKeyValue("pwd"))
   vffs.__init__(si)

   if vffs.test1() == 0:
	print("***::TEST1 PASSED")
   else:
	print("XXX::TEST1 FAILED")
	vffs.resetSystem(cmd)
	restartHost(pscmd, startcmd, stopcmd)
        si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                  user=args.GetKeyValue("user"),
                                  pwd=args.GetKeyValue("pwd"))
	vffs.__init__(si)

   if vffs.test2() == 0:
	print("***::TEST2 PASSED")
   else:
	print("XXX::TEST2 FAILED")
	vffs.resetSystem(cmd)
	restartHost(pscmd, startcmd, stopcmd)
        si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                  user=args.GetKeyValue("user"),
                                  pwd=args.GetKeyValue("pwd"))
	vffs.__init__(si)

   if vffs.test3() == 0:
	print("***::TEST3 PASSED")
   else:
	print("XXX::TEST3 FAILED")
	vffs.resetSystem(cmd)
	restartHost(pscmd, startcmd, stopcmd)
   	si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                  user=args.GetKeyValue("user"),
                                  pwd=args.GetKeyValue("pwd"))
	vffs.__init__(si)

   if vffs.test4() == 0:
	print("***::TEST4 PASSED")
   else:
	print("XXX::TEST4 FAILED")
	vffs.resetSystem(cmd)
	restartHost(pscmd, startcmd, stopcmd)
   	si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                  user=args.GetKeyValue("user"),
                                  pwd=args.GetKeyValue("pwd"))
	vffs.__init__(si)

   if vffs.test5_part1() == 0:
   	ret = restartHost(pscmd, startcmd, stopcmd)
   	if ret == 1:
   		si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                          user=args.GetKeyValue("user"),
                                          pwd=args.GetKeyValue("pwd"))
		vffs.__init__(si)
   		if vffs.test5_part2() == 0:
   			ret = restartHost(pscmd, startcmd, stopcmd)
   			if ret == 1:
   				si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                                          user=args.GetKeyValue("user"),
                                                          pwd=args.GetKeyValue("pwd"))
				vffs.__init__(si)
   				if vffs.test5_part3() == 0:
					print("***::TEST5 PASS")
   				else:
   					print("XXX::TEST5 FAILED")
					vffs.resetSystem(cmd)
					restartHost(pscmd, startcmd, stopcmd)
   					si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                                                  user=args.GetKeyValue("user"),
                                                                  pwd=args.GetKeyValue("pwd"))
					vffs.__init__(si)
   		else:
   			print("XXX::TEST5 FAILED")
			vffs.resetSystem(cmd)
			restartHost(pscmd, startcmd, stopcmd)
   			si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                                  user=args.GetKeyValue("user"),
                                                  pwd=args.GetKeyValue("pwd"))
			vffs.__init__(si)
   	else:
   		print("XXX::TEST5 FAILED: Failed to restart host")
		vffs.resetSystem(cmd)
		restartHost(pscmd, startcmd, stopcmd)
   		si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                          user=args.GetKeyValue("user"),
                                          pwd=args.GetKeyValue("pwd"))
		vffs.__init__(si)
   else:
	print("XXX::TEST5 FAILED")
	vffs.resetSystem(cmd)
	restartHost(pscmd, startcmd, stopcmd)
   	si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                  user=args.GetKeyValue("user"),
                                  pwd=args.GetKeyValue("pwd"))
        vffs.__init__(si)

   if vffs.test6() == 0:
        ret = restartHost(pscmd, startcmd, stopcmd)
        if ret == 1:
                si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                          user=args.GetKeyValue("user"),
                                          pwd=args.GetKeyValue("pwd"))
                vffs.__init__(si)
                if vffs.test6_() == 0:
                        print("***::TEST6 PASS")
                else:
                        print("XXX::TEST6 FAILED")
                        vffs.resetSystem(cmd)
                        restartHost(pscmd, startcmd, stopcmd)
                        si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                                  user=args.GetKeyValue("user"),
                                                  pwd=args.GetKeyValue("pwd"))
                        vffs.__init__(si)
        else:
                print("XXX::TEST6 FAILED: Failed to restart host")
                vffs.resetSystem(cmd)
                restartHost(pscmd, startcmd, stopcmd)
                si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                          user=args.GetKeyValue("user"),
                                          pwd=args.GetKeyValue("pwd"))
                vffs.__init__(si)
   else:
        print("XXX::TEST6 FAILED")
        vffs.resetSystem(cmd)
        restartHost(pscmd, startcmd, stopcmd)
        si = connect.SmartConnect(host=args.GetKeyValue("host"),
                                  user=args.GetKeyValue("user"),
                                  pwd=args.GetKeyValue("pwd"))
        vffs.__init__(si)

# Start program
if __name__ == "__main__":
    main()
