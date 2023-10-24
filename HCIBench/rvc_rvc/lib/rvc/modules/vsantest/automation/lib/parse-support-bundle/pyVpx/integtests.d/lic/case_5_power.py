#!/usr/bin/env python
# Copyright 2008 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file case_5_power.py --

# TestCase 5 verifies LicenseManager prevents power-on VMs if
# no license is set or if max VM VPU is not met

__author__ = "VMware, Inc"

from keys import ESXKeys
from pyVim import integtest
from pyVim import vm
from pyVmomi import Vmodl

class TestLicenseVMPowerOp(integtest.FixtureCreateDummyVM):
   def test1_PowerOnVMButNoLicense(self):
      '''With no license (and no eval) should get fault'''
      self.GetLicMgr()
      self.failIfRaises("Removing license should not fail.",
                        self._lic.RemoveLicense, "")
      dut = vm.VM(self._vm, None, None)
      try:
         dut.PowerOn()
         self.fail("Expected power on with out license to fail");
      except:
         pass
      

   def test2_PowerOnVMCheckBadVPU(self):
      '''foundation max vpus is 2, verify vpu=4 fails this test'''
      tag = 'VMware_Foundation_32_forever'
      self.InstallLic(tag)
      # @todo check that max vpu count is 2
      dut = vm.VM(self._vm, None, None)
      dut.SetVpu(4)
      self.failUnlessRaises(Vmodl.Fault.NotEnoughLicenses,
                            dut.PowerOn)

   def test3_PowerOnVMCheckGoodVPU(self):
      '''standard max vpus is 4, verify vpu=4 passes this test'''
      tag = 'VMware_Standard_32_forever'
      self.InstallLic(tag)
      dut = vm.VM(self._vm, None, None)
      dut.SetVpu(4)
      self.failIfRaises(dut.PowerOn)

   def test4_PowerOnVMGoodLicense(self):
      '''with a hefty 32 cpu enterprise lic should work'''
      tag = 'VMware_Enterprise_32_forever'
      self.InstallLic(tag)
      dut = vm.VM(self._vm, None, None)
      self.failIfRaises(dut.PowerOn)

   
   def GetLicMgr(self):
      '''this should move to the fixture, it is setup code'''
      self._hs = self._host.GetHostSystem()
      self._cfgm = self._hs.GetConfigManager()
      self._lic = self._cfgm.GetLicenseManager()

   def InstallLic(self, tag):
      '''this should move to pyVim library'''
      self.GetLicMgr()
      lic = ESXKeys()
      serial = lic.data[tag]
      result = self._lic.UpdateLicense(serial)
      self.failIf(result is None, 
               "Install enterprise edition license, verify result is not None")
      self.failUnless(result.licenseKey == serial, 
       "Check serial matches got:%s vs given:%s" % (result.licenseKey, serial))
