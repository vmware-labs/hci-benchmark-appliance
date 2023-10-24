# **********************************************************
# Copyright 2005-2022 VMware, Inc.  All rights reserved. -- VMware Confidential
# **********************************************************

import sys
if sys.version_info < (2, 7, 9):
    sys.stderr.write("pyVmomi requires Python 2.7.9 or newer")
    sys.exit(1)

_initialized = False


# Definition precedes pyVmomi modules imports to escape circular
# dependency error if modules import is_initialized()
def _assert_not_initialized():
    if _initialized:
        raise RuntimeError("pyVmomi is already initialized!")


try:
    from .pyVmomiSettings import *  # noqa: F403
except ImportError:
    pass

# set default settings
_allowGetSet = locals().get('allowGetSet', True)
_allowCapitalizedNames = locals().get('allowCapitalizedNames', True)

from . import __bindings  # noqa: F401
from . import VmomiSupport  # noqa: F402
from . import Feature  # noqa: F402

# All data object types and fault types have DynamicData as an ancestor
# As well load it proactively.
# Note: This should be done before importing SoapAdapter as it uses
# some fault types
VmomiSupport.GetVmodlType("vmodl.DynamicData")

from .SoapAdapter import (  # noqa: E402,F401
    SessionOrientedStub, SoapCmdStubAdapter, SoapStubAdapter, StubAdapterBase,
    ThumbprintMismatchException)

types = VmomiSupport.types

# This will allow files to use Create** functions
# directly from pyVmomi
CreateEnumType = VmomiSupport.CreateEnumType
CreateDataType = VmomiSupport.CreateDataType
CreateManagedType = VmomiSupport.CreateManagedType

# For all the top level names, creating a LazyModule object
# in the global namespace of pyVmomi. Files can just import the
# top level namespace and we will figure out what to load and when
# Examples:
# ALLOWED: from pyVmomi import vim
# NOT ALLOWED: from pyVmomi import vim.host
_globals = globals()
for name in VmomiSupport._topLevelNames:
    upperCaseName = VmomiSupport.Capitalize(name)
    obj = VmomiSupport.LazyModule(name)
    _globals[name] = obj
    if _allowCapitalizedNames:
        _globals[upperCaseName] = obj
    if not hasattr(VmomiSupport.types, name):
        setattr(VmomiSupport.types, name, obj)
        if _allowCapitalizedNames:
            setattr(VmomiSupport.types, upperCaseName, obj)
del _globals


def init():
    _assert_not_initialized()
    Feature._init()
    global _initialized
    _initialized = True
