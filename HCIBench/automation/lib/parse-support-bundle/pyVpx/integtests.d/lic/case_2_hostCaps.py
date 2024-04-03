#!/usr/bin/python
# Copyright 2008 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file case_2_hostCaps.py --
# TestCase 2 verifies hostCapabilities object returns values
#   that change if license with VSMP attribute is set

__author__ = "VMware, Inc"

from pyVim import integtest
from pyVmomi import Vmodl
import pyVim.vimhost

## Perform common setup tasks for all derived classes in this module
class FixtureLIC(integtest.TestCase):
   ## Establish a connection to vim managed system under test
   # @pre hostd is operational and crededitials are valid
   # @post _host contains authenticated connection to hostd
   def setUp(self):
      self._host = pyVim.vimhost.Host()
      self.failIf(self._host is None, "Connect and Login to hostd")
      self._hs = self._host.GetHostSystem()
      self.failIf(self._hs is None, "Retrieve HostSystem")
   def tearDown(self):
      self._host = None
      self._hs = None      

class TestLicenseManager(FixtureLIC):
   # @todo these values are what shows up if no license is set
   def test1_VerifyDefaultCapValues(self):
      self._cap = self._hs.GetCapability()
      self.failIf(self._cap is None, "Retrieve HostSystem Capability")
      cap = self._cap
      print "GetCapability returned = ", cap
      # these two are hard coded in haHost.cpp, overwritten...
      # self.failUnless(cap.maxSupportedVcpus == 1, "maxSupportedVcpus == 1")
      self.failUnless(cap.maxSupportedVMs == 1200, "maxSupportedVMs == 1200")
      # these are setup by License Manager...
      self.failUnless(cap.maxRunningVMs == 0, "maxRunningVMs == 0")
      # these default to true on esx or false on wgs
      #self.failUnless(cap.sanSupported is True, "sanSupported == false")
      #self.failUnless(cap.nfsSupported is True, "nfsSupported == true")
      #self.failUnless(cap.iscsiSupported is True, "iscsiSupported == true")
