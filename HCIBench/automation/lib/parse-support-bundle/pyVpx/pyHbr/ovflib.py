# Copyright (c) 2016-2022 VMware, Inc.  All rights reserved.
# -- VMware Confidential

#
# pyHbr.ovflib.py
#
# General functions useful for working with OVF.
#
import atexit
import contextlib
import logging
import os.path
import paramiko
import re
import signal
import socket
import ssl
import struct
import subprocess
import sys
import time

try:
   import simplejson as json
except ImportError:
   import json

from contextlib import contextmanager
from pyVmomi import Vim
from six.moves import http_client, urllib


logger = logging.getLogger('pyHbr.ovflib')
ImportSpecParams = Vim.OvfManager.CreateImportSpecParams
NetworkMapping = Vim.OvfManager.NetworkMapping
DiskProvisioningType = ImportSpecParams.DiskProvisioningType
IPAssignmentInfo = Vim.VApp.IPAssignmentInfo
IpAllocationPolicy = IPAssignmentInfo.IpAllocationPolicy
IpProtocols = IPAssignmentInfo.Protocols


class OVFDeployment(object):
   """Base OVF deployment class.

   Abstract class that provides a base for an OVF deployment.
   """

   def __init__(self,
                ovfUrl):
      self.properties = {}
      self.ovfUrl = ovfUrl

   def SetProperty(self, key, value):
      """Set an OVF property."""
      self.properties[key] = value

   def SetIpAllocationPolicy(self, ipAllocationPolicy):
      """Set the IP allocation policy."""
      raise NotImplementedError

   def SetIpProtocol(self, ipProtocol):
      """Set the IP protocol."""
      raise NotImplementedError

   def SetDiskMode(self, diskMode):
      """Set the disk mode."""
      raise NotImplementedError

   def SetNetwork(self, network):
      """Set the network the VM nic will be attached to."""
      raise NotImplementedError

   def SetDatastore(self, datastore):
      """Set the datastore the VM will be deployed to."""
      raise NotImplementedError

   def SetName(self, name):
      """Set the name of the VM to be deployed"""
      raise NotImplementedError

   def Deploy(self, powerOn=True):
      """Start OVF deployment.

      Powers on the VM after deployment and returns the VM managed object.
      """
      raise NotImplementedError


@contextmanager
def GetLease(resourcePool, importSpec):
   """Context manager that returns an OVF lease."""
   lease = resourcePool.ImportVApp(importSpec)
   try:
      while lease.GetState() == Vim.HttpNfcLease.State.initializing:
         time.sleep(1)
      if lease.GetState() != Vim.HttpNfcLease.State.ready:
         raise lease.error
   except:
      lease.Abort()
      raise

   yield lease

   if lease.GetState() != Vim.HttpNfcLease.State.done:
      lease.Abort()


class OVFManagerDeployment(OVFDeployment):
   """OVF deployment using ovftool"""


   def __init__(self,
                ovfUrl,
                hostd,
                defaults=True):
      OVFDeployment.__init__(self, ovfUrl)

      self.params = ImportSpecParams()
      if defaults:
         self.params.ipAllocationPolicy = IpAllocationPolicy.dhcpPolicy
         self.params.ipProtocol = IpProtocols.IPv4
         self.params.diskProvisioning = DiskProvisioningType.thin

      self.hostd = hostd

   def SetIpAllocationPolicy(self, ipAllocationPolicy):
      assert ipAllocationPolicy in [IpAllocationPolicy.dhcpPolicy,
                                    IpAllocationPolicy.fixedPolicy]
      self.params.ipAllocationPolicy = ipAllocationPolicy

   def SetIpProtocol(self, ipProtocol):
      assert ipProtocol in [IpProtocols.IPv4, IpProtocols.IPv6]
      self.params.ipProtocol = ipProtocol

   def SetDiskMode(self, diskMode):
      assert diskMode in [DiskProvisioningType.thin, DiskProvisioningType.thick]
      self.params.diskProvisioning = diskMode

   def SetNetwork(self, network):
      network = self.hostd.GetNetwork(network)
      self.params.networkMapping = [NetworkMapping(network=network)]

   def SetDatastore(self, datastore):
      self.datastore = self.hostd.GetDatastore(datastore)

   def SetName(self, name):
      self.params.entityName = name

   def _InjectOvfEnv(self, vm):
      about = self.hostd.GetServiceInstance().GetContent().GetAbout()

      data = {
         'moId': vm._moId,
         'platform': {
            'kind': about.GetName(),
            'version': about.GetVersion(),
            'vendor': about.GetVendor(),
            'locale':'en'
         },
         'properties': '\n'.join(
            ['      <Property oe:key="{}" oe:value="{}"/>'.format(k, v)
             for k, v in self.properties.items()])
      }

      ovfEnv = '''<?xml version="1.0" encoding="UTF-8"?>
<Environment\n
   xmlns="http://schemas.dmtf.org/ovf/environment/1"
   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
   xmlns:oe="http://schemas.dmtf.org/ovf/environment/1"
   xmlns:ve="http://www.vmware.com/schema/ovfenv"
   oe:id=""
   ve:esxId="{moId}">
   <PlatformSection>
      <Kind>{platform[kind]}</Kind>
      <Version>{platform[version]}</Version>
      <Vendor>{platform[vendor]}</Vendor>
      <Locale>{platform[locale]}</Locale>
   </PlatformSection>
   <PropertySection>
{properties}
   </PropertySection>
</Environment>
'''.format(**data)

      configSpec = Vim.Vm.ConfigSpec()
      configSpec.SetExtraConfig([Vim.Option.OptionValue(key='guestinfo.ovfEnv',
                                                        value=ovfEnv)])
      task = vm.Reconfigure(configSpec)
      self.hostd.WaitForTask(task)

   def Deploy(self, powerOn=True):
      context = ssl._create_unverified_context()

      response = urllib.request.urlopen(self.ovfUrl, context=context)
      data = response.read().decode('utf-8')

      self.params.propertyMapping = [Vim.KeyValue(key=key, value=value) for
                                     key, value in self.properties.items()]

      resourcePool = self.hostd.GetHostComputeResources().GetResourcePool()
      spec = self.hostd.GetOvfManager().CreateImportSpec(
         ovfDescriptor=data,
         resourcePool=resourcePool,
         datastore=self.datastore,
         cisp=self.params)
      importSpec = spec.GetImportSpec()

      baseDir = os.path.dirname(self.ovfUrl)

      vm = None
      with GetLease(resourcePool, importSpec) as lease:
         uploadUrlMap = {}
         for deviceUrl in lease.info.deviceUrl:
            uploadUrlMap[deviceUrl.importKey] = (deviceUrl.key, deviceUrl.url)

         totalSize = 1
         for fileItem in spec.fileItem:
            totalSize += fileItem.size

         counter = 0
         chunk = 32 * 1024 * 1024 # 32MB
         progressMark = max(totalSize // 10 // chunk, 1)
         for fileItem in spec.fileItem:
            key, url = uploadUrlMap[fileItem.deviceId]
            srcDiskPath = os.path.join(baseDir, fileItem.path)

            parsedUrl = urllib.parse.urlparse(url)
            if parsedUrl.scheme == 'https':
               HttpConnection = lambda host: http_client.HTTPSConnection(host,
                                                                         context=context)
            else:
               HttpConnection = http_client.HTTPConnection

            host = parsedUrl.netloc
            if host == '*':
               host = self.hostd.Hostname()

            logger.info('Connecting to {}'.format(host))
            httpConn = HttpConnection(host)
            source = urllib.request.urlopen(srcDiskPath, context=context)

            with contextlib.closing(source) as srcDisk, \
                  contextlib.closing(httpConn) as httpConn:
               diskSize = int(srcDisk.headers.get('Content-Length'))

               requestType = 'PUT' if fileItem.create else 'POST'
               logger.info('{} {} => {}'.format(requestType,
                                                srcDiskPath,
                                                parsedUrl.path))
               httpConn.putrequest(requestType, parsedUrl.path)
               httpConn.putheader('Content-Length', diskSize)
               httpConn.endheaders()

               while True:
                  start = time.time()
                  data = srcDisk.read(chunk)
                  end = time.time()
                  logger.debug('Read {} bytes in {} (speed = {} MB/s)'.format(
                               chunk, end - start, chunk / 1024 / 1024 / (end - start)))
                  if len(data) == 0:
                     break
                  if lease.GetState() != Vim.HttpNfcLease.State.ready:
                     raise RuntimeError('Lease expired')
                  start = time.time()
                  httpConn.send(data)
                  end = time.time()
                  logger.debug('Wrote {} bytes in {} (speed = {} MB/s)'.format(
                               chunk, end - start, chunk / 1024 / 1024 / (end - start)))
                  counter += 1

                  if counter % progressMark == 0:
                     progress = int(min(99, counter * chunk * 100 // totalSize))
                     logger.info('Progress at {}%'.format(progress))
                     lease.Progress(progress)

               if lease.state == Vim.HttpNfcLease.State.error:
                  raise lease.error
               elif lease.state not in [Vim.HttpNfcLease.State.ready,
                                        Vim.HttpNfcLease.State.done]:
                  raise RuntimeError('Upload aborted, lease state {}'.format(
                     lease.state))

               logger.debug('HTTP response from server {}'.format(
                  httpConn.getresponse().read()))

         vm = lease.info.entity

         lease.Progress(100)
         lease.Complete()

         self._InjectOvfEnv(vm)

         if powerOn:
            task = vm.PowerOn()
            self.hostd.WaitForTask(task)

      return vm


