#!/usr/bin/env python
"""
Copyright 2008-2020 VMware, Inc.  All rights reserved.
-- VMware Confidential

This module is used to test soap handler
"""
__author__ = "VMware, Inc"

import unittest

# import SoapHandler
import sys
sys.path.append("..")
from SoapHandler import SoapHandler, SoapSerializer, ExceptionMsg, Validator
from PyVmomiServer import ImportTypesAndManagedObjects
from pyVmomi import Vim, Vmodl, VmomiSupport, SoapAdapter
from pyVmomi.VmomiSupport import newestVersions


class TestSoapHandler(unittest.TestCase):
    # Setup
    def setUp(self):
        self.version = newestVersions.GetName('vim')
        self.versionUri = VmomiSupport.GetVersionNamespace(self.version)
        self.futureVersionUri = "vim25/foo"
        self.badVersionUri = "notvim/foo"
        self.stub = SoapAdapter.SoapStubAdapter(version=self.version)
        self.deserializer = SoapAdapter.SoapResponseDeserializer(self.stub)
        self.soapHeaderBegin = \
           """<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope
               xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
               xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <soapenv:Body>"""
        self.soapHeaderEnd = \
           """</soapenv:Body>
            </soapenv:Envelope>"""
        ImportTypesAndManagedObjects()

    # tearDown
    def tearDown(self):
        pass

    # Test HandleRequest FutureVersion.
    # Should suceed (use default version handler)
    def test_HandleRequest_FutureVersion(self):
        versionUri = self.futureVersionUri
        request = self.soapHeaderBegin + """
         <DynamicTypeMgrQueryMoInstances xmlns="urn:vim25">
            <_this type="InternalDynamicTypeManager">ha-dynamic-type-manager-python</_this>
         </DynamicTypeMgrQueryMoInstances>""" \
           + self.soapHeaderEnd
        isFault, response = SoapHandler().HandleRequest(request, versionUri)
        self.assertFalse(isFault)

        obj = self.deserializer.Deserialize(
            response,
            Vmodl.Reflect.DynamicTypeManager.QueryMoInstances.info.result)
        self.assertTrue(
            isinstance(obj, Vmodl.Reflect.DynamicTypeManager.MoInstance.Array))

    # Test HandleRequest BadVersion
    def test_HandleRequest_BadVersion(self):
        versionUri = self.badVersionUri
        request = ""
        isFault, response = SoapHandler().HandleRequest(request, versionUri)
        self.assertTrue(isFault)

        obj = self.deserializer.Deserialize(response, None)
        self.assertTrue(isinstance(obj, Vmodl.RuntimeFault))

    # Test HandleRequest BadRequest
    def test_HandleRequest_BadRequest(self):
        versionUri = self.versionUri
        request = "I am bad"
        isFault, response = SoapHandler().HandleRequest(request, versionUri)
        self.assertTrue(isFault)

        obj = self.deserializer.Deserialize(response, None)
        self.assertTrue(isinstance(obj, Vmodl.Fault.InvalidRequest))

    # Test HandleRequest type not found
    def test_HandleRequest_TypeNotFound(self):
        versionUri = self.versionUri
        request = self.soapHeaderBegin + """
         <DynamicTypeMgrQueryMoInstances xmlns="urn:vim25">
            <_this type="BadType">ha-dynamic-type-manager</_this>
         </DynamicTypeMgrQueryMoInstances>""" \
           + self.soapHeaderEnd
        isFault, response = SoapHandler().HandleRequest(request, versionUri)
        self.assertTrue(isFault)

        obj = self.deserializer.Deserialize(response, None)
        self.assertTrue(isinstance(obj, Vmodl.Fault.InvalidRequest))

    # Test HandleRequest ManagedObject not found
    def test_HandleRequest_ManagedObjectNotFound(self):
        versionUri = self.versionUri
        request = self.soapHeaderBegin + """
         <DynamicTypeMgrQueryMoInstances xmlns="urn:vim25">
            <_this type="InternalDynamicTypeManager">ha-dynamic-type-manager</_this>
         </DynamicTypeMgrQueryMoInstances>""" \
           + self.soapHeaderEnd
        isFault, response = SoapHandler().HandleRequest(request, versionUri)
        self.assertTrue(isFault)

        obj = self.deserializer.Deserialize(response, None)
        self.assertTrue(isinstance(obj, Vmodl.Fault.ManagedObjectNotFound))

    # Test HandleRequest Method not found
    def test_HandleRequest_MethodNotFound(self):
        versionUri = self.versionUri
        request = self.soapHeaderBegin + """
         <Foo xmlns="urn:vim25">
            <_this type="InternalDynamicTypeManager">ha-dynamic-type-manager-python</_this>
         </Foo>""" \
           + self.soapHeaderEnd
        isFault, response = SoapHandler().HandleRequest(request, versionUri)
        self.assertTrue(isFault)

        obj = self.deserializer.Deserialize(response, None)
        self.assertTrue(isinstance(obj, Vmodl.Fault.MethodNotFound))

    # Test HandleRequest Property not found (fault: Method not found)
    def test_HandleRequest_PropertyNotFound(self):
        versionUri = self.versionUri
        request = self.soapHeaderBegin + """
         <Fetch xmlns="urn:vim25">
            <_this type="InternalDynamicTypeManager">ha-dynamic-type-manager-python</_this>
            <prop>foo</prop>
         </Fetch>""" \
           + self.soapHeaderEnd
        isFault, response = SoapHandler().HandleRequest(request, versionUri)
        self.assertTrue(isFault)

        obj = self.deserializer.Deserialize(response, None)
        self.assertTrue(isinstance(obj, Vmodl.Fault.MethodNotFound))

    # Test HandleRequest DynamicTypeManager QueryMoInstancesValid
    def test_HandleRequest_DynamicTypeManager_QueryMoInstances(self):
        versionUri = self.versionUri
        request = self.soapHeaderBegin + """
         <DynamicTypeMgrQueryMoInstances xmlns="urn:vim25">
            <_this type="InternalDynamicTypeManager">ha-dynamic-type-manager-python</_this>
            <filterSpec xsi:type="DynamicTypeMgrMoFilterSpec"><typeSubstr>vim</typeSubstr></filterSpec>
         </DynamicTypeMgrQueryMoInstances>""" \
           + self.soapHeaderEnd
        isFault, response = SoapHandler().HandleRequest(request, versionUri)
        self.assertFalse(isFault)

    # Test a Validator
    def test_Validator(self):
        class TestValidator(Validator):
            def __init__(self):
                self.called = False

            def validateMethodCall(self, context, info, mo, params):
                self.called = True

        testValidator = TestValidator()
        SoapHandler.RegisterValidator(testValidator)
        versionUri = self.versionUri
        request = self.soapHeaderBegin + """
         <DynamicTypeMgrQueryMoInstances xmlns="urn:vim25">
            <_this type="InternalDynamicTypeManager">ha-dynamic-type-manager-python</_this>
            <filterSpec xsi:type="DynamicTypeMgrMoFilterSpec"><typeSubstr>vim</typeSubstr></filterSpec>
         </DynamicTypeMgrQueryMoInstances>""" \
           + self.soapHeaderEnd
        isFault, response = SoapHandler().HandleRequest(request, versionUri)
        self.assertFalse(isFault)
        self.assertFalse(not testValidator.called)

    # Test performance
    def test_Performance(self):
        # Profile test
        versionUri = self.versionUri
        request = self.soapHeaderBegin + """
         <DynamicTypeMgrQueryMoInstances xmlns="urn:vim25">
            <_this type="InternalDynamicTypeManager">ha-dynamic-type-manager-python</_this>
            <filterSpec xsi:type="DynamicTypeMgrMoFilterSpec"><typeSubstr>vim</typeSubstr></filterSpec>
         </DynamicTypeMgrQueryMoInstances>""" \
           + self.soapHeaderEnd
        command = \
           """for x in range(1,4096):
               isFault, response = SoapHandler().HandleRequest(request, versionUri)
               obj = self.deserializer.Deserialize(response,
                  Vmodl.Reflect.DynamicTypeManager.QueryMoInstances.info.result)"""
        profileName = "test.profile"
        import cProfile
        cProfile.runctx(command, globals(), locals(), filename=profileName)

        # Dump stat
        import pstats
        p = pstats.Stats(profileName)
        p.strip_dirs().sort_stats('time', 'calls',
                                  'cumulative').print_stats(.3)

    # Test fault is correctly serialized and deserialized with some version
    def test_SoapSerializer_SerializeServerFault(self):
        fault = Vmodl.Fault.InvalidArgument(invalidProperty="Testing")
        fault.faultMessage = [
            Vmodl.LocalizableMessage(
                key="vim.fault.ProfileUpdateFailed.UpdateFailure")
        ]
        response = SoapSerializer().SerializeServerFault(fault, self.version)
        obj = self.deserializer.Deserialize(response, None)
        self.assertFalse(len(fault.faultMessage) != len(obj.faultMessage))
        for org, new in zip(fault.faultMessage, obj.faultMessage):
            self.assertFalse(org.key != new.key)

    # Test fault is correctly serialized and deserialized with default version
    def test_SoapSerializer_SerializeServerFault_Default_Version(self):
        fault = Vmodl.Fault.InvalidArgument(invalidProperty="Testing")
        fault.faultMessage = [
            Vmodl.LocalizableMessage(
                key="vim.fault.ProfileUpdateFailed.UpdateFailure")
        ]
        # Serialize to base version. Should not have faultMessage
        response = SoapSerializer().SerializeServerFault(fault)
        obj = self.deserializer.Deserialize(response, None)
        self.assertFalse(len(obj.faultMessage) != 0)


# Test main
if __name__ == "__main__":
    unittest.main()
