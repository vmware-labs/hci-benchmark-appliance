#!/usr/bin/python
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file case_3.py --
# TestCase 3 verifies VirtualMachine.java API against a powered on VM with
# a guest OS (dsl linux) and VMWare tools (TTTVM2) and 'independent' vdisk

__author__ = "VMware, Inc"

import os
import time
import unittest
import testoob
from pyVim.integtest import FixtureCreateDummyVM
from pyVmomi import Vim, Vmodl
import pyVim.vimhost

## Perform common setup tasks for all derived classes in this module
class FixtureCreateVM(FixtureCreateDummyVM):
   ## Establish a connection to vim managed system under test
   # @pre hostd is operational and crededitials are valid
   # @post _host contains authenticated connection to hostd
   def setUp(self):
      super(FixtureCreateVM, self).setUp()
      self.failIfRaises("Powering on VM should not fail.",
                        self._vm.PowerOn)
      self.failUnless(self._vm.IsRunning(),
                      "VM should be 'poweredOn', it is '%s'"  %
                      (self._vm.ReportState()))


## Run though all VM operations against a Powered On VM that has
# a guest os and tools and independent vdisk
class TestPoweredOnVM(FixtureCreateVM):
   ## Verify Suspend, PowerOn, Reset against a powered on VM with tools
   # XXX NO TOOLS!!!
   def test1_VerifyPowerOffToSuspend(self):
      self.failIfRaises("Suspending powered-on VM should not fail.", self._vm.Suspend)
      self.failUnlessRaises("Suspending suspended VM is expected to raise.",
                            Vim.Fault.InvalidPowerState, self._vm.Suspend)
      self.failUnless(self._vm.IsSuspended(),
                         "After Suspend(), VM state should be 'poweredOn': %s"  %
                      (self._vm.ReportState()))
      self.failIfRaises("Powering on suspended VM should not fail.", self._vm.PowerOn)
      self.failUnlessRaises("Powering on powered-on VM is expected to raise.",
                            Vim.Fault.InvalidPowerState, self._vm.PowerOn)
      self.failUnless(self._vm.IsRunning(),
                         "After PowerOn(), VM state should be 'poweredOn': %s"  %
                      (self._vm.ReportState()))
      self.failIfRaises("Resetting powered-on VM should not fail.", self._vm.Reset)
      self.failIfRaises("Resetting powered-on VM should not fail.", self._vm.Reset)
      self.failUnless(self._vm.IsRunning(),
                         "After Reset() VM should be powered on, got: %s" %
                      (self._vm.ReportState()))

   ## Apply snashot operations to a powered off vm, verify state is not changed
   # @pre TTTVM2 is registered and in the powered off state
   def test2_VerifyBasicSnapshotOps(self):
      vm = self._vm

      try:
         self.failUnlessRaises("Removing all snapshots is expected to raise.",
                               Vim.Fault.InvalidState, self._vm.RemoveAllSnapshots)
         self.failUnless(self._vm.IsRunning(),
            "Verify VM state is on after failed RemoveAllSnapshots: %s" % 
                         (self._vm.ReportState()))
         self.failUnlessRaises("Reverting to current snapshot is expected to raise.",
                               Vim.Fault.NotFound,
                               self._vm.RevertToCurrentSnapshot)
         self.failUnless(self._vm.IsRunning(),
       "Verify VM state is on after failed RevertToCurrentSnapshot: %s" %
                         (self._vm.ReportState()))
         snapName = "TTTtest-" + str(os.getpid())
         self.failUnlessRaises("Creating snapshot is expected to raise.",
                               Vim.Fault.MemorySnapshotOnIndependentDisk,
                               self._vm.CreateSnapshot, snapName, self.__doc__)
         ## @todo verify this failed via alternate method 
         self.failUnless(self._vm.IsRunning(),
                       "Verify VM state is on after CreateSnapshot: %s" %                            
                         (self._vm.ReportState()))
         self.failUnlessRaises("Reverting to current snapshot is expected to raise.",
                               Vim.Fault.NotFound, self._vm.RevertToCurrentSnapshot)
         self.failUnless(self._vm.IsRunning(),
   "Verify VM state is on after successful RevertToCurrentSnapshot: %s" %                            
                         (self._vm.ReportState()))
         self.failUnlessRaises("Removing all snapshots is expected to raise.",
                               Vim.Fault.InvalidState, self._vm.RemoveAllSnapshots)
         ## @todo verify this worked via alternate method          
         self.failUnless(self._vm.IsRunning(),
              "Verify VM is on after successful RemoveAllSnapshots: %s" %
                         (self._vm.ReportState()))
         self.failUnlessRaises("Removing all snapshots is expected to raise.",
                               Vim.Fault.InvalidState, self._vm.RemoveAllSnapshots)
         self.failUnless(self._vm.IsRunning(),
                  "Verify VM is on after failed RemoveAllSnapshots: %s" %
                         (self._vm.ReportState()))
      except AssertionError, msg:
         self.fail("No exception thrown:" + str(msg.args))
      except Exception, msg:
         self.fail("Unexpected Exception:: %s %s" % (repr(msg),
                                                     str(msg.args)))
   ## Apply Guest OS related operations 
   # @pre TTTVM2 is registered and in the powered on state
   def test3_VerifyGuestVmOps(self):
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
      self.failUnlessRaises("Checking customization spec is not supported and expected to raise.",
                            Vmodl.Fault.NotSupported, self._vm.CheckCustomizationSpec, spec)
      self.failUnless(self._vm.IsRunning(),
                      "Verify VM state is on after CheckCustomizationSpec: %s" %
                      (self._vm.ReportState()))
      self.failUnlessRaises("Customizing the spec is not supported and expected to raise.",
                            Vmodl.Fault.NotSupported, self._vm.Customize, spec)
      self.failUnless(self._vm.IsRunning(),
                      "Verify VM state is on after Customize: %s" %
                      (self._vm.ReportState()))

      self.failUnlessRaises("Resetting guest information is not supported and expected to raise.",
                            Vmodl.Fault.NotSupported, self._vm.ResetGuestInformation)
      self.failUnless(self._vm.IsRunning(),
             "Verify VM state is on after ResetGuestInformation: %s" %                            
                      (self._vm.ReportState()))

      self.failUnlessRaises("Unmounting tools while the disk is not mounted is expected to raise.",
                            Vim.Fault.InvalidState, self._vm.UnmountToolsInstaller)
      self._vm.MountToolsInstaller()
      self._vm.MountToolsInstaller()
      self.failUnlessRaises("Unmounting tools is expected to raise.",
                            Vim.Fault.InvalidState, self._vm.UnmountToolsInstaller)
      self.failUnlessRaises("Upgrading tools is expected to raise.",
                            Vmodl.Fault.NotSupported, self._vm.UpgradeTools)
      self.failUnlessRaises("Upgrading tools is expected to raise.",
                            Vmodl.Fault.NotSupported, self._vm.UpgradeTools)
      while not self._vm.IsVMToolsRunning(): # @todo code self._vm.WaitForTools() (task.WaitForStateChange)
         print "INFO: waiting for tools"
         time.sleep(1)
      self.failUnless(self._vm.IsVMToolsRunning(),"VM Tools must be running")
      self._vm.StandbyGuest()
      self.failUnlessRaises("Standby while guest is in standby state is expected to raise.",
                            Vim.Fault.InvalidPowerState, self._vm.StandbyGuest)
      self.failUnless(self._vm.self._vm.IsSuspended(),"Verify VM state is standby after StandbyGuest(): %s" %
                      (self._vm.ReportState()))
      self.failUnless(not self._vm.IsVMToolsRunning(),"Guest heartbeat should not be green")
      self._vm.PowerOn()
      while not self._vm.IsVMToolsRunning(): # @todo code self._vm.WaitForTools() (task.WaitForStateChange)
         print "INFO: waiting for tools"
         time.sleep(1)
      self.failUnless(self._vm.IsRunning(),"Verify VM power state is on after PowerOn: %s" %
                      (self._vm.ReportState()))
      self.failUnless(self._vm.IsVMToolsRunning(),"Guest heartbeat shoul be green")

##       self._vm.ShutdownGuest()
##       self._vm.ShutdownGuest()
##       while not self._vm.IsVMToolsRunning():
##          time.sleep(1)
##       self.failUnless(self._vm.IsVMToolsRunning(),"VM Tools must be running")
##       self._vm.PowerOn()
##       self._vm.RebootGuest()
      
      self.failUnless(self._vm.IsRunning(),
                      "Verify VM state is on after UpgradeTools: %s" %
                      (self._vm.ReportState()))
      
# end of tests

