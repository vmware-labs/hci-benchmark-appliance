#!/usr/bin/python
# Copyright 2008 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file case_1_FnsExist.py --
# TestCase 1 verifies ESX LicenseManager Interface implements functions:
#   DecodeLicense
#   QueryLicenses
#   RemoveLicense
#   UpdateLicense
# and that it does not Implement AddLicense
# as specified in the vmodl bora/vim/vmodl/vim/LicenseManager.java

__author__ = "VMware, Inc"

from pyVim import integtest
from pyVmomi import Vmodl
import pyVim.vimhost


class FixtureLIC(integtest.TestCase):
   ''' Establish a connection to vim managed system under test
    @pre hostd is operational and crededitials are valid
    @post _host contains authenticated connection to hostd
    '''
   def setUp(self):
      self.serial = "1w33barbitrarRy-string"      
      self._host = pyVim.vimhost.Host()
      self.failIf(self._host is None, "Connect and Login to hostd")
      self._hs = self._host.GetHostSystem()
      self.failIf(self._hs is None, "Retrieve HostSystem")
      self._cfgm = self._hs.GetConfigManager()
      self.failIf(self._cfgm is None, "Retrieve HostSystem.ConfigManager")
      self._lic = self._cfgm.GetLicenseManager()
      self.failIf(self._lic is None,
                  "Retrieve HostSystem.ConfigManager.LicenseManager")

   def tearDown(self):
      self._host = None
      self._hs = None      
      self._cfgm = None
      self._lic = None
      self.serial = None

   # utility routine for checking results
   def HasKey(self, result, keyName):
      for item in result.properties:
         if item.key == keyName:
            return True
      return False


class TestLicenseManager(FixtureLIC):
   def test1_VerifyDecodeLicenseMethod(self):
      self.failUnless(True,
                      "Attempting to decode license: %s" % (self.serial))
      result = self._lic.DecodeLicense(self.serial);
      self.failUnless(self.HasKey(result, 'diagnostic'),
                      "Must return 'diagnostic' key")
      self.failUnless(self.HasKey(result, 'lc_error'),
                      "Must return 'lc_error' key")

   def test2_VerifyQueryLicenseMethod(self):
      self.failUnless(True,
                      "Attempting to Query license: key = %s" % (self.serial))
      result = self._lic.QueryLicenses(self.serial)
      count = len(result)
      self.failUnless(count == 0 or count == 1,
                      "Verify array is zero or one, got: %d" % (count))
      
   def test3_VerifyAddLicenseMethod(self):
      self.failUnless(True,
                      "Attempting to Add license: key = %s" % (self.serial))
      self.failUnlessRaises("Adding license should raise NotImplemented.",
                            Vmodl.Fault.NotImplemented,
                                            self._lic.AddLicense, self.serial)
      
   def test4_VerifyUpdateLicenseMethod(self):
      self.failUnless(True,
                      "Attempting to Update license: key = %s" % (self.serial))
      result = self._lic.UpdateLicense(self.serial)
      self.failUnless(self.HasKey(result, 'diagnostic'),
                      "Must return 'diagnostic' key")
      self.failUnless(self.HasKey(result, 'lc_error'),
                      "Must return 'lc_error' key")
      
   def test5_VerifyRemoveLicenseMethod(self):
      self.failUnless(True,
                      "Attempting to Remove license: key = %s" % (self.serial)) 
      self._lic.RemoveLicense(self.serial)
      
