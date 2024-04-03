#!/usr/bin/python
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file case_1.py --
# TestCase 1 verifies VirtualMachine.java API against a suspended VM (TTTVM1)
# that does not have a guest OS installed

__author__ = "VMware, Inc"

import os
from pyVim.integtest import FixtureCreateDummyVM
from pyVim.vm import VM
from pyVmomi import Vim, Vmodl
from pyVim import folder

class FixtureSuspendVM(FixtureCreateDummyVM):
   """
   Perform common setup tasks for all derived classes in this module.
   """
   def setUp(self):
      """
      Create a dummy VM, establish a connection to vim
      managed system under test.
      """
      super(FixtureSuspendVM, self).setUp()
      self.failIfRaises("Powering on VM should not fail.",
                        self._vm.PowerOn)
      self.failUnless(self._vm.IsRunning(),
                      "VM should be 'poweredOn', it is '%s'"  %
                      (self._vm.ReportState()))
      self.failIfRaises("Suspending VM should not fail.",
                        self._vm.Suspend)
      self.failUnless(self._vm.IsSuspended(),
                      "Initial VM state should be suspended, it is '%s'" %
                      (self._vm.ReportState()))


class TestSuspendedVM(FixtureSuspendVM):
   """
   Run though all VM operations against a suspended VM that has
   no guest os or tools.
   """
   def test1_VerifySuspend(self):
      """
      Apply Suspend on a Suspended VM doesn't change state
      @pre VM is registered and in the suspended state
      @post VM is left in suspended state
      """
      self.failUnlessRaises(
         "Suspending suspended guest is expected to raise.",
         Vim.Fault.InvalidPowerState, self._vm.Suspend)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify still in suspended state after issuing Suspend(): %s" %
         (self._vm.ReportState()))

   def test2_VerifyBasicSnapshotOps(self):
      """
      Apply snapshot operations to a suspended vm and verify state
      is not changed.
      @pre VM is registered and in the suspended state
      @post VM is left in suspended state
      """
      self.failUnlessRaises(
         "Removing all snapshots from a suspended VM is expected to raise.",
         Vmodl.Fault.SystemError, self._vm.RemoveAllSnapshots)
      self.failUnless(
         self._vm.IsSuspended(),
         "Verify VM state is suspended after failed RemoveAllSnapshots: %s" %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Reverting to non-existent current snapshot is expected to raise.",
         Vim.Fault.NotFound,
         self._vm.RevertToCurrentSnapshot)
      self.failUnless(
         self._vm.IsSuspended(),
         "Verify VM state is suspended after failed RevertToCurrentSnapshot: %s" %
         (self._vm.ReportState()))
      snapName = "TTTtest-" + str(os.getpid())
      self.failUnlessRaises(
         "Creating snapshot for suspended VM is expected to raise.",
         Vim.Fault.InvalidPowerState,
         self._vm.CreateSnapshot, snapName, self.__class__.__name__)
      self.failUnless(
         self._vm.IsSuspended(),
         "Verify VM state is suspended after CreateSnapshot: %s" %
         (self._vm.ReportState()))
      self._vm.RevertToCurrentSnapshot()
      self.failUnless(
         self._vm.IsSuspended(),
         "Verify VM state is suspended after successful RevertToCurrentSnapshot: %s" %
         (self._vm.ReportState()))
      self._vm.RemoveAllSnapshots()
         ## @todo verify this worked via alternate method
      self.failUnless(
         self._vm.IsSuspended(),
         "Verify VM is suspended after successful RemoveAllSnapshots: %s" %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Removing all snapshots from suspended VM is expected to raise.",
         Vmodl.Fault.SystemError,
         self._vm.RemoveAllSnapshots)
      self.failUnless(
         self._vm.IsSuspended(),
         "Verify VM is suspended after failed RemoveAllSnapshots: %s" %
         (self._vm.ReportState()))

   def test3_VerifyGuestVmOps(self):
      """
      Apply Guest OS related operations.
      @pre VM is registered and in the suspended state
      @post VM is left in suspended state
      """
      self.failUnlessRaises(
         "Resetting guest information is not supported and is expected to raise.",
         Vmodl.Fault.NotSupported, self._vm.ResetGuestInformation)
      self.failUnless(
         self._vm.IsSuspended(),
             "Verify VM state is suspended after ResetGuestInformation: %s" %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Shutting down suspended guest is expected to raise.",
         Vim.Fault.InvalidPowerState, self._vm.ShutdownGuest)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after ShutdownGuest: %s" %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Rebooting suspended guist is expected to raise.",
         Vim.Fault.InvalidPowerState, self._vm.RebootGuest)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after RebootGuest: %s" %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Standby on a suspended guest is expected to raise.",
         Vim.Fault.InvalidPowerState, self._vm.StandbyGuest)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after StandbyGuest: %s" %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Mounting tool on a suspended guest is expected to raise.",
         Vim.Fault.InvalidState, self._vm.MountToolsInstaller)
      self.failUnless(
         self._vm.IsSuspended(),
                 "Verify VM state is suspended after MountToolsInstaller: %s" %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Unmounting tools on a suspended guest is expected to raise.",
         Vim.Fault.InvalidState, self._vm.UnmountToolsInstaller)
      self.failUnless(
         self._vm.IsSuspended(),
                "Verify VM state is suspended after UnmountToolsInstaller: %s" %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Upgrading tools on a suspended guest is expected to raise.",
         Vim.Fault.InvalidState, self._vm.UpgradeTools)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after UpgradeTools: %s" %
         (self._vm.ReportState()))

      # 1. construct the identity object
      id = Vim.Vm.Customization.LinuxPrep()
      id.SetDomain("eng.vmware.com")
      hostName = Vim.Vm.Customization.FixedName()
      hostName.SetName("TTTVM1")
      id.SetHostName(hostName)

      # 2. construct globalIPSettings object
      ipaddrs = Vim.Vm.Customization.GlobalIPSettings()
      ipaddrs.SetDnsServerList(["10.17.0.1", "10.17.0.2"])
      ipaddrs.SetDnsSuffixList(["eng.vmware.com", "vmware.com"])

      # 3. construct the spec object composed of identity, GlobalIPSettings
      spec = Vim.Vm.Customization.Specification()
      spec.SetIdentity(id)
      spec.SetGlobalIPSettings(ipaddrs)
      self.failUnlessRaises(
         "Checking customization is not supported and is expected to raise.",
         Vmodl.Fault.NotSupported, self._vm.CheckCustomizationSpec, spec)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after CheckCustomizationSpec: %s" %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Customizing guest spec is not supported and is expected to raise.",
         Vmodl.Fault.NotSupported, self._vm.Customize, spec)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after Customize: %s" %
         (self._vm.ReportState()))

   def test4_VerifyVmTypeMutability(self):
      """
      Apply VM typing operations
      @pre VM is registered and in the suspended state
      @post VM is left in suspended state
      """
      self.failUnlessRaises(
         "Marking a suspended VM as template is not supported.",
         Vmodl.Fault.NotSupported,
         self._vm.MarkAsTemplate)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after MarkAsTemplate: %s" %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Marking suspended VM as VM is not supported.",
         Vmodl.Fault.NotSupported,
         self._vm.MarkAsVirtualMachine)
      self.failUnless(
         self._vm.IsSuspended(),
                "Verify VM state is suspended after MarkAsVirtualMachine: %s" %
         (self._vm.ReportState()))

   def test5_VerifyThingsHostdWontDoDirectly(self):
      """
      Apply all VM operations that are "Not Supported".
      @pre VM is registered and in the suspended state
      @post VM is left in suspended state
      """
      self.failUnlessRaises(
         "Upgrading virtual hardware is expected to raise.",
         Vim.Fault.AlreadyUpgraded,
         self._vm.UpgradeVirtualHardware)
      self.failUnless(
         self._vm.IsSuspended(),
               "Verify VM state is suspended after UpdateVirtualHardware: %s" %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Migrating suspended VM is not supported.",
         Vmodl.Fault.NotSupported, self._vm.Migrate)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after Migrate: %s" %
         (self._vm.ReportState()))
      spec = Vim.Vm.RelocateSpec()
      self.failUnlessRaises(
         "Relocating suspended VM is not supported.",
         Vmodl.Fault.NotSupported, self._vm.Relocate, spec)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after Relocate: %s" %
         (self._vm.ReportState()))
      ## @todo should Clone() throw NotSupported?
      vmf = self._host.GetFolderOfVMs()
      self.failUnlessRaises(
         "Cloning suspended VM is expected to raise.",
         Vmodl.Fault.InvalidRequest, self._vm.Clone,
                            vmf, "TTTVM1-CLONE", None)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after Clone: %s" %
         (self._vm.ReportState()))

   def test6_VerifyVmReconfig(self):
      """
      Apply two changes via Reconfiguration function, one no-op, one annotation.
      @pre TTTVM1 is registered and in the suspended state
      @post VM is left in suspended state
      @todo @see full set of tests just for reconfigure of suspended VMs
      """
      cfgspec = Vim.Vm.ConfigSpec()
      self._vm.Reconfigure(cfgspec)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after no-op Reconfigure: %s" %
         (self._vm.ReportState()))

   def test7_VerifyKVM(self):
      """
      Apply KVM style operations to self._vm.
      @pre TTTVM1 is registered and in the suspended state
      @post VM is left in suspended state
      """
      self.failUnlessRaises(
         "Acquire mks ticket on a suspended VM is expected to raise.",
         Vim.Fault.InvalidPowerState, self._vm.AcquireMksTicket)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after AcquireMksTicket: %s" %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Setting screen resolution on a suspended VM is expected to raise.",
         Vim.Fault.InvalidPowerState, self._vm.SetScreenResolution, 80, 24)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after SetScreenResolution: %s" %
         (self._vm.ReportState()))

   def test8_VerifyAnswer(self):
      """
      Verify Answer works with suspended vm that has no question present.
      @pre no question is present on the VM
      @post VM is left in suspended state
      """
      # some arbitrary values for arguments to said function
      qid = "1"
      choice = "3"
      self.failUnlessRaises(
         "Asking suspended VM is expected to raise.",
         Vmodl.Fault.InvalidArgument, self._vm.Answer, qid, choice)
      self.failUnless(
         self._vm.IsSuspended(),
                      "Verify VM state is suspended after Answer: %s" %
         (self._vm.ReportState()))

   def test9_VerifyUnregister(self):
      """
      Verify Unregister takes VM out of host inventory.
      """
      self.failIfRaises(
         "Unregistering the VM should not fail.",
         self._vm.Unregister)


class TestPoweringOnSuspendedVM(FixtureSuspendVM):
   """
   Run though all VM operations against a suspended VM that has
   no guest os or tools.
   """
   def test1_VerifySuspendToPowerOn(self):
      """
      Power on suspended VM and verify it is running.
      @pre VM is registered and in the suspended state
      VMQA: vmops/poweron
         POS001 PowerOn a single suspended vm from a standalone host
         NEG003 Power on a Suspended VM with invalid (empty) Host System
         NEG058 PowerOn a already poweredOn VM
      VMQA: vmops/unregistervm
         POS003 Unregister a suspended VM on standalone host
      """
         ## @todo, ideally we'd lock out other clients from modifying this vm
      self.failUnlessRaises(
         "Powering off suspended VM is expected to raise.",
         Vim.Fault.InvalidPowerState, self._vm.PowerOff)
      self.failUnless(
         self._vm.IsSuspended(),
                        "VM should be suspended after failed PowerOff, is: %s" %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Resetting suspended VM is expected to raise.",
         Vim.Fault.InvalidPowerState, self._vm.Reset)
      self.failUnless(
         self._vm.IsSuspended(),
                         "VM should be suspended after failed Reset, is: %s" %
         (self._vm.ReportState()))
      self.failIfRaises(
         "Powering on the VM should not fail.",
         self._vm.PowerOn)
      self.failUnless(
         self._vm.IsRunning(),
                             "After PowerOn, VM should be 'poweredOn': %s"  %
         (self._vm.ReportState()))
      self.failUnlessRaises(
         "Powering powered-on VM is expected to raise.",
         Vim.Fault.InvalidPowerState, self._vm.PowerOn)
      self.failIfRaises(
         "Suspending powered-on VM should not fail.",
         self._vm.Suspend)

# end of tests
