#!/usr/bin/env python
"""
Copyright 2008-2022 VMware, Inc.  All rights reserved. -- VMware Confidential

This module provides convinent fns related to ManagedMethodExecuter
"""
__author__ = "VMware, Inc"

from six.moves import zip

from . import vmodl
from .SoapAdapter import Deserialize, SerializeToStr, SoapStubAdapterBase
from .VmomiSupport import GetVmodlName


# ManagedMethodExecuter soap stub adapter
#
class MMESoapStubAdapter(SoapStubAdapterBase):
    """ Managed method executer stub adapter  """

    # Constructor
    #
    # The endpoint can be specified individually as either a host/port
    # combination, or with a URL (using a url= keyword).
    #
    # @param self self
    # @param mme  managed method executer
    def __init__(self, mme):
        stub = mme._stub
        SoapStubAdapterBase.__init__(self, version=stub.version)
        self.mme = mme

    # Invoke a managed method, with _ExecuteSoap. Wohooo!
    #
    # @param self self
    # @param mo the 'this'
    # @param info method info
    # @param args arguments
    def InvokeMethod(self, mo, info, args):
        # Serialize parameters to soap parameters
        methodArgs = None
        if info.params:
            mme = vmodl.Reflect.ManagedMethodExecuter
            methodArgs = mme.SoapArgument.Array()
            for param, arg in zip(info.params, args):
                if arg is not None:
                    # Serialize parameters to soap snippets
                    soapVal = SerializeToStr(val=arg,
                                             info=param,
                                             version=self.version)

                    # Insert argument
                    soapArg = vmodl.Reflect.ManagedMethodExecuter.SoapArgument(
                        name=param.name, val=soapVal)
                    methodArgs.append(soapArg)

        moid = mo._GetMoId()
        version = self.versionId[1:-1]
        methodName = GetVmodlName(info.type) + "." + info.name

        # Execute method
        result = self.mme.ExecuteSoap(moid=moid,
                                      version=version,
                                      method=methodName,
                                      argument=methodArgs)
        return self._DeserializeExecuterResult(result, info.result)

    # Invoke a managed property accessor
    #
    # @param self self
    # @param mo the 'this'
    # @param info property info
    def InvokeAccessor(self, mo, info):
        moid = mo._GetMoId()
        version = self.versionId[1:-1]
        prop = info.name

        # Fetch property
        result = self.mme.FetchSoap(moid=moid, version=version, prop=prop)
        return self._DeserializeExecuterResult(result, info.type)

    # Deserialize result from ExecuteSoap / FetchSoap
    #
    # @param self self
    # @param result result from ExecuteSoap / FetchSoap
    # @param resultType Expected result type
    def _DeserializeExecuterResult(self, result, resultType):
        obj = None
        if result:
            # Parse the return soap snippet. If fault, raise exception
            if result.response:
                # Deserialize back to result
                obj = Deserialize(result.response, resultType, stub=self)
            elif result.fault:
                # Deserialize back to fault (or vmomi fault)
                fault = Deserialize(result.fault.faultDetail,
                                    object,
                                    stub=self)
                # Silent pylint
                raise fault  # pylint: disable-msg=E0702
            else:
                # Unexpected: result should have either response or fault
                msg = "Unexpected execute/fetchSoap error"
                reason = "execute/fetchSoap did not return response or fault"
                raise vmodl.Fault.SystemError(msg=msg, reason=reason)
        return obj
