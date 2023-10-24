# Copyright (c) 2016-2022 VMware, Inc.  All rights reserved.
# -- VMware Confidential

#
# Python wrappers for manipulating hbrsrv replicated disks.
#
# Not meant to be invoked directly.  Shared utility code for other hbrsrv
# wrappers.
#
import fnmatch
import logging
import os
import pyHbr.hostd
import pyVim.task
import pyVim.host
import re
import subprocess

from xml.dom import minidom
from pyHbr.exceptions import NoSuchDiskError
from pyVmomi import Vim, Vmodl, Hbr

logger = logging.getLogger('pyHbr.disks')


def SortedDevices(config, deviceType):
   """Return a sorted list of the disks in this Vim.Vm.ConfigInfo
   structure. This is used to keep the i'th disk index stable.

   @param config [in] Vim.Vm.ConfigInfo structure
   @return a list of deviceType references sorted by key
   """
   devices = [device
              for device in config.GetHardware().GetDevice()
              if isinstance(device, deviceType)]
   devices.sort(key=lambda d: d.GetKey())
   return devices


def SortedDisksOfVM(vm):
   """Return a sorted list of a VM's disks.  This is used to keep the
   i'th disk index stable.

   @param vm [in] Vim.VirtualMachine reference
   @return a list of Vim.Vm.Device.VirtualDisk references sorted by key
   """
   return SortedDevices(vm.GetConfig(), Vim.Vm.Device.VirtualDisk)


def GetDiskReplicationId(repConfig, diskKey):
   """Return the replication ID of the disk.

   @param repConfig [in] Vim.Vm.ReplicationConfigSpec
   @param diskKey   [in] key of the disk we want the replication ID for
   @returns the replication ID
   """
   for disk in repConfig.GetDisk():
      if disk.key == diskKey:
         return disk.diskReplicationId


def ParsePath(path):
   """Decode an absolute path into a (datastore, relative path) tuple.

   E.g., "/vmfs/volumes/foo/bar/baz.vmdk" becomes ("foo", "bar/baz.vmdk").
   Also supports simpler "foo/bar/baz.vmdk" input which would also become
   ("foo", "bar/baz.vmdk").

   @param path [in] a 'full' datastore path
   @return a (datastore, relative path) tuple

   @throws ValueError if path cannot be split
   """
   parts = path.split('/')

   if parts[0] == 'vmfs' and parts[1] == 'volumes':
      idx = 2
   elif parts[1] == 'vmfs' and parts[2] == 'volumes':
      idx = 3
   else:
      # Assume its "datastore/path".
      idx = 0

   datastore = parts[idx]
   relative_path = '/'.join(parts[idx + 1:])

   if not datastore or not relative_path:
      raise ValueError('Path "{0}" cannot be split into parts'.format(path))

   return (datastore, relative_path)


def ParseDatastorePath(filePath):
   """Split a datastore path of the form "[ds] path" into
   datastore part and relative file path

   """
   try:
      match = re.match(r'\[(.*)\] (.*)', filePath)
      datastore = match.group(1)
      relPath = match.group(2)
   except:
      raise RuntimeError('Invalid datastore path {0}'.format(filePath))

   return (datastore, relPath)


def FindDiskWithKey(vm, diskDeviceKey):
   """Find a disk with the specified device key in the VM's config.

   @param vm            [in] Vim.VirtualMachine reference
   @param diskDeviceKey [in] The device key of the disk to find
   @return a Vim.Vm.Device.VirtualDisk reference

   @throws NoSuchDiskError if no disk with the given key can be found.
   """
   for device in vm.GetConfig().GetHardware().GetDevice():
      if isinstance(device, Vim.Vm.Device.VirtualDisk):
         if (device.GetKey() == diskDeviceKey):
            return device

   raise NoSuchDiskError(vm, diskKey=diskDeviceKey)


def FindDiskAtIndex(vm, i):
   """Find the i'th disk on the given VM.

   @param vm [in] Vim.VirtualMachine reference
   @param i  [in] the index of the requested disk
   @return a Vim.Vm.Device.VirtualDisk reference

   @throws NoSuchDiskError if i is out of range
   """

   # First sort the disks by device key, I'm not sure how stable this
   # 'index' is otherwise.
   disks = SortedDisksOfVM(vm)

   if i > len(disks):
      raise NoSuchDiskError(vm, diskIndex=i)

   return disks[i]


def GetDiskType(vmDisk):
   """Return the disk typeof the disk.

   @param vmDisk [in] Vim.Vm.Device.VirtualDisk reference
   @return a Vim.VirtualDiskManager.VirtualDiskType value
   """
   backing = type(vmDisk.backing).__name__.split(".")[-1]

   if backing.find("Flat") == 0:
      if backing == "FlatVer2BackingInfo":
         if vmDisk.backing.thinProvisioned:
            diskType = Vim.VirtualDiskManager.VirtualDiskType.thin
         else:
            if vmDisk.backing.eagerlyScrub:
               diskType = Vim.VirtualDiskManager.VirtualDiskType.eagerZeroedThick
            else:
               diskType = Vim.VirtualDiskManager.VirtualDiskType.preallocated
      else:
         diskType = Vim.VirtualDiskManager.VirtualDiskType.preallocated
   elif backing.find("SeSparse") == 0:
      if vmDisk.backing.parent:
         # A snapshot
         diskType = Vim.VirtualDiskManager.VirtualDiskType.thin
      else:
         # As a base disk.
         diskType = Vim.VirtualDiskManager.VirtualDiskType.seSparse
   elif backing.find("Sparse") == 0:
      diskType = Vim.VirtualDiskManager.VirtualDiskType.thin
   else:
      # For anything else (rdm, unknown, etc.) return preallocated
      diskType = Vim.VirtualDiskManager.VirtualDiskType.preallocated

   return diskType


def MakeVMDKName(vmDisk):
   """Make a name for a replica-side VMDK for the given primary-side
   disk.

   NOTE: The disk replication ID is a function of the VM name
   and the primary-side disk key, so its very stable.

   @param vmDisk [in] Vim.Vm.ReplicationConfigSpec.DiskSettings reference
   @return a string representing the VMDK name
   """
   return "%s.vmdk" % vmDisk.GetDiskReplicationId()


def CreateDiskRemoteStorage(vm,
                            priDiskSpec,
                            ds,
                            destDir,
                            policy=None,
                            keyServerId=None,
                            keyId=None,
                            mayExist=False):
   """Create the remote site storage for the given primary-site disk spec.

   @param vm          [in] Vim.VirtualMachine reference
   @param priDiskSpec [in] Vim.Vm.ReplicationConfigSpec.DiskSettings reference
   @param ds          [in] RemoteStorage wrapper of the remote datastore.
   @param destDir     [in] destination directory for the disk.
   @param policy      [in] policy to apply to the disk.
   @param mayExist    [in] don't raise an exception if the disk already exists.

   @throws Vmodl.Fault.NotSupported if the requested disk type is not
           supported by the host
   @throws Vim.Fault.FileAlreadyExists, Vim.Fault.CannotCreateFile if
           the disk already exists and mayExist is False
   """
   # Find the primary's VM disk (to get the size/type)
   vmDisk = FindDiskWithKey(vm, priDiskSpec.GetKey())

   size = vmDisk.GetCapacityInKB()
   diskType = GetDiskType(vmDisk)

   # Concoct a standard name based on the primary disk spec
   targetDisk = "%s/%s" % (destDir, MakeVMDKName(priDiskSpec))

   try:
      try:
         ds.CreateDisk(path=targetDisk, sizeKb=size, diskType=diskType,
                       policy=policy, keyServerId=keyServerId, keyId=keyId)
      except Vmodl.Fault.NotSupported as e:
         if diskType == Vim.VirtualDiskManager.VirtualDiskType.seSparse:
            #
            # Fall back to thin for secondaries that don't support
            # seSparse.
            #
            # XXX PR 1370814
            # We don't support hosts older than 5.5 anymore so we
            # should always have suport for seSparse and this should
            # be removed.
            #
            logger.warning('Host can\'t support seSparse disks. '
                           'Falling back to thin.')
            diskType = Vim.VirtualDiskManager.VirtualDiskType.thin
            ds.CreateDisk(path=targetDisk, sizeKb=size, diskType=diskType)
         else:
            raise e
   except (Vim.Fault.FileAlreadyExists, Vim.Fault.CannotCreateFile) as e:
      if mayExist:
         return
      raise e


def SupportedDiskFormatChoices():
   """Get the short names of the supported disk formats. Useful for passing
   as a "choices" argument to optparse.
   """
   return ['thin', 'preallocated', 'seSparse', 'eagerZeroedThick']


def SupportedDiskFormatChoicesToDiskType(diskType):
   """Convert a short disk format name to a virtual disk type.

   @return a Vim.VirtualDiskManager.VirtualDiskType value
   """
   dt = Vim.VirtualDiskManager.VirtualDiskType
   types = {
      'thin'            : dt.thin,
      'preallocated'    : dt.preallocated,
      'seSparse'        : dt.seSparse,
      'eagerZeroedThick': dt.eagerZeroedThick
   }

   return types[diskType]


def _GetStoragePolicy(name='None',
                      profileId='Phony Profile ID',
                      createdBy='None',
                      creationTime='1970-01-01T00:00:00Z',
                      lastUpdatedTime='1970-01-01T00:00:00Z',
                      generationId='1'):
   """Create an empty storage policy XML document.

   @return a tuple of (document, subProfiles) where document
           is a minidom.Document and subProfiles is the child
           to be used to add capabilities.
   """
   policy = minidom.Document()

   storageProfile = policy.createElement('storageProfile')
   storageProfile.setAttribute('xsi:type', 'StorageProfile')
   policy.appendChild(storageProfile)

   createdByEl = policy.createElement('createdBy')
   createdByEl.appendChild(policy.createTextNode(createdBy))
   storageProfile.appendChild(createdByEl)

   creationTimeEl = policy.createElement('creationTime')
   creationTimeEl.appendChild(policy.createTextNode(creationTime))
   storageProfile.appendChild(creationTimeEl)

   lastUpdatedTimeEl = policy.createElement('lastUpdatedTime')
   lastUpdatedTimeEl.appendChild(policy.createTextNode(lastUpdatedTime))
   storageProfile.appendChild(lastUpdatedTimeEl)

   generationIdEl = policy.createElement('generationId')
   generationIdEl.appendChild(policy.createTextNode(generationId))
   storageProfile.appendChild(generationIdEl)

   nameEl = policy.createElement('name')
   nameEl.appendChild(policy.createTextNode(name))
   storageProfile.appendChild(nameEl)

   profileIdEl = policy.createElement('profileId')
   profileIdEl.appendChild(policy.createTextNode(profileId))
   storageProfile.appendChild(profileIdEl)

   constraints = policy.createElement('constraints')
   storageProfile.appendChild(constraints)

   subProfiles = policy.createElement('subProfiles')
   constraints.appendChild(subProfiles)

   return policy, subProfiles


def GetEncryptionPolicy():
   """Create a policy that attaches the encryption filter to the disk."""
   policy, subProfiles = _GetStoragePolicy()

   capabilityEl = policy.createElement('capability')
   subProfiles.appendChild(capabilityEl)

   capabilityIdEl = policy.createElement('capabilityId')
   capabilityEl.appendChild(capabilityIdEl)

   idEl = policy.createElement('id')
   idEl.appendChild(policy.createTextNode('vmwarevmcrypt@ENCRYPTION'))
   capabilityIdEl.appendChild(idEl)

   namespaceEl = policy.createElement('namespace')
   namespaceEl.appendChild(policy.createTextNode('IOFILTERS'))
   capabilityIdEl.appendChild(namespaceEl)

   constraintEl = policy.createElement('constraint')
   capabilityIdEl.appendChild(constraintEl)

   nameEl = policy.createElement('name')
   nameEl.appendChild(policy.createTextNode("Rule-Set 1: IOFILTERS"))
   subProfiles.appendChild(nameEl)

   return policy.toprettyxml(encoding='UTF-8')


class RemoteStorage():
   """Wrapper for the HBR-ish uses of remote storage for a single
   datastore.  Provides methods for creating disks, creating directories,
   and cleaning both up.
   """

   def __init__(self,
                datastore='Storage1',
                si=None,
                hostd=None):
      """Wrap a datastore on a certain host.

      @param datastore [in] name of the datastore to create a wrapper for
      @param si        [in] service instance of the hostd agent of the
                            host used to access the datastore

      @throws RuntimeError if the given datastore can't be found on given host
      """
      assert si is None

      self._hostd = hostd
      self._si = hostd.GetServiceInstance()

      testPath = "/vmfs/volumes/%s" % datastore

      # What's this?
      rc = self._si.RetrieveContent()

      # Look up the given datastore (mostly to get the UUID of the ds):
      hs = pyVim.host.GetHostSystem(self._si)

      # Get the VirtualDiskManager and FileManager APIs out of hostd:
      self._vdm = rc.GetVirtualDiskManager()
      self._fm = rc.GetFileManager()
      self._datastorePrettyName = None
      self._datastorePath = None
      self._dsb = hs.GetDatastoreBrowser()

      datastores = hs.GetDatastore()
      for d in datastores:
         dInfo = d.GetSummary()
         # Craptastic: need to get the mount list, as its on the only
         # reliable place to get the UUID for both VMFS and NFS mounts.
         # It stored in the 'mount path'.
         mnts = d.GetHost()
         # Must be at least one mount, all mounts should have same UUID
         # path ... so "mnts[0]" is fine without any checks.
         if dInfo.name == datastore or testPath == mnts[0].mountInfo.path:
            self._datastoreType = dInfo.GetType()
            self._datastorePrettyName = dInfo.name
            self._datastorePath = mnts[0].mountInfo.path
            self._datastoreMO = d
            self._datastoreUUID = os.path.split(self._datastorePath)[1]

      if not self._datastorePath:
         raise RuntimeError('Cannot find datastore %s on host %s' % \
               (datastore, hs))

   def __str__(self):
      return "[%s]" % (self._datastorePrettyName)

   def Host(self):
      return self._hostd

   def CreateDisksFor(self,
                      groupSpec,
                      diskSizes,
                      mkdir=True,
                      dirCanExist=True,
                      disksCanExist=False):
      """Create all the directories and disks needed for the given
      replica-side replication spec.

      diskSizes is a hash mapping diskIDs to KB size of the disk

      XXX hoist this into hostd wrapper so it can handle multiple datastores
      """

      madeDirs = {}

      assert len(groupSpec.vms) == 1
      assert self._datastoreUUID == groupSpec.vms[0].virtualMachineIdent.datastoreUUID

      vmDir = groupSpec.vms[0].virtualMachineIdent.pathname

      try:
         self.MakeDirectory(vmDir)
      except Vim.Fault.FileAlreadyExists as e:
         if not dirCanExist:
            raise e

      madeDirs[vmDir] = True

      for disk in groupSpec.vms[0].replicatedDisks:
         diskID = disk.diskIdent.id
         ds = disk.diskIdent.datastoreUUID
         pth = disk.diskIdent.pathname
         sz = diskSizes[diskID]

         # XXX handle disks in new paths ... (make path on demand)
         assert os.path.dirname(pth) in madeDirs

         # XXX all on the same datastore for now
         assert ds == self._datastoreUUID

         try:
            self.CreateDisk(pth, sz)
         except Vim.Fault.FileAlreadyExists as e:
            if not disksCanExist:
               raise e

   def VMFSPath(self, path):
      """Return the vanilla VMFS version of the given path on the datastore
      represented by this object.  Returns the "UUID" version
      of the path (not the prettyname version).

      @param path [in] relative path in the datastore
      @return an absolute path of the form "/vmfs/volumes/UUID/path".
      """

      if path.startswith(self._datastorePath):
         return path
      return os.path.join(self._datastorePath, path)

   def DatastoreType(self):
      """Return the datastore type."""
      return self._datastoreType

   def IsObjectBackend(self):
      """Return True if datastore is object based, False otherwise"""
      objBackends = {'vsan', 'vsand', 'vvol'}
      if self.DatastoreType().lower() in objBackends:
         return True
      return False

   def DatastorePrettyName(self):
      """Return the "pretty name" of the datastore this object represents.
      """
      return self._datastorePrettyName

   def DatastoreUUID(self):
      """Return the UUID of the datastore this object represents."""
      return self._datastoreUUID

   def DatastorePath(self, path):
      """Return the 'datastore' style name of the given path on the datastore
      represented by this object.  Returns the "UUID" version
      of the path (not the prettyname version).

      @param path [in] relative path in the datastore
      @return a string of the form "[] /vmfs/volumes/UUID/path".
      """
      return "[] %s" % self.VMFSPath(path)

   def DatastoreToVMFSPath(self, path):
      """Convert a datastore path to a vanilla VMFS path

      @param path [in] datastore path of the form "[ds] path"
      @return an absolute path of the form "/vmfs/volumes/UUID/path".
      """
      try:
         match = re.match(r'\[(.*)\] (.*)', path)
         datastore = match.group(1)
         path = match.group(2)
      except:
         raise RuntimeError('Invalid datastore path {0}'.format(path))

      if datastore != self._datastorePrettyName and\
            datastore != self._datastoreUUID:
         raise RuntimeError('Invalid datastore {0}'.format(datastore))

      return os.path.join(self._datastorePath, path)

   def CreateDisk(self,
                  path,
                  sizeKb=4 * 1024,
                  diskType=Vim.VirtualDiskManager.VirtualDiskType.thin,
                  adapType=Vim.VirtualDiskManager.VirtualDiskAdapterType.lsiLogic,
                  policy=None,
                  keyServerId=None,
                  keyId=None):
      """Create a disk with the given name on the this datastore.

      @param path     [in] path where the disk will be created
      @param sizeKb   [in] size of the disk in kilobytes
      @param diskType [in] type of the disk
      @param adapType [in] type of the adapter used for the disk
      @param policy   [in] policy blob to use for this disk
      """

      if diskType == Vim.VirtualDiskManager.VirtualDiskType.seSparse:
         #
         # seSparse uses a different virtual disk spec that lets you
         # set the grain size if you want to. However, we just want
         # to stick with the default
         #
         spec = Vim.VirtualDiskManager.SeSparseVirtualDiskSpec(
            diskType=diskType,
            adapterType=adapType,
            capacityKb=sizeKb)
      else:
         spec = Vim.VirtualDiskManager.FileBackedVirtualDiskSpec(
            diskType=diskType,
            adapterType=adapType,
            capacityKb=sizeKb)

      if policy != None:
         profileSpec = Vim.Vm.DefinedProfileSpec()
         magicKey = "com.vmware.vim.sps"
         magicId = "someMagicValueThatMeansSomethingHigherUpInTheStack"
         profileSpec.SetProfileId(magicId)
         profileData = Vim.Vm.ProfileRawData()
         profileData.SetExtensionKey(magicKey)
         profileData.SetObjectData(policy)
         profileSpec.SetProfileData(profileData)
         spec.SetProfile([profileSpec])

      if keyServerId != None and keyId != None:
         spec.SetCrypto(pyHbr.hostd.CreateCryptoSpec(keyId, keyServerId))

      logger.info('Creating disk {} with spec {}'.format(
         path, spec))
      path = self.DatastorePath(path)
      crTask = self._vdm.CreateVirtualDisk(name=path,
                                           spec=spec)
      pyVim.task.WaitForTask(crTask, si=self._si)

   def CreateChildDisk(self,
                       parentPath,
                       childPath,
                       isLinkedClone=False):
      """Create a child disk from the parent on the this datastore.

      @param parentPath    [in] path of the parent disk
      @param childPath     [in] path of the child disk
      @param isLinkedClone [in] create a linked clone
      """
      ccTask = self._vdm.CreateChildDisk(childName=childPath,
                                         parentName=parentPath,
                                         isLinkedClone=isLinkedClone)
      pyVim.task.WaitForTask(ccTask, si=self._si)


   def CreateDiskHierarchy(self,
                           basePath,
                           numSnaps,
                           sizeKb=4 * 1024,
                           diskType=Vim.VirtualDiskManager.VirtualDiskType.thin,
                           adapType=Vim.VirtualDiskManager.VirtualDiskAdapterType.lsiLogic):
      """Create a disk hierarchy with the given depth on the datastore.

      @param basePath [in] path of the base disk
      @param numSnaps [in] number of disk in the hierarchy
      @param sizeKb   [in] size of the base disk
      @param diskType [in] type of the disk hierarchy
      @param adapType [in] type of the adapter used for the disk hierarchy
      @return the list of disk paths from the base to the child-most disk.
      """

      paths = []

      # First, create the base disk.
      self.CreateDisk(path=basePath,
                      sizeKb=sizeKb,
                      diskType=diskType,
                      adapType=adapType)
      paths.append(self.DatastorePath(basePath))

      # Then create the child disks
      baseFmt = basePath[:basePath.find('.vmdk')] + '-%03d.vmdk'
      for i in range(0, numSnaps):
         childPath = self.DatastorePath(baseFmt % i)
         self.CreateChildDisk(parentPath=paths[-1], childPath=childPath)
         paths.append(childPath)

      return paths

   def ImportUnmanagedSnapshot(self,
                               path,
                               uri):
      """Import an unmanaged object to a managed disk.

      @param path    [in] Path where the descriptor should be created
      @param uri     [in] unmanaged object URI that should be imported
      """
      path = self.DatastorePath(path)
      self._vdm.ImportUnmanagedSnapshot(vdisk=path, vvolId=uri)


   def ReleaseManagedSnapshot(self, path):
      """Release a managed snapshot descriptor, reverting its
      underlying object to an unmanaged state.

      @param path    [in] Path to the descriptor that should be released
      """
      path = self.DatastorePath(path)
      self._vdm.ReleaseManagedSnapshot(vdisk=path)

   def QueryObjectInfo(self, uri, includeDependents=True):
      """Get info about a uri.

      @param uri     [in] object uri to query
      @param includeDependents [in] include dependent object info
      """
      convTask = self._vdm.QueryObjectInfo(uri=uri,
                                           includeDependents=includeDependents)
      result = pyVim.task.WaitForTask(convTask, si=self._si)
      if result == "error":
         raise convTask.info.error
      return convTask.info.result

   def QueryObjectTypes(self):
      """Get a list of supported object types on a host
      """
      return self._vdm.QueryObjectTypes()

   def DeleteDisk(self, path):
      """Delete the given disk from this datastore.

      @param path [in] path of the disk
      """
      path = self.DatastorePath(path)

      delTask = self._vdm.DeleteVirtualDisk(name=path)
      pyVim.task.WaitForTask(delTask, si=self._si)
      # Note: No error on if disk is already gone?

   def GetDiskType(self, path, usingParent=True):
      path = self.DatastorePath(path)
      task = self._vdm.QueryVirtualDiskInfo(name=path,
                                            includeParents=usingParent)
      result = pyVim.task.WaitForTask(task, si=self._si)
      if result == "error":
         raise task.info.error

      return task.info.result

   def MakeDirectory(self, path):
      """Make a directory with the given name on this datastore.  Will not
      create any required intermediate directories.

      @param path [in] path of the new directory
      """
      path = self.DatastorePath(path)

      # MakeDirectory call is synchronous, so no need to WaitForTask
      self._fm.MakeDirectory(path)

   def CleanupDirectory(self, path):
      """Remove the given directory.  Recursively deletes all content!

      @param path [in] path of the directory to cleanup
      """
      # Construct the search spec
      searchSpec = Vim.Host.DatastoreBrowser.SearchSpec()
      # When deleting a vvol directory, the path must end with "/"
      if not path.endswith("/"):
         path = path + "/"
      path = self.DatastorePath(path)

      # Invoke the search
      try:
         searchTask = self._dsb.SearchSubFolders(path, searchSpec)
         pyVim.task.WaitForTask(searchTask, si=self._si)
      except Vim.Fault.FileNotFound:
         # Directory not there is good enough.
         return

      # Delete all the files in the directory
      # PR 2932904 - currently hostd will leave vSAN orphan objects if we delete
      # the disks one by one. However, it will behave well if we delete the whole
      # directory (it will scan the dir and enumerate obj backed items and properly
      # delete them)
      if not self.IsObjectBackend():
         flatVmdks = []
         for r in searchTask.GetInfo().GetResult():
            for f in r.GetFile():
               if f.GetPath().endswith("-flat.vmdk"):
                  flatVmdks.append(f)
                  continue

               # Skip VMFS system files, they cannot be deleted
               if (f.GetPath().endswith('.sf')):
                  continue

               filepath = path + f.GetPath()
               try:
                  logger.debug("Deleting: {}".format(f.GetPath()))
                  delTask = self._fm.DeleteFile(filepath)
                  pyVim.task.WaitForTask(delTask, si=self._si)
               except Vim.Fault.FileNotFound:
                  pass

         for f in flatVmdks:
            filepath = path + f.GetPath()
            try:
               logger.debug("Deleting: {}".format(f.GetPath()))
               delTask = self._fm.DeleteFile(filepath)
               pyVim.task.WaitForTask(delTask, si=self._si)
            except Vim.Fault.FileNotFound:
               pass

      # Finally, delete the directory
      try:
         delTask = self._fm.DeleteFile(path)
         pyVim.task.WaitForTask(delTask, si=self._si)
      except Vim.Fault.FileNotFound:
         # Directory not there is good enough.
         pass

   def Move(self, path, newPath):
      """Move the given file or directory from the existing path to the
      newPath.

      NOTE: both path and new path are assumed to be on this datastore.

      @param path    [in] old path of the file or directory
      @param newPath [in] new path of the file or directory
      """

      path = self.DatastorePath(path)
      newPath = self.DatastorePath(newPath)

      task = self._fm.Move(sourcePath=path, destinationPath=newPath,
                           force=False, fileType="File")

      pyVim.task.WaitForTask(task, si=self._si)

   def Copy(self, path, newPath, force=False):
      """Copy the given file or directory from the existing path to the
      newPath.

      NOTE: both path and new path are assumed to be on this datastore.

      @param path    [in] source of the file or directory
      @param newPath [in] destination where to copy the file or directory
      """
      path = self.DatastorePath(path)
      newPath = self.DatastorePath(newPath)

      task = self._fm.CopyFile(sourceName=path,
                               destinationName=newPath,
                               force=force)

      pyVim.task.WaitForTask(task, si=self._si)

   def ListFiles(self, directory, glob='*', recurse=False):
      """Lists all the files in the given directory.

      @param directory [in] path of the directory to list files from
      @param glob      [in] pattern that the files must match
      @param recurse   [in] whether the search should recurse inside
                            subdirectories
      @return a list of all the files matching the pattern
      """
      # Construct the search spec
      searchSpec = Vim.Host.DatastoreBrowser.SearchSpec()
      # when delete vvol directory, the path must end up with "/"
      if not directory.endswith("/"):
         directory = directory + "/"
      path = self.DatastorePath(directory)

      # Invoke the search
      try:
         if recurse:
            searchTask = self._dsb.SearchSubFolders(path, searchSpec)
         else:
            searchTask = self._dsb.Search(path, searchSpec)
         pyVim.task.WaitForTask(searchTask, si=self._si)
      except Vim.Fault.FileNotFound:
         # Directory not there is good enough.
         return

      if recurse:
         results = searchTask.GetInfo().GetResult()
      else:
         results = [searchTask.GetInfo().GetResult()]

      files = []
      for r in results:
         for f in r.GetFile():
            if fnmatch.fnmatch(f.GetPath(), glob):
               files += [f.GetPath()]

      return sorted(files)

