#!/usr/bin/env python

__doc__ = """
@file case_4_FlagInfo.py --
Copyright 2006-2014 VMware, Inc. All rights reserved. -- VMware Confidential

TestCase 4 verifies FlagsInfo.java API against a suspended VM without
guest VM installed.
"""
__author__ = "VMware, Inc"

import pyVim
from pyVim import integtest
from pyVmomi import Vim, Vmodl

# debugInfo, monitorType, diResult, mtResult, exception
FlagInfoValues = [(False, None, False, "release", None),
                  (True, None, True, "debug", None),
                  (None, "release", False, "release", None),
                  (None, "debug", True, "debug", None),
                  (None, "stats", False, "stats", None),
                  (False, "debug", None, None, Vmodl.Fault.InvalidArgument),
                  (True, "release", None, None, Vmodl.Fault.InvalidArgument),
                  (True, "stats", None, None, Vmodl.Fault.InvalidArgument),
                 ]

class TestMonitorType(integtest.FixtureCreateDummyVM):
   def setFlagInfo(self, debugInfo, monitorType):
      """
      A helper method that sets the runWithDebugInfo and/or monitorType properties.
      """
      cfgspec = Vim.Vm.ConfigSpec()
      flags = Vim.Vm.FlagInfo()
      if debugInfo is not None:
         flags.SetRunWithDebugInfo(debugInfo)
      if monitorType is not None:
         flags.SetMonitorType(monitorType)
      cfgspec.SetFlags(flags)
      self._vm.Reconfigure(cfgspec)
      # calling it again to test the indempotency
      self._vm.Reconfigure(cfgspec)

   def test1_Verify_MonitorType(self):
      """
      Verify setting runWithDebugInfo and monitorType properties to different values.
      """
      for (debugInfo, monitorType, diResult, mtResult, exception) in FlagInfoValues:
         if exception is not None:
            # Save current values, they should not change if the exception is thrown
            diResult = self._vm.GetConfig().GetFlags().GetRunWithDebugInfo()
            mtResult = self._vm.GetConfig().GetFlags().GetMonitorType()
            self.failUnlessRaises("Setting FlagInfo expected to raise %s" % exception,
                                  exception, self.setFlagInfo, debugInfo, monitorType)
         else:
            self.failIfRaises("Setting FlagInfo should not raise.",
                              self.setFlagInfo, debugInfo, monitorType)
         self.failUnless(self._vm.IsPoweredOff(),
                         "VM must remain powered off after Reconfigure")
         flags = self._vm.GetConfig().GetFlags()
         self.failUnlessEqual(flags.GetRunWithDebugInfo(), diResult,
                              "Expected runWithDebugInfo to be '%s'" % diResult)
         self.failUnlessEqual(flags.GetMonitorType(), mtResult,
                              "Expected monitorType to be '%s'" % mtResult)

# end of tests
