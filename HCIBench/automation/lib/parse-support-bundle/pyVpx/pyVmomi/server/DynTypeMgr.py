#!/usr/bin/env python
"""
Copyright 2008-2022 VMware, Inc.  All rights reserved. -- VMware Confidential

This module handles dynamic type infomation for pyVmomiServer managed objects
"""
__author__ = "VMware, Inc"

from pyVmomi import VmomiSupport
import logging


# Get WSDL Array name
#
# @param  name the non-array wsdlname
# @return WSDL array name
def GetWsdlArrayName(name):
    """Get WSDL array name"""
    if name:
        return "ArrayOf" + name[0].capitalize() + name[1:]
    else:
        return None


# Dynamic type manager
class DynTypeMgr:
    """Dynamic type manager"""

    def __init__(self):
        self._dynTypes = {}

    # Get all dynamic types
    #
    # @return a dict of {vmodl name, dynamic types}
    def GetTypes(self):
        """Get registered dynamic types"""
        return self._dynTypes.copy()

    # Create a data object type
    # Note: Must call RegisterTypes to seal the type
    #
    # @param vmodlName the VMODL name of the type
    # @param wsdlName the WSDL name of the type
    # @param parent the WSDL name of the parent type
    # @param version the version of the type
    # @param props properties of the type
    # @return the new data object type
    def CreateDataType(self, vmodlName, wsdlName, parent, version, props):
        """Create data type"""

        # Cannot add array type directly
        assert (not wsdlName.startswith("ArrayOf"))
        self._FailIfWsdlTypeExists(version, wsdlName)

        # Convert to pyVmomi properties
        properties = self._ConvertDataProperties(props)

        # The types created by this function are currently used at the bootup
        # time of hostd.  So, creating and loading them immediately without
        # deferring the loading of the type Create data type
        aType = VmomiSupport.CreateAndLoadDataType(vmodlName, wsdlName, parent,
                                                   version, properties)

        return aType

    # Create a managed object type
    # Note: Must call RegisterTypes to seal the type
    #
    # @param vmodlName the VMODL name of the type
    # @param wsdlName the WSDL name of the type
    # @param parent the WSDL name of the parent type
    # @param version the version of the type
    # @param props properties of the type
    # @param methods methods of the type
    # @return the new managed object type
    def CreateManagedType(self, vmodlName, wsdlName, parent, version, props,
                          methods):
        """Create managed type"""

        # Cannot add array type directly
        assert (not wsdlName.startswith("ArrayOf"))
        self._FailIfWsdlTypeExists(version, wsdlName)
        # Convert to pyVmomi methods / properties
        allMethods = self._ConvertMethods(methods)
        properties = self._ConvertManagedProperties(props)

        # The types created by this function are currently used at the bootup
        # time of hostd.  So, creating and loading them immediately without
        # deferring the loading of the type Create managed type
        aType = VmomiSupport.CreateAndLoadManagedType(vmodlName, wsdlName,
                                                      parent, version,
                                                      properties, allMethods)

        return aType

    # Create an enum type
    # Note: Must call RegisterTypes to seal the type
    #
    # @param vmodlName the VMODL name of the type
    # @param wsdlName the WSDL name of the type
    # @param version the version of the type
    # @param values enum values
    # @return the new enum type
    def CreateEnumType(self, vmodlName, wsdlName, version, values):
        """Create enum type"""

        # Cannot add array type directly
        assert (not wsdlName.startswith("ArrayOf"))
        self._FailIfWsdlTypeExists(version, wsdlName)
        # The types created by this function are currently used at the bootup
        # time of hostd.  So, creating and loading them immediately without
        # deferring the loading of the type
        aType = VmomiSupport.CreateAndLoadEnumType(vmodlName, wsdlName,
                                                   version, values)
        return aType

    # Register type
    #
    # @param  aType type returns from CreateXYZType
    def RegisterType(self, aType):
        """Register type"""
        self._RegisterTypeAndArrayType(aType)

    # Register types
    #
    # @param  types iteratable types returns from CreateXYZType
    def RegisterTypes(self, types):
        """Register types"""
        for aType in types:
            self.RegisterType(aType)

    # Lookup wsdl type. Fail if type exists
    #
    # @param wsdlName the WSDL name of the type
    # @throw KeyError if type exists
    def _FailIfWsdlTypeExists(self, version, wsdlName):
        """Lookup wsdl type. Raise KeyError if type exists"""
        try:
            ns = VmomiSupport.GetWsdlNamespace(version)
            aType = VmomiSupport.GetWsdlType(ns, wsdlName)
        except KeyError:
            aType = None

        if aType:
            message = "Type '" + wsdlName + "' already exists"
            logging.error(message)
            raise KeyError(message)

    # Register type
    #
    # @param name the vmodl name of the type
    # @param aType type
    def _RegisterType(self, name, aType):
        """Register type"""
        dynType = self._dynTypes.get(name)
        if dynType:
            message = "Type '" + name + "' already exists"
            logging.error(message)
            raise KeyError(message)
        # Register type
        self._dynTypes[name] = aType

    # Register both the type and the array type
    #
    # @param aType the named type
    def _RegisterTypeAndArrayType(self, aType):
        """Register both the type and the array type"""
        vmodlName = VmomiSupport.GetVmodlName(aType)
        arrayTypeVmodlName = vmodlName + "[]"
        arrayType = VmomiSupport.GetVmodlType(arrayTypeVmodlName)
        self._RegisterType(vmodlName, aType)
        self._RegisterType(arrayTypeVmodlName, arrayType)

    # Convert properties to pyVmomi managed object properties
    #
    # @param  props List of properties with the following attrs:
    #           name, wsdlType, version, flags
    # @return pyVmomi properties
    @staticmethod
    def _ConvertManagedProperties(props):
        """Convert properties to pyVmomi properties"""
        return [(prop.name, prop.type, prop.version, prop.flags, prop.privId) \
                                                  for prop in props]

    # Convert properties to pyVmomi data object properties
    #
    # @param  props List of properties with the following attrs:
    #           name, wsdlType, version, flags
    # @return pyVmomi properties
    @staticmethod
    def _ConvertDataProperties(props):
        """Convert properties to pyVmomi properties"""
        return [(prop.name, prop.type, prop.version, prop.flags) \
                                                  for prop in props]

    # Convert methods to pyVmomi methods
    #
    # @param  allMethods List of method with the following attrs:
    #           name, wsdlName, version, params, returns
    #         where params is a list of obj with attrs:
    #           name, wsdlType, version, flags
    #         and returns has attr: wsdlType
    # @return pyVmomi methods
    @staticmethod
    def _ConvertMethods(allMethods):
        """Convert methods to pyVmomi methods"""
        methods = []
        for method in allMethods:
            # Handle method parameters
            methodParams = \
                     [(param.name, param.type, param.version, param.flags,
                       param.privId) \
                      for param in method.params]
            if method.isTask:
                taskReturnType = "vim.Task"
            else:
                taskReturnType = method.returns.type

            aMethod = (method.name, method.wsdlName, method.version,
                       tuple(methodParams),
                       (method.returns.flags, taskReturnType,
                        method.returns.type), method.privId, method.faults)
            methods.append(aMethod)
        return methods


# Get dynamic type manager
_gDynTypeMgr = DynTypeMgr()


def GetDynTypeMgr():
    """Get the dynamic type manager"""
    return _gDynTypeMgr
