## @file volumeResigTests.py
## @brief Volume Resignaturing Tests
##
## Utilities for operating with volume resignaturing

"""
Volume Resignaturing Tests

Utilities and tests for operating with host disks

Warning:

This test will clobber all the VMFS volumes that it finds on the
server for the purposes of cleaning up after previous runs of this
test!!!

Test Prerequisites:
1. Need at least 6 blank disks that are a minimum of 1 GB in size.
"""

from __future__ import print_function

__author__ = "VMware, Inc"

import traceback
from pyVmomi import Vim
import pyVim
import pyVim.configSerialize, pyVim.connect
import popen2
import sys
import time

class DataCache:
   def __init__(self, hostSystem):
      self._hostSystem = hostSystem
      self.Refresh()

   def Refresh(self):
      self._datastoreSystem = None
      self._storageSystem = None
      self._storageDeviceInfo = None
      self._fileSystemVolumeInfo = None
      self._diskPartitionInfos = None
      self._unresolvedVmfsVolumes = None

   def GetHostSystem(self):
      return self._hostSystem

   def GetDatastoreSystem(self):
      if self._datastoreSystem == None:
         self._datastoreSystem = self.GetHostSystem().configManager.datastoreSystem
      return self._datastoreSystem

   def GetStorageSystem(self):
      if self._storageSystem == None:
         self._storageSystem = self.GetHostSystem().configManager.storageSystem
      return self._storageSystem

   def GetStorageDeviceInfo(self):
      if (self._storageDeviceInfo == None):
         self._storageDeviceInfo = self.GetStorageSystem().storageDeviceInfo
      return self._storageDeviceInfo

   def GetFileSystemVolumeInfo(self):
      if (self._fileSystemVolumeInfo == None):
         self._fileSystemVolumeInfo = self.GetStorageSystem().fileSystemVolumeInfo
      return self._fileSystemVolumeInfo

   def GetDiskPartitionInfos(self):
      if (self._diskPartitionInfos == None):
         storageSystem = self.GetStorageSystem()
         self._diskPartitionInfos = storageSystem.RetrieveDiskPartitionInfo([lun.devicePath for lun in self.GetStorageDeviceInfo().scsiLun if isinstance(lun, Vim.Host.ScsiDisk)])
      return self._diskPartitionInfos

   def QueryUnresolvedVmfsVolume(self):
      if (self._unresolvedVmfsVolumes == None):
         storageSystem = self.GetStorageSystem()
         self._unresolvedVmfsVolumes = storageSystem.QueryUnresolvedVmfsVolume()
      return self._unresolvedVmfsVolumes


class Selector:
   def __init__(self, data):
      self._data = data

   def _GetDevicePathToDiskMap(self):
      disks = self.GetDisks()
      return dict(zip([disk.devicePath for disk in disks], disks))

   def GetDisks(self):
      return [lun for lun in self._data.GetStorageDeviceInfo().scsiLun if isinstance(lun, Vim.Host.ScsiDisk)]

   def GetDiskFromDevicePath(self, devicePath):
      for disk in self.GetDisks():
         if disk.devicePath == devicePath:
            return disk
      return None

   def GetDiskFromCanonicalName(self, canonicalName):
      for disk in self.GetDisks():
         if disk.canonicalName == canonicalName:
            return disk
      return None

   def GetDiskPartitionInfo(self, devicePath):
      for part in self._data.GetDiskPartitionInfos():
         if part.deviceName == devicePath:
            return part
      return None

   def GetBlankDisks(self):
      partitions = self._data.GetDiskPartitionInfos()
      devicePaths = [part.deviceName for part in partitions if len(part.spec.partition) == 0]
      devicePathMap = self._GetDevicePathToDiskMap()
      return [devicePathMap[devicePath] for devicePath in devicePaths]

   def GetNonBlankDisks(self):
      partitions = self._data.GetDiskPartitionInfos()
      devicePaths = [part.deviceName for part in partitions if len(part.spec.partition) != 0]
      devicePathMap = self._GetDevicePathToDiskMap()
      return [devicePathMap[devicePath] for devicePath in devicePaths]

   def GetVmfsDatastores(self):
      datastoreSystem = self._data.GetDatastoreSystem()
      return [datastore for datastore in datastoreSystem.datastore if isinstance(datastore.info, Vim.Host.VmfsDatastoreInfo)]

   def GetUnresolvedVolumes(self):
      storageSystem = self._data.GetStorageSystem()
      return self._data.QueryUnresolvedVmfsVolume()

class Mutator:
   def __init__(self, data):
      self._data = data

   # Create a VMFS volume to take up an entire disk
   def CreateVmfsDatastore(self, volumeName, disk):
      print(ActionMarker() + "Creating VMFS Datastore '%s' on disk %s."
            % (volumeName, disk.devicePath))

      datastoreSystem = self._data.GetDatastoreSystem()
      storageSystem = self._data.GetStorageSystem()

      # Get the partitioning option that creates VMFS that takes up the entire LUN:
      partitionOption = [option.info for option in datastoreSystem.QueryVmfsDatastoreCreateOptions(disk.devicePath) if isinstance(option.info, Vim.Host.VmfsDatastoreOption.AllExtentInfo)][0]

      # Convert the partition block range into a partition spec
      partitionSpec = storageSystem.ComputeDiskPartitionInfo(disk.devicePath, partitionOption.layout).spec

      # Build VmfsDatastoreCreateSpec
      vmfsVolumeSpec = Vim.Host.VmfsVolume.Specification(majorVersion=6,
                                                         volumeName=volumeName,
                                                         extent=Vim.Host.ScsiDisk.Partition(diskName=disk.canonicalName,
                                                                                            partition=partitionOption.vmfsExtent.partition))
      vmfsDatastoreCreateSpec = Vim.Host.VmfsDatastoreCreateSpec(diskUuid=disk.uuid, partition=partitionSpec, vmfs=vmfsVolumeSpec)

      # Create the VMFS volume
      datastore = datastoreSystem.CreateVmfsDatastore(vmfsDatastoreCreateSpec)
      return datastore

   # Extend a VMFS volume to take up an entire disk
   def ExtendVmfsDatastore(self, datastore, disk):
      datastoreSystem = self._data.GetDatastoreSystem()
      storageSystem = self._data.GetStorageSystem()

      print(ActionMarker() + "Extending VMFS Datastore '%s' on disk %s."
            % (datastore.summary.name, disk.devicePath))

      # Get the partitioning option that creates VMFS that takes up the entire LUN:
      # Note that the datastore parameter is needed from when the datastore was created.
      partitionOption = [option.info for option in datastoreSystem.QueryVmfsDatastoreExtendOptions(datastore,disk.devicePath) if isinstance(option.info, Vim.Host.VmfsDatastoreOption.AllExtentInfo)][0]

      # Convert the partition block range into a partition spec
      partitionSpec = storageSystem.ComputeDiskPartitionInfo(disk.devicePath, partitionOption.layout).spec

      # Build VmfsDatastoreExtendSpec
      vmfsDatastoreExtendSpec = Vim.Host.VmfsDatastoreExtendSpec(diskUuid = disk.uuid,
                                                                 partition=partitionSpec,
                                                                 extent=[Vim.Host.ScsiDisk.Partition(diskName=disk.canonicalName,
                                                                                                     partition=partitionOption.vmfsExtent.partition)])

      # Extend the VMFS volume
      datastore = datastoreSystem.ExtendVmfsDatastore(datastore, vmfsDatastoreExtendSpec)

      return datastore

   def ClearDisk(self, disk):
      storageSystem = self._data.GetStorageSystem()
      print(ActionMarker() + "Clearing partitions on disk %s."
            % disk.devicePath)
      storageSystem.UpdateDiskPartitions(disk.devicePath, Vim.Host.DiskPartitionInfo.Specification())

   def DestroyVmfsDatastore(self, datastore):
      maxAttempts = 10
      numSeconds = 10
      attempt = 0
      datastoreSystem = self._data.GetDatastoreSystem()
      print(ActionMarker() + "Destroying VMFS Datastore '%s'."
            % (datastore.summary.name))
      while attempt < maxAttempts:
         try:
            datastoreSystem.RemoveDatastore(datastore)
            return
         except Vim.Fault.ResourceInUse:
            attempt += 1
            print(ActionMarker(1) + "Failed to remove datastore.  Attempt %d/%d.  "
                  "Waiting for %d seconds." % (attempt, maxAttempts,
                                               numSeconds * attempt))
            time.sleep(numSeconds * attempt)
      raise Exception("Failed to remove datastore '%s' after %d attempts." % (datastore.summary.name, maxAttempts))

   def SnapshotDisk(self, hostname, diskSrc, diskDst):
      print(ActionMarker() + "Simulating creation of disk snapshot from %s to %s."
            % (diskSrc.devicePath, diskDst.devicePath))
      cmd = "ssh root@%s dd if=%s of=%s bs=%s count=%d conv=notrunc" % (hostname,
                                                                        diskSrc.devicePath,
                                                                        diskDst.devicePath,
                                                                        "1M",
                                                                        1024)
      print("$ %s" % cmd)
      out = []
      (stdout, stdin) = popen2.popen4(cmd)
      stdin.close()
      for line in stdout:
         out.append(line)
      stdout.close()
      sys.stdout.write("".join(out))

   def RunEsxCfgVolume(self, hostname):
      cmd = "ssh root@%s esxcfg-volume -l" % (hostname)
      print("$ %s" % cmd)
      out = []
      (stdout, stdin) = popen2.popen4(cmd)
      stdin.close()
      for line in stdout:
         out.append(line)
      stdout.close()
      sys.stdout.write("".join(out))

   def RescanVmfs(self):
      print(ActionMarker() + "Rescanning VMFS volumes.")
      storageSystem = self._data.GetStorageSystem()
      storageSystem.RescanVmfs()
      self._data.Refresh()

### Disk Views
def DiskDevicePath(disk, select):
   return "%s" % disk.devicePath

def DiskCapacity(disk, select):
   return "%d MB" % (disk.capacity.block * disk.capacity.blockSize / 1024 / 1024)

def DiskPartitionCount(disk, select):
   partitions = select.GetDiskPartitionInfo(disk.devicePath)
   return (partitions and "%d partitions" % len(partitions.spec.partition) or "No partition info.")

gDiskViews = {"devicePath": ("%-60s", DiskDevicePath),
              "capacity": ("%-10s", DiskCapacity),
              "partitionCount": ("%-15s", DiskPartitionCount)
             }

gMarker1 = "==========================================================================="
gTestSetupMarker = "\n==== Phase: Setup ===="
gTestVerificationMarker = "\n==== Phase: Verification ===="
gTestCleanupMarker = "\n==== Phase: Clean Up ===="
gRawOutputMarker = "-----------------------------------------------------------------"

def ActionMarker(level=0):
   return "--" * (level + 1) + "> "

class Viewer:
   def __init__(self, select):
      self._select = select
      self.data = select._data

   def _Disks(self, attributes, func):
      if attributes == None:
         attributes = ["devicePath"]
      attrs = [gDiskViews[attribute] for attribute in attributes if gDiskViews.has_key(attribute)]
      for disk in func():
         print(" ".join([attr[0] % attr[1](disk, self._select) for attr in attrs]))

   def Disks(self, attributes=None):
      self._Disks(attributes, self._select.GetDisks)

   def BlankDisks(self, attributes=None):
      self._Disks(attributes, self._select.GetBlankDisks)

   def NonBlankDisks(self, attributes=None):
      self._Disks(attributes, self._select.GetNonBlankDisks)

   def VmfsVolumes(self, attributes=None):
      for volume in self.data.GetFileSystemVolumeInfo().mountInfo:
         if not isinstance(volume.volume, Vim.Host.VmfsVolume):
            continue
         print(volume.volume.name)
         print("\n".join(["%s" % ("\n".join(["   %s:%d" % (extent.diskName,extent.partition) for extent in volume.volume.extent]))]))

   def UnresolvedVolumes(self, attributes=None):
      for volume in self.data.QueryUnresolvedVmfsVolume():
         stat = volume.resolveStatus
         print("VMFS label (UUID): %s (%s) Size: %d" %
               (volume.vmfsLabel, volume.vmfsUuid, volume.totalBlocks))
         print("   Resolvable: %s" % (stat.resolvable and "Yes" or "No"))
         print("   Incomplete Extents: %s" % ((stat.incompleteExtents == True and "Yes") or
                                              (stat.incompleteExtents == False and "No") or "Unknown"))
         print("   Multiple Copies: %s" % ((stat.multipleCopies == True and "Yes") or
                                           (stat.multipleCopies == False and "No") or "Unknown"))
         print("   Extents:")
         for extent in volume.extent:
            print("      %s:%d order: %d (%s) range %d - %d" % (extent.device.diskName,
                                                                extent.device.partition,
                                                                extent.ordinal,
                                                                extent.isHeadExtent and "head" or "not head",
                                                                extent.startBlock,
                                                                extent.endBlock))

class Util:
   def __init__(self, data, hostname):
      self.data = data
      self.hostname = hostname
      self.select = Selector(data)
      self.mutate = Mutator(data)
      self.view = Viewer(self.select)

   def Refresh(self):
      self.data.Refresh()


def GetUtil(si, hostname, hostSystem=None):
   if hostSystem == None:
      # Assume the host inventory if the host is not provided
      hostSystem = si.content.rootFolder.childEntity[0].hostFolder.childEntity[0].host[0]
   data = DataCache(hostSystem)
   return Util(data, hostname)


def GetUsableDisks(disks, numDisksForVolumes, numDisksForSnapshot):
   minSize = long(1024 * 1024 * 1024)
   disks = [disk for disk in disks if long(disk.capacity.block * disk.capacity.blockSize) >= minSize]

   totalDisks = numDisksForVolumes + numDisksForSnapshot
   if len(disks) < totalDisks:
      raise Exception("Could not find enough usable disks.  Need %d.  Found %d." % (totalDisks, len(disks)))
   return (disks[0:numDisksForVolumes], disks[numDisksForVolumes:totalDisks])

def ClearVmfsDatastores(util):
   cleared = 0
   datastores = util.select.GetVmfsDatastores()
   for datastore in datastores:
      print("Removing datastore %s." % datastore.summary.name)
      util.mutate.DestroyVmfsDatastore(datastore)
      cleared += 1
   return cleared

def ClearUnresolvedVolumes(util):
   cleared = 0
   volumes = util.select.GetUnresolvedVolumes()
   for volume in volumes:
      for extent in volume.extent:
         print("Clearing unresolved volume on disk %s." % extent.device.diskName)
         disk = util.select.GetDiskFromCanonicalName(extent.device.diskName)
         util.mutate.ClearDisk(disk)
         cleared += 1
   return cleared


def CheckInitialSetup(util):
   print(gMarker1)
   print("Initial Inventory\n")

   print("Disks:")
   util.view.Disks(["devicePath", "capacity", "partitionCount"])
   print('')

   print("Non-blank disks:")
   util.view.NonBlankDisks(["devicePath", "capacity", "partitionCount"])
   print('')

   print("Blank disks:")
   util.view.BlankDisks(["devicePath", "capacity", "partitionCount"])
   print('')

   print("VMFS volumes:")
   util.view.VmfsVolumes()
   print('')

   print("Unresolved VMFS volumes:")
   util.view.UnresolvedVolumes()
   print('')


class Test:
   def __init__(self, util):
      self._util = util
      self._testCount = 0
      self._testResult = []

   def StartTest(self, testName):
      self._testCount += 1
      print(gMarker1)
      label = "%d. %s" % (self._testCount, testName)
      print(label)
      print('')
      self._testResult.append([label, None])

   def EndTest(self):
#      __import__("pdb").set_trace()
      pass

   def ReportFailure(self, message):
      print("====> FAILED: %s" % message)
      self._testResult[-1][1] = False

   def ReportSuccess(self):
      print("====> Success")
      self._testResult[-1][1] = True

   def Finish(self):
      print(gMarker1)
      print("Test Results:")
      for result in self._testResult:
         r = "Unknown"
         if result[1] == True:
            r = "Success"
         elif result[1] == False:
            r = "FAILED"
         print("%s ====> %s" % (result[0], r))


   def CleanupTest(self, disks, datastore):
      util = self._util
      print(gTestCleanupMarker + "\n")
      for disk in disks:
         util.mutate.ClearDisk(disk)
      if datastore:
         util.mutate.DestroyVmfsDatastore(datastore)
      util.mutate.RescanVmfs()
      util.Refresh()

   #
   # volumeSpec['name'] The name of the VMFS volume to be created.
   # volumeSpec['numExtents'] The number of extents to attache to the VMFS volume
   #           (including the head extent).
   # volumeSpec['destroy'] Whether or not to destroy the VMFS volume after
   #           setting up the snapshot.
   #
   # snapshotList Is a list indicating which of the volume extents should be
   #              be cloned into a snapshot LUN.  The volume extents are referenced
   #              by ordinal value.  A zero value refers to the head extent.  An
   #              extent may be cloned multiple times by referring to the same
   #              ordinal value multiple times.
   #
   def SetupStorage(self, volumeSpec, snapshotList):
      numDisksForVolumes = volumeSpec['numExtents']
      numDisksForSnapshot = len(snapshotList)

      (volDisks, snapDisks) = GetUsableDisks(self._util.select.GetBlankDisks(),
                                             numDisksForVolumes,
                                             numDisksForSnapshot)
      datastore = self.SetupDatastore(volumeSpec['name'], volDisks)

      # Make an array of tuples that map from the index specified in
      # snapshotList to a positional index
      snapshotMap = [(volDisks[m[0]], snapDisks[m[1]]) for m in zip(snapshotList, range(len(snapshotList)))]
      self.SetupSnapshots(snapshotMap)

      if volumeSpec['destroy']:
         self._util.mutate.DestroyVmfsDatastore(datastore)
         datastore = None

      return (volDisks, snapDisks, datastore)

   def SetupDatastore(self, name, disks):
      util = self._util
      datastore = util.mutate.CreateVmfsDatastore(name, disks[0])
      for disk in disks[1:]:
         util.mutate.ExtendVmfsDatastore(datastore, disk)
      return datastore

   def SetupSnapshots(self, diskMapList):
      util = self._util
      for diskMap in diskMapList:
         util.mutate.SnapshotDisk(util.hostname, diskMap[0], diskMap[1])
      util.mutate.RescanVmfs()
      util.Refresh()

   def VerifyOutput(self, volumeSpec, snapshotList, volDisks, snapDisks, stat):
      util = self._util
      volumes = util.select.GetUnresolvedVolumes()
      if len(volumes) != 1:
         self.ReportFailure("Did not find one unresolved volume.")
         return False
      volume = volumes[0]

      if volume.vmfsLabel != volumeSpec['name']:
         self.ReportFailure("Unresolved volume name mismatch.")
         return False

      status = volume.resolveStatus
      if status.resolvable != stat["resolvable"]:
         self.ReportFailure("Resolvable mismatch.")
         return False
      if status.incompleteExtents != stat["incompleteExtents"]:
         self.ReportFailure("Incomplete extents mismatch.")
         return False
      if status.multipleCopies != stat["multipleCopies"]:
         self.ReportFailure("Multiple copies mismatch.")
         return False
      self.ReportSuccess()
      return True

   def PrintExpectedOutput(self, volumeSpec, snapshotList, volDisks, snapDisks,
                           stat):
      print("-- Expected VMFS Volumes --")
      if volumeSpec['destroy'] == False:
         print(volumeSpec['name'])
         print("\n".join(["   %s:?" % (disk.canonicalName) for disk in volDisks]))

      print("-- Expected Unresolved Volumes --")
      print("VMFS label: %s" % (volumeSpec['name']))
      print("   Resolvable: %s" % (stat["resolvable"] and "Yes" or "No"))
      print("   Incomplete Extents: %s" % ((stat["incompleteExtents"] == True and "Yes") or
                                           (stat["incompleteExtents"] == False and "No") or "Unknown"))
      print("   Multiple Copies: %s" % ((stat["multipleCopies"] == True and "Yes") or
                                        (stat["multipleCopies"] == False and "No") or "Unknown"))
      print("   Extents:")
      for i in range(len(snapDisks)):
         print("      %s:? order: %d" % (snapDisks[i].canonicalName, snapshotList[i]))

   def PrintVerificationOutput(self):
      util = self._util
      print(gTestVerificationMarker + "\n")
      print("-- VMFS Volumes --")
      util.view.VmfsVolumes()
      print("-- Unresolved Volumes --")
      util.view.UnresolvedVolumes()
      print("-- esxcfg-volume -l Output --")
      util.mutate.RunEsxCfgVolume(util.hostname)

   def TestSingleCopySingleExtentMounted(self):
      self.StartTest("Test: Single Copy, Single Extent, Mounted Volume")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "SingleExtent", 'numExtents': 1, 'destroy': False}
      snapshotList = [0]
      # Expected status for the result
      status = {'resolvable': True,
                'incompleteExtents': False,
                'multipleCopies' : False}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()

   def TestSingleCopyMultipleExtentMounted(self):
      self.StartTest("Test: Single Copy, Multiple Extent, Mounted Volume")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': False}
      snapshotList = [0, 1]
      # Expected status for the result
      status = {'resolvable': True,
                'incompleteExtents': False,
                'multipleCopies' : False}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestSingleCopySingleExtentNotMounted(self):
      self.StartTest("Test: Single Copy, Single Extent, Volume Not Mounted")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "SingleExtent", 'numExtents': 1, 'destroy': True}
      snapshotList = [0]
      # Expected status for the result
      status = {'resolvable': True,
                'incompleteExtents': False,
                'multipleCopies' : False}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestSingleCopyMultipleExtentNotMounted(self):
      self.StartTest("Test: Single Copy, Multiple Extent, Volume Not Mounted")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': True}
      snapshotList = [0, 1]
      # Expected status for the result
      status = {'resolvable': True,
                'incompleteExtents': False,
                'multipleCopies' : False}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestMultipleCopySingleExtentMounted(self):
      self.StartTest("Test: Multiple Copy, Single Extent, Mounted Volume")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "SingleExtent", 'numExtents': 1, 'destroy': False}
      snapshotList = [0, 0]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': False,
                'multipleCopies' : True}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestMultipleCopyMultipleExtentMounted(self):
      self.StartTest("Test: Multiple Copy, Multiple Extent, Mounted Volume")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': False}
      snapshotList = [0, 1, 0, 1]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': False,
                'multipleCopies' : True}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestMultipleCopyMultipleHeadExtentMounted(self):
      self.StartTest("Test: Multiple Copy, Multiple Head Extent, Mounted Volume")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': False}
      snapshotList = [0, 1, 0]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': False,
                'multipleCopies' : True}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestMultipleCopyMultipleTailExtentMounted(self):
      self.StartTest("Test: Multiple Copy, Multiple Tail Extent, Mounted Volume")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': False}
      snapshotList = [0, 1, 1]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': False,
                'multipleCopies' : True}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestMultipleCopySingleExtentNotMounted(self):
      self.StartTest("Test: Multiple Copy, Single Extent, Volume Not Mounted")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "SingleExtent", 'numExtents': 1, 'destroy': True}
      snapshotList = [0, 0]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': False,
                'multipleCopies' : True}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestMultipleCopyMultipleExtentNotMounted(self):
      self.StartTest("Test: Multiple Copy, Multiple Extent, Volume Not Mounted")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': True}
      snapshotList = [0, 1, 0, 1]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': False,
                'multipleCopies' : True}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestMultipleCopyMultipleHeadExtentNotMounted(self):
      self.StartTest("Test: Multiple Copy, Multiple Head Extent, Volume Not Mounted")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': True}
      snapshotList = [0, 1, 0]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': False,
                'multipleCopies' : True}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestMultipleCopyMultipleTailExtentNotMounted(self):
      self.StartTest("Test: Multiple Copy, Multiple Tail Extent, Volume Not Mounted")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': True}
      snapshotList = [0, 1, 1]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': False,
                'multipleCopies' : True}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestPartialCopyHeadExtentMultipleExtentMounted(self):
      self.StartTest("Test: Partial Copy, Head Extent, Multiple Extent, Mounted Volume")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': False}
      snapshotList = [0]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': True,
                'multipleCopies' : False}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestPartialCopyTailExtentMultipleExtentMounted(self):
      self.StartTest("Test: Partial Copy, Tail Extent, Multiple Extent, Mounted Volume")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': False}
      snapshotList = [1]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': True,
                'multipleCopies' : False}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # When the head is missing, metadata like the volume UUID is missing
      volumeSpec['name'] = ''
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestPartialCopyHeadExtentMultipleExtentNotMounted(self):
      self.StartTest("Test: Partial Copy, Head Extent, Multiple Extent, Volume Not Mounted")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': True}
      snapshotList = [0]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': True,
                'multipleCopies' : False}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestPartialCopyTailExtentMultipleExtentNotMounted(self):
      self.StartTest("Test: Partial Copy, Tail Extent, Multiple Extent, Volume Not Mounted")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': True}
      snapshotList = [1]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': True,
                'multipleCopies' : False}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # When the head is missing, metadata like the volume UUID is missing
      volumeSpec['name'] = ''
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()

   def TestMultiplePartialCopyHeadExtentMultipleExtentMounted(self):
      self.StartTest("Test: Multiple Partial Copy, Head Extent, Multiple Extent, Volume Mounted")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': False}
      snapshotList = [0, 0]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': True,
                'multipleCopies' : True}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()

   def TestMultiplePartialCopyTailExtentMultipleExtentMounted(self):
      self.StartTest("Test: Multiple Partial Copy, Tail Extent, Multiple Extent, Volume Mounted")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': False}
      snapshotList = [1, 1]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': True,
                'multipleCopies' : True}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # When the head is missing, metadata like the volume UUID is missing
      volumeSpec['name'] = ''
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


   def TestMultiplePartialCopyHeadExtentMultipleExtentNotMounted(self):
      self.StartTest("Test: Multiple Partial Copy, Head Extent, Multiple Extent, Volume Not Mounted")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': True}
      snapshotList = [0, 0]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': True,
                'multipleCopies' : True}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()

   def TestMultiplePartialCopyTailExtentMultipleExtentNotMounted(self):
      self.StartTest("Test: Multiple Partial Copy, Tail Extent, Multiple Extent, Volume Not Mounted")

      # Setup: volume information and snapshotList indicating volume disks to snapshot
      volumeSpec = {'name': "MultipleExtent", 'numExtents': 2, 'destroy': False}
      snapshotList = [1, 1]
      # Expected status for the result
      status = {'resolvable': False,
                'incompleteExtents': True,
                'multipleCopies' : True}

      (volDisks, snapDisks, datastore) = self.SetupStorage(volumeSpec, snapshotList)

      # Verification
      self.PrintVerificationOutput()
      self.PrintExpectedOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # When the head is missing, metadata like the volume UUID is missing
      volumeSpec['name'] = ''
      self.VerifyOutput(volumeSpec, snapshotList, volDisks, snapDisks, status)

      # Cleanup
      self.CleanupTest(snapDisks, datastore)
      self.EndTest()


def main(hostname):
   import pyVim.shell;
   global si
   si = pyVim.connect.Connect(hostname, version="vim.version.version9")
   global util
   util = GetUtil(si, hostname)


def test(hostname):
   global si
   si = pyVim.connect.Connect(hostname, version="vim.version.version9")
   global util
   util = GetUtil(si, hostname)

   print(gMarker1)
   print("Initial Cleanup\n")
   if ClearVmfsDatastores(util) + ClearUnresolvedVolumes(util) > 0:
      util.Refresh()

   CheckInitialSetup(util)

   test = Test(util)

   test.TestSingleCopySingleExtentMounted()
   test.TestSingleCopyMultipleExtentMounted()
   test.TestSingleCopySingleExtentNotMounted()
   test.TestSingleCopyMultipleExtentNotMounted()

   test.TestMultipleCopySingleExtentMounted()
   test.TestMultipleCopyMultipleExtentMounted()
   test.TestMultipleCopyMultipleHeadExtentMounted()
   test.TestMultipleCopyMultipleTailExtentMounted()

   test.TestMultipleCopySingleExtentNotMounted()
   test.TestMultipleCopyMultipleExtentNotMounted()
   test.TestMultipleCopyMultipleHeadExtentNotMounted()
   test.TestMultipleCopyMultipleTailExtentNotMounted()

   test.TestPartialCopyHeadExtentMultipleExtentMounted()
   test.TestPartialCopyTailExtentMultipleExtentMounted()
   test.TestPartialCopyHeadExtentMultipleExtentNotMounted()
   test.TestPartialCopyTailExtentMultipleExtentNotMounted()

   test.TestMultiplePartialCopyHeadExtentMultipleExtentMounted()
   test.TestMultiplePartialCopyTailExtentMultipleExtentMounted()
   test.TestMultiplePartialCopyHeadExtentMultipleExtentNotMounted()
   test.TestMultiplePartialCopyTailExtentMultipleExtentNotMounted()

   test.Finish()

if __name__ == "__main__":
    test(sys.argv[1])
#    main(sys.argv[1])
