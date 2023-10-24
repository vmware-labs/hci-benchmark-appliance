#!/usr/bin/python
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file case_2.py --
# TestCase 2 verifies VirtualMachine.java API against a powered off VM with
# a guest OS (dsl linux) and VMWare tools (TTTVM2)

__author__ = "VMware, Inc"

import os
import unittest
import testoob
from pyVim.integtest import FixtureCreateDummyVM
from pyVmomi import Vim, Vmodl
import pyVim.vimhost


## Run though all VM operations against a Powered Off VM that has
# a guest os and tools 
class TestPoweredOffVM(FixtureCreateDummyVM):
   ## Try to suspend a powerd off VM
   # @pre TTTVM1 is registered and in powered off state
   # @post VM is left in powered off state
   def test1_VerifyPowerOffToSuspend(self):
         ## @todo, ideally we'd lock out other clients from modifying this vm
      self.failUnlessRaises("Powering off powered-off VM is expected to raise.",
                            Vim.Fault.InvalidPowerState, self._vm.PowerOff)
      self.failUnless(self._vm.IsPoweredOff(),
                 "Verify still off state after issuing Poweroff(): %s" %
                      (self._vm.ReportState()))
      self.failUnlessRaises("Suspending powered-off VM is expected to raise.",
                            Vim.Fault.InvalidPowerState, self._vm.Suspend)
      self.failUnless(self._vm.IsPoweredOff(),
                        "Verify still in off after failed Suspend, is: %s" %
                      (self._vm.ReportState()))
      self.failUnlessRaises("Resetting powered-off VM is expected to raise.",
                            Vim.Fault.InvalidPowerState, self._vm.Reset)
      self.failUnless(self._vm.IsPoweredOff(),
                         "VM should be off after failed Reset, is: %s" %
                      (self._vm.ReportState()))

   ## Apply snashot operations to a powered off vm, verify state is not changed
   # @pre TTTVM2 is registered and in the powered off state
   # @post VM is left in powered off state
   def test2_VerifyBasicSnapshotOps(self):
      self.failUnlessRaises("Removing snapshots from powered-off VM should fail.",
                            Vim.Fault.InvalidState, self._vm.RemoveAllSnapshots)
      self.failUnless(self._vm.IsPoweredOff(),
            "Verify VM state is off after failed RemoveAllSnapshots: %s" % 
                      (self._vm.ReportState()))
      self.failUnlessRaises("Reverting powered-off VM to current snapshot should fail.",
                            Vim.Fault.NotFound,
                            self._vm.RevertToCurrentSnapshot)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after failed RevertToCurrentSnapshot: %s" %
                      (self._vm.ReportState()))
      snapName = "TTTtest-" + str(os.getpid())
      self._vm.CreateSnapshot(snapName, self.__doc__)
         ## @todo verify this worked via alternate method 
      self.failUnless(self._vm.IsPoweredOff(),
                       "Verify VM state is off after CreateSnapshot: %s" %                            
                      (self._vm.ReportState()))
      self._vm.RevertToCurrentSnapshot()
      self.failUnless(self._vm.IsPoweredOff(),
   "Verify VM state is off after successful RevertToCurrentSnapshot: %s" %                            
                      (self._vm.ReportState()))
      self._vm.RemoveAllSnapshots()
         ## @todo verify this worked via alternate method          
      self.failUnless(self._vm.IsPoweredOff(),
              "Verify VM is off after successful RemoveAllSnapshots: %s" %
                      (self._vm.ReportState()))
      self.failUnlessRaises("Removing snapshots from powered-off VM should fail.",
                            Vim.Fault.InvalidState, self._vm.RemoveAllSnapshots)
      self.failUnless(self._vm.IsPoweredOff(),
                  "Verify VM is off after failed RemoveAllSnapshots: %s" %
                      (self._vm.ReportState()))

   ## Apply Guest OS related operations 
   # @pre TTTVM2 is registered and in the powered off state
   # @post VM is left in powered off state
   def test3_VerifyGuestVmOps(self):
      vm = self._vm
      self.failUnlessRaises("Resetting guest info on a powered-off VM is not supported.",
                            Vmodl.Fault.NotSupported, self._vm.ResetGuestInformation)
      self.failUnless(self._vm.IsPoweredOff(),
             "Verify VM state is off after ResetGuestInformation: %s" %                            
                      (self._vm.ReportState()))
      self.failUnlessRaises("Shutting down guest in a powered-off VM should fail.",
                            Vim.Fault.InvalidPowerState, self._vm.ShutdownGuest)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after ShutdownGuest: %s" %                            
                      (self._vm.ReportState()))
      self.failUnlessRaises("Rebooting guest in a powered-off VM should fail.",
                            Vim.Fault.InvalidPowerState, self._vm.RebootGuest)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after RebootGuest: %s" %                            
                      (self._vm.ReportState()))
      self.failUnlessRaises("Standby guest in a powered-off VM should fail.",
                            Vim.Fault.InvalidPowerState, self._vm.StandbyGuest)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after StandbyGuest: %s" %                            
                      (self._vm.ReportState()))
      self.failUnlessRaises("Mounting tools in a powered-off VM should fail.",
                            Vim.Fault.InvalidState, self._vm.MountToolsInstaller)
      self.failUnless(self._vm.IsPoweredOff(),
                 "Verify VM state is off after MountToolsInstaller: %s" %
                      (self._vm.ReportState()))
      self.failUnlessRaises("Unmounting tools in a powered-off VM should fail.",
                            Vim.Fault.InvalidState, self._vm.UnmountToolsInstaller)
      self.failUnless(self._vm.IsPoweredOff(),
                "Verify VM state is off after UnmountToolsInstaller: %s" %
                      (self._vm.ReportState()))
      self.failUnlessRaises("Upgrading tools in a powered-off VM should fail.",
                            Vim.Fault.InvalidState,
                            self._vm.UpgradeTools)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after UpgradeTools: %s" %
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
      self.failUnlessRaises("Checking customization spec of a powered-off VM is not supported.",
                            Vmodl.Fault.NotSupported, self._vm.CheckCustomizationSpec, spec)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after CheckCustomizationSpec: %s" %
                      (self._vm.ReportState()))
      self.failUnlessRaises("Customizing powered-off VM is not supported.",
                            Vmodl.Fault.NotSupported, self._vm.Customize, spec)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after Customize: %s" %
                      (self._vm.ReportState()))

   ## Apply VM typing operations 
   # @pre TTTVM1 is registered and in the off state
   # @post VM is left in off state
   def test4_VerifyVmTypeMutability(self):
      vm = self._vm
      self.failUnlessRaises("Marking powered-off VM as template is not supported.",
                            Vmodl.Fault.NotSupported, self._vm.MarkAsTemplate)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after MarkAsTemplate: %s" %
                      (self._vm.ReportState()))
      self.failUnlessRaises("Marking powered-off VM as VM is not supported.",
                            Vmodl.Fault.NotSupported, self._vm.MarkAsVirtualMachine)
      self.failUnless(self._vm.IsPoweredOff(),
                "Verify VM state is off after MarkAsVirtualMachine: %s" %
                      (self._vm.ReportState()))

   ## Apply all VM operations that are "Not Supported"
   # @pre TTTVM1 is registered and in the off state
   # @post VM is left in suspended state
   def test5_VerifyThingsHostdWontDoDirectly(self):
      vm = self._vm
      self.failUnlessRaises("Upgrading powered-off VM should fail.",
                            Vim.Fault.AlreadyUpgraded,
                            self._vm.UpgradeVirtualHardware)
      self.failUnless(self._vm.IsPoweredOff(),
               "Verify VM state is off after UpdateVirtualHardware: %s" %
                      (self._vm.ReportState()))
      self.failUnlessRaises("Migrating powered-off VM is not supported.",
                            Vmodl.Fault.NotSupported, self._vm.Migrate)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after Migrate: %s" %
                      (self._vm.ReportState()))
      spec = Vim.Vm.RelocateSpec()
      self.failUnlessRaises("Relocating powered-off VM is not supported.",
                            Vmodl.Fault.NotSupported, self._vm.Relocate, spec)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after Relocate: %s" %
                      (self._vm.ReportState()))
      ## @todo should Clone() throw NotSupported?
      vmf = self._host.GetFolderOfVMs()
      self.failUnlessRaises("Cloning powered-off VM should fail.",
                            Vmodl.Fault.InvalidRequest, self._vm.Clone,
                            vmf, "TTTVM1-CLONE", None)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after Clone: %s" %
                      (self._vm.ReportState()))

   ## Apply two changes via Reconfiguration function, one no-op, one annotation
   # @pre TTTVM1 is registered and in the off state
   # @post VM is left in off state
   # @todo @see full set of tests just for reconfigure of off VMs
   def test6_VerifyVmReconfig(self):
      cfgspec = Vim.Vm.ConfigSpec()
      self._vm.Reconfigure(cfgspec)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after no-op Reconfigure: %s" %
                      (self._vm.ReportState()))

   ## Apply KVM style operations to VM
   # @pre TTTVM1 is registered and in the off state
   # @post VM is left in off state
   def test7_VerifyKVM(self):
      self.failUnlessRaises("Acquiring mks ticket from powered-off VM should fail.",
                            Vim.Fault.InvalidState, self._vm.AcquireMksTicket)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after AcquireMksTicket: %s" %
                      (self._vm.ReportState()))
      self.failUnlessRaises("Setting screen resolution of a powered-off VM should fail.",
                            Vim.Fault.InvalidState, self._vm.SetScreenResolution, 80, 24)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after SetScreenResolution: %s" %
                      (self._vm.ReportState()))
      
   ## Verify Answer works with off vm that has no question present
   # @pre no question is present on the VM      
   # @post VM is left in off state
   def test8_VerifyAnswer(self):
      # some arbitrary values for arguments to said function
      qid = "1"
      choice = "3"
      self.failUnlessRaises("Asking answer from powered-off VM should fail.",
                            Vmodl.Fault.InvalidArgument, self._vm.Answer, qid, choice)
      self.failUnless(self._vm.IsPoweredOff(),
                      "Verify VM state is off after Answer: %s" %
                      (self._vm.ReportState()))

   ## Verify Unregister takes VM out of host inventory
   # @post VM is left in suspended state
   def test9_VerifyUnregister(self):
      self.failIfRaises(
         "Unregistering the VM should not fail.",
         self._vm.Unregister)


## Run though all VM operations against a Powered Off VM that has
# a guest os and tools 
class TestPoweringOnVM(FixtureCreateDummyVM):
   ## Change VM power states: off -> on -> off
   # @pre none
   # @post VM is powered off state
   # VMQA: vmops/poweron
   #    POS008 PowerOn a single suspended vm from a standalone host
   #    
   def test1_VerifyPowerOffToPowerOn(self):
      self.failIfRaises("Powering on the VM should not fail.", self._vm.PowerOn)
      self.failUnless(self._vm.IsRunning(),
                             "After PowerOn(), VM state should be 'poweredOn': %s"  %
                      (self._vm.ReportState()))
      self.failUnlessRaises("Powering on powered-on VM should fail.",
                            Vim.Fault.InvalidPowerState, self._vm.PowerOn)
      self.failUnless(self._vm.IsRunning(),
                             "After PowerOn(), VM state should be 'poweredOn': %s"  %
                      (self._vm.ReportState()))
      self.failIfRaises("Suspending the VM should not fail.", self._vm.Suspend)
      self.failUnlessRaises("Suspending suspended VM should fail.",
                            Vim.Fault.InvalidPowerState, self._vm.Suspend)
      self.failUnless(self._vm.IsSuspended(),
                             "After PowerOn(), VM state should be 'poweredOn': %s"  %
                      (self._vm.ReportState()))
      self.failIfRaises("Powering on the VM should not fail.", self._vm.PowerOn)
      self.failUnlessRaises("Powering on powered-on VM should fail.",
                            Vim.Fault.InvalidPowerState, self._vm.PowerOn)
      self.failUnless(self._vm.IsRunning(),
                             "After PowerOn(), VM state should be 'poweredOn': %s"  %
                      (self._vm.ReportState()))
      self.failIfRaises("Powering off the VM should not fail.", self._vm.PowerOff)
      self.failUnlessRaises("Powering off powered-off VM should fail.",
                            Vim.Fault.InvalidPowerState, self._vm.PowerOff)
      
# end of tests
