#!/usr/bin/python
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file case_3.py --
# TestCase 3 verifies FileManager Copy function works
# Assumes /etc/motd file exists

__author__ = "VMware, Inc"

import os
from case_1 import FixtureFM

class TestFileManagerCopy(FixtureFM):
   def test1_VerifyCopyFile(self):
      srcFile = '/etc/motd'
      dstFile = os.path.join(self._fileSys, 'motd.bak')
      self.CopyFunc(srcFile, dstFile, "regular", True, self._ftFile)
      # test force option      
      self.CopyFunc(srcFile, dstFile, "regular", True, self._ftFile)
      self.failUnlessRaises("Copying should not overwrite existing file and is expected to raise.",
                            Vim.Fault.FileAlreadyExists,
                            self.CopyFunc, srcFile, dstFile,
                            "regular", False, self._ftFile)

   def test2_VerifyCopyDirectory(self):
      srcFile = '/var/cache'
      dstFile = '/var/cache.bak'
      self.failUnlessRaises("Copying directory is not implemented and is expected to raise.",
                            Vmodl.Fault.NotImplemented,
                            self.CopyFunc, srcFile, dstFile,
                            "directory", False, self._ftFile)
      self.failUnlessRaises("Repeating the above step is expected to raise again.",
                            Vmodl.Fault.NotImplemented,
                            self.CopyFunc, srcFile, dstFile,
                            "directory", False, self._ftFile)

   # @post a copy of dst file exists in _fileSys,
   # that is used by the delete disk test see case_5.py
   def test3_VerifyCopyDisk(self):
      srcFile = self.GetTestDiskPathName()
      (head, tail) = os.path.split(srcFile)
      dstFile = os.path.join(self._fileSys, tail)
      self.CopyFunc(srcFile, dstFile, "VirtualDisk", True, self._ftDisk)
      # test force option works
      self.failUnlessRaises("Copying over the existing virtual disk is expected to raise.",
                            Vim.Fault.FileAlreadyExists,      
                            self.CopyFunc, srcFile, dstFile,
                            "VirtualDisk", False, self._ftDisk)

   def test4_VerifyCopyDiskError(self):
      srcFile = '/etc/motd'
      dstFile = '/etc/motd.bak'
      self.failUnlessRaises("Copying an invalid virtual disk is expected to raise.",
                            Vmodl.Fault.InvalidArgument,
                            self.CopyFunc, srcFile, dstFile,
                            "VirtualDisk", False, self._ftDisk)
      
  # @todo test that sparse files are copied correctly
  
# end of case_3.py

