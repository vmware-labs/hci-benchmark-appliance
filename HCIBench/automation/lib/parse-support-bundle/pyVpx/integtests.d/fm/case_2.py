#!/usr/bin/python
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file case_2.py --
# TestCase 2 verifies FileManager Move function works
#      

__author__ = "VMware, Inc"

import os
from case_1 import FixtureFM

def debugListFile(file):
   if os.getenv('VERBOSE'): os.system("ls -l %s" % file)

class LocalTestFile:
   @staticmethod
   def getTempFile():
      from tempfile import NamedTemporaryFile
      tempFile = NamedTemporaryFile()
      f = LocalTestFile(tempFile.name)
      f.tempFile = tempFile
      return f

   @staticmethod
   def exists(name):
      return os.path.exists(name)

   def __init__(self, name):
      self.name = name

   def close(self):
      if hasattr(self, 'tempFile') and self.tempFile and hasattr(self.tempFile, 'close'):
         self.tempFile.close()

class TestFileManagerMove(FixtureFM):
   def setUp(self):
      FixtureFM.setUp(self)

      # By changing the following line to point to a different file
      # implementation (e.g.: RemoteTestFile), you can
      # change the behavior of the tests.
      fileFuncs = LocalTestFile

      self.getTempFile = fileFuncs.getTempFile
      self.exists = fileFuncs.exists

   def test_RenameLocalFile(self):
      try:
         tmpFile = self.getTempFile()
         self.failIf(tmpFile is None, "Get a temporary file")

         srcName = tmpFile.name
         dstName = tmpFile.name + ".bak"
         debugListFile(srcName)
         self.failUnless(self.exists(srcName), "Source file exists")

         self.MoveFunc(srcName, dstName, self._ftFile)
         debugListFile(dstName)
         self.failIf(self.exists(srcName))
         self.failUnless(self.exists(dstName), "Destination file exists")

         (srcName, dstName) = (dstName, srcName)

         self.MoveFunc(srcName, dstName, self._ftFile)
         debugListFile(dstName)
         self.failIf(self.exists(srcName), "Source file shouldn't exist after move")
         self.failUnless(self.exists(dstName), "Destination file should exist after move")
      finally:
         if tmpFile is not None: tmpFile.close()

   def test1_VerifyFileRename(self):
      srcFile = '/etc/motd'
      dstFile = '/etc/motd.bak'
      self.MoveFunc(srcFile, dstFile, self._ftFile)

   def test2_VerifyDirectoryRename(self):
      srcFile = '/var/cache'
      dstFile = '/var/cache.bak'
      self.MoveFunc(srcFile, dstFile, self._ftFile)

   def test3_VerifyDiskRename(self):
      srcFile = self.GetTestDiskPathName()
      (head, tail) = os.path.split(srcFile)
      dstFile = os.path.join(head, "bak-" + tail)
      self.MoveFunc(srcFile, dstFile, self._ftDisk)

   def test4_VerifyMoveFile(self):
      srcFile = '/etc/motd'
      dstFile = os.path.join(self._fileSys, 'motd.bak')
      self.MoveFunc(srcFile, dstFile, self._ftFile)

   def test5_VerifyMoveDirectory(self): # move a dir across filesystems
      srcFile = '/var/cache'
      dstFile = os.path.join(self._fileSys, 'cache.bak')
      # @todo fix nfc, it leaves an empty file in the destination when it should not
      import pyVim, pyVmomi
      self.failUnlessRaises("Verify that moving directory across filesystems is not implemented.",
                            pyVmomi.Vmodl.Fault.NotImplemented,
                            self.MoveFunc, srcFile, dstFile, self._ftFile)

   def test6_VerifyMoveDisk(self):
      srcFile = self.GetTestDiskPathName()
      (head, tail) = os.path.split(srcFile)
      dstFile = os.path.join(self._fileSys, tail)
      try:
         print "Moving disk %s -> %s" % (srcFile, dstFile)         
         self.MoveFunc(srcFile, dstFile, self._ftDisk)
      except AssertionError, msg:
         print "Moving disk %s -> %s" % (srcFile, dstFile)
         srcFile = os.path.join(head, "bak-" + tail)
         self.MoveFunc(srcFile, dstFile, self._ftDisk)
         
# end of case_2.py
