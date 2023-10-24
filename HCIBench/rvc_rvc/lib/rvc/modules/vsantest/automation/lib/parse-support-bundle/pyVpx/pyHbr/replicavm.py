# Copyright (c) 2015-2022 VMware, Inc.  All rights reserved.
# -- VMware Confidential

import logging
import pyHbr.hbrsrv
import time

from pyHbr.hbrsrv import GroupSpecFromRepVmInfo, \
                         CreateRetentionPolicy, \
                         CreateGroupMappingFromGroupSpec
from pyHbr.hostd import CreateReplicationConfigSpec,\
                        CreateDiskSettingsFromVirtualDisk
from pyHbr.disks import CreateDiskRemoteStorage
from pyHbr.util import FindIPAddressFor, SSHCLI
from pyVmomi import Vim
from pyVmomi import Hbr

logger = logging.getLogger('pyHbr.replicavm')

class BaseReplicaVM(object):
   """Shared methods/state for different replicated VM types

   XXX Right now, this operates under the assumption that there is only one
   VM in a replication group.
   XXX Most of the settings for this are hard-coded. Change this so it's
   more easily customizable.
   """

   def __init__(self, vm, primaryHostd):
      self._vm = vm._mo
      self._primaryHostd = primaryHostd
      self._hbrManager = primaryHostd.GetHbrManager()
      self._hbrInternalSystem = primaryHostd.GetHbrInternalSystem()
      self._replicaHostd = None
      self._targetDs = None
      self._hbrsrvVmodl = None
      self._repMgr = None

   def GetGroupID(self):
      if not hasattr(self, '_groupID'):
         vmName = self._vm.GetConfig().GetName()

         self._vmName = vmName
         self._groupID = '{0}'.format(vmName)
      return self._groupID

   def GetReplicationConfig(self):
      return self._hbrManager.RetrieveReplicationConfig(self._vm)

   def GetReplicationState(self):
      return self._hbrManager.QueryReplicationState(self._vm)

   def GetPrimaryVM(self):
      return self._vm

   def EnableReplication(self, hbrsrvIp, hbrsrvLwdPort,
                         netCompression=True, quiesceGuest=True,
                         netEncryption=False,
                         remoteCertificateThumbprint=None,
                         broker=False,
                         dataSetsReplicationEnabled=False):
      disks = list(filter(lambda device: isinstance(device, Vim.Vm.Device.VirtualDisk),
                          self._vm.GetConfig().GetHardware().GetDevice()))
      disks = list(map(lambda disk: CreateDiskSettingsFromVirtualDisk(
                                       disk, '{0}_{1}'.format(self.GetGroupID(),
                                                              disk.GetKey())),
                       disks))

      # Must be an IP address
      hbrsrvIp = FindIPAddressFor(hbrsrvIp)
      repConfig = CreateReplicationConfigSpec(self.GetGroupID(), hbrsrvIp,
              hbrsrvLwdPort, disks,
              netCompression=netCompression, quiesceGuest=quiesceGuest,
              netEncryption=netEncryption,
              remoteCertificateThumbprint=remoteCertificateThumbprint,
              broker=broker)
      repConfig.SetDataSetsReplicationEnabled(dataSetsReplicationEnabled)
      task = self._hbrManager.EnableReplication(self._vm, repConfig)
      self._primaryHostd.WaitForTask(task)

   def DisableReplication(self):
      task = self._hbrManager.DisableReplication(self._vm)
      self._primaryHostd.WaitForTask(task)

   def GetGroupSpec(self):
      return self._groupSpec

   def RecreateReplicationGroup(self, groupSpec=None):
      if groupSpec is None:
         groupSpec = self._groupSpec
      task = self._repMgr.CreateReplicationGroup(groupSpec)
      self._hbrsrvVmodl.WaitForTask(task)
      self._groupSpec = groupSpec

   def GetReplicationGroup(self):
      assert self._repMgr is not None

      return self._repMgr.GetReplicationGroup(self.GetGroupID())

   def RemoveReplicationGroup(self):
      assert self._repMgr is not None

      repConfig = self.GetReplicationConfig()

      group = self._repMgr.GetReplicationGroup(self.GetGroupID())
      task = group.Remove()
      self._hbrsrvVmodl.WaitForTask(task)

   def WaitForVMHbrState(self, targetState, timeout=-1, progressCB=None):
      def replicationProgress(progress):
         if progress >= 0:
            logger.info('{}% of the timeout has elapsed'.format(progress))

         logger.info('Replication state: {}'.format(self.GetReplicationState()))

      if progressCB is None:
         progressCB = replicationProgress

      self._primaryHostd.WaitForVMHbrState(self._vm, targetState, timeout,
                                           progressCB=progressCB)

   def PowerOn(self):
      task = self._vm.PowerOn()
      self._primaryHostd.WaitForTask(task)

   def PowerOff(self):
      task = self._vm.PowerOff()
      self._primaryHostd.WaitForTask(task)

   def InvokeFSR(self):
      task = self._vm.InvokeFSR()
      self._primaryHostd.WaitForTask(task)

   def CreateHbrsrvFilter(self, *properties):
      assert self._repMgr is not None
      group = self._repMgr.GetReplicationGroup(self.GetGroupID())
      pc = pyHbr.hbrsrv.CreateGroupsFilter(self._repMgr, [group], *properties)
      return pc

   def FullSync(self):
      task = self._hbrManager.FullSync(self._vm)
      self._primaryHostd.WaitForTask(task)

   def CreateInstance(self, wait=False, timeout=-1):
      task = self._hbrManager.CreateInstance(self._vm)
      self._primaryHostd.WaitForTask(task)

      if wait:
         self.WaitForVMHbrState('idle', timeout)

   def ReconfigureReplication(self, newRepConfig):
      task = self._hbrManager.ReconfigureReplication(self._vm, newRepConfig)
      self._primaryHostd.WaitForTask(task)

   def SetRpo(self, rpo):
      repConfig = self.GetReplicationConfig()
      repConfig.SetRpo(rpo)

      self.ReconfigureReplication(repConfig)

   def PauseReplication(self):
      task = self._hbrManager.PauseReplication(self._vm)
      self._primaryHostd.WaitForTask(task)

   def ResumeReplication(self):
      task = self._hbrManager.ResumeReplication(self._vm)
      self._primaryHost.WaitForTask(task)

   def StartOfflineInstance(self, imageId=None, wait=False, maxWaitTime=None,):
      task = self._hbrManager.StartOfflineInstance(self._vm, imageId)

      if wait:
         self._primaryHostd.WaitForTask(task, maxWaitTime = maxWaitTime)
         return None
      else:
         return task

   def StopOfflineInstance(self, imageId=None):
      self._hbrManager.StopOfflineInstance(self._vm, imageId)

   def AbortInstance(self):
      self._hbrInternalSystem.AbortVmInstance(self._vm)

   def RunCommand(self, cmd):
      for i in range(12):
         ip = self._vm.GetGuest().GetIpAddress()
         if ip is not None:
            break
         time.sleep(5)

      assert ip is not None

      with SSHCLI(ip, 'root', 'ca$hc0w') as ssh:
         return ssh.RunCommand(cmd)

   def RunCommandInBackground(self, cmd):
      for i in range(12):
         ip = self._vm.GetGuest().GetIpAddress()
         if ip is not None:
            break
         time.sleep(5)

      assert ip is not None

      with SSHCLI(ip, 'root', 'ca$hc0w') as ssh:
         return ssh.RunCommandInBackground(cmd)

   def Reconfigure(self, configSpec):
      task = self._vm.Reconfigure(configSpec)
      self._primaryHostd.WaitForTask(task)

   def WaitForTools(self):
      for i in range(60):
         guest = self._vm.GetGuest()
         if (guest.GetGuestId() and
             guest.GetToolsStatus() in [
                Vim.Vm.GuestInfo.ToolsStatus.toolsOld,
                Vim.Vm.GuestInfo.ToolsStatus.toolsOk
                ]):
            break
         time.sleep(5)
      else:
         raise RuntimeError("VM tools were not ready after 3 minutes")

   def GetRootSnapshot(self):
      return self._vm.GetRootSnapshot()

class ReplicaVM(BaseReplicaVM):
   """Wrapper for a typical host file-path based replications
   """
   def __init__(self, vm, primaryHostd, replicaHostd):
      super(ReplicaVM, self).__init__(vm, primaryHostd)
      self._replicaHostd = replicaHostd

   def GetReplicaDir(self):
      if not hasattr(self, '_replicaDir'):
         vmName = self._vm.GetConfig().GetName()
         self._replicaDir = '{0}_replica'.format(vmName)
      return self._replicaDir

   def GetImagesDir(self):
      if not hasattr(self, '_imagesDir'):
         vmName = self._vm.GetConfig().GetName()
         self._imagesDir = '{0}_images'.format(vmName)
      return self._imagesDir

   def GetRecoveredVM(self, image=None):
      if image is None:
         group = self._repMgr.GetReplicationGroup(self.GetGroupID())
         image = group.GetActiveImage().virtualMachines[0]

      vmx = None
      FileType = Hbr.Replica.ConfigFileImage.FileType
      for file in image.configFiles:
         if file.type == FileType.config:
            vmx = file
            break

      assert vmx is not None, 'No vmx in the image configuration files'

      vmName = '{0}_image'.format(self._vmName)

      replicaDs = self._replicaHostd.RemoteStorage(
         image.virtualMachineIdent.location.hostDatastoreUUID)
      vmxPath = '{0}/{1}'.format(
         image.virtualMachineIdent.location.hostPathname,
         vmx.baseFileName)

      task = self._replicaHostd.RegisterVm(
         cfg=replicaDs.DatastorePath(vmxPath),
         name=vmName)
      self._replicaHostd.WaitForTask(task)

      vm = task.info.result
      return self._replicaHostd.GetPyVimVM(vm)

   def CreateReplicaDisksForVm(self, replicaHostd, targetDatastore, policy=None,
                               keyServerId=None, keyId=None, mayExist=False):
      repConfig = self.GetReplicationConfig()
      self._replicaHostd = replicaHostd
      self._targetDs = replicaHostd.RemoteStorage(targetDatastore)

      try:
         self._targetDs.MakeDirectory(self.GetReplicaDir())
      except (Vim.Fault.FileAlreadyExists, Vim.Fault.CannotCreateFile) as e:
         logger.warning('Destination directory already exists ([{0}] {1})'.format(
                           targetDatastore, self.GetReplicaDir()))

      for disk in repConfig.disk:
         CreateDiskRemoteStorage(self._vm, disk, self._targetDs,
                                 self.GetReplicaDir(),
                                 policy=policy,
                                 keyServerId=keyServerId, keyId=keyId,
                                 mayExist=mayExist)

   def CreateReplicationGroup(self,
                              hbrsrvVmodl,
                              policyTiers=[],
                              trustedSite=None,
                              clientEncryptionRequired=None):
      vmRepConfig = self.GetReplicationConfig()
      groupSpec = GroupSpecFromRepVmInfo(vmRepConfig,
                                         self._targetDs.DatastoreUUID(),
                                         self.GetReplicaDir())
      groupSpec.retentionPolicy = CreateRetentionPolicy(policyTiers=policyTiers)
      groupSpec.trustedSite = trustedSite
      groupSpec.clientEncryptionRequired = clientEncryptionRequired

      self._groupSpec = groupSpec

      self._hbrsrvVmodl = hbrsrvVmodl
      self._repMgr = hbrsrvVmodl.GetReplicationManager()

      task = self._repMgr.CreateReplicationGroup(groupSpec)
      self._hbrsrvVmodl.WaitForTask(task)

   def AddToBroker(self,
                   brokerVmodl):
      """
      Add the replica group to the broker.
      The replication must already be configured on the group.
      """
      self._brokerVmodl = brokerVmodl
      hbrsrvVmodl = self._hbrsrvVmodl

      mapping = CreateGroupMappingFromGroupSpec(self._groupSpec,
                                                hbrsrvVmodl.GetInstanceUUID(),
                                                hbrsrvVmodl.GetIPAddress())
      self._brokerMgr = brokerVmodl.GetBrokerManager()

      task = self._brokerMgr.AddServerMappings([mapping])
      brokerVmodl.WaitForTask(task)

   def DeleteFromBroker(self):
      """
      Delete the replica from the broker.
      """
      groupID = self._groupSpec.id
      task = self._brokerMgr.DeleteServerMappings([groupID])
      self._brokerVmodl.WaitForTask(task)

   def RemoveReplicaDisksForVm(self):
      """
      Given a groupID remove the remote storage that was allocated for
      the group and remove the group's configuration from the HBR Server

      The hbrvmCfg and esxCfg parameters should each be of the
      form "<user>:<pass>@<host>".
      """
      assert self._targetDs is not None
      self._targetDs.CleanupDirectory(self.GetReplicaDir())

   def SetArchivalGroupSpec(self, archivalGroupSpec):
      self._archivalGroupSpec = archivalGroupSpec

   def GetArchivalGroupId(self):
      assert self._archivalGroupSpec is not None
      return self._archivalGroupSpec.archivalGroupId

   def RelinkArhivalGroup(self):
      """
      Re-link archival group to replication group. Both groups must exists.
      This is needed if both groups have been created and later replica group
      was removed and recreated again. It was re-created unlinked to prior
      archival group. This method re-link it back again.

      _archivalGroupSpec is not none, if previously archival group has been
      created.
      """
      if self._archivalGroupSpec is not None:
         repGroup = self.GetReplicationGroup()
         assert repGroup is not None

         try:
            repGroup.ConfigureArchival(self._archivalGroupSpec)
         except Hbr.Replica.Fault.ArchivalAlreadyConfigured as e:
            logger.info("Error when re-link archival group. Ignore error. "\
                        "Error is: {}".format(e))

   def RecreateReplicationGroup(self, groupSpec=None):
      """
      After recreation, re-link archive group if it existed before.
      """
      super(ReplicaVM, self).RecreateReplicationGroup(groupSpec)
      self.RelinkArhivalGroup()
      logger.info('Re-Link archival group {} to {}. Replication state is: {}'
                     .format(self.GetArchivalGroupId(), self._groupID,
                     self.GetReplicationState()))

