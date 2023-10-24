#!/usr/bin/env python

"""
Copyright 2011-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

Unit test for ManagedMethodExecuter implementation
"""
__author__ = "VMware, Inc"

from . import PathCommon
from . import StubsCommon

import unittest
from pyVmomi import vmodl, ManagedMethodExecuterHelper, Differ
from pyJack.pyMo.vim.ManagedMethodExecuter import RegisterManagedMethodExecuter

mmeMoId = "ha-managed-method-executer-python"

class TestVimManagedMethodExecuter(unittest.TestCase):

   RegisterManagedMethodExecuter(mmeMoId)
   ## Setup
   #
   def setUp(self):
      self.stub = StubsCommon.GetStub(self, "vim.version.version9")
      self.moId = mmeMoId

   ## tearDown
   #
   def tearDown(self):
      pass

   ## test for negative values
   #
   def testBogusArguments(self):
      mme = vmodl.reflect.ManagedMethodExecuter(self.moId, self.stub)
      mmeHelper = ManagedMethodExecuterHelper.MMESoapStubAdapter(mme)
      dtmMoId = "ha-dynamic-type-manager-python"
      versionNS = "urn:reflect/1.0"
      dtmMethodName = "QueryMoInstances"
      try:
         # testing ExecuteSoap with invalid moid
         mme.ExecuteSoap("bogus", versionNS, dtmMethodName, None)
         self.assertFalse(True)
      except vmodl.fault.InvalidArgument as f:
         self.assertFalse(f.invalidProperty != "moid")

      try:
         # testing ExecuteSoap with invalid version
         mme.ExecuteSoap(dtmMoId, "bogus", dtmMethodName, None)
         self.assertFalse(True)
      except vmodl.fault.InvalidArgument as f:
         self.assertFalse(f.invalidProperty != "version")
      except Exception:
         self.assertFalse(True)

      try:
         # testing ExecuteSoap with invalid method
         mme.ExecuteSoap(dtmMoId, versionNS, "bogus", None)
         self.assertFalse(True)
      except vmodl.fault.InvalidArgument as f:
         self.assertFalse(f.invalidProperty != "method")
      except Exception:
         self.assertFalse(True)

   ## test ExecuteSoap with no arguments
   #
   def testExecuteSoap(self):
      mme = vmodl.reflect.ManagedMethodExecuter(self.moId, self.stub)
      mmeHelper = ManagedMethodExecuterHelper.MMESoapStubAdapter(mme)
      dtmMoId = "ha-dynamic-type-manager-python"
      dtm = vmodl.reflect.DynamicTypeManager(dtmMoId, self.stub)
      allInstancesByDTM = dtm.QueryMoInstances()

      try:
         allInstancesByMME = mmeHelper.InvokeMethod(mo=dtm, info=dtm._GetMethodInfo("QueryMoInstances"), args=[None])
      except Exception as e:
         self.assertFalse(True)

      differ = Differ.Differ()
      self.assertFalse(not differ.DiffDoArrays(allInstancesByMME, allInstancesByDTM, False))

   ## test ExecuteSoap with arguments
   #
   def testExecuteSoapWithArgs(self):
      mme = vmodl.reflect.ManagedMethodExecuter(self.moId, self.stub)
      mmeHelper = ManagedMethodExecuterHelper.MMESoapStubAdapter(mme)
      dtmMoId = "ha-dynamic-type-manager-python"
      dtm = vmodl.reflect.DynamicTypeManager(dtmMoId, self.stub)
      filterSpec = vmodl.reflect.DynamicTypeManager.MoFilterSpec()
      filterSpec.typeSubstr = "vmodl.reflect"
      allInstancesByDTM = dtm.QueryMoInstances(filterSpec)

      try:
         allInstancesByMME = mmeHelper.InvokeMethod(mo=dtm, info=dtm._GetMethodInfo("QueryMoInstances"), args=[filterSpec])
      except Exception as e:
         self.assertFalse(True)

      differ = Differ.Differ()
      self.assertFalse(not differ.DiffDoArrays(allInstancesByMME, allInstancesByDTM, False))

if __name__ == "__main__":
   # Register MME
   unittest.main()
