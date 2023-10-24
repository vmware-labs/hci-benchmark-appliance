#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential
#
## @file nfc/case_2.py --
#
# TestCase 1 verify nfcsvc protocol operations
#  Assumes: TTTVM2 is registered and is not powered on, vmx file is 854 bytes
# 
#  NfcLib protocol API functions tested using per VM and per Data store tickets
#   TCP/IPv4 Connect/disconnect to hostd's nfclib via authd using ticket
#   PUT [force]
#   GET
#   RENAME
#   DELETE
#   

__author__ = "VMware, Inc"

import pdb
import os
from stat import *
import pyVmomi
import nfclib
from case_1 import FixtureNFC

class NfcFunctionTest(FixtureNFC):
   def test1_VerifyNfcSessionSetupAndShutdown(self):
      self._ds = self._host.GetDS().GetSummary().GetDatastore()
      self.failUnless(self._ds is not None, "Using datastore:[%s]" % \
                      (self._host.GetDS().GetSummary().GetName()))
      tkt = self._nfc.FileManagement(self._ds, None)
      self.failUnless(tkt is not None)
      self.failUnless(isinstance(tkt, pyVmomi.Vim.HostServiceTicket),
      "FileManagement() returns: pyVmomi.Vim.HostServiceTicket, got\'%s\'"  %
                            (str(tkt)))
      print str(tkt)
      nfc = pyVim.nfclib.NfcClient(tkt)
      self.failIf(nfc.Connect() is False, "Connecting to nfclib via authd")
      self.failIf(nfc.Disconnect() is False, "Dropping connection to nfclib")
      newNfc = pyVim.nfclib.NfcClient(tkt)
      # @todo presently a second connect will even after ticket is already been used
      # self.failIf(newNfc.Connect() is True,
      #            "Connecting to nfclib via authd with used ticket should fail")


   # Verify original get VMX file works
   # @post created TTTVM2.vmx to current working directory   
   def test2_VerifyNfcVmGetOperation(self):
      self._vm = self._host.GetVM(self._vmname)
      self.failIf(self._vm is None,
                  "Retrieve a VM named %s on host %s to run tests against" % 
                  (self._vmname,self._host.GetName()))
      tkt = self._nfc.GetVmFiles(self._vm._mo, None)
      self.failUnless(tkt is not None, "Checking results from GetVmFiles")
      self.failUnless(isinstance(tkt, pyVmomi.Vim.HostServiceTicket),
      "Expecting GetVmFiles rc = pyVmomi.Vim.HostServiceTicket, got\'%s\'"  %
                            (str(tkt)))
      print str(tkt)
      nfc = pyVim.nfclib.NfcClient(tkt)
      self.failIf(nfc.Connect() is False, "Connecting to nfclib via authd")
      fileset = []
      local = 0
      remote = 1
      vmxNames = self.GenerateFullDSPath(self._vmname, ".vmx")
      fileset.append((vmxNames[remote], vmxNames[local]))
      if os.path.exists(vmxNames[local]):
         print "Deleting local file %s" % (vmxNames[local])
         os.unlink(vmxNames[local])
      self.failUnless(nfc.GetFiles(fileset),
                      "expecting nfc.GetFiles() to return true");
      self.failIf(nfc.Disconnect() is False,
                  "Dropping connection to nfclib")
      # verify the file we received is what we expect
      self.failUnless(os.path.exists(vmxNames[local]),
                      "Checking we got file %s" % \
                      vmxNames[local])
      fsize = 854L
      self.failUnless((self.FileSize(vmxNames[local]) == fsize),
                      "Checking file size is %d" % \
                      fsize)


   # Verify original get VMX file works
   # @post created TTTVM2.vmx to current working directory   
   def test3_VerifyNfcVmPutOperation(self):
      self._vm = self._host.GetVM(self._vmname)
      self.failIf(self._vm is None,
                  "Retrieve a VM named %s on host %s to run tests against" % 
                  (self._vmname,self._host.GetName()))
      tkt = self._nfc.PutVmFiles(self._vm._mo, None)
      self.failUnless(tkt is not None, "Checking results from GetVmFiles")
      self.failUnless(isinstance(tkt, pyVmomi.Vim.HostServiceTicket),
      "Expecting GetVmFiles rc = pyVmomi.Vim.HostServiceTicket, got\'%s\'"  %
                            (str(tkt)))
      print str(tkt)
      nfc = pyVim.nfclib.NfcClient(tkt)
      self.failIf(nfc.Connect() is False, "Connecting to nfclib via authd")
      fileset = []
      vmxNames = self.GenerateFullDSPath(self._vmname, ".vmx")
      fileset.append(vmxNames)
      local = 0      
      self.failUnless(os.path.exists(vmxNames[local]),
                 "Checking local file %s exists" % (vmxNames[local]))
      self.failUnless(nfc.PutFiles(fileset,nfc.NFC_CREATE_OVERWRITE),
                      "expecting nfc.PutFiles() to return true");
      self.failIf(nfc.Disconnect() is False,
                  "Dropping connection to nfclib")
      # @todo Need to add tests for GetFileWithPassword and 
      #       LocalCopyWithPassword

   
   # rname the vmx file 2x
   def test4_VerifyNfcRenameFunction(self):
      self._dsName = "[" + self._host.GetDS().GetSummary().GetName() +  "]"
      self._ds = self._host.GetDS().GetSummary().GetDatastore()
      self.failUnless(self._ds is not None, "Using datastore:[%s]" % \
                      (self._dsName))
      tkt = self._nfc.FileManagement(self._ds, None)
      self.failUnless(tkt is not None, "Verify ticket is returned")
      self.failUnless(isinstance(tkt, pyVmomi.Vim.HostServiceTicket),
      "ExpectingFileManagement() to return \
pyVmomi.Vim.HostServiceTicket, got\'%s\'" % \
                            (str(tkt)))
      nfc = pyVim.nfclib.NfcClient(tkt)
      self.failIf(nfc.Connect() is False, "Connecting to nfclib via authd")
      fileset = []
      remote = 1
      vmxNames = self.GenerateFullDSPath(self._vmname, ".vmx")
      chgStr = "-changed"      
      newVmxName = vmxNames[remote] + chgStr
      fileset.append((vmxNames[remote], newVmxName))
      fileset.append((newVmxName, vmxNames[remote]))      
      self.failUnless(nfc.RenameFiles(fileset),
                      "expecting nfc.RenameFiles() to return true");
      self.failIf(nfc.Disconnect() is False,
                  "Dropping connection to nfclib")


   def test5_VerifyNfcRenameFunction(self):
      self._dsName = "[" + self._host.GetDS().GetSummary().GetName() +  "]"
      self._ds = self._host.GetDS().GetSummary().GetDatastore()
      self.failUnless(self._ds is not None, "Using datastore:[%s]" % \
                      (self._dsName))
      tkt = self._nfc.FileManagement(self._ds, None)
      self.failUnless(tkt is not None, "Verify ticket is returned")
      self.failUnless(isinstance(tkt, pyVmomi.Vim.HostServiceTicket),
      "ExpectingFileManagement() to return \
pyVmomi.Vim.HostServiceTicket, got\'%s\'" % \
                            (str(tkt)))
      nfc = pyVim.nfclib.NfcClient(tkt)
      self.failIf(nfc.Connect() is False, "Connecting to nfclib via authd")
      fileset = []
      remote = 1
      local = 0            
      vmxNames = self.GenerateFullDSPath(self._vmname, ".vmx")
      fileset.append(vmxNames)
      self.failUnless(os.path.exists(vmxNames[local]),
                 "Checking local file %s exists" % (vmxNames[local]))
      self.failUnless(nfc.DeleteFiles([vmxNames[remote]]),
                      "expecting nfc.DeleteFiles() to return true");
      self.failUnless(nfc.PutFiles(fileset),
                      "expecting nfc.PutFiles() to return true");
      self.failIf(nfc.Disconnect() is False,
                  "Dropping connection to nfclib")


   # @pre pathname is regular file
   # @return size of pathname   
   def FileSize(self,
                pathname):
      sb = os.stat(pathname)
      if not S_ISREG(sb[ST_MODE]):
         raise Exception, "Expecting a regular file for '%s'" % (pathname)
      return sb[ST_SIZE]


   # given VM name and file extention construct filenames for a get/put command
   # @return ('DStoreName path/file.ext', 'vmname.ext')
   def GenerateFullDSPath(self,
                          vmname,
                          fileExt):
      cfgExt = fileExt
      localFile = vmname + cfgExt
      # assume disk is vmdk and config file is in same directory
      key, backing = self.GetADiskKeyAndDSPath(self._vmname)
      self.failIf(backing is None, "Getting disk backing and id")
      diskFile = backing.GetFileName()
      self.failIf(diskFile is None, "Getting path to disk file")
      diskExt = '.vmdk'
      remoteFile = diskFile[0:diskFile.find(diskExt)] + cfgExt
      return (localFile, remoteFile)

