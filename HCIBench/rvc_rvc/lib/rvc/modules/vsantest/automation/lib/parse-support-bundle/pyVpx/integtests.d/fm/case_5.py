#!/usr/bin/python
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file case_5.py --
# TestCase 5 verifies FileManager Delete function works

__author__ = "VMware, Inc"

import os
import unittest
import testoob
from pyVmomi import Vim
from pyVmomi import Vmodl
import pyVim.vimhost
import random
from case_1 import FixtureFM

class TestFileManagerDelete(FixtureFM):
   def test1_VerifyDeleteFile(self):
      # see case_3/test1 which left this file 
      dstFile = os.path.join(self._fileSys, 'motd.bak')
      self.failIfRaises("Deleting a file should not raise.",
                        self.DeleteFunc, dstFile, self._ftFile)
      # setup for subsequent runs for next run
      srcFile = '/etc/motd'
      dstFile = os.path.join(self._fileSys, 'motd.bak')
      self.CopyFunc(srcFile, dstFile, "regular", True, self._ftFile)

   def test2_VerifyDeleteDirectory(self):
      fm = self._fm      
      # see case_4/test2 which verified mkdir will work
      newpath = os.path.join(self._srcDspath, "empytDir")
      self.failIfRaises("Creating a directory should not raise.",
                        fm.MakeDirectory, self._dctr, newpath, True)
      self.failIfRaises("Deleting a directory should not raise.",
                        self.DeleteFunc, newpath, self._ftFile)
   
   def test3_VerifyDeleteDisk(self):
      fm = self._fm
      srcFile = self.GetTestDiskPathName()
      (head, tail) = os.path.split(srcFile)
      dstFile = os.path.join(self._fileSys, tail)
      # see case_3/test3 which left this file       
      self.failIfRaises("Deleting a disk should not raise.",
                        fm.Delete, self._dctr, dstFile, self._ftDisk)
      self.CopyFunc(srcFile, dstFile, "VirtualDisk", True, self._ftDisk)

# end of case_5.py
