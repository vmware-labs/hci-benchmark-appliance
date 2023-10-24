#!/usr/bin/env python

__doc__ = """
@file case_1_MessWithPowerOps.py --
Copyright 2007-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module verifies VM power operations.
"""

__author__ = "VMware, Inc"

from pyVmomi import Vim
from pyVim import vm
from pyVim import integtest

class TestPowerOps(integtest.FixtureCreateDummyVM):
    """
    This is a very slow test that exercises various power operations
    on a dummy test VM.
    """

    def test1_PowerOperations(self):
        # Power on the VM
      self.failIfRaises(
         "Powering the VM should not raise", 
         self._vm.PowerOn)
      self.failUnless(
         self._vm.IsRunning(),
                        "VM must be running after we power it on.")

        # Reset the powered VM
      self.failIfRaises(
         "Resetting powered-on VM should not raise", 
         self._vm.Reset)
      self.failUnless(
         self._vm.IsRunning(),
                        "VM must be running after we reset it.")

        # Suspend the powered VM
      self.failIfRaises(
         "Suspending powered-on VM should not raise", 
         self._vm.Suspend)
      self.failUnless(
         self._vm.IsSuspended(),
                        "VM must be suspended.")

        # Power off the suspended VM
      self.failUnlessRaises(
         "Powering off the suspended VM is expected to raise.", 
         Vim.Fault.InvalidPowerState,
         self._vm.PowerOff)
      self.failUnless(
         self._vm.IsSuspended(),
                        "VM must remain suspended.")

        # Power on the suspended VM
      self.failIfRaises(
         "Powering on suspended VM should not raise.", 
         self._vm.PowerOn)
      self.failUnless(
         self._vm.IsRunning(),
                        "VM must be running after we power it from the suspened state.")

