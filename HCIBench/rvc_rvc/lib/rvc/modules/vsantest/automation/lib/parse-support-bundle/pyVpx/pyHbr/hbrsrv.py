# Copyright (c) 2016-2022 VMware, Inc.  All rights reserved.
# -- VMware Confidential

#
# Python wrapper class for a connection to an hbrsrv
#
# XXX move the 'pyHbr.servercnx' content into here?
#

import logging
import platform
import pyHbr.servercnx
import pyHbr.util
import pyHbr.task
import pyHbr.disks
import socket
import sys
import time
import uuid

from datetime import datetime
from pyHbr.exceptions import ConfigError
from pyVmomi import Hbr
from pyVmomi import Vim, Vmodl, vmodl, types, VmomiSupport

import paramiko

logger = logging.getLogger('pyHbr.hbrsrv')

HMS_THUMB_GUESTINFO_KEY="guestinfo.hbr.hms-thumbprint"

class Hbrsrv:
   """Wrapper for Hbr server connection instance.

   Wraps access to the top-level manager objects (ReplicationManager,
   SessionManager, StorageManager).
   """

   def __init__(self,
                host='localhost',
                user='root',
                password='vmware11',
                vmodlPort=pyHbr.servercnx.DEFAULT_VMODL_PORT,
                uwVmodlPort=pyHbr.servercnx.DEFAULT_USER_WORLD_VMODL_PORT,
                keyFile=None,
                certFile=None,
                pushCert=False,
                uw=False):
      """Create connection to the hbrsrv using the given credentials.

      @param host      [in] hostname or IP of the hbrsrv.
      @param user      [in] username to use to connect to the hbrsrv.
      @param password  [in] password to use to connect to the hbrsrv.
      @param vmodlPort [in] port to use for the VMODL connection.
      @param keyFile   [in] path of the file containing the private key
                            used to login into the hbrsrv.
      @param certFile  [in] file containing the certificate
                            used to login into the hbrsrv.
      @param pushCert  [in] whether the current certificate should be
                            pushed to the hbrsrv.
      @param uw        [in] whether HBR is running as user world or in appliance.

      @throws ConfigError if the configuration is invalid.

      Notes:
         The hbrsrv only supports user/password authentication on the debug
         builds. The credentials are hardcoded in the sense that any password
         used in combination with the 'root' user will work.
         However, pushing a new thumbprint to the hbrsrv is an operation which
         requires SSH access to the appliance and uses the same credentials
         given here. This means that even if you are using thumbprint
         authentication, you must still provide a valid user and password
         for this operation to work.
      """
      self._host = host
      self._user = user
      self._pswd = password
      self._vmodlPort = uwVmodlPort if uw else vmodlPort

      if not uw and pushCert:
         #
         # If an HMS thumbprint is provided, we push it out to the HBR server
         # so the SOAP connection below can work for secure connections.
         #
         # This logic is not needed for HBR UserWorld since HMS will use a
         # different connection scheme for it.
         #
         if keyFile and certFile:
            #
            # The hbrsrv doesn't have our cert cached. So we need to push
            # it in and then tell the hbrsrv to use it below.
            #
            logger.debug('Pushing certificate thumbprint')
            thumb = pyHbr.util.CertFileToThumbprint(certFile)
            self.SetGuestInfo(HMS_THUMB_GUESTINFO_KEY, thumb)
         else:
            raise ConfigError('Certificate thumbprint push requested but no '\
                              'certificate provided')

      self._soapStub = pyHbr.servercnx.CreateHbrsrvSoapStub(self._host,
                                                            self._vmodlPort,
                                                            username=user,
                                                            password=password,
                                                            keyFile=keyFile,
                                                            certFile=certFile,
                                                            reliableCnx=True,
                                                            uw=uw)
      logger.debug('Created hbrsrv SOAP stub')

      self._repMgr = pyHbr.servercnx.HbrReplicationManager(self._soapStub)
      self._sessionMgr = pyHbr.servercnx.HbrSessionManager(self._soapStub)
      self._serverMgr = pyHbr.servercnx.HbrServerManager(self._soapStub)
      self._brokerMgr = pyHbr.servercnx.HbrBrokerManager(self._soapStub)

      self._storageMgr = None

   def __enter__(self):
      return self

   def __exit__(self, exc_type, exc_value, traceback):
      self.Disconnect()

   def __str__(self):
      return "hbrsrv[%s]" % self._host

   def GetSoapConnection(self):
      """Get the soap connection stub to this HBR server."""
      return self._soapStub

   def Hostname(self):
      """Get the hostname of this HBR server."""
      return self._host

   def Username(self):
      """Get the username used for this HBR server."""
      return self._user

   def Password(self):
      """Get the password used for this HBR server."""
      return self._pswd

   def GetIPAddress(self):
      """Get the IP address of this hbrsrv."""
      return pyHbr.util.FindIPAddressFor(self._host)

   def GetInstanceUUID(self):
      """Get the instance UUID of this hbrsrv."""
      return self._repMgr.GetServerDetails().instanceUUID

   def GetReplicationManager(self):
      """Get the ReplicationManager reference."""
      return self._repMgr

   def GetSessionManager(self):
      """Get the SessionManager reference."""
      return self._sessionMgr

   def GetServerManager(self):
      """Get the ServerManager reference."""
      return self._serverMgr

   def GetStorageManager(self):
      """Get the StorageManager reference."""
      if not self._storageMgr:
         self._storageMgr = self.GetReplicationManager().GetStorageManager()
      return self._storageMgr

   def GetBrokerManager(self):
      """Get the BrokerManager reference."""
      return self._brokerMgr

   def GetTaskObj(self, moId):
      """Get an Hbr.Replica.Task object.

      @param moId [in] managed object ID of the task.
      @return task reference
      """
      return Hbr.Replica.Task(moId, self._soapStub)

   def Disconnect(self):
      """Disconnect from the hbrsrv."""
      sessionMgr = pyHbr.servercnx.HbrSessionManager(self._soapStub)
      sessionMgr.Logoff()
      logger.debug('Logged out of hbrsrv')

   def WaitForTask(self, task, verbose=True):
      """Wrap pyHbr.task.WaitForTask so we can pass the right replication manager
      for this hbrsrv.
      """
      return pyHbr.task.WaitForTask(task,
                                    raiseOnError=True,
                                    si=self.GetReplicationManager(),
                                    pc=None, # use default si prop collector
                                    onProgressUpdate=pyHbr.task.TaskUpdatesVerbose,
                                    verbose=verbose)

   def WaitForTasks(self, tasks, results=None, verbose=True):
      """Wrap pyHbr.task.WaitForTasks so we can pass the right replication manager
      for this hbrsrv.
      """
      return pyHbr.task.WaitForTasks(tasks,
                                     raiseOnError=True,
                                     si=self.GetReplicationManager(),
                                     pc=None, # use default si prop collector
                                     onProgressUpdate=pyHbr.task.TaskUpdatesVerbose,
                                     verbose=verbose,
                                     results=results)

   def GetGuestInfo(self, key):
      """Get the value of a guestinfo key."""
      ssh = paramiko.SSHClient()
      ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      ssh.connect(self._host, username=self._user, password=self._pswd)

      cmd = "hbrsrv-guestinfo.sh get %s" % (key)
      stdin, stdout, stderr = ssh.exec_command(cmd)
      value = stdout.read().rstrip().decode('utf-8')

      logger.debug('Retrieved guestInfo key {0}: {1}'.format(key, value))

      return value

   def SetGuestInfo(self, key, value):
      """Set the value of a guestinfo key."""

      ssh = paramiko.SSHClient()
      ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      ssh.connect(self._host, username=self._user, password=self._pswd)

      cmd = "hbrsrv-guestinfo.sh set %s %s" % (key, value)
      ssh.exec_command(cmd)

      startTime = datetime.now()
      while self.GetGuestInfo(key) != value:
         #
         # Check that the value was actually set before moving on
         # to avoid having the hbrsrv read the old value.
         #
         now = datetime.now()
         if (now - startTime).seconds > 120:
            raise ConfigError('Couldn\'t set the guestinfo key "{0}" to '\
                              '"{1}".'.format(key, value))
         time.sleep(2)


      logger.debug('Set the guestInfo key {0} to {1}'.format(key, value))

   def _EnableHost(self, hostd, useThumb, extraAddresses, isAsync):
      """Internal implementation to add a new host to the hbrsrv chosings
         between sync or async

      @param hostd          [in] pyHbr.hostd.Hostd instance of the host.
      @param useThumb       [in] whether to use thumbprint authentication
      @param extraAddresses [in] other addresses this host can be reached
                                 through.
      """

      logger.debug('Adding a new host to the hbrsrv: {0}'.format(hostd.Hostname()))
      if useThumb:
         hostd.Connect()

         # Make sure the host has a copy of the hbrsrv's thumbprint
         hbrsrvThumb = self.Thumbprint()
         hostd.AddThumbprint(hbrsrvThumb)

         # Use the host's thumbprint instead of user/pass to login.
         hostAuth = "-:%s" % hostd.Thumbprint()
         logger.debug('Adding host thumbprint')
      else:
         # Just use the host's user/pass to login
         hostAuth = hostd.AuthInfo()
         logger.debug('Adding host user/password')

      hostSpec = CreateHostSpec(hostd.Hostname(),
                                hostd.Hostname(),
                                hostAuth,
                                [hostd.Hostname()] + extraAddresses)
      if isAsync:
         return self.GetStorageManager().EnableHostAsync(hostSpec)
      else:
         return self.GetStorageManager().EnableHost(hostSpec)

   def EnableHost(self, hostd, useThumb=True, extraAddresses=[]):
      """Synchronously add a new host to the hbrsrv

      @param hostd          [in] pyHbr.hostd.Hostd instance of the host.
      @param useThumb       [in] whether to use thumbprint authentication
      @param extraAddresses [in] other addresses this host can be reached
                                 through.
      """
      return self._EnableHost(hostd, useThumb,
                              extraAddresses, isAsync=False);

   def EnableHostAsync(self, hostd, useThumb=True, extraAddresses=[]):
      """Asynchronously add a new host to the hbrsrv returning a task

      @param hostd          [in] pyHbr.hostd.Hostd instance of the host.
      @param useThumb       [in] whether to use thumbprint authentication
      @param extraAddresses [in] other addresses this host can be reached
                                 through.
      """
      return self._EnableHost(hostd, useThumb,
                              extraAddresses, isAsync=True);

   def AddPrimaryHost(self, hostd, primarySite):
      """Add a primary host to the HBR server.

      @param hostd       [in] pyHbr.hostd.Hostd instance of the host.
      @param primarySite [in] primary site to add the host to.
      """
      logger.debug('Adding a new primary host to the hbrsrv: {0}'.format(
         hostd.Hostname()))

      hostd.Connect()
      hostSpec = CreatePrimaryHostSpec(hostd.Hostname(), hostd.Thumbprint())

      return self.GetReplicationManager().AddPrimaryHosts(primarySite, [hostSpec])

   def RemovePrimaryHost(self, hostd, primarySite):
      """Remove a primary host from the HBR server.

      @param hostd       [in] pyHbr.hostd.Hostd instance of the host.
      @param primarySite [in] primary site to remove the host from.
      """
      logger.debug('Removing host from the hbrsrv: {0}'.format(
         hostd.Hostname()))

      hostd.Connect()

      return self.GetReplicationManager().RemovePrimaryHosts(primarySite, [hostd.Hostname()])

   def Thumbprint(self):
      """Get the SSL thumbprint of the HBR server."""
      return pyHbr.util.GetThumbprint(self._host, self._vmodlPort)

   def Base64Thumbprint(self):
      """Get the SSL thumbprint of the HBR server base64 encoded."""
      return pyHbr.util.GetBase64Thumbprint(self._host, self._vmodlPort)


def CreateGroupsFilter(repMgr, groups, *properties):
   """Create a PropertyCollector filter for the specified properties
   for all the specified groups.

   @param repMgr     [in] ReplicationManager reference.
   @param groups     [in] a list of groups the filter will wait for
                          updates from.
   @param properties [in] a list of properties the filter will wait
                          for updates of.
   @return reference to a new PropertyCollector with this filter. The
      caller is responsible to call Destroy after use.
   """

   VQPC = Vmodl.Query.PropertyCollector
   pc = repMgr.propertyCollector

   if groups is None:
      #
      # Create a traversal spec to say we want to look at all the
      # groups reported by the replication manager.
      #
      # Note: The TraversalSpec can also take a selection spec to
      # further drill down several layers but we only need to drill
      # down into one layer.
      #
      traversalSpec = VQPC.TraversalSpec(type=Hbr.Replica.ReplicationManager,
                                         path='replicationGroups',
                                         skip=False)

      #
      # There's a single traversal spec, so just make a singleton
      # selection spec array.
      #
      # Note: This may be somewhat confusing but both Traversal and Object specs
      # can have selection specs.
      #
      selectionSpecArray = VQPC.SelectionSpec.Array()
      selectionSpecArray.append(traversalSpec)

      #
      # Create an object spec that inspects the replication manager using
      # the selection spec array, with the single traversal spec above.
      #
      objectSpec = VQPC.ObjectSpec(obj=repMgr,
                                   skip=False,
                                   selectSet=selectionSpecArray)

      #
      # There's only one replication manager, so we're only going to
      # look at it using the single object spec created above.
      # Add that to a singleton array.
      #
      objectSpecArray = VQPC.ObjectSpec.Array()
      objectSpecArray.append(objectSpec)
   else:
      #
      # Get the properties for the specified group objects only.
      #
      objs = [VQPC.ObjectSpec(obj=x) for x in groups]
      objectSpecArray = VQPC.ObjectSpec.Array(objs)

   #
   # Get the properties we're interested in.
   #
   if not properties:
      propList = ("state",
                  "lastGroupError",
                  "currentRpoViolation",
                  "latestInstance",
                  "groupStats",
                  "latestInstances",
                  "syncPruneTask");
   else:
      propList = list(properties)

   propertyPaths = types.PropertyPathArray(propList)
   propertySpec = VQPC.PropertySpec(type=Hbr.Replica.ReplicationGroup,
                                    pathSet = propertyPaths)

   #
   # We're only looking at a single set of properties so make
   # a singleton array with that.
   #
   propertiesArray = VQPC.PropertySpec.Array()
   propertiesArray.append(propertySpec)

   #
   # Create a filter to traverse the objects using the traversal spec
   # and then look for the properties that we're interested in on those
   # traversal specs.
   #
   filterSpec = VQPC.FilterSpec(propSet = propertiesArray,
                                objectSet = objectSpecArray)

   newPc = pc.CreatePropertyCollector()
   newPc.CreateFilter(filterSpec, True)

   return newPc

def CreateHostsFilter(repMgr, hosts, *properties):
   """Create a PropertyCollector filter for the specified properties
   for all the specified hosts.

   @param storageMgr [in] ReplicationManager reference.
   @param hosts      [in] a list of hosts the filter will wait for
                          updates from.
   @param properties [in] a list of properties the filter will wait
                          for updates of.
   @return reference to a new PropertyCollector with this filter. The
      caller is responsible to call Destroy after use.
   """
   VQPC = Vmodl.Query.PropertyCollector
   pc = repMgr.propertyCollector
   storageMgr = repMgr.GetStorageManager()

   if hosts is None:
      #
      # Create a traversal spec to say we want to look at all the
      # groups reported by the replication manager.
      #
      # Note: The TraversalSpec can also take a selection spec to
      # further drill down several layers but we only need to drill
      # down into one layer.
      #
      traversalSpec = VQPC.TraversalSpec(type=Hbr.Replica.StorageManager,
                                         path='enabledHostsList',
                                         skip=False)

      #
      # There's a single traversal spec, so just make a singleton
      # selection spec array.
      #
      # Note: This may be somewhat confusing but both Traversal and Object specs
      # can have selection specs.
      #
      selectionSpecArray = VQPC.SelectionSpec.Array()
      selectionSpecArray.append(traversalSpec)

      #
      # Create an object spec that inspects the replication manager using
      # the selection spec array, with the single traversal spec above.
      #
      objectSpec = VQPC.ObjectSpec(obj=storageMgr,
                                   skip=False,
                                   selectSet=selectionSpecArray)

      #
      # There's only one replication manager, so we're only going to
      # look at it using the single object spec created above.
      # Add that to a singleton array.
      #
      objectSpecArray = VQPC.ObjectSpec.Array()
      objectSpecArray.append(objectSpec)

   else:
      #
      # Get the properties for the specified group objects only.
      #
      objs = [VQPC.ObjectSpec(obj=x) for x in groups]
      objectSpecArray = VQPC.ObjectSpec.Array(objs)

   #
   # Get the properties we're interested in.
   #
   propertyPaths = types.PropertyPathArray(list(properties))
   propertySpec = VQPC.PropertySpec(type=Hbr.Replica.Host,
                                    pathSet = propertyPaths)

   #
   # We're only looking at a single set of properties so make
   # a singleton array with that.
   #
   propertiesArray = VQPC.PropertySpec.Array()
   propertiesArray.append(propertySpec)

   #
   # Create a filter to traverse the objects using the traversal spec
   # and then look for the properties that we're interested in on those
   # traversal specs.
   #
   filterSpec = VQPC.FilterSpec(propSet = propertiesArray,
                                objectSet = objectSpecArray)

   newPc = pc.CreatePropertyCollector()
   newPc.CreateFilter(filterSpec, True)

   return newPc


def CreateDatastoresFilter(repMgr, datastores, *properties):
   """Create a PropertyCollector filter for the specified properties
   for all the specified datastores.

   @param repMgr [in] ReplicationManager reference.
   @param datastores [in] a list of datastores the filter will wait for
                          updates from.
   @param properties [in] a list of properties the filter will wait
                          for updates of.
   @return reference to a new PropertyCollector with this filter. The
      caller is responsible to call Destroy after use.
   """
   VQPC = Vmodl.Query.PropertyCollector
   pc = repMgr.propertyCollector
   storageMgr = repMgr.GetStorageManager()

   if datastores is None:
      #
      # Create a traversal spec to say we want to look at all the
      # groups reported by the replication manager.
      #
      # Note: The TraversalSpec can also take a selection spec to
      # further drill down several layers but we only need to drill
      # down into one layer.
      #
      traversalSpec = VQPC.TraversalSpec(type=Hbr.Replica.StorageManager,
                                         path='expectedDatastoresList',
                                         skip=False)

      #
      # There's a single traversal spec, so just make a singleton
      # selection spec array.
      #
      # Note: This may be somewhat confusing but both Traversal and Object specs
      # can have selection specs.
      #
      selectionSpecArray = VQPC.SelectionSpec.Array()
      selectionSpecArray.append(traversalSpec)

      #
      # Create an object spec that inspects the replication manager using
      # the selection spec array, with the single traversal spec above.
      #
      objectSpec = VQPC.ObjectSpec(obj=storageMgr,
                                   skip=False,
                                   selectSet=selectionSpecArray)

      #
      # There's only one replication manager, so we're only going to
      # look at it using the single object spec created above.
      # Add that to a singleton array.
      #
      objectSpecArray = VQPC.ObjectSpec.Array()
      objectSpecArray.append(objectSpec)

   else:
      #
      # Get the properties for the specified group objects only.
      #
      objs = [VQPC.ObjectSpec(obj=x) for x in groups]
      objectSpecArray = VQPC.ObjectSpec.Array(objs)

   #
   # Get the properties we're interested in.
   #
   propertyPaths = types.PropertyPathArray(list(properties))
   propertySpec = VQPC.PropertySpec(type=Hbr.Replica.Datastore,
                                    pathSet = propertyPaths)

   #
   # We're only looking at a single set of properties so make
   # a singleton array with that.
   #
   propertiesArray = VQPC.PropertySpec.Array()
   propertiesArray.append(propertySpec)

   #
   # Create a filter to traverse the objects using the traversal spec
   # and then look for the properties that we're interested in on those
   # traversal specs.
   #
   filterSpec = VQPC.FilterSpec(propSet = propertiesArray,
                                objectSet = objectSpecArray)

   newPc = pc.CreatePropertyCollector()
   newPc.CreateFilter(filterSpec, True)

   return newPc


def CreateHostSpec(hostId, hostNameOnCert, hostAuth, hostAddresses):
   """Create an Hbr.Replica.HostSpec. See the VMODL documentation for
   more information.
   """
   hostSpec = Hbr.Replica.HostSpec()
   hostSpec.hostId = hostId
   hostSpec.hostNameOnCert = hostNameOnCert
   hostSpec.hostAddresses = hostAddresses
   hostSpec.hostAuth = hostAuth

   return hostSpec

def CreateIdentSpec(id, datastoreUUID, pathname):
   """Create an Hbr.Replica.IdentSpec with a Hbr.Replica.HostFilePathLocation.
   See the VMODL documentation for more information.
   """
   idSpec = Hbr.Replica.IdentSpec()
   idSpec.id = id
   idSpec.location = Hbr.Replica.HostFilePathLocation()
   idSpec.location.hostDatastoreUUID = datastoreUUID
   idSpec.location.hostPathname = pathname

   return idSpec

def CreateCloudIdentSpec(id, providerId):
   """Create an Hbr.Replica.IdentSpec with a Hbr.Replica.CloudLocation.
   See the VMODL documentation for more information.
   """
   idSpec = Hbr.Replica.IdentSpec()
   idSpec.id = id
   idSpec.location = Hbr.Replica.CloudLocation()
   idSpec.location.providerId = providerId

   return idSpec

def IsCloudLocation(loc):
   return type(loc) == Hbr.Replica.CloudLocation

def IsCloudIdentSpec(spec):
   return IsCloudLocation(spec.location)

def CreateDiskSpec(diskId, diskPath, useNativeSnapshots=None,
                   storagePolicy=None):
   """Create an Hbr.Replica.DiskSpec. See the VMODL documentation for
   more information.

   @throws ValueError if diskPath cannot be split into
         a (datastore, relative path) tuple
   """
   diskSpec = Hbr.Replica.DiskSpec()
   (ds, path) = pyHbr.disks.ParsePath(diskPath)
   diskSpec.diskIdent = CreateIdentSpec(diskId, ds, path)
   diskSpec.useNativeSnapshots = useNativeSnapshots
   diskSpec.storagePolicy = storagePolicy

   return diskSpec

def CreateCloudDiskSpec(diskId, providerId, useNativeSnapshots=None,
                        storagePolicy=None):
   """Create an Hbr.Replica.DiskSpec. See the VMODL documentation for
   more information.
   """
   diskSpec = Hbr.Replica.DiskSpec()
   diskSpec.diskIdent = CreateCloudIdentSpec(diskId, providerId)
   diskSpec.useNativeSnapshots = useNativeSnapshots
   diskSpec.storagePolicy = storagePolicy

   return diskSpec

def CreateReplicaVMSpec(groupID, vmDir, disks=[],
                        useNativeSnapshots=None,
                        storagePolicy=None):
   """Create an Hbr.Replica.VirtualMachineSpec. See the VMODL documentation for
   more information.
   """
   vmSpec = Hbr.Replica.VirtualMachineSpec()
   (ds, path) = pyHbr.disks.ParsePath(vmDir)
   vmSpec.virtualMachineIdent = CreateIdentSpec(groupID, ds, path)

   vmSpec.replicatedDisks = []
   for disk in disks:
      diskSpec = CreateDiskSpec(disk[0], disk[1],
                                useNativeSnapshots, storagePolicy)
      vmSpec.replicatedDisks.append(diskSpec)

   return vmSpec

def CreateCloudReplicaVMSpec(groupID, providerId, disks=[],
                             useNativeSnapshots=None,
                             storagePolicy=None):
   """Create an Hbr.Replica.VirtualMachineSpec. See the VMODL documentation for
   more information.
   """
   vmSpec = Hbr.Replica.VirtualMachineSpec()
   vmSpec.virtualMachineIdent = CreateCloudIdentSpec(groupID, providerId)

   vmSpec.replicatedDisks = []
   for disk in disks:
      diskSpec = CreateCloudDiskSpec(disk[0],
                                     disk[1],
                                     useNativeSnapshots,
                                     storagePolicy)
      vmSpec.replicatedDisks.append(diskSpec)

   return vmSpec

def CreateRetentionPolicy(policyTiers=[]):
   """Create an Hbr.Replica.LegacyRetentionPolicy.
      See the VMODL documentation for more information.
   """
   if len(policyTiers) == 0:
      return None

   policy = Hbr.Replica.RetentionPolicy()
   policy.tiers = []

   for policyTier in policyTiers:
      tier = Hbr.Replica.RetentionPolicy.Tier()
      tier.SetGranularityMinutes(policyTier[0])
      tier.SetNumSlots(policyTier[1])

      policy.tiers.append(tier)

   return policy

def CreateGroupSpec(groupID,
                    vmDir,
                    disks=[],
                    policyTiers=[],
                    rpo=30,
                    trustedSite=None,
                    clientEncryptionRequired=None):
   """Create an Hbr.Replica.GroupSpec. See the VMODL documentation for
   more information.
   """
   vmSpec = CreateReplicaVMSpec(groupID, vmDir, disks)

   groupSpec = Hbr.Replica.GroupSpec()
   groupSpec.id = groupID
   groupSpec.rpo = rpo
   groupSpec.vms = [CreateReplicaVMSpec(groupID, vmDir, disks)]
   groupSpec.retentionPolicy = CreateRetentionPolicy(policyTiers)
   groupSpec.trustedSite = trustedSite
   groupSpec.clientEncryptionRequired = clientEncryptionRequired

   return groupSpec

def GroupSpecFromGroup(group):
   """Create an Hbr.Replica.GroupSpec from the given existing
   Hbr.Replica.Group reference.
   """

   groupID = group.GetId()
   vm = group.GetVms()[0]

   vmSpec = Hbr.Replica.VirtualMachineSpec()
   vmSpec.virtualMachineIdent = vm.GetVirtualMachineIdent()

   vmSpec.replicatedDisks = []

   for vmDisk in vm.GetDisks():
      # Do not include unconfigured disks in the spec
      if not vmDisk.GetUnconfigured():
         disk = Hbr.Replica.DiskSpec()
         disk.diskIdent = vmDisk.GetDiskIdent()
         vmSpec.replicatedDisks.append(disk)

   spec = Hbr.Replica.GroupSpec()
   spec.id = groupID
   spec.rpo = group.GetRepConfig().GetRpo()

   spec.vms = [ vmSpec, ]

   return spec


def FixupImage(image, esxHost, newMacAddr=False):
   """Fixup the given image."""
   vmImg = image.virtualMachines[0]
   vmDS = vmImg.virtualMachineIdent.location.hostDatastoreUUID
   vmDir = vmImg.virtualMachineIdent.location.hostPathname

   # Find the .vmx config file to fix up in the image
   for cf in vmImg.configFiles:
      if cf.type == Hbr.Replica.ConfigFileImage.FileType.config:
         cfgPath="%s/%s" % (vmDir, cf.baseFileName)
         print("Fixup [%s] %s" % (vmDS, cfgPath))

   # Save the replica disk info to patch up the config file disk names
   disks = {}
   for disk in vmImg.disks:
      disks[disk.diskIdent.id] = "/vmfs/volumes/%s/%s" % \
                                 (disk.diskIdent.location.hostDatastoreUUID,
                                  disk.diskIdent.location.hostPathname)

   logger.debug('Making a backup copy ({0}.premunge) ...'.format(cfgPath))
   rs = esxHost.RemoteStorage(vmDS)
   rs.Copy(cfgPath, cfgPath + ".premunge", force=True)

   # Read the config file off the ESX host
   logger.debug('Downloading {0} ...'.format(cfgPath))
   cfgFile = esxHost.ReadRemoteFile(vmDS, cfgPath)

   logger.debug('Munging config file ...')
   result = pyHbr.util.MungeConfigFile(cfgFile, disks, newMacAddr)

   logger.debug('Uploading munged config file ...')
   esxHost.WriteRemoteFile(vmDS, cfgPath, "\n".join(result)+"\n")

def MakeImage(group, destPath, snapshotPIT=False, disableNics=False,
              keepOnlyReplicatedDisks=True, dormantRepSpec=None,
              instance=None, isTestBubble=False, fullCloneDisks=False):
   ds, path = pyHbr.disks.ParsePath(destPath)
   locations = [CreateIdentSpec(group.GetId(), ds, path)]

   if isTestBubble:
      return group.CreateTestBubbleImage(instance, snapshotPIT, locations,
                                         disableNics, keepOnlyReplicatedDisks,
                                         fullCloneDisks)
   else:
      return group.CreateFailoverImage(instance, snapshotPIT, locations,
                                       disableNics, keepOnlyReplicatedDisks,
                                       dormantRepSpec)

def ExportInstance(group, destPath, snapshotPIT=False, disableNics=False,
                   keepOnlyReplicatedDisks=False, instance=None):
   ds, path = pyHbr.disks.ParsePath(destPath)
   locations = [CreateIdentSpec(group.GetId(), ds, path)]

   return group.ExportInstance(instance, snapshotPIT, locations,
                               disableNics, keepOnlyReplicatedDisks)

def WaitForNewInstance(group, instance, maxRetryCount=60):
   retryCount = 0
   while True:
      latestInstance = group.GetLatestInstance()
      if latestInstance is not None:
         if latestInstance.GetSequenceNumber() > instance.GetSequenceNumber():
            break
      retryCount = retryCount + 1
      if retryCount > maxRetryCount:
         return False
      time.sleep(5)
   return True

def DiskSpecFromDiskSettings(primaryDisk, datastore, vmDir):
   """Create an hbrsrv disk spec from the given primary-site
   replication spec.

   The disk is assumed to be named after its RDID and to exist in the
   given vmDir directory
   """

   # NOTE: Assumes replica disk name is based on diskID ...
   # NOTE: Puts all replica disks in the VM directory
   pathname = "{0}/{1}".format(vmDir,pyHbr.disks.MakeVMDKName(primaryDisk))

   diskSpec = Hbr.Replica.DiskSpec()
   diskSpec.diskIdent = CreateIdentSpec(primaryDisk.GetDiskReplicationId(),
                                        datastore,
                                        pathname)
   return diskSpec

def GroupSpecFromRepVmInfo(repVmInfo,
                           datastoreUUID,
                           vmDir,
                           trustedSite=None,
                           clientEncryptionRequired=None):
   """Convert a primary-side replication configuration (repVmInfo) into an
   equivalent, new replica-side hbrsrv GroupSpec.

   All is one-to-one (ids, number of disks, rpo, etc) except for the disk
   names on the replica side.  For those we assume that naming the base
   disk after the replication ID is okay.  (See CreateVMRemoteStorage.)

   @param repVmInfo [in] hostd replication info for VM
   @param datastore [in] UUID of the target datastore
   @param vmDir     [in] relative path for replication destination
   @return the Hbr.Replica.GroupSpec
   """

   # Fill in VM spec header with group ID and VM config state dir
   vmSpec = Hbr.Replica.VirtualMachineSpec()
   vmSpec.virtualMachineIdent = CreateIdentSpec(repVmInfo.GetVmReplicationId(),
                                                datastoreUUID,
                                                vmDir)

   # Map the disks over
   vmSpec.replicatedDisks = []

   for primaryDisk in repVmInfo.disk:
      diskSpec = DiskSpecFromDiskSettings(primaryDisk,
                                          datastoreUUID,
                                          vmDir)
      vmSpec.replicatedDisks.append(diskSpec)

   groupSpec = Hbr.Replica.GroupSpec()
   groupSpec.id = vmSpec.virtualMachineIdent.id
   groupSpec.rpo = repVmInfo.GetRpo()
   groupSpec.vms = [ vmSpec, ]
   groupSpec.trustedSite = trustedSite
   groupSpec.clientEncryptionRequired = clientEncryptionRequired

   return groupSpec


def CreateReplicationConfig(rpo,
                            policyTiers=[]):
   """Create an Hbr.Replica.ReplicationConfig. See the VMODL documentation for
   more information.
   """
   repConfig = Hbr.Replica.ReplicationConfig()
   repConfig.rpo = rpo
   repConfig.policy = CreateRetentionPolicy(policyTiers)
   return repConfig

def CreateGroupMappingFromGroupSpec(groupSpec,
                                    serverId,
                                    address):
   """
   Create an Hbr.Replica.GroupMappingSpec to map a group
   to a target HBR server ID and address.
   """
   server = Hbr.Replica.GroupServerMappingSpec.ServerSpec()
   server.serverId = serverId
   server.address = address

   if groupSpec.clientEncryptionRequired:
      server.port = 32032
      # XXX Add secure connections later.
   else:
      server.port = 31031
      server.auth = Hbr.Replica.AuthNoneSpec()

   mapping = Hbr.Replica.GroupServerMappingSpec()
   mapping.groupId = groupSpec.id
   mapping.trustedSite = groupSpec.trustedSite
   mapping.servers = [server]

   return mapping


def MakeReplicationGroupRef(hbrsrv, groupId):
   """ Make a replication group stub using the specified group Id

       This method does not verify the group exists in HBR server, but
       just creates a managed object reference to the group using the group Id.
       This is useful for testing with invalid group MoRefs, for methods that
       take MoRefs directly as VMODL input. eg. CloudStorageGroupSpec.parent
   """
   groupMoid = "Hbr.Replica.Group." + groupId
   return Hbr.Replica.ReplicationGroup(groupMoid, hbrsrv.GetSoapConnection())

def CreatePrimaryHostSpec(hostId, hostThumbprint):
   """Create an Hbr.Replica.PrimaryHostSpec. See the VMODL documentation for
   more information.
   """
   hostSpec = Hbr.Replica.PrimaryHostSpec()
   hostSpec.hostId = hostId
   hostSpec.thumbprint = hostThumbprint

   return hostSpec
#eof
