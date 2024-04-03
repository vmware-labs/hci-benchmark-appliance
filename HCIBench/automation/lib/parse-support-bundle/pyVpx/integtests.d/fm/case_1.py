#!/usr/bin/python
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential

"""
Test Case 1 verifies that the FileManager interface exists and that it
has all the methods specified in the vmodl.
"""

__name__ = "FileManager Test Case 1"
__author__ = "VMware, Inc"

import os
import pyVim
import pyVim.fm
import pyVim.vimhost
from pyVim.integtest import FixtureCreateDummyVM
from pyVmomi import Vim
import random


## Perform common setup tasks for all derived classes in this module
class FixtureFM(FixtureCreateDummyVM):
   ## Establish a connection to vim managed system under test
   # @pre hostd is operational and crededitials are valid
   # @post _host contains authenticated connection to hostd
   def setUp(self):
      super(FixtureFM, self).setUp()
      self._host = pyVim.vimhost.Host()
      self.failIf(self._host is None, "Connect and Login to hostd")
      self._dctr = self._host.GetDatacenter()
      self.failIf(self._dctr is None, "Obtain datacenter managed entity")
      self._fm = self._host.GetFileManager()
      self.failIf(self._fm is None,
                  "Retrieve a File Manager Interface on host %s to run tests against" % 
                  (self._host.GetName()))
      # Note: we use /var/log/vmware path since that is known to be a separate
      # filesystem on ESX hosts, now why wasn't it simply '/var' -- don't know!
      self._fileSys = "/var/log/vmware"

      # these two strings are from FileManager.java IDL FileType enum
      self._ftFile = 'File'
      self._ftDisk = 'VirtualDisk'
      self._srcDsbase = "/tmp/integtests/"
      self._srcDspath = os.path.join(self._srcDsbase, "tt_srcPath" + str(random.random()))
      self._dstDspath = os.path.join(self._srcDsbase, "tt_srcPath" + str(random.random()))      

   ## Drops connection to host 
   #      
   def tearDown(self):
      super(FixtureFM, self).tearDown()
      self._host = None
      self._dctr = None
      self._fm = None
      self._ftFile = None
      self._ftDisk = None

   def GetTestDiskPathName(self):
      diskType = 'vim.vm.device.VirtualDisk'
      vm = self._vm
      self.failIf(vm is None, "Get path to virtual disk for VM %s" \
                  %(self._vmname))
      hw = vm.GetConfig().GetHardware()
      if hw is None:
         self.fail("No hardware for vm %s" % (vmname))
      devices = hw.GetDevice()
      for item in devices:
         if isinstance(item, Vim.vm.device.VirtualDisk):
            key = item.GetKey()
            backing = item.GetBacking()
            if backing is not None:
               return backing.GetFileName()
      self.fail("Vm %s was expected to have at least one disk" % (vmname))

   ##
   # move srcFile to dstFile and report its type as typeF in the log
   # if first move fails, swap src and dest and try again (idempotent)
   #
   def MoveFunc(self,
                srcFile,
                dstFile,
                typeF,
                force = True):
      try:
         pyVim.fm.Move(self._host,
                       self._dctr, srcFile,
                       None, dstFile,
                       force, typeF)
      except Vim.Fault.FileFault, msg:
         print "Move() threw \"%s\", trying switching src and dst..." % (str(msg))
         try:
            (srcFile, dstFile) = (dstFile, srcFile)
            pyVim.fm.Move(self._host,
                          self._dctr, srcFile,
                          None, dstFile,
                          force, typeF)
            print "Move() %s file %s -> %s worked" % (typeF, srcFile, dstFile)
         except Vim.Fault.FileFault, msg:
            self.fail("Move() %s failed using src/dst file %s <-> %s" % \
                      (typeF, dstFile, srcFile))

   ##
   # copy srcFile to dstFile or dstFile to srcFile
   # and report its type as typeF in the log
   #
   def CopyFunc(self,
                srcFile,
                dstFile,
                typeF,
                force,
                fType):
      pyVim.fm.Copy(self._host,
                    self._dctr, srcFile,
                    None, dstFile,
                    force, typeF)
      print "Copy %s file %s -> %s" % (typeF, srcFile, dstFile)

   def DeleteFunc(self,
                  pathName,
                  fType):
      pyVim.fm.Delete(self._host,
                      self._dctr, srcFile,
                      force, typeF)
      print "Delete %s type: %s" % (pathName, fType)

class TestFileManagerExists(FixtureFM):
   def test1_VerifyFMExists(self):
      fm = self._fm
      self.failUnless(isinstance(fm, Vim.FileManager),
                      "Expecting _fm instance type to be: Vim.FileManager, got \'%s\'"  %
                      (str(fm)))


# end of case_1.py
