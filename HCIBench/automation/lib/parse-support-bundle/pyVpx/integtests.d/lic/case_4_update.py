#!/usr/bin/python
# Copyright 2008 VMware, Inc.  All rights reserved. -- VMware Confidential
#
## @file case_4_update.py --
# TestCase 4 verifies ESX LicenseManager Configuration operations
# (Update|Remove) work properly in what the return and how they
# impact HostSystem::Capability VIM data object

__author__ = "VMware, Inc"

from pyVmomi import Vmodl
import pyVim.vimhost
from case_1_FnsExist import FixtureLIC
from keys import ESXKeys

class TestConfiguration(FixtureLIC):
   def test1_VerifyConfiguration(self):   
      self.failIfRaises(self._lic.RemoveLicense, "")
      result = self._lic.QueryLicenses()
      self.failIf(len(result) > 0, "Expect QueryLicenses to return zero length array")
      capNoLic = self._hs.GetCapability()
      self.failIf(capNoLic is None, "Retrieve HostSystem.Capability")
      self.CheckNoLic(capNoLic)
      # install a big license
      lic = ESXKeys()
      tag = 'VMware_Enterprise_32_forever'
      serial = lic.data[tag]
      result = self._lic.UpdateLicense(serial)
      self.CheckSerial(result, serial, lic, tag)
      result = self._lic.QueryLicenses()
      self.failUnless(len(result) == 1, "Expect one license to be reported")
      item = result[0]
      self.CheckSerial(item, serial, lic, tag)
      capWithLic = self._hs.GetCapability()
      self.failIf(capWithLic is None, "Retrieve HostSystem.Capability")
      self.CheckWithLic(capWithLic)

   def test2_VerifyNotEnoughCPU(self):
      self.failIfRaises(self._lic.RemoveLicense, "")
      lic = ESXKeys()
      # @todo check to see if machine under test has 2 cpu or not
      # and fail the test if not
      tag = 'VMware_Foundation_1_forever'
      serial = lic.data[tag]
      result = self._lic.UpdateLicense(serial)
      self.failUnless(self.HasKey(result, 'diagnostic'),
                      "Must return 'diagnostic' key")

   def CheckSerial(self, result, serial, lic, tag):
      self.failIf(result is None, 
                  "Install enterprise edition license, verify result is not None")
      self.failUnless(result.licenseKey == serial, 
       "Check serial matches got:%s vs given:%s" % (result.licenseKey, serial))
      self.failIf(result.used is None, "Used count is not None")      
      self.failIf(result.used == 0, "Used count is > 0")
      licCPU = lic.GetCPU(tag)
      self.failUnless(result.total == licCPU, 
               "Check cpu count %d matches license %d" % (result.total, licCPU))
      self.failUnless(result.total >= result.used,
                      "Verify total cpu %d > used %d" % (result.total, result.used))

   def CheckNoLic(self, nlic):
      self.failUnless(nlic.maxSupportedVcpus is 1, 
                      "maxSupportedVpus == 1, got %d" % (nlic.maxSupportedVcpus))
      self.failUnless(nlic.sanSupported is False, "no license san is false")
      self.failUnless(nlic.nfsSupported is False, "no license nfs is false")
      self.failUnless(nlic.nfsSupported is False, "no license iscsi is false")

   def CheckWithLic(self, havelic):
      self.failUnless(havelic.maxSupportedVcpus is 8, 
                      "maxSupportedVpus == 8 got %d" % (havelic.maxSupportedVcpus))
      self.failUnless(havelic.sanSupported is True, "no license san is true")
      self.failUnless(havelic.nfsSupported is True, "no license nfs is true")
      self.failUnless(havelic.nfsSupported is True, "no license iscsi is true")

      

