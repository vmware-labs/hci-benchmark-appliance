#!/usr/bin/env python

"""
Copyright 2016-2020 VMware, Inc.  All rights reserved.
-- VMware Confidential

Command-line wrapper around the Vim.Encryption, and family, API. This
allows querying server state, as well as adding/removing keys and key
servers, changing host state, etc.

All output should be standard YAML for easy parsing of results.

Requires the publicly available pyVmomi only; no private pyVim support
is required (and should not be added).
"""

import atexit
import base64
import os
import sys
import time

# Publicly available
from pyVmomi import Pbm, SoapStubAdapter, Vim, Vmodl, VmomiSupport
from pyVim.connect import SmartConnect, Disconnect

def Log(msg):
   """Log a message to the console."""
   print(msg)

def Error(msg):
   """Log an error message to the console."""
   Log("# ERROR: %s" % msg)

def Warn(msg):
   """Log a warning message to the console."""
   Log("# WARN: %s" % msg)

def IsVirtualCenter(si):
   """Determine if currently connected to Virtual Center.

   Some API features are only implemented on Virtual Center; they
   are left not-implemented on the ESX host. Check the API type
   for better error reporting.
   """
   return si.content.about.apiType == "VirtualCenter"

def IsLocalhostESX():
   return os.uname()[0] == "VMkernel"

def VerifyVirtualCenterConnection(si):
   """Raise an exception if the connection is not Virtual Center."""
   if not IsVirtualCenter(si):
      raise Exception("Operation requires vCenter Server.")

def TaskEta(pct):
   """Calculate estimated time to completion.

   Encryption operations can take a very long time. This function helps
   us estimate time to completion which can be displayed in the progress
   bar.
   """
   TaskEta.spoke += 1
   wheel = [ '|', '/', '-', '\\' ][TaskEta.spoke % 4]
   curTime = time.time() - TaskEta.startTime
   if pct > 0 and curTime > 3:
      rate = curTime / pct
      estTime = (100 - pct) * rate
      m, s = divmod(estTime, 60)
      return "eta %dm %ds    " % (m, s)
   return "eta %s" % wheel
TaskEta.spoke = 0
TaskEta.startTime = time.time() # XXX Use time.monotonic with Python 3.3.

def LogTaskProgress(pct):
   """Log the task progress."""
   def GetProgress(pct):
      width = 50    # Characters for progress bar.
      progress = int(pct / (100 / width))
      remainder = width - progress
      return progress, remainder, TaskEta(pct)

   progress, remainder, eta = GetProgress(pct)
   sys.stdout.write("# %3d%% [%s%s] %s\r" %
                    (pct, "#"*progress, " "*remainder, eta))
   if LogTaskProgress.done:
      sys.stdout.write("\n")
   sys.stdout.flush()
LogTaskProgress.done = False

def WaitForTask(task, progress=True):
   """Wait for a pending @task"""
   if not task:
      return None
   si = Vim.ServiceInstance("ServiceInstance", task._stub)
   pc = si.content.propertyCollector

   objspec = Vmodl.Query.PropertyCollector.ObjectSpec(obj=task)
   propspec = Vmodl.Query.PropertyCollector.PropertySpec(
                                          type=Vim.Task, pathSet=[], all=True)
   filterspec = Vmodl.Query.PropertyCollector.FilterSpec()
   filterspec.objectSet = [objspec]
   filterspec.propSet = [propspec]

   if progress:
      LogTaskProgress(0)
   filter = pc.CreateFilter(filterspec, True)

   version, state = None, None
   while state not in (Vim.TaskInfo.State.success, Vim.TaskInfo.State.error):
      try:
         if progress and task.info.progress:
            LogTaskProgress(task.info.progress)
         update = pc.WaitForUpdates(version)
         state = task.info.state
         version = update.version
      except Vmodl.Fault.ManagedObjectNotFound:
         break

   filter.Destroy()
   if progress:
      LogTaskProgress.done = True
      LogTaskProgress(100)
      LogTaskProgress.done = False
   if state == "error":
      raise task.info.error

def CreateKey(bits=256):
   """Create a key that is suitible for test purposes.

   This function creates a random key that can be used as the key
   for virtual machine configuration and virtual disk descriptor
   encryption, or as a host key, in test environments. The key is
   base64 encoded, as expected by the Vim APIs.

   Note that this approach MUST NOT be used in production.
   """
   if bits == 0 or bits % 8 != 0:
      raise ValueError("Invalid number of bits: %d" % bits)
   if sys.version_info >= (3, 0):
      rbytes = os.urandom(int(bits / 8))
      return base64.b64encode(rbytes).decode('utf-8')
   else:
      return base64.b64encode(os.urandom(bits / 8))

def GetAlgorithmBits(algo):
   if algo == "AES-128":
      return 128
   if algo == "AES-192":
      return 192
   if algo == "AES-256":
      return 256
   if algo == "XTS-AES-256":
      return 512
   raise ValueError("Unknown algorithm: %s" % algo)

def CreateProviderId(providerId):
   if not providerId:
      return None
   keyProviderId = Vim.Encryption.KeyProviderId()
   keyProviderId.SetId(providerId)
   return keyProviderId

def CreateCryptoKeyId(keyId, providerId):
   cryptoKeyId = Vim.Encryption.CryptoKeyId()
   cryptoKeyId.SetKeyId(keyId)
   if providerId:
      keyProviderId = CreateProviderId(providerId)
      cryptoKeyId.SetProviderId(keyProviderId)
   return cryptoKeyId

def CreateCryptoKeyPlain(keyId, providerId, algo="AES-256", data=None):
   cryptoKey = Vim.Encryption.CryptoKeyPlain()
   cryptoKey.SetKeyId(CreateCryptoKeyId(keyId, providerId))
   cryptoKey.SetAlgorithm(algo)
   if not data:
      data = CreateKey(GetAlgorithmBits(algo))
   cryptoKey.SetKeyData(data)
   return cryptoKey

def CreateCryptoSpecEncrypt(keyId):
   cryptoSpec = Vim.Encryption.CryptoSpecEncrypt()
   cryptoSpec.SetCryptoKeyId(keyId)
   return cryptoSpec

def CreateCryptoSpecDecrypt():
   return Vim.Encryption.CryptoSpecDecrypt()

def CreateCryptoSpecRecryptDeep(keyId):
   cryptoSpec = Vim.Encryption.CryptoSpecDeepRecrypt()
   cryptoSpec.SetNewKeyId(keyId)
   return cryptoSpec

def CreateCryptoSpecRecryptShallow(keyId):
   cryptoSpec = Vim.Encryption.CryptoSpecShallowRecrypt()
   cryptoSpec.SetNewKeyId(keyId)
   return cryptoSpec

def GetCryptoManager(si, hostName=None):
   if hostName:
      hostSystems = HostGetHostSystems(si, hostName=hostName)
      if len(hostSystems) == 0:
         raise Exception("Host name not found: %s" % args.host)
      if len(hostSystems) > 1:
         raise Exception("More than one host named '%s'." % args.host)
      cryptoMgr = hostSystems[0].configManager.cryptoManager
   else:
      content = si.RetrieveContent()
      cryptoMgr = content.cryptoManager
   if not cryptoMgr or not cryptoMgr.enabled:
      raise Exception("CryptoManager is not enabled.")
   return cryptoMgr

def LogCryptoKeyId(keyId, tabs=0, sequence=False):
   spaces = tabs * 3   # 3 spaces per tab
   leader = " " * spaces
   if sequence:
      assert tabs > 0
      Log("%skeyId: %s" % ((" " * (3 * (tabs - 1))) + " - ", keyId.keyId))
   else:
      Log("%skeyId: %s" % (leader, keyId.keyId))
   if keyId.providerId:
      Log("%sproviderId:" % leader)
      Log("%s   id: %s" % (leader, keyId.providerId.id))

def KeysList(si, args):
   """List all of the key identifiers present on the server."""
   cryptoMgr = GetCryptoManager(si, hostName=args.host)
   keys = cryptoMgr.ListKeys()
   Log("---")
   Log("keys:")
   for key in keys:
      LogCryptoKeyId(key, tabs=1, sequence=True)
   Log("...")

def KeysRemove(si, args):
   """Remove the specified key identifiers from the server.

   Supports remove multiple keys from the same key provider. The
   operation will report failure if any one of the keys fails to be
   removed.
   """
   cryptoMgr = GetCryptoManager(si, hostName=args.host)
   cryptoKeyIds = []
   for keyId in args.keyIds:
      cryptoKeyId = CreateCryptoKeyId(keyId, args.providerId)
      cryptoKeyIds.append(cryptoKeyId)
   results = cryptoMgr.RemoveKeys(cryptoKeyIds, args.force)
   failed = False
   for result in results:
      if not result.success:
         Log("# Failed to remove key '%s': %s" %
             (result.keyId.keyId, result.reason))
         failed = True
   if failed:
      raise Exception("Failed to remove key.")

def KeysAdd(si, args):
   """Add a key to the server."""
   cryptoMgr = GetCryptoManager(si, hostName=args.host)
   cryptoKey = CreateCryptoKeyPlain(args.keyId, args.providerId,
                                    args.algorithm, args.data)
   cryptoMgr.AddKey(cryptoKey)
   Log("---")
   Log("key:")
   Log("   keyId:")
   LogCryptoKeyId(cryptoKey.keyId, tabs=2)
   Log("   algorithm: %s" % cryptoKey.algorithm)
   Log("   keyData: %s" % cryptoKey.keyData)
   Log("...")

def KeysMatch(cryptoKeyId, keyId, providerId):
   """Match a CryptoKeyId.

   Test if the provided CryptoKeyId matches the provided keyId and
   providerId. Either keyId or providerId can be specified as None to
   match any value, but one of keyId or providerId must be specified.
   """
   assert cryptoKeyId
   assert keyId or providerId
   if keyId and keyId != cryptoKeyId.keyId:
      return False
   if providerId:
      if not cryptoKeyId.providerId:
         return False
      if providerId != cryptoKeyId.providerId.id:
         return False
   return True

def KeysFind(si, args):
   """Find objects that are using the specified key."""
   if not args.keyId and not args.providerId:
      raise Exception("A key ID or provider ID must be specified.")

   def LOG(msg):
      if not args.countOnly:
         Log(msg)

   count = 0
   Log("---")

   first = True
   hostSystems = HostGetHostSystems(si, datacenterName=args.datacenter)
   for hs in hostSystems:
      if hs.runtime.cryptoKeyId:
         if KeysMatch(hs.runtime.cryptoKeyId, args.keyId, args.providerId):
            if first:
               LOG("host:")
               first = False
            LOG(" - name: %s" % hs.name)
            LOG("   moid: %s" % hs._moId)
            if args.verbose:
               LOG("   keyId:")
               if not args.countOnly:
                  LogCryptoKeyId(hs.runtime.cryptoKeyId, tabs=2)
            count += 1


   def LogVm(vm, first):
      if first:
         LOG("vm:")
      LOG(" - name: %s" % vm.name)
      LOG("   moid: %s" % vm._moId)
      if args.verbose:
         LOG("   keyId:")
         if not args.countOnly:
            LogCryptoKeyId(vm.config.keyId, tabs=2)

   first = True
   vms = VmGetVms(si, datacenterName=args.datacenter)
   for vm in vms:
      vmLogged = False
      firstDisk = True
      if vm.config.keyId:
         if KeysMatch(vm.config.keyId, args.keyId, args.providerId):
            LogVm(vm, first)
            first = False
            count += 1
            vmLogged = True
      for device in vm.config.hardware.device:
         if isinstance(device, Vim.Vm.Device.VirtualDisk):
            if (isinstance(device.backing,
                           Vim.Vm.Device.VirtualDisk.FlatVer2BackingInfo) or
                isinstance(device.backing,
                           Vim.Vm.Device.VirtualDisk.SeSparseBackingInfo) or
                isinstance(device.backing,
                           Vim.Vm.Device.VirtualDisk.SparseVer2BackingInfo)):
               if device.backing.keyId:
                  if KeysMatch(device.backing.keyId, args.keyId,
                               args.providerId):
                     if not vmLogged:
                        LogVm(vm, first)
                        first = False
                     if firstDisk:
                        LOG("   disk:")
                        firstDisk = False
                     LOG("    - index: %s" % device.key)
                     LOG("      fileName: %s" % device.backing.fileName)
                     if args.verbose:
                        LOG("      keyId:")
                        if not args.countOnly:
                           LogCryptoKeyId(device.backing.keyId, tabs=3)
                     count += 1

   Log("count: %d" % count)
   Log("...")

def KeysGenerate(si, args):
   """Generate a new key.

   The key identifier for the new key cannot be specified, so we log
   the result on success.
   """
   VerifyVirtualCenterConnection(si)
   cryptoMgr = GetCryptoManager(si)
   result = cryptoMgr.GenerateKey(CreateProviderId(args.providerId))
   if result.success:
      Log("---")
      Log("key:")
      LogCryptoKeyId(result.keyId, tabs=1)
      Log("...")
   else:
      raise Exception("Failed to generate key: %s" %  result.reason)

def KeysParser(parser):
   subparsers = parser.add_subparsers(title="commands", dest="cmd")
   subparsers.required = True

   subparser = subparsers.add_parser("list", help="List all keys")
   subparser.add_argument("--host", help="The hostname/IP-address")
   subparser.set_defaults(func=KeysList)

   subparser = subparsers.add_parser("add", help="Add a key")
   subparser.add_argument("-p", "--provider-id", dest="providerId",
                          help="Provider/cluster identifier")
   subparser.add_argument("-a", "--algorithm", default="AES-256",
                          help="Key algorithm (default: %(default)s)")
   subparser.add_argument("-d", "--data",
                          help="Base64 encoded key data (default: generated)")
   subparser.add_argument("--host", help="The hostname/IP-address")
   subparser.add_argument("keyId", metavar="key-id", help="Key identifier")
   subparser.set_defaults(func=KeysAdd)

   subparser = subparsers.add_parser("remove", help="Remove keys")
   subparser.add_argument("-p", "--provider-id", dest="providerId",
                          help="Provider/cluster identifier")
   subparser.add_argument("-f", "--force", action="store_true",
                          help="Force remove")
   subparser.add_argument("--host", help="The hostname/IP-address")
   subparser.add_argument("keyIds", metavar="key-id", nargs="*",
                          help="Key identifiers")
   subparser.set_defaults(func=KeysRemove)

   subparser = subparsers.add_parser("find", help="Find keys")
   subparser.add_argument("-c", "--count-only", dest="countOnly",
                          action="store_true", help="Report only the count")
   subparser.add_argument("-p", "--provider-id", dest="providerId",
                          help="Provider/cluster identifier")
   subparser.add_argument("--datacenter", help="The datacenter to inspect")
   subparser.add_argument("keyId", metavar="key-id", nargs="?",
                          default=None, help="Key identifier")
   subparser.set_defaults(func=KeysFind)

   subparser = subparsers.add_parser("generate",
                                     help="Generate a key on a key server")
   subparser.add_argument("-p", "--provider-id", dest="providerId",
                          help="Provider/cluster identifier")
   subparser.set_defaults(func=KeysGenerate)

def KmsLogServerInfo(cryptoMgr, providerId=None, name=None):
   count = 0
   Log("---")
   Log("cluster:")
   for cluster in cryptoMgr.kmipServers:
      if not providerId or cluster.clusterId.id == providerId:
         Log(" - id: %s" % cluster.clusterId.id)
         for server in cluster.servers:
            Log("   server:")
            if not name or server.name == name:
               Log("    - name: %s" % server.name)
               Log("      address: %s" % server.address)
               Log("      port: %s" % server.port)
               if server.proxyAddress:
                  Log("      proxyAddress: %s" % server.proxyAddress)
               if server.proxyPort:
                  Log("      proxyPort: %d" % server.proxyPort)
               if server.reconnect:
                  Log("      reconnect: %d" % server.reconnect)
               if server.protocol:
                  Log("      Protocol: %d" % server.protocol)
               if server.nbio:
                  Log("      nbio: %d" % server.nbio)
               if server.timeout:
                  Log("      timeout: %d" % server.timeout)
               if server.userName:
                  Log("      userName: %s" % server.userName)
               count += 1
         useAsDefault = "yes" if cluster.useAsDefault else "no"
         Log("   useAsDefault: %s" % useAsDefault)
   Log("...")
   return count

def KmsFindServers(cryptoMgr, providerId, name, required=True):
   servers = []
   for cluster in cryptoMgr.kmipServers:
      if cluster.clusterId.id == providerId:
         for server in cluster.servers:
            if not name or server.name == name:
               servers.append(server)
   if required and len(servers) == 0:
      raise Exception("No matching key servers were found.")
   return servers

def KmsList(si, args):
   """List all key servers."""
   VerifyVirtualCenterConnection(si)
   cryptoMgr = GetCryptoManager(si)
   KmsLogServerInfo(cryptoMgr)

def KmsInfo(si, args):
   """Log key server info for the specified provider.

   This is basically the same as the "list" command, except that info
   for one server or provider can be requested. Also we throw an error
   if no matching servers are found.
   """
   VerifyVirtualCenterConnection(si)
   cryptoMgr = GetCryptoManager(si)
   count = KmsLogServerInfo(cryptoMgr, args.providerId, args.name)
   if count == 0:
      raise Exception("No matching key servers were found.")

def KmsLogCertificateInfo(certInfo, tabs=0):
   spaces = tabs * 3   # 3 spaces per tab
   leader = " " * spaces
   Log("%ssubject: |" % leader)
   Log("%s   %s" %
       (leader, ("\n%s   " % leader).join(certInfo.subject.split("\n"))))
   Log("%sissuer: |" % leader)
   Log("%s   %s" %
       (leader, ("\n%s   " % leader).join(certInfo.issuer.split("\n"))))
   Log("%sserialNumber: %s" % (leader, certInfo.serialNumber))
   Log("%snotBefore: %s" % (leader, certInfo.notBefore))
   Log("%snotAfter: %s" % (leader, certInfo.notAfter))
   Log("%sfingerprint: %s" % (leader, certInfo.fingerprint))
   Log("%scheckTime: %s" % (leader, certInfo.checkTime))
   if certInfo.secondsSinceValid:
      Log("%ssecondsSinceValid: %s" % (leader, certInfo.secondsSinceValid))
   if certInfo.secondsBeforeExpire:
      Log("%ssecondsBeforeExpire: %s" % (leader, certInfo.secondsSinceValid))

def KmsStatus(si, args):
   """Log key server status for the specified provider.

   A key server can be added, but not functional. This command lets us
   determine if the server is connected and authenticated.
   """
   VerifyVirtualCenterConnection(si)
   cryptoMgr = GetCryptoManager(si)
   clusterInfo = Vim.Encryption.KmipClusterInfo()
   clusterInfo.clusterId = CreateProviderId(args.providerId)

   clusterInfo.servers = KmsFindServers(cryptoMgr, args.providerId, args.name)
   task = cryptoMgr.RetrieveKmipServersStatus([clusterInfo])
   WaitForTask(task, progress=False)
   status = task.info.result
   assert len(status) == 1
   status = status[0]

   Log("---")
   Log("status:")
   Log("   clusterId:")
   Log("      id: %s" % args.providerId)
   Log("   servers:")
   for server in status.servers:
      Log("    - name: %s" % server.name)
      Log("      status: %s" % server.status)
      Log("      connectionStatus: %s" % server.connectionStatus)
      if server.certInfo:
         Log("      certInfo:")
         KmsLogCertificateInfo(server.certInfo, tabs=3)
      if server.clientTrustServer:
         Log("      clientTrustServer: %d" % server.clientTrustServer)
      if server.serverTrustClient:
         Log("      serverTrustClient: %d" % server.serverTrustClient)
   if status.clientCertInfo:
      Log("   clientCertInfo:")
      KmsLogCertificateInfo(status.clientCertInfo, tabs=2)
   Log("...")

def KmsAdd(si, args):
   """Add a new key server."""
   VerifyVirtualCenterConnection(si)

   info = Vim.Encryption.KmipServerInfo()
   info.name = args.name if args.name else args.providerId
   info.address = args.address
   if args.port:
      info.port = args.port
   else:
      info.port = 5696
   if args.proxyAddress:
      info.proxyAddress = args.proxyAddress
   if args.proxyPort:
      info.proxyPort = args.proxyPort
   if args.user:
      info.userName = args.kmsUser

   spec = Vim.Encryption.KmipServerSpec()
   spec.clusterId = CreateProviderId(args.providerId)
   if args.password:
      spec.password = args.kmsPassword
   spec.info = info

   cryptoMgr = GetCryptoManager(si)
   cryptoMgr.RegisterKmipServer(spec)

   if args.trust:
      certInfo = cryptoMgr.RetrieveKmipServerCert(spec.clusterId, info)
      if not certInfo.certificate or certInfo.certificate == "":
         raise Exception("Failed to retrieve server certificate. Cannot trust.")
      cryptoMgr.UploadKmipServerCert(spec.clusterId, certInfo.certificate)

   if args.markDefault:
      cryptoMgr.MarkDefault(spec.clusterId)

def KmsRemove(si, args):
   """Remove a key server, or cluster of key servers."""
   VerifyVirtualCenterConnection(si)
   cryptoMgr = GetCryptoManager(si)
   servers = KmsFindServers(cryptoMgr, args.providerId, args.name, False)
   for server in servers:
      cryptoMgr.RemoveKmipServer(CreateProviderId(args.providerId), server.name)

def KmsTrust(si, args):
   """Allow Virtual Center to trust the key server.

   Adding a key server is a three step process: 1) add the key server,
   2) have VC trust the key server, and 3) have the key server trust VC.
   We automatically do step (2) in the "add" command, but the "trust"
   command allows this step to be done explicitly.

   Note that we cannot automate step (3) without access to the key
   server. However, PyKMIP servers do not require step (3).
   """
   VerifyVirtualCenterConnection(si)
   cryptoMgr = GetCryptoManager(si)
   servers = KmsFindServers(cryptoMgr, args.providerId, args.name)
   for server in servers:
      clusterId = CreateProviderId(args.providerId)
      certInfo = cryptoMgr.RetrieveKmipServerCert(clusterId, server)
      if not certInfo.certificate or certInfo.certificate == "":
         raise Exception("Failed to retrieve server certificate.")
      Log("certificate =\n%s" % certInfo.certificate)
      cryptoMgr.UploadKmipServerCert(clusterId, certInfo.certificate)

def KmsCertificate(si, args):
   """Log the key server certificate."""
   VerifyVirtualCenterConnection(si)
   cryptoMgr = GetCryptoManager(si)
   servers = KmsFindServers(cryptoMgr, args.providerId, args.name)
   assert len(servers) == 1
   for server in servers:
      clusterId = CreateProviderId(args.providerId)
      certInfo = cryptoMgr.RetrieveKmipServerCert(clusterId, server)
      Log("---")
      Log("certificate: |")
      Log("   %s" % "\n   ".join(certInfo.certificate.split("\n")))
      Log("...")

def KmsMarkDefault(si, args):
   """Mark the specified cluster as the default for key generation."""
   VerifyVirtualCenterConnection(si)
   cryptoMgr = GetCryptoManager(si)
   cryptoMgr.MarkDefault(CreateProviderId(args.providerId))

def KmsParser(parser):
   subparsers = parser.add_subparsers(title="commands", dest="cmd")
   subparsers.required = True

   subparser = subparsers.add_parser("list", help="List all key servers")
   subparser.set_defaults(func=KmsList)

   subparser = subparsers.add_parser("info", help="Describe key server")
   subparser.add_argument("providerId", metavar="provider-id",
                          help="Server cluster name")
   subparser.add_argument("-n", "--name", help="Unique server name")
   subparser.set_defaults(func=KmsInfo)

   subparser = subparsers.add_parser("status", help="Key server status")
   subparser.add_argument("providerId", metavar="provider-id",
                          help="Server cluster name")
   subparser.add_argument("-n", "--name", help="Unique server name")
   subparser.set_defaults(func=KmsStatus)

   subparser = subparsers.add_parser("add", help="Add a key server")
   subparser.add_argument("-n", "--name", help="Unique server name")
   subparser.add_argument("-p", "--port", default="5696", type=int,
                          help="Port number")
   subparser.add_argument("--proxy-address", dest="proxyAddress",
                          help="Proxy hostname/IP-address")
   subparser.add_argument("--proxy-port", dest="proxyPort",
                          help="Proxy port number")
   subparser.add_argument("--user", dest="kmsUser", help="Username")
   subparser.add_argument("--password", dest="kmsPassword", help="Password")
   subparser.add_argument("--no-trust", dest="trust", action="store_false",
                          help="Skip trusting the server")
   subparser.add_argument("-d", "--mark-default",
                          dest="markDefault", action="store_true",
                          help="Make this server the default")
   subparser.add_argument("providerId", metavar="provider-id",
                          help="Server cluster name")
   subparser.add_argument("address", help="Server hostname/IP-address")
   subparser.set_defaults(func=KmsAdd)

   subparser = subparsers.add_parser("remove", help="Remove a key server")
   subparser.add_argument("providerId", metavar="provider-id",
                          help="Server cluster name")
   subparser.add_argument("-n", "--name", help="Unique server name")
   subparser.set_defaults(func=KmsRemove)

   subparser = subparsers.add_parser("trust", help="Trust a key server")
   subparser.add_argument("providerId", metavar="provider-id",
                          help="Server cluster name")
   subparser.add_argument("-n", "--name", help="Unique server name")
   subparser.set_defaults(func=KmsTrust)

   subparser = subparsers.add_parser("certificate",
                                     help="Get the server certificate")
   subparser.add_argument("providerId", metavar="provider-id",
                          help="Server cluster name")
   subparser.add_argument("name", help="Unique server name")
   subparser.set_defaults(func=KmsCertificate)

   subparser = subparsers.add_parser("mark-default",
                                     help="Make a cluster default")
   subparser.add_argument("providerId", metavar="provider-id",
                          help="Server cluster name")
   subparser.set_defaults(func=KmsMarkDefault)

def HostGetHostSystems(si, datacenterName=None, hostName=None):
   hostSystems = []
   content = si.RetrieveContent()

   for datacenter in content.GetRootFolder().GetChildEntity():
      if not datacenterName or datacenter.name == datacenterName:
         hostFolder = datacenter.GetHostFolder()
         for computeResource in hostFolder.GetChildEntity():
            for hostSystem in computeResource.GetHost():
               if not hostName or hostSystem.name == hostName:
                  hostSystems.append(hostSystem)
   return hostSystems

def HostInfoCpuSupport(hs):
   aesni = False
   clmul = False
   found = False
   for cpu in hs.hardware.cpuPkg:
      for level in cpu.cpuFeature:
         assert len(level.ecx) == 39
         # There are two features that we're interested in: AES-NI for
         # data-at-rest encryption, and PCLMULQDQ for improved
         # performance of AES-GCM, used by vMotion. Both features are
         # identified in leaf 1, ecx:
         #
         #   '----:--1-:----:----:----:----:----:--1-'
         #           ^                             ^
         #         AES-NI                      PCLMULQDQ
         #
         # All ESX supported CPUs will have the above instructions in
         # the 2017 release (post 6.5). However, AES-NI can be disabled
         # in the BIOS.
         #
         if level.level == 1:
            if not found:
               aesni = level.ecx[7] == "1"
               clmul = level.ecx[37] == "1"
            else:
               if (level.ecx[7] == "1" and not aesni or
                   level.ecx[37] == "1" and not clmul):
                  Warn("CPU packages with mismatched feature sets.")
            found = True
            break
   return aesni, clmul

def HostInfo(si, args):
   """Log host crypto state information."""
   hostSystems = HostGetHostSystems(si, args.datacenter, args.host)
   Log("---")
   Log("host:")
   for hs in hostSystems:
      aesni, clmul = HostInfoCpuSupport(hs)
      Log(" - name: %s" % hs.name)
      Log("   cryptoState: %s" % hs.runtime.cryptoState)
      if hs.runtime.cryptoKeyId:
         Log("   cryptoKeyId:")
         LogCryptoKeyId(hs.runtime.cryptoKeyId, tabs=2)
      if args.verbose:
         Log("   aesni: %s" % aesni)
         Log("   clmul: %s" % clmul)
   Log("...")

def HostEnable(si, args):
   """Enable a host for crypto operations.

   An ESXi host must be explicitly put in a "safe" crypto state before
   any key material is pushed.
   """
   cryptoKey = None
   cryptoKeyId = None

   if args.keyId:
      if IsVirtualCenter(si) and args.providerId:
         raise Exception("Provider ID cannot be specified with key ID.")
      if not args.data:
         Warn("Generating random key data ...")
      cryptoKey = CreateCryptoKeyPlain(args.keyId, args.providerId,
                                       args.algorithm, args.data)
      Log("# Using plain host key with key ID '%s' : %s" %
          (args.keyId, cryptoKey.keyData))
   elif args.data:
      raise ValueError("Key identifier is required.")
   elif args.providerId:
      VerifyVirtualCenterConnection(si)
      cryptoMgr = GetCryptoManager(si)
      result = cryptoMgr.GenerateKey(CreateProviderId(args.providerId))
      if not result.success:
         raise Exception("Failed to generate key: %s" %  result.reason)
      cryptoKeyId = result.keyId
      Log("# Using host key provider '%s' with key ID '%s'" %
          (cryptoKeyId.providerId.id, cryptoKeyId.keyId))
   elif not IsVirtualCenter(si):
      testingKeyId = "VMwareInternalHostKeyForTesting"
      testingAlgo  = "AES-256"
      testingKey   = "mxeZ/HG3itSGTRP3fEPxFLD0r/3HckVlHZAaplRoSxo="
      cryptoKey = CreateCryptoKeyPlain(testingKeyId, None, testingAlgo,
                                       testingKey)
      Log("# Using default host key with key ID '%s' : %s" %
          (testingKeyId, testingKey))

   hostSystems = HostGetHostSystems(si, args.datacenter, args.host)
   for hs in hostSystems:
      if len(hostSystems) > 1:
         if hs.runtime.cryptoState == "safe":
            Log("# Rekeying host-key for %s ..." % hs.name)
         else:
            Log("# Setting host-key for %s ..." % hs.name)
      if cryptoKey:
         if hs.runtime.cryptoState != "prepared":
            hs.PrepareCrypto()
         hs.EnableCrypto(cryptoKey)
      else:
         if hs.runtime.cryptoState == "safe" and not cryptoKeyId:
            errStr = "Key provider must be specified for rekey: %s" % hs.name
            if len(hostSystems) > 1:
               Warn(errStr)
            else:
               raise Exception(errStr)
         hs.ConfigureCryptoKey(cryptoKeyId)

def HostPrepare(si, args):
   """Prepare a host for crypto operations.

   Enabling an ESXi host for crypto requires an intermediate step where
   core dumps are first disabled. This operation puts the host in this
   intermediate, "prepared" state. This is mostly useful for testing.
   """
   hostSystems = HostGetHostSystems(si, args.datacenter, args.host)
   for hs in hostSystems:
      if hs.runtime.cryptoState == "incapable":
         hs.PrepareCrypto()

def HostParser(parser):
   subparsers = parser.add_subparsers(title="commands", dest="cmd")
   subparsers.required = True

   subparser = subparsers.add_parser("info", help="Get host crypto information")
   subparser.add_argument("--datacenter", help="The datacenter to inspect")
   subparser.add_argument("host", nargs="?", default=None,
                          help="The hostname/IP-address")
   subparser.set_defaults(func=HostInfo)

   subparser = subparsers.add_parser("enable", help="Enable crypto safe state")
   subparser.add_argument("--datacenter", help="The datacenter")
   subparser.add_argument("-p", "--provider-id", dest="providerId",
                          help="Provider/cluster identifier")
   subparser.add_argument("-k", "--key-id", dest="keyId", help="Key identifier")
   subparser.add_argument("-a", "--algorithm", default="AES-256",
                          help="Key algorithm (default: %(default)s)")
   subparser.add_argument("-d", "--data",
                          help="Base64 encoded key data (default: generated)")
   subparser.add_argument("host", nargs="?", default=None,
                          help="The hostname/IP-address")
   subparser.set_defaults(func=HostEnable)

   subparser = subparsers.add_parser("prepare", help="Prepare host for crypto")
   subparser.add_argument("--datacenter", help="The datacenter to inspect")
   subparser.add_argument("host", nargs="?", default=None,
                          help="The hostname/IP-address")
   subparser.set_defaults(func=HostPrepare)

def PolicyGetPbmServiceInstance(vpxdStub, server):
   """Get the PBM service instance.

   Policy based management, PBM, is handled by a separate service in VC,
   and we need to explicitly connect to that service. This function
   uses our existing VC session to authenticate with the PBM service.
   """
   import Cookie

   sessionCookie = vpxdStub.cookie.split('"')[1]
   cookie = Cookie.SimpleCookie()
   cookie["vmware_soap_session"] = sessionCookie
   httpContext = VmomiSupport.GetHttpContext()
   httpContext["cookies"] = cookie
   VmomiSupport.GetRequestContext()["vcSessionCookie"] = sessionCookie

   pbmVersion = VmomiSupport.newestVersions.GetName('pbm')
   pbmStub = SoapStubAdapter(host=server,
                             version=pbmVersion,
                             path="/pbm/sdk",
                             poolSize=0)
   Log("# Connected to PBM (version=%s)" % pbmVersion)
   return Pbm.ServiceInstance("ServiceInstance", pbmStub)

def PolicyGetPbmServiceContent(si, args):
   VerifyVirtualCenterConnection(si)
   Log("# Connecting to PBM ...")
   vpxdStub = si._GetStub()
   pbmSi = PolicyGetPbmServiceInstance(vpxdStub, args.server)
   return pbmSi.RetrieveContent()

def PolicyGetProfileManager(si, args):
   pbmServiceContent = PolicyGetPbmServiceContent(si, args)
   return pbmServiceContent.profileManager

def PolicyGetStorageProfiles(profileMgr):
   storageType = Pbm.profile.ResourceType()
   storageType.SetResourceType("STORAGE")
   # REQUIREMENT profiles can be assigned to VMs and disks.
   profileIds = profileMgr.QueryProfile(storageType, "REQUIREMENT")
   return profileMgr.RetrieveContent(profileIds)

def PolicyGetStorageDataServices(profileMgr, profileIds=None):
   if not profileIds:
      storageType = Pbm.profile.ResourceType()
      storageType.SetResourceType("STORAGE")
      # DATA_SERVICE_POLICY profiles CANNOT be assigned to VMs or disks.
      profileIds = profileMgr.QueryProfile(storageType, "DATA_SERVICE_POLICY")
   return profileMgr.RetrieveContent(profileIds)

def PolicyIsDataServiceCapability(capability):
   namespace = capability.id.namespace
   return namespace == "com.vmware.storageprofile.dataservice"

def PolicyGetDataServiceProfile(profileMgr, capability):
   if PolicyIsDataServiceCapability(capability):
      for constraint in capability.constraint:
         assert len(constraint.propertyInstance) == 1
         profileId = Pbm.Profile.ProfileId()
         profileId.uniqueId = constraint.propertyInstance[0].id
         profiles = PolicyGetStorageDataServices(profileMgr, [profileId])
         if profiles:
            assert len(profiles) == 1
            return profiles[0]
   return None

def PolicyIsEncryptionProfile(profileMgr, profile, schemas=None):
   assert isinstance(profile, Pbm.Profile.CapabilityBasedProfile)
   if isinstance(profile.constraints,
                 Pbm.Profile.SubProfileCapabilityConstraints):
      if not schemas:
         schemas = profileMgr.FetchCapabilitySchema(None, ["ENCRYPTION"]);
         for schema in list(schemas):
            if not isinstance(schema.lineOfService,
                              Pbm.Capability.Provider.VaioDataServiceInfo):
               Warn("Unexpected encryption line-of-service: %s",
                    schema.lineOfService.label)
               schemas.remove(schema)

      for subProfile in profile.constraints.subProfiles:
         for capability in subProfile.capability:
            dsProfile = PolicyGetDataServiceProfile(profileMgr, capability)
            if dsProfile and PolicyIsEncryptionProfile(profileMgr, dsProfile,
                                                       schemas):
               return True
            for schema in schemas:
               if capability.id.namespace == schema.namespaceInfo.namespace:
                  return True
   return False

def PolicyGetEncryptionStorageProfiles(profileMgr):
   profiles = PolicyGetStorageProfiles(profileMgr)
   for profile in list(profiles):
      if not isinstance(profile, Pbm.Profile.CapabilityBasedProfile):
         Warn("Profile has unknown type: %s" % profile.name)
         profiles.remove(profile)
      elif not PolicyIsEncryptionProfile(profileMgr, profile):
         profiles.remove(profile)
   return profiles

def PolicyListConstraints(profileMgr, profile):
   if not isinstance(profile.constraints,
                     Pbm.Profile.SubProfileCapabilityConstraints):
      return
   for subProfile in profile.constraints.subProfiles:
      for capability in subProfile.capability:
         if PolicyIsDataServiceCapability(capability):
            dsProfile = PolicyGetDataServiceProfile(profileMgr, capability)
            if dsProfile:
               PolicyListConstraints(profileMgr, dsProfile)
         else:
            Log("    - namespace: %s" % capability.id.namespace)
            for constraint in capability.constraint:
               Log("      properties:")
               for propertyInstance in constraint.propertyInstance:
                  Log("       - id: %s" % propertyInstance.id)
                  Log("         value: %s" % propertyInstance.value)

def PolicyList(si, args):
   """List the storage profiles

   By default lists only the encryption storage profiles, but can
   optionally list all storage profiles.
   """
   profileMgr = PolicyGetProfileManager(si, args)
   profiles = PolicyGetStorageProfiles(profileMgr)

   Log("---")
   Log("profiles:")
   for profile in profiles:
      if not isinstance(profile, Pbm.Profile.CapabilityBasedProfile):
         Warn("Profile has unknown type: %s" % profile.name)
         continue
      if args.all or PolicyIsEncryptionProfile(profileMgr, profile):
         Log(" - name: %s" % profile.name)
         if profile.description:
            Log("   description: %s" % profile.description)
         Log("   profileId: %s" % profile.profileId.uniqueId)
         Log("   generationId: %s" % profile.generationId)
         if isinstance(profile.constraints,
                       Pbm.Profile.SubProfileCapabilityConstraints):
            Log("   constraints:")
            PolicyListConstraints(profileMgr, profile)
   Log("...")

def PolicyGetFilterMetadata(profileMgr):
   resType = Pbm.Profile.ResourceType()
   resType.SetResourceType(Pbm.Profile.ResourceTypeEnum.STORAGE)
   return profileMgr.FetchCapabilityMetadata(resType, "com.vmware.iofilters")

def PolicyGetEncryptionFilterMetadata(profileMgr, filterName):
   for metadata in PolicyGetFilterMetadata(profileMgr):
      if metadata.subCategory == "ENCRYPTION":
         for capabilityMetadata in metadata.capabilityMetadata:
            if capabilityMetadata.id.namespace == filterName:
               return metadata
   return None

def PolicyGetDefaultCapability(metadata):
   uniqueId = None
   constraints = []
   for capabilityMetadata in metadata.capabilityMetadata:
      if not uniqueId:
         uniqueId = capabilityMetadata.id
      else:
         assert(capabilityMetadata.id.namespace == uniqueId.namespace and
                capabilityMetadata.id.id == uniqueId.id)
      properties = []
      for propertyMetadata in capabilityMetadata.propertyMetadata:
         propertyInstance = Pbm.Capability.PropertyInstance()
         propertyInstance.id = propertyMetadata.id
         propertyInstance.value = propertyMetadata.defaultValue
         properties.append(propertyInstance)
      constraint = Pbm.Capability.ConstraintInstance()
      constraint.propertyInstance = properties
      constraints.append(constraint)

   if not uniqueId:
      raise Exception("Invalid encryption metadata.")
   capability = Pbm.Capability.CapabilityInstance()
   capability.id = uniqueId
   capability.constraint = constraints
   return capability

def PolicyAddEncryptionProfile(profileMgr, name,
                               iofilter="vmwarevmcrypt",
                               description=None):
   """Create a new encryption storage profile

   The PBM API is complicated, but we're only taking the needed bits
   in order to create a simple storage profile. We use defaults as much
   as possible.
   """
   metadata = PolicyGetEncryptionFilterMetadata(profileMgr, iofilter)
   if not metadata:
      raise Exception("Failed to locate encryption filter: %s" % iofilter)

   spec = Pbm.Profile.CapabilityBasedProfileCreateSpec()
   spec.name = name
   spec.description = description

   resourceType = Pbm.profile.ResourceType()
   resourceType.SetResourceType("STORAGE")
   spec.resourceType = resourceType

   capability = PolicyGetDefaultCapability(metadata)
   subProfile = Pbm.Profile.SubProfileCapabilityConstraints.SubProfile()
   subProfile.name = "Rule-Set 1"
   subProfile.capability = [capability]
   constraints = Pbm.Profile.SubProfileCapabilityConstraints()
   constraints.subProfiles = [subProfile]
   spec.constraints = constraints

   return profileMgr.Create(spec)

def PolicyAdd(si, args):
   """Add a new profile."""
   profileMgr = PolicyGetProfileManager(si, args)
   PolicyAddEncryptionProfile(profileMgr, args.name,
                              args.filter,
                              args.description)

def PolicyRemove(si, args):
   """Remove the specified storage profile.

   Annoyingly, PBM reports success when a profile is removed while in
   use. List the profiles to confirm that it's gone.
   """
   profileMgr = PolicyGetProfileManager(si, args)
   profiles = PolicyGetStorageProfiles(profileMgr)

   for profile in profiles:
      if profile.name == args.name:
         if not PolicyIsEncryptionProfile(profileMgr, profile):
            raise Exception("Not an encryption storage profile: %s" %
                            profile.name)
         outcome = profileMgr.Delete([profile.profileId])
         if outcome and outcome[0].fault:
            # Explicitly log here, because PBM faults stink.
            Error("Failed to remove storage policy. In use?")
            raise outcome[0].fault
         return
   raise Exception("Failed to locate storage profile: %s" % args.name)

def PolicyParser(parser):
   subparsers = parser.add_subparsers(title="commands", dest="cmd")
   subparsers.required = True

   subparser = subparsers.add_parser("list", help="List encryption profiles")
   subparser.add_argument("-a", "--all", action="store_true",
                          help="List all storage profiles")
   subparser.set_defaults(func=PolicyList)

   subparser = subparsers.add_parser("add", help="Create encryption profile")
   subparser.add_argument("-d", "--description", help="Profile description")
   subparser.add_argument("-f", "--filter", default="vmwarevmcrypt",
                          help="Encryption VAIO filter (default: %(default)s)")
   subparser.add_argument("name", help="Profile name")
   subparser.set_defaults(func=PolicyAdd)

   subparser = subparsers.add_parser("remove", help="Remove encryption profile")
   subparser.add_argument("name", help="Profile name")
   subparser.set_defaults(func=PolicyRemove)

def VmGetVmFolder(si, folder, name=None):
   vms = []
   for entity in folder.GetChildEntity():
      if isinstance(entity, Vim.VirtualMachine):
         if not name or entity.name == name:
            vms.append(entity)
      elif isinstance(entity, Vim.Folder):
         vms.extend(VmGetVmFolder(si, entity, name))
      else:
         raise Exception("Unknown managed entity: %s" % entity.name)
   return vms

def VmGetVms(si, name=None, datacenterName=None):
   vms = []
   content = si.RetrieveContent()
   for datacenter in content.GetRootFolder().GetChildEntity():
      if not datacenterName or datacenter.name == datacenterName:
         vms.extend(VmGetVmFolder(si, datacenter.GetVmFolder(), name))
   return vms

def VmGetVm(si, name, datacenterName=None):
   assert name
   vms = VmGetVms(si, name, datacenterName)
   if len(vms) > 1:
      raise Exception("More than one virtual machine named '%s'." % name)
   if len(vms) == 0:
      raise Exception("Virtual machine not found: %s" % name)
   if not vms[0].config:
      raise Exception("Invalid virtual machine configuration: %s" % name)
   return vms[0]

def VmDiskGetAssociatedProfiles(profileMgr, vm, disk):
   vmRef = Pbm.ServerObjectRef()
   vmRef.objectType = Pbm.ServerObjectRef.ObjectType.virtualDiskId
   vmRef.key = "%s:%s" % (vm._moId, disk.key)
   profileIds = profileMgr.QueryAssociatedProfile(vmRef)
   if not profileIds:
      return None
   return profileMgr.RetrieveContent(profileIds)

def VmLogDisk(vm, disk, profileMgr=None, tabs=0, sequence=False):
   spaces = tabs * 3   # 3 spaces per tab
   leader = " " * spaces
   if sequence:
      Log("%sindex: %s # Use to reference the disk" %
          ((" " * (3 * (tabs - 1))) + " - ", disk.key))
   else:
      Log("%sindex: %s # Use to reference the disk" % (leader, disk.key))
   Log("%slabel: %s" % (leader, disk.deviceInfo.label))
   Log("%ssummary: %s" % (leader, disk.deviceInfo.summary))
   if profileMgr:
      profiles = VmDiskGetAssociatedProfiles(profileMgr, vm, disk)
      if profiles:
         Log("      profile:")
         for profile in profiles:
            Log("       - name: %s" % profile.name)
   if isinstance(disk.backing,
                 Vim.Vm.Device.VirtualDevice.FileBackingInfo):
      Log("%sbacking:" % leader)
      Log("%s   fileName: %s" % (leader, disk.backing.fileName))
      Log("%s   uuid: %s" % (leader, disk.backing.uuid))
   if (isinstance(disk.backing,
                  Vim.Vm.Device.VirtualDisk.FlatVer2BackingInfo) or
       isinstance(disk.backing,
                  Vim.Vm.Device.VirtualDisk.SeSparseBackingInfo) or
       isinstance(disk.backing,
                  Vim.Vm.Device.VirtualDisk.SparseVer2BackingInfo)):
         if disk.backing.keyId:
            Log("%s   keyId:" % leader)
            LogCryptoKeyId(disk.backing.keyId, tabs=tabs + 2)
   if disk.vDiskId:
      Log("%svDiskId: %s" % (leader, disk.vDiskId.id))
   if disk.iofilter:
      Log("%siofilter:" % leader)
      for filter in disk.iofilter:
         Log("%s - id: %s" % (leader, filter))

def VmGetAssociatedProfiles(profileMgr, vm):
   vmRef = Pbm.ServerObjectRef()
   vmRef.objectType = Pbm.ServerObjectRef.ObjectType.virtualMachine
   vmRef.key = vm._moId
   profileIds = profileMgr.QueryAssociatedProfile(vmRef)
   if not profileIds:
      return None
   return profileMgr.RetrieveContent(profileIds)

def VmLogVm(si, vm, profileMgr=None, disks=False):
   # XXX A heuristic for determining locked state. PR 1685346
   locked = (vm.runtime.connectionState == "invalid" and
             vm.config and vm.config.keyId)
   Log(" - name: %s" % vm.name)
   Log("   connectionState: %s" % vm.runtime.connectionState)
   Log("   locked: %s" % ("yes # Suspected" if locked else "no"))
   if profileMgr:
      profiles = VmGetAssociatedProfiles(profileMgr, vm)
      if profiles:
         Log("   profile:")
         for profile in profiles:
            Log("    - name: %s" % profile.name)
   if vm.config and vm.config.keyId:
      Log("   keyId:")
      LogCryptoKeyId(vm.config.keyId, 2)
   if disks and vm.config:
      Log("   disks:")
      for device in vm.config.hardware.device:
         if isinstance(device, Vim.Vm.Device.VirtualDisk):
            VmLogDisk(vm, device, profileMgr, tabs=2, sequence=True)

def VmList(si, args):
   """List encrypted virtual machines."""
   if IsVirtualCenter(si):
      profileMgr = PolicyGetProfileManager(si, args)
   else:
      profileMgr = None
   vms = VmGetVms(si, args.datacenter)
   Log("---")
   Log("vm:")
   for vm in vms:
      if args.all or (vm.config and vm.config.keyId):
         VmLogVm(si, vm, profileMgr)
   Log("...")

def VmInfo(si, args):
   """Log virtual machine details."""
   if IsVirtualCenter(si):
      profileMgr = PolicyGetProfileManager(si, args)
   else:
      profileMgr = None
   vms = VmGetVms(si, args.datacenter)
   Log("---")
   Log("vm:")
   for vm in vms:
      if vm.name == args.name:
         VmLogVm(si, vm, profileMgr, disks=True)
   Log("...")

def VmGetDefaultProfileSpecVC(si, args, encryption, profileMgr):
   """Get a default encryption storage profile on VC.

   When a storage profile is not specified we either use the first
   encryption profile that we can find, or create a new default
   encryption profile.
   """
   assert IsVirtualCenter(si)

   if encryption:
      profiles = PolicyGetEncryptionStorageProfiles(profileMgr)
      if len(profiles) == 0:
         name = "Default Encryption Profile"
         Warn("Creating default encryption storage profile: %s" % name)
         profileId = PolicyAddEncryptionProfile(profileMgr, name)
      else:
         Log("# Using default encryption storage profile: %s" %
             profiles[0].name)
         profileId = profiles[0].profileId
      profileSpec = Vim.Vm.DefinedProfileSpec()
      profileSpec.profileId = profileId.uniqueId
      return profileSpec
   else:
      Log("# Using virtual machine default storage profile.")
      return Vim.VirtualMachineDefaultProfileSpec()

def VmGetDefaultProfileSpecESX(si, encryption):
   """Get a default encryption storage profile on ESX.

   ESX doesn't support storage profiles natively, but we can pass it a
   phony profile in the expected format, and it will do the right thing.
   """
   assert not IsVirtualCenter(si)
   header   = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
               "<storageProfile xsi:type=\"StorageProfile\">"
               "<constraints><subProfiles>")
   footer   = ("<name>What's in a name?</name>"
               "</subProfiles></constraints>"
               "<createdBy>None</createdBy>"
               "<creationTime>1970-01-01T00:00:00Z</creationTime>"
               "<lastUpdatedTime>1970-01-01T00:00:00Z</lastUpdatedTime>"
               "<generationId>1</generationId>"
               "<name>None</name>"
               "<profileId>Phony Profile ID</profileId>"
               "</storageProfile>")
   iofilter = ("<capability><capabilityId>"
               "<id>vmwarevmcrypt@ENCRYPTION</id>"
               "<namespace>IOFILTERS</namespace>"
               "<constraint></constraint>"
               "</capabilityId></capability>")
   if encryption:
      policy = header + iofilter + footer
   else:
      policy = header + footer
   profileSpec = Vim.Vm.DefinedProfileSpec()
   profileSpec.SetProfileId('')  # There is no ID
   rawData = Vim.Vm.ProfileRawData()
   rawData.SetExtensionKey("com.vmware.vim.sps")
   rawData.SetObjectData(policy)
   profileSpec.SetProfileData(rawData)
   return profileSpec

def VmGetDefaultProfileSpec(si, args, encryption, profileMgr=None):
   if IsVirtualCenter(si):
      return VmGetDefaultProfileSpecVC(si, args, encryption, profileMgr)
   else:
      return VmGetDefaultProfileSpecESX(si, encryption)

def VmCreateProfileSpec(si, args, encryption=True, profileMgr=None):
   """Create a ProfileSpec for Reconfigure.

   This function handles the details of ProfileSpec creation based on
   the user provided arguments. There are several cases we're covering
   that make this look a little ugly.
   """
   profileSpec = None
   if IsVirtualCenter(si):
      if not profileMgr:
         profileMgr = PolicyGetProfileManager(si, args)
      if args.profileName:
         profiles = PolicyGetStorageProfiles(profileMgr)
         for profile in profiles:
            if profile.name == args.profileName:
               if not PolicyIsEncryptionProfile(profileMgr, profile):
                  raise ValueError("Profile does not specify encryption: %s" %
                                   args.profileName)
               profileSpec = Vim.Vm.DefinedProfileSpec()
               profileSpec.profileId = profile.profileId.uniqueId
         if not profileSpec:
            raise ValueError("Profile was not found: %s" % args.profileName)
      else:
         profileSpec = VmGetDefaultProfileSpec(si, args, encryption,
                                               profileMgr)
   else:
      if args.profileName:
         raise Exception("ESXi host cannot apply profile.")
      profileSpec = VmGetDefaultProfileSpec(si, args, encryption)
   return profileSpec

def VmCreateCryptoKeyId(si, keyId, providerId):
   """Create a CryptoKeyId for Reconfigure.

   This function handles the details of CryptoKeyId creation based on
   the user provided arguments. There are several cases we're covering
   that make this look a little ugly.
   """
   if providerId and not keyId:
      # When only the provider is specified, we try to generate a key on
      # that key server.
      if not IsVirtualCenter(si):
         raise ValueError("Key identifier required")
      cryptoMgr = GetCryptoManager(si)
      result = cryptoMgr.GenerateKey(CreateProviderId(providerId))
      if result.success:
         cryptoKeyId = result.keyId
      else:
         raise Exception("Failed to generate key: %s" %  result.reason)
   elif keyId:
      cryptoKeyId = CreateCryptoKeyId(keyId, providerId)
   else:
      if not IsVirtualCenter(si):
         raise ValueError("Key identifier required")
      # When nothing is specified, we try to generate a key on the
      # default key server. If that fails, allow VC to report the
      # appropriate error; return None.
      cryptoMgr = GetCryptoManager(si)
      result = cryptoMgr.GenerateKey()
      if result.success:
         cryptoKeyId = result.keyId
      else:
         cryptoKeyId = None
   return cryptoKeyId

def VmDiskGetVirtualDeviceSpec(devices, profileSpec=None, cryptoSpec=None):
   deviceChange = []
   for device in devices:
      if isinstance(device, Vim.Vm.Device.VirtualDisk):
         if not (isinstance(device.backing,
                            Vim.Vm.Device.VirtualDisk.FlatVer2BackingInfo) or
                 isinstance(device.backing,
                            Vim.Vm.Device.VirtualDisk.SeSparseBackingInfo) or
                 isinstance(device.backing,
                            Vim.Vm.Device.VirtualDisk.SparseVer2BackingInfo)):
            Warn("Virtual disk '%d' cannot be encrypted." % device.key)
            continue
         if isinstance(cryptoSpec, Vim.Encryption.CryptoSpecDecrypt):
            if not device.backing.keyId:
               continue
         devSpec = Vim.Vm.Device.VirtualDeviceSpec()
         devSpec.device = device
         devSpec.operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
         if profileSpec:
            devSpec.profile = [profileSpec]
         if cryptoSpec:
            backingSpec = Vim.Vm.Device.VirtualDeviceSpec.BackingSpec()
            backingSpec.crypto = cryptoSpec
            devSpec.backing = backingSpec
         deviceChange.append(devSpec)
   return deviceChange

def VmEncrypt(si, args):
   """Encrypt a virtual machine."""
   profileSpec = VmCreateProfileSpec(si, args, encryption=True)
   keyId = VmCreateCryptoKeyId(si, args.keyId, args.providerId)
   if keyId:
      cryptoSpec = CreateCryptoSpecEncrypt(keyId)
   else:
      cryptoSpec = None
   vm = VmGetVm(si, args.name)
   if not vm:
      raise Exception("Virtual machine not found: %s" % args.name)

   spec = Vim.Vm.ConfigSpec()
   spec.crypto = cryptoSpec
   spec.vmProfile = [profileSpec]
   if not args.skipDisks:
      spec.deviceChange = VmDiskGetVirtualDeviceSpec(vm.config.hardware.device,
                                                     profileSpec, cryptoSpec)
   if args.verbose:
      Log("%s" % spec)
   task = vm.Reconfigure(spec)
   WaitForTask(task)

def VmUnlock(si, args):
   """Unlock a virtual machine."""
   VerifyVirtualCenterConnection(si)
   vm = VmGetVm(si, args.name)
   if not vm:
      raise Exception("Virtual machine not found: %s" % args.name)
   task = vm.CryptoUnlock()
   WaitForTask(task)

def VmDecrypt(si, args):
   """Decrypt a virtual machine."""
   profileSpec = VmCreateProfileSpec(si, args, encryption=False)
   cryptoSpec = CreateCryptoSpecDecrypt()
   vm = VmGetVm(si, args.name)
   if not vm:
      raise Exception("Virtual machine not found: %s" % args.name)

   spec = Vim.Vm.ConfigSpec()
   spec.crypto = cryptoSpec
   spec.vmProfile = [profileSpec]
   spec.deviceChange = VmDiskGetVirtualDeviceSpec(vm.config.hardware.device,
                                                  profileSpec, cryptoSpec)
   if args.verbose:
      Log("%s" % spec)
   task = vm.Reconfigure(spec)
   WaitForTask(task)

def VmRecrypt(si, args):
   """Recrypt one or more virtual machines."""
   if (not args.name and not args.all) or (args.name and args.all):
      raise Exception("Virtual machine name required or, --all.")

   vms = VmGetVms(si, args.name, args.datacenter)
   if args.name and len(vms) != 1:
      if len(vms) > 1:
         raise Exception("More than one virtual machine named '%s'." %
                         args.name)
      if len(vms) == 0:
         raise Exception("Virtual machine not found: %s" % args.name)
      if not vm.config.keyId:
         raise Exception("Virtual machine not encrypted: %s" % args.name)
   if len(vms) == 0:
      raise Exception("No virtual machines found.")

   if IsVirtualCenter(si):
      profileMgr = PolicyGetProfileManager(si, args)
   else:
      profileMgr = None

   failed = False

   for vm in vms:
      try:
         profileSpec = None
         if profileMgr:
            profiles = VmGetAssociatedProfiles(profileMgr, vm)
            if profiles:
               if len(profiles) != 1:
                  Warn("Invalid storage profile for %s." % vm.name)
               profileSpec = Vim.Vm.DefinedProfileSpec()
               profileSpec.profileId = profiles[0].profileId.uniqueId
         if not profileSpec:
            profileSpec = VmCreateProfileSpec(si, args, profileMgr=profileMgr)

         keyId = VmCreateCryptoKeyId(si, args.keyId, args.providerId)
         if keyId:
            if args.deep:
               cryptoSpec = CreateCryptoSpecRecryptDeep(keyId)
            else:
               cryptoSpec = CreateCryptoSpecRecryptShallow(keyId)

         spec = Vim.Vm.ConfigSpec()
         spec.crypto = cryptoSpec
         spec.vmProfile = [profileSpec]
         if not args.skipDisks:
            deviceChange = VmDiskGetVirtualDeviceSpec(vm.config.hardware.device,
                                                      profileSpec, cryptoSpec)
            spec.deviceChange = deviceChange
         if not args.name:
            Log("# Rekeying %s with key ID %s ..." % (vm.name, keyId.keyId))
         task = vm.Reconfigure(spec)
         WaitForTask(task)
      except Vmodl.MethodFault as e:
         if args.name:
            assert len(vms) == 1
            raise
         Error("Failed to rekey %s: %s" % (vm.name, e.msg))
         failed = True

   if failed:
      raise Exception("Operation failed.")

def VmDiskFindByIndex(vm, index):
   disk = None
   for device in vm.config.hardware.device:
      if device.key == args.index:
         disk = device
         break
   if not disk:
      raise Exception("Virtual device not found: %s" % args.index)
   if not isinstance(disk, Vim.Vm.Device.VirtualDisk):
      raise Exception("Virtual device is not a disk: %s" % args.index)
   return disk

def VmDiskEncrypt(si, args):
   """Encrypt a virtual disk."""
   profileSpec = VmCreateProfileSpec(si, args, encryption=True)
   keyId = VmCreateCryptoKeyId(si, args.keyId, args.providerId)
   if keyId:
      cryptoSpec = CreateCryptoSpecEncrypt(keyId)
   else:
      cryptoSpec = None
   vm = VmGetVm(si, args.name)
   disk = VmDiskFindByIndex(vm, args.index)

   spec = Vim.Vm.ConfigSpec()
   spec.deviceChange = VmDiskGetVirtualDeviceSpec([disk], profileSpec,
                                                  cryptoSpec)
   if args.verbose:
      Log("%s" % spec)
   task = vm.Reconfigure(spec)
   WaitForTask(task)

def VmDiskDecrypt(si, args):
   """Decrypt a virtual disk."""
   profileSpec = VmCreateProfileSpec(si, args, encryption=False)
   cryptoSpec = CreateCryptoSpecDecrypt()
   vm = VmGetVm(si, args.name)
   disk = VmDiskFindByIndex(vm, args.index)

   spec = Vim.Vm.ConfigSpec()
   spec.deviceChange = VmDiskGetVirtualDeviceSpec([disk], profileSpec,
                                                  cryptoSpec)
   if args.verbose:
      Log("%s" % spec)
   task = vm.Reconfigure(spec)
   WaitForTask(task)

def VmDiskRecrypt(si, args):
   """Recrypt a virtual disk.

   XXX We should try to keep the existing profile if one is not
   provided on the commandline.
   """
   profileSpec = VmCreateProfileSpec(si, args, encryption=True)
   keyId = VmCreateCryptoKeyId(si, args.keyId, args.providerId)
   if not keyId:
      raise ValueError("Key identifier required")
   if args.deep:
      cryptoSpec = CreateCryptoSpecRecryptDeep(keyId)
   else:
      cryptoSpec = CreateCryptoSpecRecryptShallow(keyId)
   vm = VmGetVm(si, args.name)
   disk = VmDiskFindByIndex(vm, args.index)

   spec = Vim.Vm.ConfigSpec()
   spec.deviceChange = VmDiskGetVirtualDeviceSpec([disk], profileSpec,
                                                  cryptoSpec)
   if args.verbose:
      Log("%s" % spec)
   task = vm.Reconfigure(spec)
   WaitForTask(task)

def VmDiskParser(parser):
   subparsers = parser.add_subparsers(title="commands", dest="cmd")
   subparsers.required = True

   subparser = subparsers.add_parser("encrypt",
                                     help="Encrypt a virtual disk")
   subparser.add_argument("-p", "--profile-name", dest="profileName",
                          help="Profile name")
   subparser.add_argument("--provider-id", dest="providerId",
                          help="Provider/cluster identifier")
   subparser.add_argument("-k", "--key-id", dest="keyId", help="Key identifier")
   subparser.add_argument("name", help="Virtual machine name")
   subparser.add_argument("index", type=int, help="Device index")
   subparser.set_defaults(func=VmDiskEncrypt)

   subparser = subparsers.add_parser("decrypt",
                                     help="Decrypt a virtual disk")
   subparser.add_argument("-p", "--profile-name", dest="profileName",
                          help="Profile name")
   subparser.add_argument("name", help="Virtual machine name")
   subparser.add_argument("index", type=int, help="Device index")
   subparser.set_defaults(func=VmDiskDecrypt)

   subparser = subparsers.add_parser("recrypt",
                                     help="Recrypt a virtual disk")
   subparser.add_argument("-p", "--profile-name", dest="profileName",
                          help="Profile name")
   subparser.add_argument("--provider-id", dest="providerId",
                          help="Provider/cluster identifier")
   subparser.add_argument("-k", "--key-id", dest="keyId", help="Key identifier")
   subparser.add_argument("--deep", action="store_true",
                          help="Deep re-encryption (slow)")
   subparser.add_argument("name", help="Virtual machine name")
   subparser.add_argument("index", type=int, help="Device index")
   subparser.set_defaults(func=VmDiskRecrypt)

def VmParser(parser):
   subparsers = parser.add_subparsers(title="commands", dest="cmd")
   subparsers.required = True

   subparser = subparsers.add_parser("list",
                                     help="List encrypted virtual machines")
   subparser.add_argument("--datacenter", help="The datacenter to inspect")
   subparser.add_argument("-a", "--all", action="store_true",
                          help="List all virtual machines")
   subparser.set_defaults(func=VmList)

   subparser = subparsers.add_parser("info",
                                     help="Virtual maching information")
   subparser.add_argument("--datacenter", help="The datacenter to inspect")
   subparser.add_argument("name", help="Virtual machine name")
   subparser.set_defaults(func=VmInfo)

   subparser = subparsers.add_parser("encrypt",
                                     help="Encrypt a virtual machine")
   subparser.add_argument("-p", "--profile-name", dest="profileName",
                          help="Profile name")
   subparser.add_argument("--provider-id", dest="providerId",
                          help="Provider/cluster identifier")
   subparser.add_argument("-k", "--key-id", dest="keyId", help="Key identifier")
   subparser.add_argument("--skip-disks", action="store_true",
                          dest="skipDisks",
                          help="Do not encrypt virtual disks")
   subparser.add_argument("name", help="Virtual machine name")
   subparser.set_defaults(func=VmEncrypt)

   subparser = subparsers.add_parser("decrypt",
                                     help="Decrypt a virtual machine")
   subparser.add_argument("-p", "--profile-name", dest="profileName",
                          help="Profile name")
   subparser.add_argument("name", help="Virtual machine name")
   subparser.set_defaults(func=VmDecrypt)

   subparser = subparsers.add_parser("unlock",
                                     help="Unlock a virtual machine")
   subparser.add_argument("name", help="Virtual machine name")
   subparser.set_defaults(func=VmUnlock)

   subparser = subparsers.add_parser("recrypt",
                                     help="Recrypt a virtual machine")
   subparser.add_argument("-p", "--profile-name", dest="profileName",
                          help="Profile name")
   subparser.add_argument("--provider-id", dest="providerId",
                          help="Provider/cluster identifier")
   subparser.add_argument("-k", "--key-id", dest="keyId", help="Key identifier")
   subparser.add_argument("--skip-disks", action="store_true",
                          dest="skipDisks",
                          help="Do not recrypt virtual disks")
   subparser.add_argument("--deep", action="store_true",
                          help="Deep re-encryption (slow)")
   subparser.add_argument("-a", "--all", action="store_true",
                          help="Re-encrypt all virtual machines")
   subparser.add_argument("--datacenter", help="The datacenter to inspect")
   subparser.add_argument("name", nargs="?", default=None,
                          help="Virtual machine name")
   subparser.set_defaults(func=VmRecrypt)

   subparser = subparsers.add_parser("disk", help="Configure disks")
   VmDiskParser(subparser)

def ParseArgs():
   import argparse
   parser = argparse.ArgumentParser()

   parser.add_argument("-s", "--server", default="localhost",
                       help="vCenter or ESXi hostname/IP-address")
   parser.add_argument("-u", "--user", default=None,
                       help="User to authenticate")
   parser.add_argument("-p", "--password", default=None,
                       help="Password for authentication")
   parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose logging')
   parser.add_argument('-a', '--api', default=None,
                       help='vSphere API version')

   subparsers = parser.add_subparsers(title="commands", dest="cmd")
   # http://bugs.python.org/issue9253#msg186387
   subparsers.required = True

   subparser = subparsers.add_parser("keys", help="Manipulate Keys")
   KeysParser(subparser)
   subparser = subparsers.add_parser("kms",
                                     help="Configure Key Management Servers")
   KmsParser(subparser)
   subparser = subparsers.add_parser("host", help="Configure ESXi Hosts")
   HostParser(subparser)
   subparser = subparsers.add_parser("policy",
                                     help="Configure Storage Policies")
   PolicyParser(subparser)
   subparser = subparsers.add_parser("vm", help="Configure Virtual Machines")
   VmParser(subparser)

   return parser

def GetConnectCredentials(args):
   """Get the username and password for login.

   It can be super annoying to have to type out long usernames and
   passwords, so this function guesses the best default.
   """
   user = args.user
   password = args.password

   if not user:
      if not IsLocalhostESX():
         user = "Administrator@vsphere.local"
      else:
         user = "root"
   if not password:
      if not IsLocalhostESX() and user != "root":
         password = "Admin!23"
      else:
         password = ""

   return user, password

def Connect(args):
   user, password = GetConnectCredentials(args)
   Log("# Connecting to %s as %s ..." % (args.server, user))
   Warn("Using unverified SSL context.")
   if sys.version_info >= (2, 7, 9):
      import ssl
      sslContext = ssl._create_unverified_context()
   else:
      sslContext = None
   if args.api:
      apiVersions = [args.api]
   else:
      apiVersions = None
   si = SmartConnect(host=args.server, port=443,
                     user=user, pwd=password,
                     preferredApiVersions=apiVersions,
                     sslContext=sslContext)
   if not si:
      raise Exception("Could not connect to '%s'." % args.server)
   atexit.register(Disconnect, si)
   Log("# Connected to %s (%s)" % (args.server, si.content.about.fullName))
   return si

if __name__ == '__main__':
   parser = ParseArgs()
   args = parser.parse_args()
   try:
      si = Connect(args)
      args.func(si, args)
   except Vmodl.MethodFault as e:
      msg = e.msg
      if e.faultMessage and len(e.faultMessage) != 0:
         for faultMessage in e.faultMessage:
            msg = msg + " " + faultMessage.message
      Error(msg)
      if args.verbose:
         raise
      sys.exit(1)
   except Exception as e:
      Error(str(e))
      if args.verbose:
         raise
      sys.exit(1)
   Log("# OK.")
