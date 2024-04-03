#!/usr/bin/env python
"""
Copyright 2008-2022 VMware, Inc.  All rights reserved. -- VMware Confidential

This module provides vmodl decorators for vmomi dynamic types declaration
"""
__author__ = "VMware, Inc"

import inspect
import logging
from . import DynTypeMgr
from pyVmomi import VmomiSupport

# Base version (version 1)
VERSION1 = "vim.version.version9"

# Flags (same as VmomiSupport flags)
F_LINK = VmomiSupport.F_LINK
F_LINKABLE = VmomiSupport.F_LINKABLE
F_OPTIONAL = VmomiSupport.F_OPTIONAL

# Decorator types
from collections import OrderedDict
_gDecoratorTypes = OrderedDict()


class VmodlDecoratorException(Exception):
    """Base Decorator exception"""
    # Python 2.6+ deprecated 'message' attr from BaseException. Override the
    # BaseException.message attr and make this a simple str
    message = ""

    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message


class ManagedTypeContainer:
    """Managed type container"""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class DataTypeContainer:
    """Data type container"""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class EnumTypeContainer:
    """Enum type container"""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


# Generate wsdl name from vmodl name
#
# @param  dottedName fully qualified vmodl name
# @return Generated wsdl name
def GenerateWsdlName(dottedName):
    """Generate WSDL name from vmodl name"""
    return "".join(
        [VmomiSupport.Capitalize(name) for name in dottedName.split(".")])


# Test for type exists
#
# @param  name fully qualified vmodl name
# @return True if exists
def TypeExists(name):
    """Type exists?"""
    if VmomiSupport.TypeDefExists(name):
        return True
    else:
        if name.endswith("[]"):
            name = name[:-2]
        return name in _gDecoratorTypes


# Test if the property is already defined in the type
#
# @param aType dynamic type
# @propName name of the property
# @return True if it is a duplicate property
def IsDuplicateProperty(aType, propName):
    """Duplicate Property?"""
    for prop in aType.properties:
        if prop.name == propName:
            return True
    return False


# Test if the method is already defined in the type
#
# @param aType dynamic type
# @propName name of the method
# @return True if it is a duplicate method
def IsDuplicateMethod(aType, methodName):
    """Duplicate Method?"""
    for method in aType.methods:
        if method.name == methodName:
            return True
    return False


# Test for version exists
#
# @param  version fully qualified vmodl version name
# @return True if exists
def VersionExists(version):
    """Version exists?"""

    return version in VmomiSupport.nsMap


# Guess version from parent version and input version.
#  Throw if version not exist / not child of parent version
#
# @param  parentVersion fully qualified vmodl parent version name
# @param  version fully qualified vmodl version name
# @return  version if exists
def GuessVersion(parentVersion, version):
    """Verify version"""
    if version:
        # Make sure version exists
        if not VersionExists(version):
            message = "Unknown version " + version
            raise VmodlDecoratorException(message)

        # Make sure version is same or newer than parent version
        if not VmomiSupport.IsChildVersion(version, parentVersion):
            message = "Version " + version + " is not child of " + parentVersion
            raise VmodlDecoratorException(message)
    else:
        # Does not specify method version. Same as parent version
        version = parentVersion
    return version


# Uncapitalize a name
#
# @param  name A string
# @return An un-capitalized string
def UnCapitalize(name):
    """Uncapitalize a name"""
    if name:
        return name[0].lower() + name[1:]
    else:
        return name


# Managed type decorator
#
# @param  name fully qualified vmodl name
# @param  wsdlName WSDL name
# @param  base fully qualified vmodl base name
# @param  version Version
# @return Managed type decorator
def ManagedType(name,
                wsdlName=None,
                base="vmodl.ManagedObject",
                version=VERSION1):
    """Managed type decorator constructor"""
    def Decorate(f):
        """Managed type decorator"""
        # Make sure managed type doesn't exists
        if TypeExists(name):
            message = "@ManagedType " + name + " already exists"
            logging.error(message)
            raise VmodlDecoratorException(message)

        if not VersionExists(version):
            message = "@ManagedType unknown version " + version
            logging.error(message)
            raise VmodlDecoratorException(message)

        # Generate wsdlName if not given
        typeWsdlName = wsdlName and wsdlName or GenerateWsdlName(name)

        # TODO: Verify base is inherited from ManagedObject

        # Log info
        # logging.info("ManagedType: " + name + " " + typeWsdlName + " "
        #                              + base + " " + version)

        # Add managed type
        _gDecoratorTypes[name] = ManagedTypeContainer(name=name,
                                                      wsdlName=typeWsdlName,
                                                      base=base,
                                                      version=version,
                                                      properties=[],
                                                      methods=[])
        return f

    return Decorate


# Data type decorator
#
# @param  name fully qualified vmodl name
# @param  wsdlName WSDL name
# @param  base fully qualified vmodl base name
# @param  version Version
# @return Data type decorator
def DataType(name, wsdlName=None, base="vmodl.DynamicData", version=VERSION1):
    """Data type decorator constructor"""
    def Decorate(f):
        """Data type decorator"""
        # Make sure data type doesn't exists
        if TypeExists(name):
            message = "@DataType " + name + " already exists"
            logging.error(message)
            raise VmodlDecoratorException(message)

        if not VersionExists(version):
            message = "@DataType unknown version " + version
            logging.error(message)
            raise VmodlDecoratorException(message)

        # Generate wsdlName if not given
        typeWsdlName = wsdlName and wsdlName or GenerateWsdlName(name)

        # TODO: Verify base is inherited from DynamicData

        # Log info
        # logging.info("DataType: " + name + " " + typeWsdlName + " "
        #                           + base + " " + version)

        # Add data type
        _gDecoratorTypes[name] = DataTypeContainer(name=name,
                                                   wsdlName=typeWsdlName,
                                                   base=base,
                                                   version=version,
                                                   properties=[])
        return f

    return Decorate


# Enum type decorator
#
# @param  name fully qualified vmodl name
# @param  wsdlName WSDL name
# @param  version Version
# @param  values Enum values
# @return Enum type decorator
def EnumType(name, wsdlName=None, version=VERSION1, values=None):
    """Enum type decorator constructor"""
    def Decorate(f):
        """Enum type decorator"""
        # Make sure data type doesn't exists
        if TypeExists(name):
            message = "@EnumType " + name + " already exists"
            logging.error(message)
            raise VmodlDecoratorException(message)

        if not VersionExists(version):
            message = "@EnumType unknown version " + version
            logging.error(message)
            raise VmodlDecoratorException(message)

        # At least one enum value is required
        if not values:
            message = "@EnumType " + name + " missing enum values"
            logging.error(message)
            raise VmodlDecoratorException(message)

        # Add data type
        # Generate wsdlName if not given
        typeWsdlName = wsdlName and wsdlName or GenerateWsdlName(name)

        # Log info
        # logging.info("EnumType: " + name + " " + typeWsdlName + " "
        #                           + version + " " + str(values))

        _gDecoratorTypes[name] = EnumTypeContainer(name=name,
                                                   wsdlName=typeWsdlName,
                                                   version=version,
                                                   values=values)
        return f

    return Decorate


# Managed type method decorator
#
# @param  name fully qualified vmodl name
# @param  wsdlName WSDL name
# @param  version Version. None => same as parent version
# @param  faults Method faults
# @param  privId Privilege id
# @return Method decorator
def Method(parent,
           wsdlName=None,
           version=None,
           faults=None,
           privId=None,
           isTask=False):
    """Method type decorator constructor"""
    def Decorate(f):
        """Method type decorator"""

        # Make sure parent exists
        try:
            aType = _gDecoratorTypes[parent]
        except KeyError:
            message = "@Method " + f.__name__ + \
                      " parent " + parent + " does not exist"
            logging.error(message)
            raise VmodlDecoratorException(message)

        # Parent is a managed type
        if not isinstance(aType, ManagedTypeContainer):
            message = "@Method " + f.__name__ + \
                      " parent " + parent + " is not managed type"
            logging.error(message)
            raise VmodlDecoratorException(message)

        # Verify that the method was not already defined
        if IsDuplicateMethod(aType, f.__name__):
            message = "@Method " + f.__name__ + " already defined"
            logging.error(message)
            raise VmodlDecoratorException(message)

        # Guess version
        try:
            methodVersion = GuessVersion(aType.version, version)
        except VmodlDecoratorException as err:
            err.message = "@Method " + f.__name__ + " " + UnCapitalize(
                err.message)
            logging.error(err.message)
            raise err

        # Generate wsdlName if not given
        typeWsdlName = wsdlName and wsdlName \
                                 or GenerateWsdlName(parent + "." + f.__name__)
        if isTask:
            typeWsdlName += "_Task"
        params = hasattr(f, "_params") and f._params or []
        returns = hasattr(f, "_returns") \
                          and f._returns or VmomiSupport.Object(name="return",
                                                                type="void",
                                                                flags=0)

        # Basic params verification
        for param in params:
            if param.version:
                # Make sure version is same or newer than parent version
                try:
                    param.version = GuessVersion(methodVersion, param.version)
                except VmodlDecoratorException as err:
                    err.message = "@Param " + param.name + \
                                  " " + UnCapitalize(err.message)
                    logging.error(err.message)
                    raise err
            else:
                # Does not specific param version. Same as method version
                param.version = methodVersion

        # Check params with function params
        args, varargs, kwargs, argDefs = inspect.getargspec(f)

        # Get num of optional argument
        numNonOptionArgs = 0
        if args:
            numNonOptionArgs = len(args)
            if argDefs:
                numNonOptionArgs -= len(argDefs)

        iArg = 0
        nSelf = 0
        for arg in args:
            if arg == "self":
                numNonOptionArgs -= 1
                nSelf = 1
                continue

            # Make sure param is specified with @Param
            try:
                param = params[iArg]
            except IndexError:
                message = "No @Param for fn arguments " + str(
                    args[iArg + nSelf:])
                logging.error(message)
                raise VmodlDecoratorException(message)

            # Make sure name / order match fn definition
            if param.name != arg:
                message = "@Param " + param.name + \
                                     " name/order does not match fn arguments"
                logging.error(message)
                raise VmodlDecoratorException(message)

            # Increament argument index
            iArg += 1

        # If there is param left, make sure kwargs is not None
        if len(params) > iArg:
            for param in params[iArg:]:
                message = "@Param " + param.name + " missing from fn arguments"
                if not kwargs:
                    logging.error(message)
                    raise VmodlDecoratorException(message)
                else:
                    logging.warning(message)

        # Add method type to parent
        aType.methods.append(
            VmomiSupport.Object(name=f.__name__,
                                wsdlName=typeWsdlName,
                                version=methodVersion,
                                params=params,
                                returns=returns,
                                faults=faults,
                                privId=privId,
                                isTask=isTask))
        return f

    return Decorate


# Managed type method parameter decorator
#
# @param  name fully qualified vmodl name
# @param  typ fully qualified vmodl type name
# @param  version Version. None => same as parent version
# @param  flags Param flags
# @param  privId Privilege id
# @return Param decorator
def Param(name, typ, version=None, flags=0, privId=None):
    """Param type decorator constructor"""
    def Decorate(f):
        """Param type decorator"""
        if not hasattr(f, "_params"):
            f._params = []
        else:
            # Detect duplicated name
            for obj in f._params:
                if obj.name == name:
                    message = "@Param duplicated name " + str(name)
                    logging.error(message)
                    raise VmodlDecoratorException(message)

        # Verify type
        if not TypeExists(typ):
            message = "@Param unknown type " + str(typ)
            logging.error(message)
            raise VmodlDecoratorException(message)

        # Verify version
        if version and not VersionExists(version):
            message = "@Param unknown version " + version
            logging.error(message)
            raise VmodlDecoratorException(message)

        param = VmomiSupport.Object(name=name,
                                    type=typ,
                                    version=version,
                                    flags=flags,
                                    privId=privId)
        f._params.insert(0, param)
        return f

    return Decorate


# Managed type method return decorator
#
# @param  typ fully qualified vmodl return type name
# @param  flags return flags
# @return Return decorator
def Return(typ, flags=0):
    """Return type decorator constructor"""
    def Decorate(f):
        """Return type decorator"""
        # Verify type
        if not TypeExists(typ):
            message = "@Return unknown type " + str(typ)
            logging.error(message)
            raise VmodlDecoratorException(message)

        f._returns = VmomiSupport.Object(name="return", type=typ, flags=flags)
        return f

    return Decorate


# Managed / Data type property decorator
# Note: Fn should be named as "Property". However, it is too close to Python
#       builts-in "property". Named this fn "Attribute" instead.
#
# @param  name fully qualified vmodl name
# @param  typ fully qualified vmodl type name
# @param  version Version. None => same as parent version
# @param  flags Attribute flags
# @param  privId Privilege id (only for ManagedObject property)
# @param  msgIdFormat Msg id format
# @return Attribute decorator
def Attribute(parent,
              typ,
              version=None,
              flags=0,
              privId=None,
              msgIdFormat=None):
    """Attribute type decorator constructor"""
    def Decorate(f):
        """Attribute type decorator"""
        # Make sure parent exists
        try:
            aType = _gDecoratorTypes[parent]
        except KeyError:
            message = "@Attribute " + f.__name__ + \
                      " parent " + parent + " does not exist"
            logging.error(message)
            raise VmodlDecoratorException(message)

        # Parent is a managed type or data type
        if not isinstance(aType, ManagedTypeContainer) and \
           not isinstance(aType, DataTypeContainer):
            message = "@Attribute " + f.__name__ + \
                      " parent " + parent + " is not managed / data type"
            logging.error(message)
            raise VmodlDecoratorException(message)

        # Verify that the property was not already defined
        if IsDuplicateProperty(aType, f.__name__):
            message = "@Attribute " + f.__name__ + \
                      " already defined"
            logging.error(message)
            raise VmodlDecoratorException(message)

        if isinstance(aType, DataTypeContainer):
            if privId != None:
                message = "@Attribute for DataObject " + f.__name__ + \
                          " cannot specify privId"
                logging.error(message)
                raise VmodlDecoratorException(message)

        # Verify type
        if not TypeExists(typ):
            message = "@Attribute " + f.__name__ + " unknown type " + str(typ)
            logging.error(message)
            raise VmodlDecoratorException(message)

        # Guess version
        try:
            attrVersion = GuessVersion(aType.version, version)
        except VmodlDecoratorException as err:
            err.message = "@Attribute " + f.__name__ + \
                          " " + UnCapitalize(err.message)
            logging.error(err.message)
            raise err

        # Add property to parent
        aType.properties.append(
            VmomiSupport.Object(name=f.__name__,
                                type=typ,
                                version=attrVersion,
                                flags=flags,
                                privId=privId,
                                msgIdFormat=msgIdFormat))
        return f

    return Decorate


# Register decorated vmodl types
#
# @param  names Types to register. None => Register all stored decorators
# @param  doNotFlush Do not flush unregister types
# @return List of registered type name
def RegisterVmodlTypes(names=None, doNotFlush=False):
    """Register vmodl types"""
    dynTypeMgr = DynTypeMgr.GetDynTypeMgr()

    if names:
        registerNames = names
    else:
        registerNames = list(_gDecoratorTypes.keys())

    types = []
    registered = []
    for name in registerNames:
        try:
            aType = _gDecoratorTypes[name]
        except KeyError:
            message = name + " does not exist"
            logging.error(message)

        if isinstance(aType, ManagedTypeContainer):
            # Create managed type
            properties = aType.properties
            methods = aType.methods
            dynType = dynTypeMgr.CreateManagedType(aType.name, aType.wsdlName,
                                                   aType.base, aType.version,
                                                   properties, methods)
        elif isinstance(aType, DataTypeContainer):
            # Create data type
            properties = aType.properties
            dynType = dynTypeMgr.CreateDataType(aType.name, aType.wsdlName,
                                                aType.base, aType.version,
                                                properties)
        elif isinstance(aType, EnumTypeContainer):
            # Create enum type
            dynType = dynTypeMgr.CreateEnumType(aType.name, aType.wsdlName,
                                                aType.version, aType.values)
        else:
            message = "Unknown container type " + str(aType)
            logging.error(message)
            raise VmodlDecoratorException(message)

        # Add type
        types.append(dynType)

        # Add registered name
        registered.append(aType.name)

    # Register types
    dynTypeMgr.RegisterTypes(types)

    # Flush decorator
    if not doNotFlush:
        FlushVmodlTypes()

    return registered


def FlushVmodlTypes():
    """Flush decorated vmodl types"""
    _gDecoratorTypes.clear()
