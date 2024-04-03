# Copyright (c) 2021-2022 VMware, Inc. All rights reserved.
# VMware Confidential
#
# hostd.py
#
# HBR-centric hostd access wrapper class
#
import pyHbr.disks
import pyHbr.util
import pyHbr.servercnx
import pyVim.connect
import pyVim.host
import pyVim.task
import pyVim.vm
import ssl
import time

# python2/3 compatibility
try:
   import urllib2
except ImportError:
   import urllib.request as urllib2

from datetime import datetime
from pyVmomi import Vmodl
from pyVmomi import Vim

from pyHbr.util import PASSTHROUGH_THUMBPRINT_BASE64

# Stolen from bora/vimpy/vmware-cmd/SharedSocketFix.py
# <workaround>
#
# Workaround to make the following error go away:
#
# Exception exceptions.TypeError: "'NoneType' object is not callable"
# in <bound method SharedSocket.__del__ of <httplib.SharedSocket
# instance at 0x8b9b08c>> ignored
#
# We import httplib and then replace its SharedSocket.__del__ method
# with a version that checks the reference count before closing the
# underlying socket object.
#
# Note the bug only seems to be in 2.5.? versions of Python, so make the
# fix contingent on that.

# python2/3 compatibility
try:
   import httplib
except ImportError:
   import http.client as httplib

import sys

if sys.version_info[:2] == (2, 5):
   def SharedSocket__del__(self):
      """
      This function is meant to replace
      httplib.SharedSocket.__del__. This enhanced version checks the reference
      count before closing the underlying socket object and thus prevents the error:

      Exception exceptions.TypeError: "'NoneType' object is not callable"
      in <bound method SharedSocket.__del__ of <httplib.SharedSocket
      instance at 0x8b9b08c>> ignored
      """

      if self._refcnt == 0:
         self.sock.close()

   # Replace httplib.SharedSocket.__del__ with enhanced version
   globals()['httplib'].SharedSocket.__del__ = SharedSocket__del__
# </workaround>

# shortcuts
ReplicationConfigSpec = Vim.Vm.ReplicationConfigSpec
ReplicationVmFault = Vim.Fault.ReplicationVmFault
ReplicationVmConfigFault = Vim.Fault.ReplicationVmConfigFault
ReplicationVmInfo = Vim.HbrManager.ReplicationVmInfo

class Hostd:
   """Wrapper for a hostd connection instance. Supports accessing the
   top-level managers of interest, and some convenience functions for
   looking up and creating virtual machines.
   """

   def __init__(self, host, username, password, connect=True, allowUnstableAPI=False):
      """Create connection to hostd using given credentials."""
      self._host = host
      self._username = username
      self._password = password
      self._allowUnstableAPI=allowUnstableAPI

      if connect:
         self.Connect()

      self.datacenter = None
      self.hbrMgr = None
      self.hbrInternalSystem = None
      self.vmFolder = None
      self.compRes = None
      self.host = None
      self.hostSystem = None
      self.accountMgr = None
      self.authMgr = None
      self.licMgr = None
      self.ovfMgr = None
      self._remoteStorage = {}
      self._dsBrowser = {}

   def __enter__(self):
      return self

   def __exit__(self, exc_type, exc_value, traceback):
      self.Disconnect()

   def Connect(self):
      self._soapStub = pyHbr.servercnx.CreateHostdSoapStub(self._host,
                                                           self._username,
                                                           self._password,
                                                           self._allowUnstableAPI)
      self.si = pyHbr.servercnx.ServiceInstance(self._soapStub)

      self.pubContent = self.si.RetrieveContent()
      self.privContent = self.si.RetrieveInternalContent()

   def GetServiceInstance(self):
      return self.si

   def GetPropertyCollector(self):
      return self.si.content.propertyCollector

   def Disconnect(self):
      pyVim.connect.Disconnect(self.si)

   def __str__(self):
      return "hostd[%s]" % (self._host)

   def GetDatacenter(self):
      """Get the (only) 'Datacenter' object associated with this host."""
      if not self.datacenter:
         datacenters = self.pubContent.GetRootFolder().GetChildEntity()
         assert len(datacenters) <= 1 # hostd only has one (at most one?)
         self.datacenter = datacenters[0]
      return self.datacenter

   def GetVmFolder(self):
      """Get the (cachable) VM folder associated with this host."""
      if not self.vmFolder:
         self.vmFolder = self.GetDatacenter().GetVmFolder()
      return self.vmFolder

   def GetHostComputeResources(self):
      """Get the (cachable) ComputeResources associated with this host."""
      if not self.compRes:
         self.compRes = self.GetDatacenter().GetHostFolder().GetChildEntity()[0]
      return self.compRes

   def GetComputeHost(self):
      """Get the (cachable) host compute resource associated with this host."""
      if not self.host:
         self.host = self.GetHostComputeResources().GetHost()[0]
      return self.host

   def GetNetwork(self, name='VM Network'):
      """Get a particular network available on this host."""
      for network in self.GetDatacenter().GetNetworkFolder().GetChildEntity():
         if network.GetName() == name:
            return network
      raise RuntimeError('Network {} not found'.format(name))

   def GetDatastore(self, name='datastore1'):
      """Get a particular datastore available on this host."""
      for datastore in self.GetDatacenter().GetDatastore():
         if datastore.GetName() == name:
            return datastore
      raise RuntimeError('Datastore {} not found'.format(name))

   def GetAccountManager(self):
      if not self.accountMgr:
         self.accountMgr = self.pubContent.GetAccountManager()
      return self.accountMgr

   def GetAuthorizationManager(self):
      if not self.authMgr:
         self.authMgr = self.pubContent.GetAuthorizationManager()
      return self.authMgr

   def GetLicenseManager(self):
      if not self.licMgr:
         self.licMgr = self.pubContent.GetLicenseManager()
      return self.licMgr

   def GetOvfManager(self):
      if not self.ovfMgr:
         self.ovfMgr = self.pubContent.GetOvfManager()
      return self.ovfMgr

   def GetVmList(self):
      """Get the list of VMs registered on this host."""
      # 'childEntity' is an array of entities (VirtualMachine managed
      # objects in this case)
      return self.GetVmFolder().GetChildEntity()

   def GetPyVimVM(self, vm):
      propC = self.si.content.propertyCollector
      resPool = vm.resourcePool
      vmConfig = vm.GetConfig()
      return pyVim.vm.VM(vm, propC, resPool, vmConfig)

   def FindVmByName(self, vmname):
      """Returns Vim.VirtualMachine managed object."""
      for vm in self.GetVmList():
         try:
            cfg = vm.GetConfig()
            if cfg != None and cfg.GetName() == vmname:
               return vm
         except Vmodl.Fault.ManagedObjectNotFound:
            pass
      return None

   def FindVmByConfig(self, cfg):
      """Returns Vim.VirtualMachine managed object."""

      # First convert the given 'cfg' path (which is generally of the form
      # "/vmfs/volumes/fooUUID/bar/baz.vmx") into a pretty version that
      # will match what is stored in the VM object
      (ds, pth) = pyHbr.disks.ParsePath(cfg)
      prettyDS = self.RemoteStorage(ds).DatastorePrettyName()
      prettyCfg = "[%s] %s" % (prettyDS, pth)

      for vm in self.GetVmList():
         try:
            fl = vm.GetLayoutEx()
            # A misbehaving or invalid VM could return None, so make sure
            # GetLayoutEx() returned something.  See PR 740788.
            if fl:
               fiList = fl.GetFile()
               for f in fiList:
                  if f.type == Vim.Vm.FileLayoutEx.FileType.config:
                     if f.name == prettyCfg:
                        return vm
                     # XXX else skip to next VM?
         except Vmodl.Fault.ManagedObjectNotFound:
            pass
      return None

   def RegisterVm(self, cfg, name=None, asTemplate=False):
      """Register VM at the given path with the given name."""
      rp = self.GetHostComputeResources().GetResourcePool() # default resource pool
      vmfolder = self.GetVmFolder()
      return vmfolder.RegisterVm(cfg, name, asTemplate, rp, None)

   def WaitForTask(self, task, maxWaitTime=None):
      """
      Wrap task.WaitForTask because we need to override 'si' (otherwise it
      will look at the global 'default' si, which might not be right.
      """
      return pyVim.task.WaitForTask(task,
                                    raiseOnError=True,
                                    si=self.si,
                                    pc=None, # use default si prop collector
                                    onProgressUpdate=None,
                                    maxWaitTime = maxWaitTime)

   def WaitForTasks(self, tasks, results=None):
      """
      Wrap task.WaitForTasks because we need to override 'si' (otherwise it
      will look at the global 'default' si, which might not be right.
      """
      return pyVim.task.WaitForTasks(tasks,
                                     raiseOnError=True,
                                     si=self.si,
                                     pc=None, # use default si prop collector
                                     onProgressUpdate=None,
                                     results=results)

   def RemoteStorage(self, datastore):
      """Grab the pyHbr "RemoteStorage" wrapper for a datastore on this host."""
      rs = self._remoteStorage.get(datastore, None)
      if not rs:
         rs = pyHbr.disks.RemoteStorage(datastore=datastore,
                                        hostd=self)
         self._remoteStorage[datastore] = rs
      return rs

   def GetHbrManager(self):
      if not self.hbrMgr:
         self.hbrMgr = self.privContent.GetHbrManager()
      return self.hbrMgr

   def GetHbrInternalSystem(self):
      if not self.hbrInternalSystem:
         self.hbrInternalSystem = pyHbr.servercnx.HostdHbrInternalSystem(self._soapStub)
      return self.hbrInternalSystem

   def GetHostSystem(self):
      """
      Get reference to the (cachable) HostSystem interface for this hostd.
      """
      if not self.hostSystem:
         hosts = self.GetHostComputeResources().GetHost()
         assert len(hosts) == 1
         self.hostSystem = hosts[0]
      return self.hostSystem

   def Hostname(self):
      return self._host

   def Username(self):
      return self._username

   def Password(self):
      return self._password

   def AuthInfo(self):
      """Return 'user:password' string for this host."""
      return '{0}:{1}'.format(self._username, self._password)

   def AddVpxuser(self):
      """
      Add the 'vpxuser' account to the host and set up is permissions on
      the host.  This is what would happen if the host were added to VC.
      """

      # Define 'vpxuser' permissions
      perm = Vim.AuthorizationManager.Permission()
      perm.SetPrincipal('vpxuser')
      perm.SetGroup(False)
      perm.SetRoleId(-1)
      perm.SetPropagate(True)

      # Define 'vpxuser' account
      acct = Vim.Host.LocalAccountManager.AccountSpecification()
      acct.SetId('vpxuser')
      acct.SetPassword("invalid, unused password")

      try:
         # Try to add the account to the host
         lam = self.GetAccountManager()
         lam.CreateUser(acct)
      except Vim.Fault.AlreadyExists:
         pass

      # Try to setup permissions for the vpxuser account
      authMgr = self.GetAuthorizationManager()
      authMgr.SetEntityPermissions(self.pubContent.GetRootFolder(),
                                   [perm])

   def AddThumbprint(self, thumbprintStr):
      """
      Register the given thumbprint string as the thumbprint of an
      authorized SSL client certificate (so the client can log in via
      LoginBySSLThumbprint).

      Thumbprints look like this: 'B2:31:97:16:49:AE:2C:56:EF:E8:8E:38:D5:E6:43:A2:08:42:6F:43'
      """

      th = Vim.Host.SslThumbprintInfo()
      th.principal = "vpxuser" # Fixed, defined by VIM API
      th.ownerTag = "com.vmware.hbrdev.pyHbr"
      th.sslThumbprints = [ thumbprintStr, ]
      self.GetHostSystem().UpdateSslThumbprintInfo(th, "add")

      # The thumbprints, by definition, will log in the client as
      # 'vpxuser', so make sure 'vpxuser' exists on the server (its not
      # there by default, usually only shows up as a side-effect of
      # registering the host with VC).
      self.AddVpxuser()

   def Thumbprint(self):
      """
      Return the thumbprint of the host associated with this hostd instance.
      """
      return pyHbr.util.GetThumbprint(self.Hostname(), httplib.HTTPS_PORT)

   def _WaitForResult(self,
                      what,
                      readyYetCB,
                      targetResult,
                      progressCB,
                      timeout):
      """
      Generic busy-wait for given 'readyYetCB' to return 'targetResult' or to
      time out while waiting for that result to show up.
      """

      startTime = datetime.now()

      sleepTime = 3
      timeElapsed = 0
      if timeout >= 0 and timeout < 15: sleepTime = 1

      while True:
         actual = readyYetCB()
         if actual == targetResult:
            return 0

         if timeout >= 0 and timeElapsed > timeout:
            raise RuntimeError('Timed out waiting %u seconds for %s \'%s\' (latest %s)' % \
                (timeout, what, targetResult, actual))

         time.sleep(sleepTime)

         timeElapsed = (datetime.now() - startTime).seconds
         if progressCB is not None:
            progressCB(float(timeElapsed * 100) / timeout)

   def WaitForVMPowerState(self,
                           vm,
                           targetState,
                           timeout=-1,
                           progressCB=None):
      """
      Wait for the given vm to enter the given power state.  Timeout after
      the given timeout.  Invoke the given progress callback occasional.

      @param vm [in]          Hostd VirtualMachine MoRef
      @param targetState [in] the desired power state to wait for ('on' or 'off')
      @param timeout [in]     seconds to abandon wait after (-1 means never, 0 means poll)
      @param progressCB [in]  If not None, callback to invoke occasionally while waiting
      """

      # First convert the targetState string into a VMODL PowerState enum value
      if targetState in [ "off", "OFF", "Off" ]:
         targetState = Vim.VirtualMachine.PowerState.poweredOff
      elif targetState in [ "on", "ON", "On" ]:
         targetState = Vim.VirtualMachine.PowerState.poweredOn
      else:
         raise RuntimeError("Unknown state '%s' (should be 'on' or 'off')" %
                            targetState)

      # XXX use a property collector to wait ...
      rt = vm.GetRuntime()

      return self._WaitForResult("power state", rt.GetPowerState, targetState,
                                 progressCB, timeout)

   def WaitForVMHbrState(self,
                         vm,
                         targetState,
                         timeout=-1,
                         progressCB=None):
      """
      Wait for the given vm to enter the given HBR replication state.
      Timeout after the given timeout.  Print progress (or not).

      @param vm [in]          Hostd VirtualMachine MO
      @param state [in]       the desired hbr state to wait for ('lwd', 'sync', etc)
      @param timeout [in]     seconds to abandon wait after (-1 means never, 0 means poll)
      @param progressCB [in]  If not None, callback to invoke occasionally while waiting
      """

      # First convert the targetState string to an VMODL enum value
      if targetState in ["lwd", "LWD", "Delta", "delta", "active"]:
         targetState = Vim.HbrManager.ReplicationVmInfo.State.active
      elif targetState in ["sync", "full-sync", "fullsync", "FullSync", "Sync", "checksum"]:
         targetState = Vim.HbrManager.ReplicationVmInfo.State.syncing
      elif targetState in ["idle"]:
         targetState = Vim.HbrManager.ReplicationVmInfo.State.idle
      elif targetState in ["paused"]:
         targetState = Vim.HbrManager.ReplicationVmInfo.State.paused
      elif targetState in ["none", "off"]:
         targetState = Vim.HbrManager.ReplicationVmInfo.State.none
      else:
         raise RuntimeError("Unknown state '%s' (should be 'lwd', 'sync', 'idle', etc)" % targetState)

      def queryState():
         return hbrMgr.QueryReplicationState(vm).state

      hbrMgr = self.GetHbrManager()

      return self._WaitForResult("HBR state", queryState,
                                 targetState, progressCB, timeout);

   def _DatastoreBrowserURL(self, datastore, path):
      """
      Construct the base datastore browser URL for the given datastore.
      Register the HTTP auth handler for this datastore.

      Return a tuple of URL and urllib2.opener object

      URLs look like this:
      https://ft011.eng.vmware.com/folder/test-hbr.replicas.pid2672?dcPath=ha-datacenter&dsName=ft011:storage1

      Used by ReadRemoteFile and WriteRemoteFile
      """

      ds = self._dsBrowser.get(datastore, None)
      if not ds:
         # XXX http needs pretty name? WTF?
         prettyDs = self.RemoteStorage(datastore).DatastorePrettyName()

         # Create a password manager for the Basic Auth request
         urlRoot = "https://%s/folder" % (self.Hostname())
         user = self._username
         pswd = self._password
         passmgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
         passmgr.add_password(None, urlRoot, user, pswd)

         # Ignore invalid certificates
         sslCtx = ssl._create_unverified_context()
         sslHandler = urllib2.HTTPSHandler(context=sslCtx)

         # Install the handler.  Oddly, this is global (?)
         authhndlr = urllib2.HTTPBasicAuthHandler(passmgr)
         opener = urllib2.build_opener(authhndlr, sslHandler)

         # Store a URL generator for later callers to use
         ds = (lambda path : \
               "%s/%s?dcPath=ha%%2ddatacenter&dsName=%s" % (urlRoot, path, prettyDs),
               opener)
         self._dsBrowser[datastore] = ds

      (urlGen, opener) = ds
      return (urlGen(path), opener)

   def ReadRemoteFile(self, datastore, path):
      """
      Open an HTTP stream to the given datastore/path on this host.
      """
      (fileUrl, opener) = self._DatastoreBrowserURL(datastore, path)
      return opener.open(fileUrl)

   def WriteRemoteFile(self, datastore, path, content):
      """
      Write the given content (presumably not too big) to the given
      datastore/path on this host.
      """
      (fileUrl, opener) = self._DatastoreBrowserURL(datastore, path)

      # Simplest hack I've found for POST'ing a simple (single-part) file
      # http://stackoverflow.com/questions/111945/is-there-any-way-to-do-http-put-in-python
      request = urllib2.Request(fileUrl, data=content)
      request.add_header('Content-Type', 'application/octet-stream')
      request.add_header('Content-Length', len(content))
      request.get_method = lambda: 'PUT'  # Hackery.  Use 'PUT' instead of 'POST'
      url = opener.open(request)
      # XXX ignore 'url' object?  Should have no content/errors?
      return url

   def CurrentTime(self):
      """
      Return the current time
      """
      return self.si.CurrentTime()

   def CreateEventCollector(self, filterSpec=None):
      """Create an EventHistoryCollector and return it

      @param filterSpec     [in] Optional pyVmomi.vim.event.EventFilterSpec
      """
      if not filterSpec:
         filterSpec = Vim.event.EventFilterSpec()
      return self.pubContent.eventManager.CreateCollector(filterSpec)

   def GetEvents(self, since=None, eventTypeId=None, vmName=None):
      """Return events based on some search criteria.

      By default, all events will be returned.

      @param since             [in] Datetime. Filter out events before this time.
                                    The caller can use self.CurrentTime() to
                                    mark the start of a task.
      @param vmName            [in] String. The VM name to filter on.
      @param eventTypeId       [in] String. The eventTypeId to filter on. Can
                                    be a partial match (i.e. 'hbr.primary').
      @return events          [out] List.  A list of matching events.

      * Note *
      EventFilterSpec is broken with eventTypeId or type filtering.  See PR 615468.
      This was fixed on vmkernel-main @CN 1414320.  We should just be able to use
      a EventFilterSpec to achieve this, but since we need this to work on all
      branches we are testing, this is neccesary.
      """
      if since:
         filterSpec = Vim.event.EventFilterSpec()
         filterSpec.time = Vim.event.EventFilterSpec.ByTime(beginTime=since)
         collector = self.CreateEventCollector(filterSpec)
      else:
         collector = self.CreateEventCollector()

      # Get all the events into a list
      collector.Rewind()
      events = []
      while True:
         eventsChunk = collector.ReadNext(30)
         # Empty chunk means we've read through all the events
         if eventsChunk == []:
            break
         events.extend(eventsChunk)

      # Filter the events
      filteredEvents = self.FilterEvents(events,
                                         vmName=vmName,
                                         eventTypeId=eventTypeId)

      collector.Remove()
      return filteredEvents

   def FilterEvents(self, events, vmName=None, eventTypeId=None):
      """Return a filtered list of events

      @param events            [in] List. List of event objects to filter.
      @param vmName            [in] String. The VM name to filter on.
      @param eventTypeId       [in] String. The eventTypeId to filter on. Can
                                    be a partial match (i.e. 'hbr.primary').
      @return events          [out] List.  A list of matching events.
      """
      filteredEvents = []
      for event in events:
         match = True
         if vmName:
            try:
               if event.vm.name == vmName:
                  pass
               else:
                  match = False
            except AttributeError:
               match = False
         if eventTypeId:
            try:
               if eventTypeId in event.eventTypeId:
                  pass
               else:
                  match = False
            except AttributeError:
               match = False
         if match:
            filteredEvents.append(event)

      return filteredEvents

   def GetLatestEvents(self, numEvents=5):
      """Return the latest "n" events. Returns 5 events by default.

      No filtering, just return the last "n" events.

      @param numEvents      [in] Int. The number of events to return
      @return events       [out] List.  A list of events.
      """
      collector = self.CreateEventCollector()
      collector.SetLatestPageSize(numEvents)
      events = collector.latestPage
      collector.Remove()
      return events

   def GetDatastores(self):
      """Get all the available datastores for this host."""
      hostSystem = pyVim.host.GetHostSystem(self.si)
      return hostSystem.GetDatastore()


def CreateDiskSettingsFromVirtualDisk(disk, diskReplicationID):
   """Create the primary replication config for a disk.

   @param disk              [in] Vim.Vm.Device.VirtualDisk reference
   @param diskreplicationID [in] disk replication ID
   @return a Vim.Vm.ReplicationConfigSpec.DiskSettings object
   """
   diskSettings = ReplicationConfigSpec.DiskSettings()
   diskSettings.SetKey(disk.GetKey())
   diskSettings.SetDiskReplicationId(diskReplicationID)
   return diskSettings


def CreateReplicationConfigSpec(replicationID, destination, lwdPort, disks=[],
                                rpo=0, quiesceGuest=False, oppUpdates=False,
                                netCompression=False, netEncryption=False,
                                remoteCertificateThumbprint=None,
                                broker=False):
   """Create the primary replication config of a VM.

   @param replicationID  [in] ID of the replication
   @param destination    [in] the IP of the hbrsrv to use for this replication
   @param lwdPort        [in] port used for the LWD traffic from the primary
                              to the replica
   @param disks          [in] list of Vim.Vm.ReplicationConfig.DiskSettings
                              disks configured for replication
   @param rpo            [in] RPO of the replication
   @param quiesceGuest   [in] whether to try quiescing the guest before taking
                              an instance
   @param oppUpdates     [in] whether opportunistic updates are enabled
   @param netCompression [in] whether traffic is compressed between the primary
                              and the replica site
   @param broker         [in] whether to use the hbragent to do a brokered
                              connection.
   @return a Vim.Vm.ReplicationConfigSpec object
   """
   repConfig = ReplicationConfigSpec()
   repConfig.SetVmReplicationId(replicationID)
   if netEncryption == False:
      if broker == False:
         repConfig.SetDestination(destination)
         repConfig.SetPort(lwdPort)
         repConfig.SetRemoteCertificateThumbprint(None)
         repConfig.SetNetEncryptionEnabled(False)

      else:
         repConfig.SetDestination("127.0.0.1")
         repConfig.SetPort(44046)
         repConfig.SetEncryptionDestination(destination);
         repConfig.SetEncryptionPort(lwdPort)
         repConfig.SetRemoteCertificateThumbprint(PASSTHROUGH_THUMBPRINT_BASE64)
         repConfig.SetNetEncryptionEnabled(True)
   else:
      repConfig.SetDestination("127.0.0.1")
      if broker == False:
         repConfig.SetPort(32032)
      else:
         repConfig.SetPort(44046)
      repConfig.SetNetEncryptionEnabled(True)
      repConfig.SetRemoteCertificateThumbprint(remoteCertificateThumbprint)
      repConfig.SetEncryptionDestination(destination);
      repConfig.SetEncryptionPort(lwdPort)
   repConfig.SetRpo(rpo)
   repConfig.SetQuiesceGuestEnabled(quiesceGuest)
   repConfig.SetOppUpdatesEnabled(oppUpdates)
   repConfig.SetNetCompressionEnabled(netCompression)
   repConfig.SetDisk(disks)

   return repConfig


def CreateCryptoSpec(keyId, keyServerId=None):
    """Create an encryption crypto spec.

    @param keyId       [in] ID of the key
    @param keyServerId [in] ID of the provider

    @return Vim.Encryption.CryptoSpec object
    """
    cryptoKeyId = Vim.Encryption.CryptoKeyId()
    cryptoKeyId.SetKeyId(keyId)

    if keyServerId != None:
        keyProviderId = Vim.Encryption.KeyProviderId()
        keyProviderId.SetId(keyServerId)
        cryptoKeyId.SetProviderId(keyProviderId)

    cryptoSpec = Vim.Encryption.CryptoSpecEncrypt()
    cryptoSpec.SetCryptoKeyId(cryptoKeyId)

    return cryptoSpec
