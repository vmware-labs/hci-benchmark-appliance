# ******* WARNING - AUTO GENERATED CODE - DO NOT EDIT *******
from .VmomiSupport import CreateDataType, CreateManagedType
from .VmomiSupport import CreateEnumType
from .VmomiSupport import AddVersion, AddVersionParent
from .VmomiSupport import AddBreakingChangesInfo
from .VmomiSupport import F_LINK, F_LINKABLE
from .VmomiSupport import F_OPTIONAL, F_SECRET
from .VmomiSupport import newestVersions, ltsVersions
from .VmomiSupport import dottedVersions, oldestVersions

AddVersion("vmodl.version.version0", "", "", 0, "vim25")
AddVersion("vmodl.version.version1", "", "", 0, "vim25")
AddVersion("vmodl.version.version2", "", "", 0, "vim25")
AddVersion("vmodl.reflect.version.version1", "reflect", "1.0", 0, "reflect")
AddVersion("vmodl.reflect.version.version2", "reflect", "2.0", 0, "reflect")
AddVersionParent("vmodl.version.version0", "vmodl.version.version0")
AddVersionParent("vmodl.version.version1", "vmodl.version.version0")
AddVersionParent("vmodl.version.version1", "vmodl.version.version1")
AddVersionParent("vmodl.version.version2", "vmodl.version.version0")
AddVersionParent("vmodl.version.version2", "vmodl.version.version1")
AddVersionParent("vmodl.version.version2", "vmodl.version.version2")
AddVersionParent("vmodl.reflect.version.version1", "vmodl.version.version0")
AddVersionParent("vmodl.reflect.version.version1", "vmodl.version.version1")
AddVersionParent("vmodl.reflect.version.version1", "vmodl.version.version2")
AddVersionParent("vmodl.reflect.version.version1", "vmodl.reflect.version.version1")
AddVersionParent("vmodl.reflect.version.version2", "vmodl.version.version0")
AddVersionParent("vmodl.reflect.version.version2", "vmodl.version.version1")
AddVersionParent("vmodl.reflect.version.version2", "vmodl.version.version2")
AddVersionParent("vmodl.reflect.version.version2", "vmodl.reflect.version.version1")
AddVersionParent("vmodl.reflect.version.version2", "vmodl.reflect.version.version2")

newestVersions.Add("vmodl.reflect.version.version2")
ltsVersions.Add("vmodl.reflect.version.version2")
dottedVersions.Add("vmodl.reflect.version.version2")
oldestVersions.Add("vmodl.reflect.version.version1")

CreateManagedType("vmodl.reflect.DynamicTypeManager", "InternalDynamicTypeManager", "vmodl.ManagedObject", "vmodl.reflect.version.version1", None, [("queryTypeInfo", "DynamicTypeMgrQueryTypeInfo", "vmodl.reflect.version.version1", (("filterSpec", "vmodl.reflect.DynamicTypeManager.FilterSpec", "vmodl.reflect.version.version1", F_OPTIONAL, None),), (0, "vmodl.reflect.DynamicTypeManager.AllTypeInfo", "vmodl.reflect.DynamicTypeManager.AllTypeInfo"), "System.Read", None), ("queryMoInstances", "DynamicTypeMgrQueryMoInstances", "vmodl.reflect.version.version1", (("filterSpec", "vmodl.reflect.DynamicTypeManager.FilterSpec", "vmodl.reflect.version.version1", F_OPTIONAL, None),), (F_OPTIONAL, "vmodl.reflect.DynamicTypeManager.MoInstance[]", "vmodl.reflect.DynamicTypeManager.MoInstance[]"), "System.Read", None)])
CreateDataType("vmodl.reflect.DynamicTypeManager.Annotation", "DynamicTypeMgrAnnotation", "vmodl.DynamicData", "vmodl.reflect.version.version1", [("name", "string", "vmodl.reflect.version.version1", 0), ("parameter", "string[]", "vmodl.reflect.version.version1", F_OPTIONAL)])
CreateDataType("vmodl.reflect.DynamicTypeManager.PropertyTypeInfo", "DynamicTypeMgrPropertyTypeInfo", "vmodl.DynamicData", "vmodl.reflect.version.version1", [("name", "string", "vmodl.reflect.version.version1", 0), ("version", "string", "vmodl.reflect.version.version1", 0), ("type", "string", "vmodl.reflect.version.version1", 0), ("privId", "string", "vmodl.reflect.version.version1", F_OPTIONAL), ("msgIdFormat", "string", "vmodl.reflect.version.version1", F_OPTIONAL), ("annotation", "vmodl.reflect.DynamicTypeManager.Annotation[]", "vmodl.reflect.version.version1", F_OPTIONAL)])
CreateEnumType("vmodl.reflect.DynamicTypeManager.PropertyTypeInfo.AnnotationType", "DynamicTypeMgrPropertyTypeInfoAnnotationType", "vmodl.reflect.version.version1", ["optional", "readonly", "linkable", "link"])
CreateDataType("vmodl.reflect.DynamicTypeManager.DataTypeInfo", "DynamicTypeMgrDataTypeInfo", "vmodl.DynamicData", "vmodl.reflect.version.version1", [("name", "string", "vmodl.reflect.version.version1", 0), ("wsdlName", "string", "vmodl.reflect.version.version1", 0), ("version", "string", "vmodl.reflect.version.version1", 0), ("base", "string[]", "vmodl.reflect.version.version1", F_OPTIONAL), ("property", "vmodl.reflect.DynamicTypeManager.PropertyTypeInfo[]", "vmodl.reflect.version.version1", F_OPTIONAL), ("annotation", "vmodl.reflect.DynamicTypeManager.Annotation[]", "vmodl.reflect.version.version1", F_OPTIONAL)])
CreateDataType("vmodl.reflect.DynamicTypeManager.ParamTypeInfo", "DynamicTypeMgrParamTypeInfo", "vmodl.DynamicData", "vmodl.reflect.version.version1", [("name", "string", "vmodl.reflect.version.version1", 0), ("version", "string", "vmodl.reflect.version.version1", 0), ("type", "string", "vmodl.reflect.version.version1", 0), ("privId", "string", "vmodl.reflect.version.version1", F_OPTIONAL), ("annotation", "vmodl.reflect.DynamicTypeManager.Annotation[]", "vmodl.reflect.version.version1", F_OPTIONAL)])
CreateEnumType("vmodl.reflect.DynamicTypeManager.ParamTypeInfo.AnnotationType", "DynamicTypeMgrParamTypeInfoAnnotationType", "vmodl.reflect.version.version1", ["optional", "secret"])
CreateDataType("vmodl.reflect.DynamicTypeManager.MethodTypeInfo", "DynamicTypeMgrMethodTypeInfo", "vmodl.DynamicData", "vmodl.reflect.version.version1", [("name", "string", "vmodl.reflect.version.version1", 0), ("wsdlName", "string", "vmodl.reflect.version.version1", 0), ("version", "string", "vmodl.reflect.version.version1", 0), ("paramTypeInfo", "vmodl.reflect.DynamicTypeManager.ParamTypeInfo[]", "vmodl.reflect.version.version1", F_OPTIONAL), ("returnTypeInfo", "vmodl.reflect.DynamicTypeManager.ParamTypeInfo", "vmodl.reflect.version.version1", F_OPTIONAL), ("fault", "string[]", "vmodl.reflect.version.version1", F_OPTIONAL), ("privId", "string", "vmodl.reflect.version.version1", F_OPTIONAL), ("annotation", "vmodl.reflect.DynamicTypeManager.Annotation[]", "vmodl.reflect.version.version1", F_OPTIONAL)])
CreateEnumType("vmodl.reflect.DynamicTypeManager.MethodTypeInfo.AnnotationType", "DynamicTypeMgrMethodTypeInfoAnnotationType", "vmodl.reflect.version.version1", ["internal"])
CreateDataType("vmodl.reflect.DynamicTypeManager.ManagedTypeInfo", "DynamicTypeMgrManagedTypeInfo", "vmodl.DynamicData", "vmodl.reflect.version.version1", [("name", "string", "vmodl.reflect.version.version1", 0), ("wsdlName", "string", "vmodl.reflect.version.version1", 0), ("version", "string", "vmodl.reflect.version.version1", 0), ("base", "string[]", "vmodl.reflect.version.version1", F_OPTIONAL), ("property", "vmodl.reflect.DynamicTypeManager.PropertyTypeInfo[]", "vmodl.reflect.version.version1", F_OPTIONAL), ("method", "vmodl.reflect.DynamicTypeManager.MethodTypeInfo[]", "vmodl.reflect.version.version1", F_OPTIONAL), ("annotation", "vmodl.reflect.DynamicTypeManager.Annotation[]", "vmodl.reflect.version.version1", F_OPTIONAL)])
CreateDataType("vmodl.reflect.DynamicTypeManager.EnumTypeInfo", "DynamicTypeEnumTypeInfo", "vmodl.DynamicData", "vmodl.reflect.version.version1", [("name", "string", "vmodl.reflect.version.version1", 0), ("wsdlName", "string", "vmodl.reflect.version.version1", 0), ("version", "string", "vmodl.reflect.version.version1", 0), ("value", "string[]", "vmodl.reflect.version.version1", F_OPTIONAL), ("annotation", "vmodl.reflect.DynamicTypeManager.Annotation[]", "vmodl.reflect.version.version1", F_OPTIONAL)])
CreateDataType("vmodl.reflect.DynamicTypeManager.AllTypeInfo", "DynamicTypeMgrAllTypeInfo", "vmodl.DynamicData", "vmodl.reflect.version.version1", [("managedTypeInfo", "vmodl.reflect.DynamicTypeManager.ManagedTypeInfo[]", "vmodl.reflect.version.version1", F_OPTIONAL), ("enumTypeInfo", "vmodl.reflect.DynamicTypeManager.EnumTypeInfo[]", "vmodl.reflect.version.version1", F_OPTIONAL), ("dataTypeInfo", "vmodl.reflect.DynamicTypeManager.DataTypeInfo[]", "vmodl.reflect.version.version1", F_OPTIONAL)])
CreateDataType("vmodl.reflect.DynamicTypeManager.MoInstance", "DynamicTypeMgrMoInstance", "vmodl.DynamicData", "vmodl.reflect.version.version1", [("id", "string", "vmodl.reflect.version.version1", 0), ("moType", "string", "vmodl.reflect.version.version1", 0)])
CreateDataType("vmodl.reflect.DynamicTypeManager.FilterSpec", "DynamicTypeMgrFilterSpec", "vmodl.DynamicData", "vmodl.reflect.version.version1", None)
CreateDataType("vmodl.reflect.DynamicTypeManager.TypeFilterSpec", "DynamicTypeMgrTypeFilterSpec", "vmodl.reflect.DynamicTypeManager.FilterSpec", "vmodl.reflect.version.version1", [("typeSubstr", "string", "vmodl.reflect.version.version1", F_OPTIONAL)])
CreateDataType("vmodl.reflect.DynamicTypeManager.MoFilterSpec", "DynamicTypeMgrMoFilterSpec", "vmodl.reflect.DynamicTypeManager.FilterSpec", "vmodl.reflect.version.version1", [("id", "string", "vmodl.reflect.version.version1", F_OPTIONAL), ("typeSubstr", "string", "vmodl.reflect.version.version1", F_OPTIONAL)])
CreateManagedType("vmodl.reflect.ManagedMethodExecuter", "ReflectManagedMethodExecuter", "vmodl.ManagedObject", "vmodl.reflect.version.version1", None, [("executeSoap", "ExecuteSoap", "vmodl.reflect.version.version1", (("moid", "string", "vmodl.reflect.version.version1", 0, None),("version", "string", "vmodl.reflect.version.version1", 0, None),("method", "string", "vmodl.reflect.version.version1", 0, None),("argument", "vmodl.reflect.ManagedMethodExecuter.SoapArgument[]", "vmodl.reflect.version.version1", F_OPTIONAL, None),), (F_OPTIONAL, "vmodl.reflect.ManagedMethodExecuter.SoapResult", "vmodl.reflect.ManagedMethodExecuter.SoapResult"), None, None), ("fetchSoap", "FetchSoap", "vmodl.reflect.version.version1", (("moid", "string", "vmodl.reflect.version.version1", 0, None),("version", "string", "vmodl.reflect.version.version1", 0, None),("prop", "string", "vmodl.reflect.version.version1", 0, None),), (F_OPTIONAL, "vmodl.reflect.ManagedMethodExecuter.SoapResult", "vmodl.reflect.ManagedMethodExecuter.SoapResult"), None, None)])
CreateDataType("vmodl.reflect.ManagedMethodExecuter.SoapArgument", "ReflectManagedMethodExecuterSoapArgument", "vmodl.DynamicData", "vmodl.reflect.version.version1", [("name", "string", "vmodl.reflect.version.version1", 0), ("val", "string", "vmodl.reflect.version.version1", 0)])
CreateDataType("vmodl.reflect.ManagedMethodExecuter.SoapFault", "ReflectManagedMethodExecuterSoapFault", "vmodl.DynamicData", "vmodl.reflect.version.version1", [("faultMsg", "string", "vmodl.reflect.version.version1", 0), ("faultDetail", "string", "vmodl.reflect.version.version1", F_OPTIONAL)])
CreateDataType("vmodl.reflect.ManagedMethodExecuter.SoapResult", "ReflectManagedMethodExecuterSoapResult", "vmodl.DynamicData", "vmodl.reflect.version.version1", [("response", "string", "vmodl.reflect.version.version1", F_OPTIONAL), ("fault", "vmodl.reflect.ManagedMethodExecuter.SoapFault", "vmodl.reflect.version.version1", F_OPTIONAL)])
