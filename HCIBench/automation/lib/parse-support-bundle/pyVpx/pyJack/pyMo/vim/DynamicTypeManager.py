#!/usr/bin/env python

"""
Copyright 2008-2018 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is an implementation for managed object vmodl.reflect.DynamicTypeManager
"""
__author__ = "VMware, Inc"

from pyVmomi import vmodl, VmomiSupport
from MoManager import GetMoManager
from DynTypeMgr import GetDynTypeMgr
import logging
import six

## The vmodl.reflect.DynamicTypeManager implementation class
#
class DynamicTypeManager(vmodl.reflect.DynamicTypeManager):
   """
   vmodl.reflect.DynamicTypeManager implementation
   """

   # Translated type name
   _translatedTypeName = { "str"  : "string",
                           "bool" : "boolean",
                           "type"          : "vmodl.TypeName",
                           "datetime"      : "vmodl.DateTime",
                           "ManagedObject" : "vmodl.ManagedObject",
                           "DataObject"    : "vmodl.DataObject",
                           "ManagedMethod" : "vmodl.MethodName",
                           "PropertyPath"  : "vmodl.PropertyPath",
                           "binary" : "vmodl.Binary"}
   # Add translated array names
   for name, translated in six.iteritems(_translatedTypeName.copy()):
      _translatedTypeName[name + "[]"] = translated + "[]"


   ## Constructor
   #
   def __init__(self, moId):
      """
      vmodl.reflect.DynamicTypeManager constructor
      """
      vmodl.reflect.DynamicTypeManager.__init__(self, moId)


   ## Get a list of managed object instances in the system
   #
   # @param  filterSpec Query filter spec
   # @return A list of mo objects instance
   def QueryMoInstances(self, filterSpec=None):
      """
      vmodl.reflect.DynamicTypeManager QueryMoInstances. Get a list of dynamic mo objs
      """
      moInstances = vmodl.reflect.DynamicTypeManager.MoInstance.Array()
      objects = GetMoManager().GetObjects()
      for (moId, serverGuid), instance in six.iteritems(objects):
         si = vmodl.reflect.DynamicTypeManager.MoInstance()
         si.id = moId
         #TODO: serverGuid in QueryMoInstances?
         #si.serverGuid = serverGuid
         ns = VmomiSupport.GetWsdlNamespace(instance._version)
         aType = VmomiSupport.GetWsdlType(ns, instance._wsdlName)
         si.moType = self._GetTypeName(aType)

         # Filter
         if filterSpec:
            if filterSpec.id and filterSpec.id != si.id:
               continue

            if filterSpec.typeSubstr and si.moType.find(filterSpec.typeSubstr) == -1:
               continue

         moInstances.append(si)
      return moInstances


   ## Get a list of dynamic managed object type in the system
   #
   # @param  filterSpec Query filter spec
   # @return Managed object types
   def QueryTypeInfo(self, filterSpec=None):
      """
      vmodl.reflect.DynamicTypeManager QueryTypeInfo. Get a list of dynamic mo types
      """
      allTypeInfo = vmodl.reflect.DynamicTypeManager.AllTypeInfo()
      dataTypeInfo = vmodl.reflect.DynamicTypeManager.DataTypeInfo.Array()
      managedTypeInfo = vmodl.reflect.DynamicTypeManager.ManagedTypeInfo.Array()
      enumTypeInfo = vmodl.reflect.DynamicTypeManager.EnumTypeInfo.Array()

      allTypeInfo.dataTypeInfo = dataTypeInfo
      allTypeInfo.managedTypeInfo = managedTypeInfo
      allTypeInfo.enumTypeInfo = enumTypeInfo

      dynTypes = GetDynTypeMgr().GetTypes()
      for aType in six.itervalues(dynTypes):
         # Filter
         if filterSpec:
            moTypeName = self._GetTypeName(aType)
            if filterSpec.typeSubstr and moTypeName.find(filterSpec.typeSubstr) == -1:
               continue

         # Create data type
         if issubclass(aType, VmomiSupport.ManagedObject):
            # Create managed type
            dynManagedTypeInfo = self._CreateManagedTypeInfo(aType)
            managedTypeInfo.append(dynManagedTypeInfo)
         # Check Enum type first because the Enum type is also the subclass of DataObject
         elif issubclass(aType, VmomiSupport.Enum):
            dynEnumTypeInfo = self._CreateEnumTypeInfo(aType)
            enumTypeInfo.append(dynEnumTypeInfo)
         elif issubclass(aType, VmomiSupport.DataObject) \
              or issubclass(aType, str):
            dynDataTypeInfo = self._CreateDataTypeInfo(aType)
            dataTypeInfo.append(dynDataTypeInfo)
         elif issubclass(aType, VmomiSupport.Array):
            # Filter out array object
            pass
         else:
            # Unknown object type. Need implementation
            logging.critical("Panic: Unknwon type. Missing implementation")
            logging.critical(aType)
            logging.critical(aType.__base__)
            logging.critical(dir(aType))
            assert(False)

      return allTypeInfo


   ## Create dynamic enum type info
   #
   # @param aType a Vmomi type
   def _CreateEnumTypeInfo(self, aType):
      """
      Create dynamic enum type info
      """

      typeInfo = vmodl.reflect.DynamicTypeManager.EnumTypeInfo()
      typeInfo.name = aType.__name__
      typeInfo.wsdlName = aType._wsdlName
      typeInfo.version = aType._version
      typeInfo.value = [str(enum) for enum in aType.values]
      return typeInfo


   ## Create dynamic managed type info
   #
   # @param aType a Vmomi type
   def _CreateManagedTypeInfo(self, aType):
      """
      Create dynamic managed type info
      """

      typeInfo = vmodl.reflect.DynamicTypeManager.ManagedTypeInfo()
      typeInfo.name = aType.__name__
      typeInfo.wsdlName = aType._wsdlName
      typeInfo.version = aType._version
      typeInfo.base = [self._GetTypeName(aType.__bases__[0])]

      # Properties
      properties = vmodl.reflect.DynamicTypeManager.PropertyTypeInfo.Array()
      for info in six.itervalues(aType._propInfo):
         propTypeInfo = self._CreatePropertyTypeInfo(info)
         properties.append(propTypeInfo)
      typeInfo.property = properties

      # Methods
      methods = vmodl.reflect.DynamicTypeManager.MethodTypeInfo.Array()
      for info in six.itervalues(aType._methodInfo):
         methodTypeInfo = self._CreateMethodTypeInfo(info)
         methods.append(methodTypeInfo)
      typeInfo.method = methods

      return typeInfo


   ## Create dynamic data type info
   #
   # @param aType a Vmomi type
   def _CreateDataTypeInfo(self, aType):
      """
      Create dynamic data type info
      """

      typeInfo = vmodl.reflect.DynamicTypeManager.DataTypeInfo()
      typeInfo.name = aType.__name__
      typeInfo.wsdlName = aType._wsdlName
      typeInfo.version = aType._version
      typeInfo.base = [self._GetTypeName(aType.__bases__[0])]

      # Properties
      properties = vmodl.reflect.DynamicTypeManager.PropertyTypeInfo.Array()
      for info in aType._propList:
         propTypeInfo = self._CreatePropertyTypeInfo(info)
         properties.append(propTypeInfo)
      typeInfo.property = properties

      return typeInfo


   ## Create dynamic property type info
   #
   # @param info a Vmomi property type info
   def _CreatePropertyTypeInfo(self, info):
      """
      Create dynamic property type info
      """

      typeInfo = vmodl.reflect.DynamicTypeManager.PropertyTypeInfo()
      self._SetTypeInfo(typeInfo, info)
      return typeInfo


   ## Create dynamic method param type info
   #
   # @param info a Vmomi param type info
   def _CreateParamTypeInfo(self, info):
      """
      Create dynamic param type info
      """

      typeInfo = vmodl.reflect.DynamicTypeManager.ParamTypeInfo()
      self._SetTypeInfo(typeInfo, info)
      return typeInfo


   ## Create dynamic method return type info
   #
   # @param flags a return flags
   # @param aType a Vmomi type
   def _CreateDynReturnTypeInfo(self, flags, aType):
      """
      Create dynamic return type info
      """

      # Get version from type
      try:
         version = aType._version
      except AttributeError:
         version = VmomiSupport.BASE_VERSION

      # TODO: Emitted stub missing return val flags. Change emit code
      info = VmomiSupport.Object(name="result", type=aType,
                                 version=version, flags=flags)
      return self._CreateParamTypeInfo(info)


   ## Create dynamic method type info
   #
   # @param info a Vmomi method type info
   def _CreateMethodTypeInfo(self, info):
      """
      Create dynamic method type info
      """

      typeInfo = vmodl.reflect.DynamicTypeManager.MethodTypeInfo()
      typeInfo.name = info.name
      typeInfo.wsdlName = info.wsdlName
      typeInfo.version = info.version

      # Params
      if info.params and info.params is not VmomiSupport.NoneType:
         lstParamTypeInfo = vmodl.reflect.DynamicTypeManager.ParamTypeInfo.Array()
         for param in info.params:
            paramTypeInfo = self._CreateParamTypeInfo(param)
            lstParamTypeInfo.append(paramTypeInfo)
         typeInfo.paramTypeInfo = lstParamTypeInfo

      # Result
      flags, result = info.resultFlags, info.methodResult
      if result and result is not VmomiSupport.NoneType:
         returnTypeInfo = self._CreateDynReturnTypeInfo(flags, result)
         typeInfo.returnTypeInfo = returnTypeInfo

      # Faults
      if hasattr(info, "faults"):
         typeInfo.fault = info.faults

      # Priv Id
      if hasattr(info, "privId"):
         typeInfo.privId = info.privId

      return typeInfo

   ## Get type name
   #
   # @param type the type
   # @return fully qualified type name
   def _GetTypeName(self, aType):
      """
      Get type name
      """

      name = aType.__name__
      return self._translatedTypeName.get(name, name)

   ## Set typeinfo from Vmomi info
   #
   # @param typeInfo a typeInfo, with attr (name, version, type and flags)
   # @param info a Vmomi info
   def _SetTypeInfo(self, typeInfo, info):
      """
      Set typeInfo (name, version, type, and flags)
      """

      typeInfo.name = info.name
      typeInfo.version = info.version
      typeInfo.type = self._GetTypeName(info.type)
      typeInfo.annotation = self._ConvertToAnnotation(info.flags)
      if hasattr(info, "privId"):
         typeInfo.privId = info.privId
      return typeInfo

   ## Create annotation
   #
   # @param name the annotation name
   # @param parameters the annotation parameters
   def _CreateAnnotation(self, name, parameters=None):
      """ Create annotation """

      annotation = vmodl.reflect.DynamicTypeManager.Annotation()
      annotation.name = name
      if parameters:
         annotation.parameter = parameters
      else:
         annotation.parameter = []
      return annotation

   ## Convert numeric flag to annotations
   #
   # @param flags the numeric flag
   def _ConvertToAnnotation(self, flags):
      """
      Convert numeric flag to annotations
      """

      annotations = vmodl.reflect.DynamicTypeManager.Annotation.Array()
      if flags != 0:
         if flags & VmomiSupport.F_OPTIONAL:
            flags &= ~VmomiSupport.F_OPTIONAL
            annotations.append(self._CreateAnnotation("optional"))

         if flags & VmomiSupport.F_SECRET:
            flags &= ~VmomiSupport.F_SECRET
            annotations.append(self._CreateAnnotation("secret"))

         if flags & VmomiSupport.F_LINKABLE:
            flags &= ~VmomiSupport.F_LINKABLE
            annotations.append(self._CreateAnnotation("linkable"))

         if flags & VmomiSupport.F_LINK:
            flags &= ~VmomiSupport.F_LINK
            annotations.append(self._CreateAnnotation("link"))

         if flags:
            # Unknown flag exists
            assert(False)

      return annotations


# Add managed objects during import
GetMoManager().RegisterObjects(
                        [DynamicTypeManager("ha-dynamic-type-manager-python")])
