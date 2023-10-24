#!/usr/bin/env python
"""
Copyright 2008-2022 VMware, Inc.  All rights reserved.
-- VMware Confidential

This module is the vmomi client stub for talking to PyVmomiServer managed object
directly
"""
__author__ = "VMware, Inc"

from pyVmomi import SoapAdapter, VmomiSupport
from pyVmomi.VmomiSupport import newestVersions
from .PyVmomiServer import _ImportTypesAndManagedObjects
from . import SoapHandler
import logging


# SOAP stub adapter object for PyVmomiServer SoapHandler direct execution
class LocalClientStubAdapter(SoapAdapter.SoapStubAdapter):
    # Constructor
    #
    # The endpoint can be specified individually as either a host/port
    # combination, or with a URL (using a url= keyword).
    #
    # @param self self
    # @param version API version
    # @param printRequest print SOAP request
    # @param printResponse print SOAP response
    def __init__(self,
                 version=newestVersions.GetName('vim'),
                 printRequest=False,
                 printResponse=False):
        SoapAdapter.SoapStubAdapter.__init__(self, version=version)
        self.ns = VmomiSupport.GetVersionNamespace(version)
        self.soapHandler = SoapHandler.SoapHandler()
        self.soapDeserializer = SoapAdapter.SoapResponseDeserializer(self)
        self.printRequest = printRequest
        self.printResponse = printResponse
        _ImportTypesAndManagedObjects()

    # Invoke a managed method
    #
    # @param self self
    # @param mo the "this"
    # @param info method info
    # @param args arguments
    def InvokeMethod(self, mo, info, args):
        # Serialize
        request = self.SerializeRequest(mo, info, args)
        if self.printRequest:
            logging.info("*" * 60)
            logging.info(request)
            logging.info("*" * 60)

        # Send request
        isFault, response = self.soapHandler.HandleRequest(request, self.ns)
        if self.printResponse:
            logging.info("=" * 60)
            logging.info(response)
            logging.info("=" * 60)

        # Deserialize
        obj = self.soapDeserializer.Deserialize(str(response), info.result)

        if not isFault:
            return obj
        else:
            raise obj
