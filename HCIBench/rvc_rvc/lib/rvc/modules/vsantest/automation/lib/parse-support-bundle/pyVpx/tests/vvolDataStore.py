from __future__ import print_function
import sys
from pyVmomi import Vim, VmomiSupport, vmodl
from pyVmomi.VmomiSupport import newestVersions
from pyVim import host, connect, vm, invt, vimhost, vc, task, vimutil
from pyVim import arguments
from pyVim.connect import SmartConnect, Disconnect
from pyVim.helpers import Log,StopWatch
from pyVim import folder
import pickle
import random
import atexit
import traceback
from pyVmomi import Sms, Vim, SoapStubAdapter, VmomiSupport
import Cookie
import time, os
import vimsupport
import paramiko, warnings
import urlparse
import re

verbose=3
logTrivia=1
logVerbose=2
logInfo=3

def VerboseLog(logLevel, message, msgend='\n'):
   if(logLevel >= verbose):
      print(message, end=msgend)

##
## Duration in seconds to wait for a task to complete.
##
SMS_TASK_TIMEOUT = 60

##
## @brief Timeout exception for SMS tasks.
## @param message Error message
## @param taskInfo Information about the task that timed out
## @param duration Timeout in seconds
##
class TaskTimedOut(Exception):
   def __init__(self, message, taskInfo, duration):
      super(TaskTimedOut, self).__init__(message)
      self.taskInfo = taskInfo
      self.duration = duration

##
## Waits for an SMS task object to complete or a timeout to occur.
## This method polls every second. This is a private method.
##
## @param task SMS Task to wait
## @param timeout Seconds to wait
## @return Task's result
## @raise Error from task execution or TaskTimedOut
##
def _WaitForTask(task, timeout = SMS_TASK_TIMEOUT):
   endTime = time.time() + timeout
   taskInfo = task.QueryInfo()
   while (taskInfo.state == "running" and time.time() < endTime):
      # Wait for a second and re-poll
      time.sleep(1)
      taskInfo = task.QueryInfo()

   if (taskInfo.state == "success"):
      return task.QueryResult() # Same as taskInfo.result
   elif (taskInfo.state == "error"):
      raise taskInfo.error;
   else:
      raise TaskTimedOut("Timed out waiting for SMS task", taskInfo, timeout)


##
## Retrieves the storage manager object for the SMS.
##
## @param vcHost IP / Name of the VC
## @return SMS's Storage Manager object
##
def GetStorageManager(vcHost):
   smsStub = None
   vpxdStub = connect.GetStub()
   sessionCookie = vpxdStub.cookie.split('"')[1]
   httpContext = VmomiSupport.GetHttpContext()
   cookie = Cookie.SimpleCookie()
   cookie["vmware_soap_session"] = sessionCookie
   httpContext["cookies"] = cookie

   VmomiSupport.GetRequestContext()["vcSessionCookie"] = sessionCookie
   smsStub = SoapStubAdapter(host=vcHost, ns = "sms/4.0",
                                path = "/sms/sdk",
                                poolSize=0)

   si = Sms.ServiceInstance("ServiceInstance", smsStub)
   return si.QueryStorageManager()

##
## Registers a VASA provider
##
## @param storageManager SMS storage manager object
## @param providerUrl URL for the VASA provider
## @return SMS ProviderInfo object
## @raise Error from task execution or TaskTimedOut
##
def RegisterProvider(storageManager, providerUrl):
   vasaProviderSpec = Sms.provider.VasaProviderSpec()
   vasaProviderSpec.name = "test provider"
   vasaProviderSpec.description = "test provider"
   vasaProviderSpec.username = "username"
   vasaProviderSpec.password = "password"
   vasaProviderSpec.url = providerUrl
   task = storageManager.RegisterProvider(vasaProviderSpec)
   provider = _WaitForTask(task)
   return provider.QueryProviderInfo()

##
## Unregisters a VASA provider
##
## @param storageManager SMS storage manager object
## @param uid UID of the ithe VASA provider
## @raise Error from task execution or TaskTimedOut
##
def UnregisterProvider(storageManager, providerId):
   task = storageManager.UnregisterProvider(providerId)
   _WaitForTask(task)


##
## Finds a VASA provider with given IP/URL
##
## @param storageManager SMS storage manager object
## @param ip URL or IP of the VASA provider
## @return providerInfo or None
##
def FindProvider(storageManager, ip):
   providers = storageManager.QueryProvider()

   for provider in providers:
      info = provider.QueryProviderInfo()
      if (isinstance(info, Sms.Provider.VasaProviderInfo) and
          info.url.find(ip) != -1):
         return info

   return None

##
## Unregisters a VASA provider with given IP/URL
##
## @param storageManager SMS storage manager object
## @param ip URL or IP of the VASA provider
## @return True if found and unregistered, False otherwise
##
def UnregisterProviderByIp(storageManager, ip):
   info = FindProvider(storageManager, ip)
   if (info):
      UnregisterProvider(storageManager, info.uid)
      return True
   else:
      return False

##
## Utility function to run command over ssh
##
## @param cmd command to be executed
## @param host ip/hostname
## @param user username
## @param pwd password
## @return exitcode
##
def RunCmd(cmd, host, user="root", pwd="ca$hc0w"):
   ssh = paramiko.SSHClient()
   ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   with warnings.catch_warnings():
      warnings.filterwarnings('ignore', '.*Unknown ssh-rsa host key.*',)
      ssh.connect(host, username=user, password=pwd, look_for_keys=False)

   channel = ssh.get_transport().open_session()
   channel.exec_command(cmd)
   exitCode = channel.recv_exit_status()
   ssh.close()
   if exitCode != 0:
      print(channel.recv_stderr(1024))
      raise Exception("Could not execute command: " + cmd + "on host: " + host)

# test class
class VvolDs:
   def __init__(self, args):
      # Connect
      self._si = SmartConnect(host=args.GetKeyValue("host"),
                              user=args.GetKeyValue("user"),
                              pwd=args.GetKeyValue("pwd"))

      self._vc=args.GetKeyValue("host")
      self._user=args.GetKeyValue("user")
      self._pwd=args.GetKeyValue("pwd")
      self._vpuser=args.GetKeyValue("vpuser")
      self._vppwd=args.GetKeyValue("vppwd")
      self._nfs=args.GetKeyValue("nfs")
      self._path=args.GetKeyValue("mount")
      self._pe=args.GetKeyValue("pe")
      self._vasaMgr = self._si.RetrieveInternalContent().GetVasaManager()
      self.PopulateHosts()
      self.PopulateSmsInfo()

   def __del__(self):
      Disconnect(self._si)

   def banner(self, fn):
      VerboseLog(logInfo," " + fn.__name__ + " ", msgend='')


   def PrintExistingDs(self):
      for ds in self._host.GetConfigManager().GetDatastoreSystem().datastore:
         VerboseLog(logTrivia, ds.name)

   # Create a datastore on a host
   def CreateDs(self, spec):
      try:
         VerboseLog(logTrivia, "{ Creating: " + spec.GetScId())
         dsId = self._host.GetConfigManager().GetDatastoreSystem().CreateVvolDatastore(spec)
         return dsId
      except:
         #print e
         #traceback.print_exc(file=sys.stdout)
         raise
      finally:
         VerboseLog(logTrivia, "}")

   # Remove a datastore from host
   def removeDs(self, ds):
      try:
         VerboseLog(logTrivia, "{ Removing: " + ds.name)
         self._host.GetConfigManager().GetDatastoreSystem().RemoveDatastore(ds)
      except:
         #print e
         #traceback.print_exc(file=sys.stdout)
         raise
      finally:
         VerboseLog(logTrivia, "}")

   #  Add NFS PE to all the hosts in the VC
   def addPE(self):
      try:
         VerboseLog(logTrivia, "{ Adding PE: " + self._nfs)
         spec = Vim.Host.NasVolume.Specification()
         spec.SetRemoteHost(self._nfs)
         spec.SetRemotePath(self._path)
         spec.SetLocalPath(self._pe)
         spec.SetAccessMode("readWrite")

         for host in  self._hosts:
            VerboseLog(logTrivia, host)
            try:
               host.GetConfigManager().GetDatastoreSystem().CreateNasDatastore(spec)
            except Vim.Fault.DuplicateName:
               pass;
            except Vim.Fault.AlreadyExists:
               pass;
      except Vim.Fault.DuplicateName:
         pass;
      except Vim.Fault.AlreadyExists:
         pass;
      except :
         traceback.print_exc(file=sys.stdout)
         VerboseLog(logTrivia, "failed")
      finally:
         VerboseLog(logTrivia, "}")

   # Populate host list by iterating the first dc
   def PopulateHosts(self):
      VerboseLog(logTrivia, "{ Getting hosts: ")
      self._dc = invt.GetRootFolder().GetChildEntity()[0]
      hostFolder = self._dc.hostFolder
      self._hosts = []
      if len(hostFolder.childEntity) > 0:
         for computeResource in hostFolder.childEntity:
            self._hosts.append(computeResource.host[0])

         self._host = self._hosts[0]

         VerboseLog(logTrivia, ", ".join(map(str, self._hosts)))
      else:
         raise RuntimeError('no hosts found')
      VerboseLog(logTrivia, "}")

   # Populate sms storagemgr and a storage container id to test
   def PopulateSmsInfo(self):
      VerboseLog(logTrivia, "{ Getting SMS info: ")
      self._smsStorageMgr = GetStorageManager(self._vc)
      scList = []
      scResult = self._smsStorageMgr.QueryStorageContainer(None)
      if scResult != None:
         print(scResult)

         if len(scResult.storageContainer) <= 0:
            raise RuntimeError('no storage containers found')

         provInfo = FindProvider(self._smsStorageMgr, self._nfs)
         if provInfo == None:
            raise RuntimeError('no provider found')

         self._sc = None

         for sc in scResult.storageContainer:
            for prov in sc.providerId:
               if prov == provInfo.uid:
                  self._sc = sc.uuid
                  self._arrayIds = sc.arrayId

      if self._sc == None:
         raise RuntimeError('no storage containers found')

      arrayFound=False
      for id in self._arrayIds:
         for relatedArray in provInfo.relatedStorageArray:
            if id == relatedArray.arrayId:
               self._arrayId = id
               self._arrayPriority = relatedArray.priority
               self._provUrl = provInfo.url
               arrayFound=True
               break
         if arrayFound:
            break;

      if not arrayFound:
         raise Exception('array not found')

   # Test create vvol by specifying a dummy storage container id
   # and expects NotFound exception
   # 1. Attemtps create dummy datastore and expects excpetion
   def TestDummyCreateVvolDs(self):
      self.banner(self.TestDummyCreateVvolDs)

      VerboseLog(logTrivia, self._host)

      spec = Vim.Host.DatastoreSystem.VvolDatastoreSpec()
      spec.SetScId('dummy')
      spec.SetName("vvol-test-ds:%s" % random.randint(1,1000))

      try:
         self.CreateDs(spec)
      except Vim.Fault.NotFound:
         VerboseLog(logInfo,"passed")
         pass

   # Test create vvol datastore by specifying a valid storage container id.
   # Once created, also removes the datastore from the host
   # 1. create datastore on host
   # 2. remove datastore from host
   def TestCreateVvolDs(self):
      self.banner(self.TestCreateVvolDs)
      VerboseLog(logTrivia, self._host)

      scId = self._sc
      spec = Vim.Host.DatastoreSystem.VvolDatastoreSpec()
      spec.SetScId(scId)
      spec.SetName("vvol-test-ds:%s" % random.randint(1,1000))

      ret=True
      try:
         ds = self.CreateDs(spec)
         self.removeDs(ds)
      except:
         VerboseLog(logInfo, traceback.format_exc())
         ret=False

      VerboseLog(logInfo, "passed" if ret else "failed");

   # Test destroy vvol datastore
   # 1. create datastore on host
   # 2. destroy datastore from host
   def TestDestroyVvolDs(self):
      self.banner(self.TestDestroyVvolDs)
      scId = self._sc
      spec = Vim.Host.DatastoreSystem.VvolDatastoreSpec()
      spec.SetScId(scId)
      spec.SetName("vvol-test-ds:%s" % random.randint(1,1000))

      ret=True
      try:
         VerboseLog(logTrivia, "{ Creating bulk: ")
         create_task = self._vasaMgr.CreateVVolDatastore(spec, self._hosts)
         task.WaitForTask(create_task)
         VerboseLog(logVerbose, create_task.info.result)
         for result in create_task.info.result :
            if result.result == 'fail':
               raise Exception("create failed for host " + result.hostKey)

         for ds in self._host.GetConfigManager().GetDatastoreSystem().datastore:
            if ds.name.startswith('vvol-test-ds:'):
               vimutil.InvokeAndTrack(ds.Destroy)
               break

      except:
         VerboseLog(logTrivia, traceback.format_exc())
         ret=False
      finally:
         VerboseLog(logTrivia, "}")

      VerboseLog(logInfo, "passed" if ret else "failed");

   # Test create vvol datastore on a set of hosts.
   # 1. invokes batch create vvol api on vasamanager
   # 2. wait for the task to complete
   # 3. search the result if there is a failure on any of the host
   def TestBulkCreateVvolDs(self):
      self.banner(self.TestBulkCreateVvolDs)
      scId = self._sc
      spec = Vim.Host.DatastoreSystem.VvolDatastoreSpec()
      spec.SetScId(scId)
      spec.SetName("vvol-test-ds:%s" % random.randint(1,1000))

      ret=True
      try:
         VerboseLog(logTrivia, "{ Creating bulk: ")
         create_task = self._vasaMgr.CreateVVolDatastore(spec, self._hosts)
         task.WaitForTask(create_task)
         VerboseLog(logVerbose, create_task.info.result)
         for result in create_task.info.result :
            if result.result == 'fail':
               VerboseLog(logInfo, "create failed for host " + result.hostKey)
               ret=False

         # store the ds ref
         self._bulkDs = create_task.info.result[0].ds;

      except:
         VerboseLog(logTrivia, traceback.format_exc())
         ret=False
      finally:
         VerboseLog(logTrivia, "}")

      VerboseLog(logInfo, "passed" if ret else "failed");

   # Test remove non-vvol datastore from a set of hosts.
   # 1. invokes batch remove vvol api on vasamanager
   # 2. Expect the result to be invalid datastore
   def TestBulkRemoveNonVvolDs(self):
      self.banner(self.TestBulkRemoveNonVvolDs)

      ret=True
      try:
         VerboseLog(logTrivia, "{ Removing bulk: ")
         dc = invt.GetRootFolder().GetChildEntity()[0]
         for ids in dc.GetDatastore():
            if ids.GetName().startswith(self._pe):
               VerboseLog(logTrivia,"Removing " + ids.GetName())
               self._vasaMgr.RemoveVVolDatastore(ids, self._hosts)
      except Vim.Fault.InvalidDatastore:
         pass
      except:
         VerboseLog(logTrivia, traceback.format_exc())
         ret=False
      finally:
         VerboseLog(logTrivia, "}")

      VerboseLog(logInfo, "passed" if ret else "failed");

   # Test remove vvol datastore from a set of hosts.
   # 1. invokes batch remove vvol api on vasamanager
   # 2. wait for the task to complete
   # 3. search the result if there is a failure on any of the host
   def TestBulkRemoveVvolDs(self):
      self.banner(self.TestBulkRemoveVvolDs)

      if self._bulkDs == None:
         VerboseLog(logInfo, "skipping")
         return

      ret=True
      try:
         VerboseLog(logTrivia, "{ Removing bulk: ")
         create_task = self._vasaMgr.RemoveVVolDatastore(self._bulkDs, self._hosts)
         task.WaitForTask(create_task)
         VerboseLog(logVerbose, create_task.info.result)
         for result in create_task.info.result :
            if result.result == 'fail':
               VerboseLog(logInfo, "remove failed for host " + result.hostKey)
               ret=False

      except:
         VerboseLog(logTrivia, traceback.format_exc() + "}")
         ret=False
      finally:
         VerboseLog(logTrivia, "}")

      VerboseLog(logInfo, "passed" if ret else "failed");

   # Test remove vvol datastore with an existing VM having its disk on this datastore.
   # Expects Resource in use exception when there is a VM already.
   # 1. cleanup any test datastore
   # 2. cleanup any vvoldummyvms
   # 3. create vvol datastore on a host
   # 4. create vm with a disk on that datastore
   # 5. try remove datastore, and expects resource in use exception
   # 6. now remove the vm
   # 7. remove the datastore
   def TestRemoveVvolDsWithVms(self):

      self.banner(self.TestRemoveVvolDsWithVms)
      VerboseLog(logTrivia, self._host)

      scId = self._sc
      vmname = "vvoldummy"
      self.CleanupExistingTestDatastores()
      self.CleanupVm(vmname)

      spec = Vim.Host.DatastoreSystem.VvolDatastoreSpec()
      spec.SetScId(scId);
      spec.SetName("vvol-test-ds:%s" % random.randint(1,1000))

      testvm = None
      ds = None

      try:
         ds = self.CreateDs(spec)
         testvm = vm.CreateQuickDummy(vmname,
                                      host=self._host,
                                      datastoreName=ds.name,
                                      dc=self._dc.name,
                                      numScsiDisks=1,
                                      memory=10)
         self.removeDs(ds)
      except Vim.Fault.ResourceInUse:
         if testvm != None:
            vm.Destroy(testvm)
         if ds != None:
            self.removeDs(ds)
         pass
      except:
         VerboseLog(logInfo, traceback.format_exc())
         VerboseLog(logInfo, 'failed')

      VerboseLog(logInfo, "passed")

   # Test update vvol datastore. Following steps are executed inorder
   # 1. create datastore on host
   # 2. bump the VP priority via SCST backend
   # 3. sleep for a while and check the datastore info for updated information
   def TestUpdateVvolDs(self):
      self.banner(self.TestUpdateVvolDs)
      VerboseLog(logTrivia, self._host)

      scId = self._sc
      spec = Vim.Host.DatastoreSystem.VvolDatastoreSpec()
      spec.SetScId(scId)
      spec.SetName("vvol-test-ds:%s" % random.randint(1,1000))

      ret=True
      try:
         vvolds = self.CreateDs(spec)
         parseResult = urlparse.urlparse(self._provUrl)
         path = parseResult.path.lstrip('/')
         # get provider name from the path
         provName = re.sub(r'/.*$', "", path)
         # strip off the sms prepended namespace
         arrayId = re.sub(r'.*:', "", self._arrayId)
         newPriority= self._arrayPriority + 10

         # bump priority of VP
         cmd="perl -I/usr/local/scst/scst_scripts/vasa_scripts/ /usr/local/scst/scst_scripts/vasa_scripts/updateVPArrayPriority.pl " + arrayId + " " + provName + " " + str(newPriority)
         RunCmd(cmd, self._nfs, self._vpuser, self._vppwd)

         time.sleep(60)

         updated=False
         for vp in vvolds.info.vvolDS.vasaProviderInfo:
            if vp.provider.url == self._provUrl:
               for arrayState in vp.arrayState:
                  if arrayState.arrayId == self._arrayId:
                     if arrayState.priority != newPriority:
                        raise Exception("priority not updated")
                     else:
                        updated=True
                        break
            if updated:
               break

         if not updated:
            raise Exception("no vp found")

         self.removeDs(vvolds)
      except:
         ret=False
         VerboseLog(logInfo, traceback.format_exc())

      VerboseLog(logInfo, "passed" if ret else "failed");

   # Helper function to stop vpxa daemon on host
   # 1. stop vpxa on host by ssh
   # 2. wait till the host status reflects that it is not connected
   def StopVpxa(self):
      cmd = "/etc/init.d/vpxa stop>/dev/null 2>&1"
      RunCmd(cmd, self._host.GetName(), "root", "")

      count=0
      while count < 20:
         time.sleep(20)
         count += 1
         if self._host.GetRuntime().GetConnectionState() != "connected":
            break

      if count == 20:
         raise Exception("host not disconnected")


   # Helper function to start vpxa daemon on host
   # 1. start vpxa on host by ssh
   # 2. wait till the host status reflects that it is connected
   def StartVpxa(self):
      cmd = "/etc/init.d/vpxa start>/dev/null 2>&1"
      RunCmd(cmd, self._host.GetName(), "root", "")
      count=0
      while count < 20:
         time.sleep(20)
         count += 1
         if self._host.GetRuntime().GetConnectionState() == "connected":
            break

      if count == 20:
         raise Exception("host not connected")

   # Test create apis on disconnected host and expect that HostNotConnected fault
   # 1. Stop vpxa on a host say AAA
   #    invoke create vvol datastore
   #    Expect the HostNotConnected fault
   # 2. Invoke bulk api
   #    Expect HostNotConnected fault for host AAA and rest of the hosts succeed
   # 3. Start vpxa
   #    Create vvol datastore on host AAA
   #    Stop vpxa
   #    Invoke bulk remove method
   #    Expect HostNotConnected fault for host AAA and rest of the hosts succeed
   # 4. Do cleanup by starting vpxa and removing vvol datastore
   def TestDisconnectedHost(self):
      self.banner(self.TestDisconnectedHost)
      VerboseLog(logTrivia, self._host)

      scId = self._sc
      spec = Vim.Host.DatastoreSystem.VvolDatastoreSpec()
      spec.SetScId(scId)
      spec.SetName("vvol-test-ds:%s" % random.randint(1,1000))

      ret=True
      try:
         self.StopVpxa()

         try:
            VerboseLog(logInfo, "{Testing simple create")
            ds = self.CreateDs(spec)
         except vmodl.fault.HostNotConnected:
            pass
         except:
            raise
         finally:
            VerboseLog(logInfo, "}")

         try:
            VerboseLog(logInfo, "{Testing bulk create")
            create_task = self._vasaMgr.CreateVVolDatastore(spec, self._hosts)
            task.WaitForTask(create_task)
            VerboseLog(logVerbose, create_task.info.result)
            for result in create_task.info.result :
               if result.result == 'fail':
                  hostid = self._host.__class__.__name__ + ":" + self._host._moId
                  if result.hostKey == hostid:
                     if isinstance(result.fault, vmodl.fault.HostNotConnected) == False:
                        VerboseLog(logInfo, "failed for host " + result.hostKey)
                        raise Exception("unexpected exception")
                  else:
                     raise Exception("unexpected failure")
         finally:
            VerboseLog(logInfo, "}")

         self.StartVpxa()

         ds = self.CreateDs(spec)

         self.StopVpxa()

         try:
            VerboseLog(logInfo, "{Testing bulk remove")
            delete_task = self._vasaMgr.RemoveVVolDatastore(ds, self._hosts)
            task.WaitForTask(delete_task)
            VerboseLog(logVerbose, delete_task.info.result)
            for result in delete_task.info.result :
               if result.result == 'fail':
                  hostid = self._host.__class__.__name__ + ":" + self._host._moId
                  if result.hostKey == hostid:
                     if isinstance(result.fault, vmodl.fault.HostNotConnected) == False:
                        VerboseLog(logInfo, "failed for host " + result.hostKey)
                        raise Exception("unexpected exception")
                  else:
                     raise Exception("unexpected failure")
         finally:
            VerboseLog(logInfo, "}")

         self.StartVpxa()
         self.removeDs(ds)
      except:
         VerboseLog(logInfo, traceback.format_exc())
         ret=False
      VerboseLog(logInfo, "passed" if ret else "failed");

   # Test create directory on DatastoreNamespaceManager via hostd
   # 1. create vvol datastore on host
   # 2. create a directory on the vvol datastore
   # 3. query for the directory
   # 4. remove the directory
   # 5. remove the datastore
   def TestCreateDir(self):
      self.banner(self.TestCreateDir)
      VerboseLog(logTrivia, self._host)

      scId = self._sc
      spec = Vim.Host.DatastoreSystem.VvolDatastoreSpec()
      spec.SetScId(scId)
      spec.SetName("vvol-test-ds:%s" % random.randint(1,1000))

      ret=True
      try:
         vvolds = self.CreateDs(spec)

         session = vimsupport.CreateSession(self._host.GetName(), 443, 'root', '',
                                            newestVersions.GetWireId('vim'))
         stub = session.GetStub()
         si = Vim.ServiceInstance('ServiceInstance', stub)
         isc = si.RetrieveContent()
         dnm = isc.GetDatastoreNamespaceManager()
         ds = Vim.Datastore(scId, stub)
         stableName = dnm.CreateDirectory(ds, ".vSphere-HA")

         browser = ds.GetBrowser()
         path = "[" + ds.GetName() + "].vSphere-HA"
         task = browser.Search(path, None)
         session.WaitForTask(task)
         VerboseLog(logVerbose,  task.GetInfo())
         dnm.DeleteDirectory(stableName)
         self.removeDs(vvolds)
      except:
         VerboseLog(logInfo, traceback.format_exc())
         ret=False
      VerboseLog(logInfo, "passed" if ret else "failed");

   # Test VM migration on a vvol datastore
   # 1. create vvol datastore on set of hosts
   # 2. create a vm on src host
   # 3. power on vm
   # 4. migrate vm to dest host
   # 5. destroy vm
   # 6. remove datastore from the set of hosts
   def TestVmMigrate(self):
      self.banner(self.TestVmMigrate)

      if len(self._hosts) <= 1:
         VerboseLog(logInfo,"not enough hosts..skipping")

      vmname = "test_migrate_vvol_vm"
      self.CleanupVm(vmname)
      host1 = self._hosts[0]
      host2 = self._hosts[1]

      scId = self._sc
      spec = Vim.Host.DatastoreSystem.VvolDatastoreSpec()
      spec.SetScId(scId)
      spec.SetName("vvol-test-ds:%s" % random.randint(1,1000))

      ret=True
      try:
         VerboseLog(logTrivia, "{ Creating bulk: ")
         create_task = self._vasaMgr.CreateVVolDatastore(spec, self._hosts)
         task.WaitForTask(create_task)
         VerboseLog(logVerbose, create_task.info.result)
         for result in create_task.info.result :
            if result.result == 'fail':
               VerboseLog(logInfo, "create failed for host " + result.hostKey)
               raise Exception("unexpected failure")

         ds = create_task.info.result[0].ds;
         testvm = vm.CreateQuickDummy(vmname,
                                      host=host1,
                                      datastoreName=ds.name,
                                      dc=self._dc.name,
                                      numScsiDisks=1,
                                      memory=12)

         vm.PowerOn(testvm)

         migrate_task = testvm.Migrate(host2.parent.resourcePool, host2, Vim.VirtualMachine.MovePriority.highPriority, None)
         task.WaitForTask(migrate_task)

         vm.PowerOff(testvm)
         vm.Destroy(testvm)

         VerboseLog(logTrivia, "{ Removing bulk: ")
         delete_task = self._vasaMgr.RemoveVVolDatastore(ds, self._hosts)
         task.WaitForTask(delete_task)
         VerboseLog(logVerbose, delete_task.info.result)
         for result in delete_task.info.result :
            if result.result == 'fail':
               VerboseLog(logInfo, "remove failed for host " + result.hostKey)
               raise Exception("unexpected failure in bulk remove")

      except:
         VerboseLog(logTrivia, traceback.format_exc())
         ret=False

      VerboseLog(logInfo, "passed" if ret else "failed");

   # utility function to delete any existing vvol-test datastores
   def CleanupExistingTestDatastores(self):
      for host in  self._hosts:
         VerboseLog(logTrivia, host)
         for ds in host.GetConfigManager().GetDatastoreSystem().datastore:
            if ds.name.startswith('vvol-test-ds:'):
               host.GetConfigManager().GetDatastoreSystem().RemoveDatastore(ds)

   # utility function to cleanup VMs with the given name
   def CleanupVm(self, vmname):
      oldVms = folder.FindPrefix(vmname)
      for oldVm in oldVms:
         if oldVm.GetRuntime().GetPowerState() == \
         Vim.VirtualMachine.PowerState.poweredOn:
            vm.PowerOff(oldVm)
         vm.Destroy(oldVm)

def main():
   supportedArgs = [ (["h:", "host="], "10.20.109.41", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "vmware", "Password", "pwd"),
                     (["vpuser="], "root", "VP User name", "vpuser"),
                     (["vppwd="], "ca$hc0w", " VP Password", "vppwd"),
                     (["n:", "nfs="], "10.20.108.115", "nfs host name", "nfs"),
                     (["m:", "mount="], "/mnt/pes/pepsi_nfs_pe", "Nfs server mount point", "mount"),
                     (["d:", "pe="], "pepsi_nfs_pe", "PE name", "pe"),
                     (["v:", "verbose="], "3", "log level(1-3), the lesser the more verbose", "verbose")]

   supportedToggles = [(["usage", "help"], False, "Show usage information", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      print('Prerequisite:\n\
               1. VC with minimum of one host configured\n\
               2. VP is registered with SMS\n\
               3. VP is configured with NFS pe')
      sys.exit(0)

   global verbose
   verbose = int(args.GetKeyValue("verbose"))



   Log("Connected to vc " + args.GetKeyValue("host"))

   ds = VvolDs(args)

   ds.CleanupExistingTestDatastores()
   ds.addPE()
   ds.TestDummyCreateVvolDs()
   ds.TestCreateVvolDs()
   ds.TestDestroyVvolDs()
   ds.TestBulkCreateVvolDs()
   ds.TestBulkRemoveVvolDs()
   ds.TestBulkRemoveNonVvolDs()
   ds.TestRemoveVvolDsWithVms()
   ds.TestCreateDir()
   ds.TestVmMigrate()
   ds.TestDisconnectedHost()
   ds.TestUpdateVvolDs()
# Start program
if __name__ == "__main__":
    main()
