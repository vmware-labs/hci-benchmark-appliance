#!/usr/bin/env python

"""
Copyright 2011-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is an implementation for managed object vmodl.reflect.ManagedMethodExecuter
"""
__author__ = "VMware, Inc"

from pyVmomi import vmodl, vim
from pyVmomi.VmomiSupport import ManagedObject, IsChildVersion, GetVersionFromVersionUri, F_OPTIONAL, Uncapitalize
from pyVmomi.SoapAdapter import Serialize, Deserialize
from MoManager import GetMoManager
from SoapHandler import SoapServerStubAdapter
import logging

## The vmodl.reflect.ManagedMethodExecuter implementation class
#
class ManagedMethodExecuter(vmodl.reflect.ManagedMethodExecuter):
   """
   vmodl.reflect.ManagedMethodExecuter implementation
   """

   ## Constructor
   #
   def __init__(self, moId):
      """
      vmodl.reflect.ManagedMethodExecuter constructor
      """
      vmodl.reflect.ManagedMethodExecuter.__init__(self, moId)

   ## Execute a managed method with soap formatted arguments
   #
   # @param moid Managed Object id
   # @param version Version uri string
   # @param method Vmodl method name
   # @param argument Soap formatted Method arguments
   # @return Method Execution result
   def ExecuteSoap(self, moid, version, method, argument):
      # Lookup moid
      try:
         mo = GetMoManager().LookupObject(moid)
      except KeyError:
         raise vmodl.fault.InvalidArgument(invalidProperty="moid")

      # Get the version string from version uri. urn:vim25/5.5 -> vim.version.version9
      try:
         version = GetVersionFromVersionUri(version)
      except KeyError:
         raise vmodl.fault.InvalidArgument(invalidProperty="version")

      # Cannot invoke method on ManagedMethodExecuter
      if isinstance(mo, type(self)):
         raise vmodl.fault.InvalidArgument(invalidProperty="moid")

      # Lookup Vmodl method
      methodName = method.rsplit(".", 1)[-1]
      try:
         methodInfo = mo._GetMethodInfo(methodName)
      except AttributeError:
         # Try again with uncapitalized method name in case of older Python clients
         try:
            methodInfo = mo._GetMethodInfo(Uncapitalize(methodName))
         except AttributeError:
            raise vmodl.fault.InvalidArgument(invalidProperty="method")

      if not IsChildVersion(version, methodInfo.version):
         raise vmodl.fault.InvalidArgument(invalidProperty="method")

      # Verify and deserialize args
      if len(argument) > methodInfo.params:
         raise vmodl.fault.InvalidArgument(invalidProperty="argument")

      params = []
      iArg = 0
      for i in range(0,len(methodInfo.params)):
         paramInfo = methodInfo.params[i]

         # Add None param if param is not visible to this version
         if not IsChildVersion(version, paramInfo.version):
            params.append(None)
            continue

         if iArg >= len(argument):
            # No incoming args left
            # Ok if param is optional
            if paramInfo.flags & F_OPTIONAL:
               params.append(None)
               continue
            # Missing required param
            raise vmodl.fault.InvalidArgument(invalidProperty="argument")

         if paramInfo.name != argument[iArg].name:
            # Check if param is optional
            if paramInfo.flags & F_OPTIONAL:
               params.append(None)
               continue
            # Name mismatch ***
            raise vmodl.fault.InvalidArgument(invalidProperty="argument")

         # Deserialize soap arg to pyVmomi Object
         try:
            obj = Deserialize(argument[iArg].val, paramInfo.type)
         except Exception:
            raise vmodl.fault.InvalidArgument(invalidProperty="argument")
         params.append(obj)
         iArg = iArg + 1

      # Using local adapter to invoke method instead of direct method call as
      # it can provide additional vmomi functions like privilege validation, localization, etc
      localStub = SoapServerStubAdapter(version, GetMoManager())

      # Invoke the method
      return self._ExecuteCommon(localStub.InvokeMethod, mo, methodInfo, params)

   ## Fetch a managed object property
   #
   # @param moid Managed Object id
   # @param version Version uri string
   # @param prop Managed property name
   # @return Fetch result
   def FetchSoap(self, moid, version, prop):
      # Lookup moid
      try:
         mo = GetMoManager().LookupObject(moid)
      except KeyError:
         raise vmodl.fault.InvalidArgument(invalidProperty="moid")

      # Get the version string from version uri. urn:vim25/5.5 -> vim.version.version9
      try:
         version = GetVersionFromVersionUri(version)
      except KeyError:
         raise vmodl.fault.InvalidArgument(invalidProperty="version")

      # Lookup property
      try:
         moProp = mo._GetPropertyInfo(p.name)
      except AttributeError:
         raise vmodl.fault.InvalidArgument(invalidProperty="prop")

      if not IsChildVersion(version, moProp.version):
         raise vmodl.fault.InvalidArgument(invalidProperty="prop")

      # Using local adapter to invoke method instead of direct method call as
      # it can provide additional vmomi functions like privilege validation, localization, etc
      localStub = SoapServerStubAdapter(version, GetMoManager())

      # Invoke the property accessor
      return self._ExecuteCommon(localStub.InvokeAccessor, mo, moProp)

   ## Execute the method for execute/fetch
   def _ExecuteCommon(self, func, *args):
      faultMsg = None
      try:
         ret = func(*args)
      except vmodl.MethodFault as f:
         ret = f
         faultMsg = f.msg
      except Exception as e:
         faultMsg = str(e)
         ret = vmodl.fault.SystemError(msg=faultMsg)

      return self._CreateSoapResult(ret, faultMsg)

   ## Convert the return value to soap result
   def _CreateSoapResult(self, ret, faultMsg):
      # Serialize response
      soapRet = None
      if ret:
         try:
            soapRet = Serialize(ret)
         except Exception as e:
            faultMsg = str(e)
            soapRet = Serialize(vmodl.fault.SystemError(msg=faultMsg))

      if not faultMsg:
         if ret:
            return vmodl.reflect.ManagedMethodExecuter.SoapResult(response=soapRet)
      else:
         fault = vmodl.reflect.ManagedMethodExecuter.SoapFault(faultMsg=faultMsg, faultDetail=soapRet)
         return vmodl.reflect.ManagedMethodExecuter.SoapResult(fault=fault)

def RegisterManagedMethodExecuter(moId="ha-managed-method-executer-python"):
   GetMoManager().RegisterObjects([ManagedMethodExecuter(moId)])
