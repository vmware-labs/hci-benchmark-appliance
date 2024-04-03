#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential
#
## @file nfc/case_1.py --
#
# TestCase 1 Verify the NfcService Interface returns proper tickets
#
# ESX 3.0's NfcService this API has these functions:
#   GetVmFiles
#   PutVmFiles
#   RandomAccessOpen
#   RandomAccessOpenReadOnly
#   FileManagement  (new in 3.1)

__author__ = "VMware, Inc"

import os
import pyVmomi
from pyVim.vimhost import Host
from pyVim.integtest import FixtureCreateDummyVM

class FixtureNFC(FixtureCreateDummyVM):
   ## Obtain Nfc Interface from peer
   # This VM should not be powered on and it should have at least one disk
   def setUp(self):
      super(FixtureNFC, self).setUp()
      self._host = Host()
      self._nfc = self._host.GetNfcService()
      self._nfcSvc = "nfc"
      self._nfcVer = "1.1"

   def tearDown(self):
      super(FixtureNFC, self).tearDown()
      self._nfc = None
      self._nfcSvc = None
      self._nfcVer = None

   # return tuple of (key, Datastore Path) for first disk found
   def GetADiskKeyAndDSPath(self,
                          vmname):
      hw = self._vm.GetConfig().GetHardware()
      if hw is None:
         raise Exception, "No hardare for vm %s" % (vmname)
      devices = hw.GetDevice()
      for item in devices:
         if isinstance(item, pyVmomi.Vim.Vm.Device.VirtualDisk):
            key = item.GetKey()
            backing = item.GetBacking()
            return (key, backing)
      raise Exception, "No vm %s has no disk" % (vmname)


## Check that we get the right object type and that all methods exist
#
class NfcTicketTest(FixtureNFC):
   def test1_VerifyNfcServiceInterface(self):
      try:
         if self._nfc is None:
            self.fail("Expecting GetNfcService to not return a null object")
         else:
            self.failUnless(isinstance(self._nfc, pyVmomi.Vim.NfcService),
  "Expecting _nfc instance type to be: pyVmomi.Vim.NfcService, got \'%s\'"  %
                            (str(self._nfc)))
      except Exception, msg:
         self.fail("Unexpected Exception raised during XXX : %s" %         
                   (str(msg)))


   def test2_VerifyFileMgmtTicket(self):
      self._ds = self._host.GetDS().GetSummary().GetDatastore()
      self.failUnless(self._ds is not None, "Using datastore:[%s]" % \
                      (self._host.GetDS().GetSummary().GetName()))
      tkt = self._nfc.FileManagement(self._ds, None)
      self.failUnless(tkt is not None, "checking results from FileManagement")
      self.failUnless(isinstance(tkt, pyVmomi.Vim.HostServiceTicket),
      "Expecting FileManagement rc = pyVmomi.Vim.HostServiceTicket, got\'%s\'"  %
                            (str(tkt)))
      print str(tkt)
      self.CheckTicketValues(tkt)
      

   def test3_VerifyGetVmFilesTicket(self):
      self.failIf(self._vm is None,
                  "Retrieve a VM named %s on host %s to run tests against" % 
                  (self._vmname,self._host.GetName()))
      self.failUnless(self._vm.IsPoweredOff(), 
                      "Verify initial VM state is powered off: %s" %
                      (self._vm.ReportState()))
      tkt = self._nfc.GetVmFiles(self._vm._mo, None)
      self.failUnless(tkt is not None, "Checking results from GetVmFiles")
      self.failUnless(isinstance(tkt, pyVmomi.Vim.HostServiceTicket),
      "Expecting FileManagement rc = pyVmomi.Vim.HostServiceTicket, got\'%s\'"  %
                            (str(tkt)))
      print str(tkt)
      self.CheckTicketValues(tkt)

   def test4_VerifyPutVmFilesTicket(self):
      self.failUnless(self._vm.IsPoweredOff(), 
                      "Verify initial VM state is powered off: %s" %
                      (self._vm.ReportState()))
      self.failIf(self._vm is None,
                  "Retrieve a VM named %s on host %s to run tests against" % 
                  (self._vmname,self._host.GetName()))
      tkt = self._nfc.PutVmFiles(self._vm._mo, None)
      self.failUnless(tkt is not None, "Checking results from PutVmFiles")
      self.failUnless(isinstance(tkt, pyVmomi.Vim.HostServiceTicket),
      "Expecting FileManagement rc = pyVmomi.Vim.HostServiceTicket, got\'%s\'"  %
                            (str(tkt)))
      print str(tkt)
      self.CheckTicketValues(tkt)

   def test5_VerifyRandomAccessOpenTicket(self):
      # how to get this number from vim
      self._diskDeviceKey, backing = self.GetADiskKeyAndDSPath(self._vmname)
      self.failIf(self._vm is None,
                  "Retrieve a VM named %s on host %s to run tests against" % 
                  (self._vmname,self._host.GetName()))
      tkt = self._nfc.RandomAccessOpen(self._vm._mo, self._diskDeviceKey, None)
      self.failUnless(tkt is not None,
                      "Checking results from RandomAccessOpen(%s)" % (self._vmname)) 
      self.failUnless(isinstance(tkt, pyVmomi.Vim.HostServiceTicket),
      "Expecting FileManagement rc = pyVmomi.Vim.HostServiceTicket, got\'%s\'"  %
                            (str(tkt)))
      print str(tkt)
      self.CheckTicketValues(tkt)

   def test6_VerifyRandomAccessOpenReadonlyTicket(self):
      # how to get this number from vim
      self._diskDeviceKey, backing = self.GetADiskKeyAndDSPath(self._vmname)
      self.failIf(self._vm is None,
                  "Retrieve a VM named %s on host %s to run tests against" % 
                  (self._vmname,self._host.GetName()))
      tkt = self._nfc.RandomAccessOpenReadonly(self._vm._mo, self._diskDeviceKey, None)
      self.failUnless(tkt is not None,
                      "Checking results from RandomAccessOpen(%s)" % (self._vmname)) 
      self.failUnless(isinstance(tkt, pyVmomi.Vim.HostServiceTicket),
      "Expecting FileManagement rc = pyVmomi.Vim.HostServiceTicket, got\'%s\'"  %
                            (str(tkt)))
      print str(tkt)
      self.CheckTicketValues(tkt)

      
   def CheckTicketValues(self,
                         tkt):
      # self.failUnless(tkt.GetHost() is not None, "Checking host")
      # self.failUnless(tkt.GetPort() is not None, "Checking port")
      self.failUnless(tkt.GetService() == self._nfcSvc,
                      "Checking service is %s" % (self._nfcSvc))
      self.failUnless(tkt.GetServiceVersion() == self._nfcVer,
                      "Checking version is %s" % (self._nfcVer))
      self.failUnless(len(tkt.GetSessionId()) > 0, "Checking sessionId > 0")
      # @todo keep list of ticket values seen, report duplicates 
      
# @todo write more tests
# create as many tickets until failure
# pass in bad arguments for VM, DS (try None, Folders, etc)
   
