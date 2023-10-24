# **********************************************************
# Copyright 2011-2021 VMware, Inc.  All rights reserved.
# -- VMware Confidential
# **********************************************************

from .Version import _GetInternalVersion
from .VmomiSupport import GetVmodlNs, ManagedObject, Object


class StubAdapterAccessorMixin:
    def __init__(self):
        self.shouldEnforceInternalVersion = False
        self.__ComputeVersionInfoImpl = self.ComputeVersionInfo
        self.ComputeVersionInfo = self.__ComputeVersionInfo

    def __ComputeVersionInfo(self, version):
        vmodlNs = GetVmodlNs(version)

        # Always use the internal version for following namespaces
        if vmodlNs in ['vim']:
            version = _GetInternalVersion(version)
            self.shouldEnforceInternalVersion = True

        self.__ComputeVersionInfoImpl(version)

    # Retrieve a managed property
    #
    # @param self self
    # @param mo managed object
    # @param info property info
    def InvokeAccessor(self, mo, info):
        prop = info.name
        param = Object(name="prop", type=str, version=self.version, flags=0)
        info = Object(name=info.name,
                      type=ManagedObject,
                      wsdlName="Fetch",
                      version=info.version,
                      params=(param, ),
                      isTask=False,
                      resultFlags=info.flags,
                      result=info.type,
                      methodResult=info.type)
        return self.InvokeMethod(mo, info, (prop, ))

    def SupportServerGUIDs(self):
        return self.shouldEnforceInternalVersion
