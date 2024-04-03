#!/usr/bin/env python

"""
Copyright 2008-2020 VMware, Inc.  All rights reserved.
-- VMware Confidential

Unit test for DynamicTypeManager implementation
"""
__author__ = "VMware, Inc"

from . import PathCommon
from . import StubsCommon

import unittest
from pyVmomi import vmodl
from pyVmomi.VmomiSupport import newestVersions

class TestVimDynamicTypeManager(unittest.TestCase):
   ## Setup
   #
   def setUp(self):
      self.stub = StubsCommon.GetStub(self, newestVersions.GetName('vim'))
      self.moId = "ha-dynamic-type-manager-python"

   ## tearDown
   #
   def tearDown(self):
      pass

   ## Test for queryTypeInfo
   #
   def test_queryTypeInfo(self):
      dynTypeMgr = vmodl.reflect.DynamicTypeManager(self.moId, self.stub)
      allTypes = dynTypeMgr.QueryTypeInfo()
      # print allTypes
      self.assertTrue(len(allTypes.managedTypeInfo) > 0)

   ## Test for queryTypeInfo positive filter
   #
   def test_queryTypeInfo_filter0(self):
      dynTypeMgr = vmodl.reflect.DynamicTypeManager(self.moId, self.stub)

      filterSpec = vmodl.reflect.DynamicTypeManager.TypeFilterSpec()
      filterSpec.typeSubstr = "vim"
      allTypes = dynTypeMgr.QueryTypeInfo(filterSpec)
      self.assertTrue(len(allTypes.managedTypeInfo) > 0)
      for aType in allTypes.managedTypeInfo:
         self.assertTrue(aType.name.find(filterSpec.typeSubstr) != -1)
      for aType in allTypes.enumTypeInfo:
         self.assertTrue(aType.name.find(filterSpec.typeSubstr) != -1)
      for aType in allTypes.dataTypeInfo:
         self.assertTrue(aType.name.find(filterSpec.typeSubstr) != -1)

   ## Test for queryTypeInfo negative filter
   #
   def test_queryTypeInfo_filter1(self):
      dynTypeMgr = vmodl.reflect.DynamicTypeManager(self.moId, self.stub)

      filterSpec = vmodl.reflect.DynamicTypeManager.TypeFilterSpec()
      filterSpec.typeSubstr = "!@#$%^&*()"
      allTypes = dynTypeMgr.QueryTypeInfo(filterSpec)
      self.assertTrue(len(allTypes.managedTypeInfo) == 0)
      self.assertTrue(len(allTypes.enumTypeInfo) == 0)
      self.assertTrue(len(allTypes.dataTypeInfo) == 0)

   ## Test for queryMoInstances
   #
   def test_queryMoInstances(self):
      dynTypeMgr = vmodl.reflect.DynamicTypeManager(self.moId, self.stub)
      allInstances = dynTypeMgr.QueryMoInstances()
      self.assertTrue(len(allInstances) > 0)

   ## Test for queryMoInstances positive filter
   #
   def test_queryMoInstances_filter0(self):
      dynTypeMgr = vmodl.reflect.DynamicTypeManager(self.moId, self.stub)

      filterSpec = vmodl.reflect.DynamicTypeManager.MoFilterSpec()
      filterSpec.typeSubstr = "vmodl.reflect"
      allInstances = dynTypeMgr.QueryMoInstances(filterSpec)
      self.assertTrue(len(allInstances) > 0)
      for instance in allInstances:
         self.assertTrue(instance.moType.find(filterSpec.typeSubstr) != -1)

   ## Test for queryMoInstances positive filter
   #
   def test_queryMoInstances_filter1(self):
      dynTypeMgr = vmodl.reflect.DynamicTypeManager(self.moId, self.stub)

      filterSpec = vmodl.reflect.DynamicTypeManager.MoFilterSpec()
      filterSpec.id = self.moId
      filterSpec.typeSubstr = "vmodl.reflect"
      allInstances = dynTypeMgr.QueryMoInstances(filterSpec)
      self.assertTrue(len(allInstances) > 0)
      for instance in allInstances:
         self.assertTrue(instance.id == filterSpec.id)
         self.assertTrue(instance.moType.find(filterSpec.typeSubstr) != -1)

   ## Test for queryMoInstances negative filter
   #
   def test_queryMoInstances_filter2(self):
      dynTypeMgr = vmodl.reflect.DynamicTypeManager(self.moId, self.stub)

      filterSpec = vmodl.reflect.DynamicTypeManager.MoFilterSpec()
      filterSpec.id = self.moId
      filterSpec.typeSubstr = "!@#$%^&*()"
      allInstances = dynTypeMgr.QueryMoInstances(filterSpec)
      self.assertTrue(len(allInstances) == 0)

if __name__ == "__main__":
   unittest.main()
