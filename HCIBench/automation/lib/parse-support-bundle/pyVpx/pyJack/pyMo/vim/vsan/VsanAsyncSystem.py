#!/usr/bin/env python

"""
Copyright 2014 VMware, Inc.  All rights reserved. -- VMware Confidential
"""

from VmodlDecorators import \
    ManagedType, DataType, EnumType, \
    Attribute, Method, Param, Return, \
    F_LINK, F_LINKABLE, F_OPTIONAL, \
    VmodlDecoratorException, RegisterVmodlTypes
from pyVmomi import Vmodl

## Vmodl names
#
_VERSION = "vim.version.version10"

class VsanProactiveRebalanceInfo:
    _name = 'vim.host.VsanProactiveRebalanceInfo'

    @DataType(name=_name, version=_VERSION)
    def __init__(self):
       pass

    @Attribute(parent=_name, typ="boolean")
    def running(self):
       pass

    @Attribute(parent=_name, typ="vmodl.DateTime", flags=F_OPTIONAL)
    def startTs(self):
       pass

    @Attribute(parent=_name, typ="vmodl.DateTime", flags=F_OPTIONAL)
    def stopTs(self):
       pass

    @Attribute(parent=_name, typ="float", flags=F_OPTIONAL)
    def varianceThreshold(self):
       pass

    @Attribute(parent=_name, typ="int", flags=F_OPTIONAL)
    def timeThreshold(self):
       pass

    @Attribute(parent=_name, typ="int", flags=F_OPTIONAL)
    def rateThreshold(self):
       pass

class VsanAsyncSystem:
    _name = 'vim.host.VsanAsyncSystem'

    @ManagedType(name=_name, version=_VERSION)
    def __init__(self):
       pass

    @Method(parent=_name,
            wsdlName = "VsanAsyncVersion",
            faults=["vim.fault.NotFound"])
    @Return(typ="string")
    def VsanAsyncVersion(self):
       pass

    #
    # Initiate proactive rebalance on target host
    #
    # @param timeSpan Determines how long this proactive rebalance
    #                 operation lasts in seconds, default 86400.
    # @param varianceThreshold Only if the disk's fullness (defined as
    #                 used_capacity/disk_capacity) is above mean fullness
    #                 and exceeds the lowest-usage disk in the cluster than
    #                 this threshold, this disk is qualified for proactive
    #                 rebalancing, default 0.3.
    # @param timeThreshold Only if the variance threshold has been
    #                 continuously exceeded for this amount of time (in sec),
    #                 the proactive rebalance operation will be applied to
    #                 this disk, default 1800.
    # @param rateThreshold Determines how many bytes clomd on this node can
    #                 move out per hour (MB/hr) for proactive rebalancing,
    #                 default 51200.
    #
    @Method(parent=_name,
            wsdlName="StartProactiveRebalance",
            faults=["vim.fault.VsanFault"])
    @Param(name="timeSpan", typ="int", flags=F_OPTIONAL)
    @Param(name="varianceThreshold", typ="float", flags=F_OPTIONAL)
    @Param(name="timeThreshold", typ="int", flags=F_OPTIONAL)
    @Param(name="rateThreshold", typ="int", flags=F_OPTIONAL)
    @Return(typ="boolean")
    def StartProactiveRebalance(self, timeSpan, varianceThreshold,
                                timeThreshold, rateThreshold):
       pass

    #
    # Stop proactive rebalance on target host
    #
    #
    @Method(parent=_name,
            wsdlName="StopProactiveRebalance",
            faults=["vim.fault.VsanFault"])
    @Return(typ="boolean")
    def StopProactiveRebalance(self):
       pass

    #
    # Retereive information of proactive rebalance on this host
    #
    # @return vim.host.VsanProactiveRebalanceInfo
    #
    @Method(parent=_name,
            wsdlName="GetProactiveRebalanceInfo",
            faults=["vim.fault.VsanFault"])
    @Return(typ="vim.host.VsanProactiveRebalanceInfo")
    def GetProactiveRebalanceInfo(self):
       pass

# Register managed object types
RegisterVmodlTypes()
