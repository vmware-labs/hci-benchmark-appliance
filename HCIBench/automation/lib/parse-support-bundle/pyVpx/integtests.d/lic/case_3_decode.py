#!/usr/bin/python
# Copyright 2008 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file case_3_decode.py --
# TestCase 1 verifies ESX LicenseManager Interface DecodeLicense
# as specified in the vmodl bora/vim/vmodl/vim/LicenseManager.java

__author__ = "VMware, Inc"

from pyVim import integtest
from pyVmomi import Vmodl
import pyVim.vimhost
from keys import ESXKeys
from case_1_FnsExist import FixtureLIC

class TestLicenseManager(FixtureLIC):
   def test1_VerifyDecodeLicenseMethod(self):
      lic = ESXKeys()
      for tag in lic.data.keys():   # valid keys
         serial = lic.data[tag]
         info = self._lic.DecodeLicense(serial)
         self.failIf(info is None,
                     "DecodeLicense('%s')" % (serial))
         print "tag=%s returned: %s" % (tag, info)
         self.failIf(info.properties is None,
                     "Checking for properties");
         self.failIf(len(info.properties) == 0,
                     "Checking properties has at least one element");
         self.failIf(serial != info.licenseKey,
          "Verify serial number matches what was sent: got %s" % (info.licenseKey));
         self.failIf(len(info.name) == 0, "Verify edition name exists")
         self.failIf(len(info.costUnit) == 0, "Verify costUnit  exists")         
         self.failIf(len(info.editionKey) == 0, "Verify editionKey (vmodl handle) exists")
         self.failIf(info.total is None, "'total' must be set")
         self.failIf(info.used is None, "'used' must be set")
         self.failIf(info.total < 0, "Verify total is whole number %d" %(info.total))
         self.failIf(info.used < 0, "Verify used is whole number %d" %(info.used))
         cpuCnt = lic.GetCPU(tag)
         self.failUnless(info.total == cpuCnt,
                     "Verify decoded cpu(%d) matches license (%d)" % (info.total, cpuCnt))
         self.failIf(info.type is not None, "'type' should not be set")
