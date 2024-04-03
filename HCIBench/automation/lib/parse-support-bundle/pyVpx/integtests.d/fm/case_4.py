#!/usr/bin/python
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file case_4.py --
# TestCase 4 verifies FileManager MakeDirectory function works

__author__ = "VMware, Inc"

import os
import unittest
import testoob
from pyVmomi import Vim
from pyVmomi import Vmodl
import pyVim.vimhost
import random
from case_1 import FixtureFM


class TestFileManagerMkdir(FixtureFM):
   def test1_VerifyMkdirNoForceError(self):
      fm = self._fm
      dstPath = os.path.join(self._srcDspath, str(random.random()))
      self.failUnlessRaises("One of the parent directories doesn't exist, mkdir is expected to raise.",
                            Vim.Fault.FileNotFound,
                            fm.MakeDirectory,
                            self._dctr, dstPath, False)
      self.failUnlessRaises("Make sure previous attempt to create a directory failed. This one should too.",
                            Vim.Fault.FileNotFound,
                            fm.MakeDirectory,
                            self._dctr, dstPath, False)
   
   def test2_VerifyMkdirForceWorks(self):
      fm = self._fm
      newpath = os.path.join(self._srcDspath, "some")
      newpath = os.path.join(newpath, "other")
      newpath = os.path.join(newpath, "dir")
      # sadly mkdir API in vim is not idempotent!
      self.failIfRaises("Force mkdir should not raise.",
                        fm.MakeDirectory, self._dctr, newpath, True)
      self.failUnlessRaises("Mkdir of the directory that already exists is expected to fail.",
                            Vim.Fault.FileAlreadyExists,
                            fm.MakeDirectory,
                            self._dctr, newpath, True)

   def test3_VerifyMkdirNoForceWorks(self):
      fm = self._fm
      newpath = os.path.join(self._srcDsbase, "case4_test3" + str(random.random()))
      self.failIfRaises("Non-force mkdir should not raise.",
                        fm.MakeDirectory,
                        self._dctr, newpath, False)

   # @todo def test4_VerifyMkdirMaxPath(self):
   # @todo def test5_VerifyLegalCharsInPathName(self):

# end of case_4.py
