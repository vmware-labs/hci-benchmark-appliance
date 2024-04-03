#!/usr/bin/env python
"""
Copyright 2008-2020 VMware, Inc.  All rights reserved. -- VMware Confidential

This module manages the PyJack managed objects
"""
__author__ = "VMware, Inc"

import logging
from pyVmomi import VmomiSupport

import abc
import six


class ManagedObjectFactory(six.with_metaclass(abc.ABCMeta, object)):
    """Interface for ManagedObject Factory"""
    @abc.abstractmethod
    def CreateInstance(moId):
        pass


class ManagedObjectsManager:
    """Managed objects manager"""
    def __init__(self):
        self._managedObjects = {}
        self._moFactories = {}

    # Lookup a python managed object
    #
    # @param  moId the moId of the managed object
    # @param  serverGuid the serverGuid of the managed object
    # @return managed object
    def LookupObject(self, moId, serverGuid=None):
        """Looking managed object"""
        return self._managedObjects[(moId, serverGuid)]

    # Lookup a managed object factory
    #
    # @param  moType Type of the ManagedObject
    # @param  serverGuid the serverGuid of the managed object
    # @return Managed object factory
    def LookupMoFactory(self, moType, serverGuid=None):
        """Looking up a MoFactory"""
        return self._moFactories[(moType._wsdlName, serverGuid)]

    # Register a python managed object
    #
    # @param  moId the moId of the managed object
    # @param  serverGuid the serverGuid of the managed object
    # @param  obj the managed object
    def RegisterObject(self, obj, moId=None, serverGuid=None):
        """Register managed object"""

        if not isinstance(obj, VmomiSupport.ManagedObject):
            # Can only register ManagedObject
            if moId is None:
                message = str(obj) + " is not a managed object"
            else:
                message = moId + ":" + str(obj) + " is not a managed object"
            logging.error(message)
            raise TypeError(message)

        if moId is None:
            moId = obj._GetMoId()

        mo = self._managedObjects.get((moId, serverGuid))
        if mo:
            # Throw "Already registered" if moId exists
            message = moId + " already exists"
            logging.error(message)
            raise KeyError(message)

        # Register obj
        self._managedObjects[(moId, serverGuid)] = obj

    # Register a python managed object factory
    #
    # @param  moType Managed object type for which the factory is
    #         being registered
    # @param  serverGuid the serverGuid of the managed object
    # @param  moFactory Factory instance that can create objects of type moType
    def RegisterMoFactory(self, moFactory, moType, serverGuid=None):
        """Register managed class handler"""

        if not issubclass(moType, VmomiSupport.ManagedObject):
            # Can only register ManagedObject
            message = "%s is not a ManagedObject" % moType
            logging.error(message)
            raise TypeError(message)
        if not isinstance(moFactory, ManagedObjectFactory):
            message = "%s is not a MoFactory" % moFactory
            logging.error(message)
            raise TypeError(message)

        mo = self._moFactories.get((moType._wsdlName, serverGuid))
        if mo:
            # Throw "Already registered" if moId exists
            message = moType._wsdlName + " already exists"
            logging.error(message)
            raise KeyError(message)

        # Register obj
        self._moFactories[(moType._wsdlName, serverGuid)] = moFactory

    # Register python managed objects
    #
    # @param a list of objects, each with attr "_moId"
    def RegisterObjects(self, objects):
        """Register managed objects"""

        for obj in objects:
            self.RegisterObject(obj, obj._moId,
                                getattr(obj, "_serverGuid", None))

    # Unregister a python managed object
    #
    # @param  moId the moId of the managed object
    # @param  serverGuid the serverGuid of the managed object
    def UnregisterObject(self, moId, serverGuid=None):
        """Unregister managed object"""

        try:
            del self._managedObjects[(moId, serverGuid)]
        except KeyError:
            pass

    # Get all registered managed objects
    #
    # @return a list of managed objects
    def GetObjects(self):
        """Get all registered managed objects"""

        return self._managedObjects.copy()


# Create managed objects manager
_gMoObjsMgr = ManagedObjectsManager()


def GetMoManager():
    """Create managed objects manager"""
    return _gMoObjsMgr
