#!/usr/bin/env python
"""
Copyright 2022 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is the python vmomi server security module.
"""
__author__ = "VMware, Inc"

from abc import ABC, abstractmethod

_gAuthChecker = None

class AuthChecker(ABC):
    # Determines whether a client is authenticated
    #
    # @param soapContext The SOAP request context
    # @return boolean
    @abstractmethod
    def isAuthenticated(self, soapContext):
        pass


class AuthFaultFactory(ABC):
    # Provides a fault for use cases where a specific "not authenticated" fault
    # is required by the client.
    #
    # @param soapMsg The deserialized SOAP request envelope
    # @raise RuntimeFault
    #             Application-defined VMODL fault indicating not authenticated
    #             access. The fault must belong to the same or a base namespace
    #             as the request. If a fault used for reporting lack of
    #             authentication exists in the application code, it should be
    #             reused.
    @abstractmethod
    def getUnauthnFault(self, soapMsg):
        pass


def RegisterUnauthFaultFactory(namespaceId, faultFactory):
    ValidateAuthFaultFactory(faultFactory)
    from .SoapHandler import SoapHandler
    SoapHandler.SetUnauthenticatedFaultFactory(namespaceId, faultFactory)


def ValidateAuthFaultFactory(faultFactory):
    if not isinstance(faultFactory, AuthFaultFactory):
        raise TypeError("Invalid fault factory")


def GetAuthChecker():
    global _gAuthChecker
    return _gAuthChecker


def SetAuthChecker(authChecker):
    if not isinstance(authChecker, AuthChecker):
        raise TypeError("Invalid auth checker")
    global _gAuthChecker
    _gAuthChecker = authChecker
