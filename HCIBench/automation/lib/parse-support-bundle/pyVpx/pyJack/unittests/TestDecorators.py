#!/usr/bin/env python
"""
Copyright 2008-2020 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is used to test vmodl decorators
"""
__author__ = "VMware, Inc"

import unittest

# import decorators
import sys
sys.path.append("..")
from VmodlDecorators import ManagedType, DataType, EnumType, \
                            Attribute, Method, Param, Return, \
                            F_LINK, F_LINKABLE, F_OPTIONAL, \
                            VmodlDecoratorException, RegisterVmodlTypes


class TestVmodlDecorators(unittest.TestCase):
    # Setup
    def setUp(self):
        pass

    # Test @EnumType
    def test_Enum(self):
        name = "vim.EnumTest"
        version = "vim.version.version9"

        class EnumTest:
            @EnumType(name=name,
                      version=version,
                      values=["enum0", "enum1", "enum2"])
            def __init__(self):
                pass

        RegisterVmodlTypes()

    # Test @DataType
    def test_Data(self):
        name = "vim.DataTest"
        version = "vim.version.version9"
        newerVersion = "vim.version.version11"

        class aDataType:
            # Declare a managed object
            @DataType(name=name, version=version)
            def __init__(self):
                pass

            # Some attributes
            @property
            @Attribute(parent=name, typ="string")
            def aProperty0(self):
                pass

            @Attribute(parent=name, typ="string")
            def aProperty1(self):
                pass

            @Attribute(parent=name, typ="int")
            def aProperty2(self):
                pass

            @Attribute(parent=name, typ="float", version=newerVersion)
            def aProperty3(self):
                pass

        RegisterVmodlTypes()

    # Test @ManagedType and @Attribute
    def ManagedAttribute(self, typ):
        name = "vim.ManagedAttributesTest" + typ
        version = "vim.version.version9"

        class aManagedType:
            # Declare a managed object
            @ManagedType(name=name, version=version)
            def __init__(self):
                pass

            # Define managed property
            @Attribute(parent=name, typ=typ)
            def anAttr(self):
                pass

            @Attribute(parent=name, typ=typ + "[]")
            def anArrayAttr(self):
                pass

            @Attribute(parent=name, typ=typ, privId="System.View")
            def withPrivId(self):
                pass

            @Attribute(parent=name, typ=typ, flags=F_OPTIONAL)
            def withFlags(self):
                pass

            @Attribute(parent=name, typ=typ, msgIdFormat="foo")
            def withMsgIdFormat(self):
                pass

            @Attribute(parent=name,
                       typ=typ,
                       privId="System.Anonymous",
                       msgIdFormat="bar",
                       flags=F_OPTIONAL)
            def mix(self):
                pass

        RegisterVmodlTypes()

    # Test @DataType and @Attribute
    def DataAttribute(self, typ):
        name = "vim.DataAttributesTest" + typ
        version = "vim.version.version9"

        class aDataType:
            # Declare a data object
            @DataType(name=name, version=version)
            def __init__(self):
                pass

            # Define data property
            @Attribute(parent=name, typ=typ)
            def anAttr(self):
                pass

            @Attribute(parent=name, typ=typ + "[]")
            def anArrayAttr(self):
                pass

            @Attribute(parent=name, typ=typ, flags=F_OPTIONAL)
            def withFlags(self):
                pass

            @Attribute(parent=name, typ=typ, msgIdFormat="foo")
            def withMsgIdFormat(self):
                pass

            @Attribute(parent=name,
                       typ=typ,
                       msgIdFormat="bar",
                       flags=F_OPTIONAL)
            def mix(self):
                pass

        RegisterVmodlTypes()

    def test_Attribute(self):
        types = [
            "string", "byte", "bool", "boolean", "short", "int", "long",
            "float", "double", "anyType", "vmodl.ManagedObject", "vmodl.URI",
            "vmodl.DateTime", "vmodl.TypeName", "vmodl.MethodName",
            "vmodl.PropertyPath", "vmodl.Binary"
        ]
        for typ in types:
            self.ManagedAttribute(typ)
            self.DataAttribute(typ)

    # Test @Method
    def test_Method(self):
        name = "vim.MethodTest"
        version = "vim.version.version9"
        newerVersion = "vim.version.version11"

        class aManagedType:
            # Declare a managed object
            @ManagedType(name=name, version=version)
            def __init__(self):
                pass

            # Declare a method object
            @Method(parent=name)
            @Param(name="arg0", typ="string")
            @Param(name="arg1", typ="string")
            @Return(typ=name)
            def ParamsWithReturn(self, arg0, arg1):
                pass

            @Method(parent=name, privId="System.View")
            @Param(name="arg0", typ="string", privId="System.Anonymous")
            @Param(name="arg1", typ="string", privId="Global.Licenses")
            @Return(typ=name)
            def Privileges(self, arg0, arg1):
                pass

            # Check param / return
            @Method(parent=name)
            def NoParamsNoReturn(self):
                pass

            @Method(parent=name)
            @Return(typ=name)
            def NoParams(self):
                pass

            @Method(parent=name)
            @Param(name="arg0", typ="string")
            def NoReturn(self, arg0):
                pass

            @Method(parent=name)
            @Param(name="arg0", typ="string")
            @Return(typ=name, flags=F_OPTIONAL)
            def OptionalReturn(self, arg0):
                pass

            @Method(parent=name)
            @Param(name="arg0", typ="string")
            @Param(name="arg1", typ="string", flags=F_OPTIONAL)
            def OptionalParams(self, arg0, arg1=None):
                pass

            @Method(parent=name)
            @Param(name="arg0", typ="string")
            @Param(name="arg1", typ="string", flags=F_OPTIONAL)
            def OptionalParamsKwargs(self, arg0, arg1=None, **kwargs):
                pass

            @Method(parent=name)
            @Param(name="arg0", typ="string", flags=F_OPTIONAL)
            def OptionalParamsNoFnArgu(self, **kwargs):
                pass

            @Method(parent=name)
            @Return(typ=name)
            def aCustomReturn(self):
                pass

            @Method(parent=name)
            @Return(typ=name)
            def aSelfReturn(self):
                pass

            @Method(parent=name)
            @Param(name="arg0", typ=name)
            def aCustomParam(self, arg0):
                pass

            @Method(parent=name)
            @Param(name="arg0", typ=name)
            def aSelfParam(self, arg0):
                pass

            @Method(parent=name, isTask=True)
            @Param(name="arg0", typ=name)
            def TaskMethod(self, arg0):
                pass

            @Method(parent=name, isTask=True)
            @Param(name="arg0", typ=name)
            @Return(typ=name)
            def ReturnSelfTask(self, arg0):
                pass

            @Method(parent=name, isTask=True)
            @Param(name="arg0", typ=name)
            @Return(typ=name, flags=F_OPTIONAL)
            def ReturnOptionalSelfTask(self, arg0):
                pass

            # Check version
            @Method(parent=name)
            @Param(name="arg0", typ=name)
            def methodNoVersionSpecified(self, arg0):
                pass

            @Method(parent=name, version=version)
            @Param(name="arg0", typ=name, version=version)
            def methodSameVersionSpecified(self, arg0):
                pass

            @Method(parent=name, version=newerVersion)
            def methodNewerVersion(self):
                pass

            @Method(parent=name)
            @Param(name="arg0", typ=name, version=newerVersion)
            def methodParamNewerVersion(self, arg0):
                pass

        RegisterVmodlTypes()

    # Test unknown version
    def test_UnknownVersion(self):
        name = "vim.UnknownVersion"
        version = "vim.version.unknownversion"
        try:

            class UnknownVersionTest:
                @ManagedType(name=name, version=version)
                def __init__(self):
                    pass

            raise Exception("Failed to detect unknown managed version")
        except VmodlDecoratorException as err:
            pass

        try:

            class UnknownVersionTest:
                @DataType(name=name, version=version)
                def __init__(self):
                    pass

            raise Exception("Failed to detect unknown data version")
        except VmodlDecoratorException as err:
            pass

        try:

            class UnknownVersionTest:
                @EnumType(name=name, version=version, values=[])
                def __init__(self):
                    pass

            raise Exception("Failed to detect unknown enum version")
        except VmodlDecoratorException as err:
            pass

    # Test mismatch version
    def test_MismatchVersion(self):
        baseName = "vim.MismatchVersion"
        baseVersion = "vim.version.version9"
        newerVersion = "vim.version.version11"

        try:
            name = baseName + "0"

            class UnknownVersionTest:
                @ManagedType(name=name, version=newerVersion)
                def __init__(self):
                    pass

                @Method(parent=name, version=baseVersion)
                def MethodMismatchVersion(self):
                    pass

            raise Exception("Failed to detect mismatch method version")
        except VmodlDecoratorException as err:
            pass

        try:
            name = baseName + "1"

            class UnknownVersionTest:
                @ManagedType(name=name, version=newerVersion)
                def __init__(self):
                    pass

                @Method(parent=name, version=newerVersion)
                @Param(name="arg0", typ="string", version=baseVersion)
                def MethodParamMismatchVersion(self, arg0):
                    pass

                @Method(parent=name, version=newerVersion)
                @Param(name="arg0", typ="string", version=baseVersion)
                def MethodParamMismatchVersion(self, arg0):
                    pass

            raise Exception("Failed to detect mismatch method param version")
        except VmodlDecoratorException as err:
            pass

        try:

            class UnknownVersionTest:
                @DataType(name=name, version=newerVersion)
                def __init__(self):
                    pass

                @Attribute(parent=name, version=baseVersion)
                def foo(self):
                    pass

            raise Exception("Failed to detect mismatch method version")
        except VmodlDecoratorException as err:
            pass

    # Test null enum
    def test_NullEnum1(self):
        name = "vim.TestNullEnum0"
        version = "vim.version.version9"
        try:

            class NullEnumTest:
                @EnumType(name=name, version=version, values=[])
                def __init__(self):
                    pass

            raise Exception("Failed to detect null enum values")
        except VmodlDecoratorException as err:
            pass

    # Test null enum 2
    def test_NullEnum2(self):
        name = "vim.TestNullEnum1"
        version = "vim.version.version9"
        try:

            class NullEnumTest:
                @EnumType(name=name, version=version, values=None)
                def __init__(self):
                    pass

            raise Exception("Failed to detect null enum values")
        except VmodlDecoratorException as err:
            pass

    # Param name error
    def test_ParamsNameError(self):
        name = "vim.ExceptionTest0"
        version = "vim.version.version9"

        class ExceptionTest:
            @ManagedType(name=name, version=version)
            def __init__(self):
                pass

            try:

                @Method(parent=name)
                @Param(name="arg0", typ="string")
                def ParamsNameError(self, arg1):
                    pass

                raise Exception("Failed to detect arg name mismatch")
            except VmodlDecoratorException as err:
                pass

    # Param order mismatch
    def test_ParamsOrderMismatch(self):
        name = "vim.ExceptionTest1"
        version = "vim.version.version9"

        class ExceptionTest:
            @ManagedType(name=name, version=version)
            def __init__(self):
                pass

            try:

                @Method(parent=name)
                @Param(name="arg0", typ="string")
                @Param(name="arg1", typ="string")
                def ParamsOrderMismatch(self, arg1, arg0):
                    pass

                raise Exception("Failed to detect param order mismatch")
            except VmodlDecoratorException as err:
                pass

    # Missing @Param
    def test_MissingAtParam(self):
        name = "vim.ExceptionTest3"
        version = "vim.version.version9"

        class ExceptionTest:
            @ManagedType(name=name, version=version)
            def __init__(self):
                pass

            try:

                @Method(parent=name)
                @Param(name="arg0", typ="string")
                def MissingAtParam(self, arg0, arg1):
                    pass

                raise Exception("Failed to detect missing param")
            except VmodlDecoratorException as err:
                pass

    # Duplicated @Param
    def test_DuplicatedAtParamName(self):
        name = "vim.ExceptionTest4"
        version = "vim.version.version9"

        class ExceptionTest:
            @ManagedType(name=name, version=version)
            def __init__(self):
                pass

            try:

                @Method(parent=name)
                @Param(name="arg0", typ="string")
                @Param(name="arg0", typ="int")
                def DuplicatedAtParamName(self, arg0, **kwargs):
                    pass

                raise Exception("Failed to detect @Param duplicated name")
            except VmodlDecoratorException as err:
                pass

    # Missing fn param
    def test_MissingFnParam(self):
        name = "vim.ExceptionTest5"
        version = "vim.version.version9"

        class ExceptionTest:
            @ManagedType(name=name, version=version)
            def __init__(self):
                pass

            try:

                @Method(parent=name)
                @Param(name="arg0", typ="string")
                @Param(name="arg1", typ="string")
                def MissingFnParam(self, arg):
                    pass

                raise Exception(
                    "Failed to detect @Param mismatch with fn arguments")
            except VmodlDecoratorException as err:
                pass

    # Method not in ManagedType
    def test_ManagedMethodError(self):
        name = "vim.MethodInDataTypeTest"
        version = "vim.version.version9"
        try:

            class aDataType:
                # Declare a data object
                @DataType(name=name, version=version)
                def __init__(self):
                    pass

                # Declare a method object in Data type
                @Method(parent=name)
                def MustError(self):
                    pass

            raise Exception("Failed to detect @Method in data type")
        except VmodlDecoratorException as err:
            pass

        name = "vim.MethodInEnumTypeTest"
        version = "vim.version.version9"
        try:

            class anEnumType:
                # Declare a enum object
                @EnumType(name=name, values=["foo", "bar"])
                def __init__(self):
                    pass

                # Declare a method object in Data type
                @Method(parent=name)
                def MustError(self):
                    pass

            raise Exception("Failed to detect @Method in enum type")
        except VmodlDecoratorException as err:
            pass

    # DataType error
    def test_DataTypeDecorationError(self):
        name = "vim.DataTypeDecorationError"
        version = "vim.version.version9"
        try:

            class aDataType:
                @DataType(name=name, version=version)
                def __init__(self):
                    pass

                @Attribute(parent=name,
                           typ="string",
                           privId="System.Anonymous",
                           msgIdFormat="bar",
                           flags=F_OPTIONAL)
                def anAttr(self):
                    pass

            raise Exception("Failed to detect extra privId")
        except VmodlDecoratorException as err:
            pass

    # Duplicate property error
    def test_DuplicateProperty(self):
        name = "vim.DataTypeDuplicateProperty"
        version = "vim.version.version9"
        try:

            class aDataType:
                @DataType(name=name, version=version)
                def __init__(self):
                    pass

                @Attribute(parent=name, typ="string")
                def anAttr(self):
                    pass

                @Attribute(parent=name, typ="string")
                def anAttr(self):
                    pass

            raise Exception("Failed to detect duplicate property")
        except VmodlDecoratorException as err:
            pass

    # Duplicate method error
    def test_DuplicateMethod(self):
        name = "vim.ManagedTypeDuplicateMethod"
        version = "vim.version.version9"
        try:

            class aManagedType:
                @ManagedType(name=name, version=version)
                def __init__(self):
                    pass

                @Method(parent=name)
                def aMethod(self):
                    pass

                @Method(parent=name)
                def aMethod(self):
                    pass

            raise Exception("Failed to detect duplicate method")
        except VmodlDecoratorException as err:
            pass


# Test main
if __name__ == "__main__":
    unittest.main()
