# ******* WARNING - AUTO GENERATED CODE - DO NOT EDIT *******
from .VmomiSupport import CreateDataType, CreateManagedType
from .VmomiSupport import CreateEnumType
from .VmomiSupport import AddVersion, AddVersionParent
from .VmomiSupport import AddBreakingChangesInfo
from .VmomiSupport import F_LINK, F_LINKABLE
from .VmomiSupport import F_OPTIONAL, F_SECRET
from .VmomiSupport import newestVersions, ltsVersions
from .VmomiSupport import dottedVersions, oldestVersions

AddVersion("vmodl.query.version.version4", "", "", 0, "vim25")
AddVersion("vmodl.query.version.version3", "", "", 0, "vim25")
AddVersion("vmodl.query.version.version2", "", "", 0, "vim25")
AddVersion("vmodl.query.version.version1", "", "", 0, "vim25")
AddVersion("vim.version.version6", "vim25", "4.1", 0, "vim25")
AddVersion("vim.version.version7", "vim25", "5.0", 0, "vim25")
AddVersion("vim.version.version1", "vim2", "2.0", 0, "vim25")
AddVersion("vim.version.version4", "vim25", "2.5u2server", 0, "vim25")
AddVersion("vim.version.version5", "vim25", "4.0", 0, "vim25")
AddVersion("vim.version.version2", "vim25", "2.5", 0, "vim25")
AddVersion("vim.version.version3", "vim25", "2.5u2", 0, "vim25")
AddVersion("vmodl.version.version0", "", "", 0, "vim25")
AddVersion("vmodl.version.version1", "", "", 0, "vim25")
AddVersion("vmodl.version.version2", "", "", 0, "vim25")
AddVersion("vsm.version.version1", "vsm", "1.0", 0, "vsm")
AddVersion("vmodl.reflect.version.version1", "reflect", "1.0", 0, "reflect")
AddVersionParent("vmodl.query.version.version4", "vmodl.query.version.version4")
AddVersionParent("vmodl.query.version.version4", "vmodl.query.version.version3")
AddVersionParent("vmodl.query.version.version4", "vmodl.query.version.version2")
AddVersionParent("vmodl.query.version.version4", "vmodl.query.version.version1")
AddVersionParent("vmodl.query.version.version4", "vmodl.version.version0")
AddVersionParent("vmodl.query.version.version4", "vmodl.version.version1")
AddVersionParent("vmodl.query.version.version4", "vmodl.version.version2")
AddVersionParent("vmodl.query.version.version3", "vmodl.query.version.version3")
AddVersionParent("vmodl.query.version.version3", "vmodl.query.version.version2")
AddVersionParent("vmodl.query.version.version3", "vmodl.query.version.version1")
AddVersionParent("vmodl.query.version.version3", "vmodl.version.version0")
AddVersionParent("vmodl.query.version.version3", "vmodl.version.version1")
AddVersionParent("vmodl.query.version.version2", "vmodl.query.version.version2")
AddVersionParent("vmodl.query.version.version2", "vmodl.query.version.version1")
AddVersionParent("vmodl.query.version.version2", "vmodl.version.version0")
AddVersionParent("vmodl.query.version.version2", "vmodl.version.version1")
AddVersionParent("vmodl.query.version.version1", "vmodl.query.version.version1")
AddVersionParent("vmodl.query.version.version1", "vmodl.version.version0")
AddVersionParent("vim.version.version6", "vmodl.query.version.version3")
AddVersionParent("vim.version.version6", "vmodl.query.version.version2")
AddVersionParent("vim.version.version6", "vmodl.query.version.version1")
AddVersionParent("vim.version.version6", "vim.version.version6")
AddVersionParent("vim.version.version6", "vim.version.version1")
AddVersionParent("vim.version.version6", "vim.version.version4")
AddVersionParent("vim.version.version6", "vim.version.version5")
AddVersionParent("vim.version.version6", "vim.version.version2")
AddVersionParent("vim.version.version6", "vim.version.version3")
AddVersionParent("vim.version.version6", "vmodl.version.version0")
AddVersionParent("vim.version.version6", "vmodl.version.version1")
AddVersionParent("vim.version.version7", "vmodl.query.version.version4")
AddVersionParent("vim.version.version7", "vmodl.query.version.version3")
AddVersionParent("vim.version.version7", "vmodl.query.version.version2")
AddVersionParent("vim.version.version7", "vmodl.query.version.version1")
AddVersionParent("vim.version.version7", "vim.version.version6")
AddVersionParent("vim.version.version7", "vim.version.version7")
AddVersionParent("vim.version.version7", "vim.version.version1")
AddVersionParent("vim.version.version7", "vim.version.version4")
AddVersionParent("vim.version.version7", "vim.version.version5")
AddVersionParent("vim.version.version7", "vim.version.version2")
AddVersionParent("vim.version.version7", "vim.version.version3")
AddVersionParent("vim.version.version7", "vmodl.version.version0")
AddVersionParent("vim.version.version7", "vmodl.version.version1")
AddVersionParent("vim.version.version7", "vmodl.version.version2")
AddVersionParent("vim.version.version7", "vmodl.reflect.version.version1")
AddVersionParent("vim.version.version1", "vmodl.query.version.version1")
AddVersionParent("vim.version.version1", "vim.version.version1")
AddVersionParent("vim.version.version1", "vmodl.version.version0")
AddVersionParent("vim.version.version4", "vmodl.query.version.version1")
AddVersionParent("vim.version.version4", "vim.version.version1")
AddVersionParent("vim.version.version4", "vim.version.version4")
AddVersionParent("vim.version.version4", "vim.version.version2")
AddVersionParent("vim.version.version4", "vim.version.version3")
AddVersionParent("vim.version.version4", "vmodl.version.version0")
AddVersionParent("vim.version.version5", "vmodl.query.version.version2")
AddVersionParent("vim.version.version5", "vmodl.query.version.version1")
AddVersionParent("vim.version.version5", "vim.version.version1")
AddVersionParent("vim.version.version5", "vim.version.version4")
AddVersionParent("vim.version.version5", "vim.version.version5")
AddVersionParent("vim.version.version5", "vim.version.version2")
AddVersionParent("vim.version.version5", "vim.version.version3")
AddVersionParent("vim.version.version5", "vmodl.version.version0")
AddVersionParent("vim.version.version5", "vmodl.version.version1")
AddVersionParent("vim.version.version2", "vmodl.query.version.version1")
AddVersionParent("vim.version.version2", "vim.version.version1")
AddVersionParent("vim.version.version2", "vim.version.version2")
AddVersionParent("vim.version.version2", "vmodl.version.version0")
AddVersionParent("vim.version.version3", "vmodl.query.version.version1")
AddVersionParent("vim.version.version3", "vim.version.version1")
AddVersionParent("vim.version.version3", "vim.version.version2")
AddVersionParent("vim.version.version3", "vim.version.version3")
AddVersionParent("vim.version.version3", "vmodl.version.version0")
AddVersionParent("vmodl.version.version0", "vmodl.version.version0")
AddVersionParent("vmodl.version.version1", "vmodl.version.version0")
AddVersionParent("vmodl.version.version1", "vmodl.version.version1")
AddVersionParent("vmodl.version.version2", "vmodl.version.version0")
AddVersionParent("vmodl.version.version2", "vmodl.version.version1")
AddVersionParent("vmodl.version.version2", "vmodl.version.version2")
AddVersionParent("vsm.version.version1", "vmodl.query.version.version4")
AddVersionParent("vsm.version.version1", "vmodl.query.version.version3")
AddVersionParent("vsm.version.version1", "vmodl.query.version.version2")
AddVersionParent("vsm.version.version1", "vmodl.query.version.version1")
AddVersionParent("vsm.version.version1", "vim.version.version6")
AddVersionParent("vsm.version.version1", "vim.version.version7")
AddVersionParent("vsm.version.version1", "vim.version.version1")
AddVersionParent("vsm.version.version1", "vim.version.version4")
AddVersionParent("vsm.version.version1", "vim.version.version5")
AddVersionParent("vsm.version.version1", "vim.version.version2")
AddVersionParent("vsm.version.version1", "vim.version.version3")
AddVersionParent("vsm.version.version1", "vmodl.version.version0")
AddVersionParent("vsm.version.version1", "vmodl.version.version1")
AddVersionParent("vsm.version.version1", "vmodl.version.version2")
AddVersionParent("vsm.version.version1", "vsm.version.version1")
AddVersionParent("vsm.version.version1", "vmodl.reflect.version.version1")
AddVersionParent("vmodl.reflect.version.version1", "vmodl.version.version0")
AddVersionParent("vmodl.reflect.version.version1", "vmodl.version.version1")
AddVersionParent("vmodl.reflect.version.version1", "vmodl.version.version2")
AddVersionParent("vmodl.reflect.version.version1", "vmodl.reflect.version.version1")

newestVersions.Add("vsm.version.version1")
ltsVersions.Add("vsm.version.version1")
dottedVersions.Add("vsm.version.version1")
oldestVersions.Add("vsm.version.version1")

CreateDataType("vsm.DependencyInfo", "DependencyInfo", "vmodl.DynamicData", "vsm.version.version1", [("entityKey", "string", "vsm.version.version1", 0), ("id", "string", "vsm.version.version1", F_OPTIONAL), ("vServiceType", "string", "vsm.version.version1", F_OPTIONAL), ("name", "string", "vsm.version.version1", F_OPTIONAL), ("description", "string", "vsm.version.version1", F_OPTIONAL), ("required", "boolean", "vsm.version.version1", F_OPTIONAL), ("boundProvider", "vsm.ProviderInfo", "vsm.version.version1", F_OPTIONAL)])
CreateDataType("vsm.ProviderInfo", "ProviderInfo", "vmodl.DynamicData", "vsm.version.version1", [("entityKey", "string", "vsm.version.version1", F_OPTIONAL), ("id", "string", "vsm.version.version1", 0), ("vServiceType", "string", "vsm.version.version1", 0), ("name", "string", "vsm.version.version1", 0), ("description", "string", "vsm.version.version1", 0), ("singleton", "boolean", "vsm.version.version1", 0), ("automaticBinding", "boolean", "vsm.version.version1", 0), ("privilegeId", "string", "vsm.version.version1", 0)])
CreateManagedType("vsm.VServiceManager", "VServiceManager", "vmodl.ManagedObject", "vsm.version.version1", None, [("queryDependencies", "QueryDependencies", "vsm.version.version1", (("entityKey", "string", "vsm.version.version1", 0, None),), (F_OPTIONAL, "vsm.DependencyInfo[]", "vsm.DependencyInfo[]"), None, ["vsm.fault.VServiceManagerFault", ]), ("queryProviders", "QueryProviders", "vsm.version.version1", (("entityKey", "string", "vsm.version.version1", F_OPTIONAL, None),), (F_OPTIONAL, "vsm.ProviderInfo[]", "vsm.ProviderInfo[]"), None, ["vsm.fault.VServiceManagerFault", ]), ("queryBoundDependencies", "QueryBoundDependencies", "vsm.version.version1", (("entityKey", "string", "vsm.version.version1", 0, None),("providerId", "string", "vsm.version.version1", 0, None),), (F_OPTIONAL, "vsm.DependencyInfo[]", "vsm.DependencyInfo[]"), None, ["vsm.fault.VServiceManagerFault", ]), ("queryCompatibleProviders", "QueryCompatibleProviders", "vsm.version.version1", (("entityKey", "string", "vsm.version.version1", 0, None),("dependencyId", "string", "vsm.version.version1", 0, None),), (F_OPTIONAL, "vsm.VServiceManager.QueryProvidersResult[]", "vsm.VServiceManager.QueryProvidersResult[]"), None, ["vsm.fault.VServiceManagerFault", ]), ("queryDependencyConfiguration", "QueryDependencyConfiguration", "vsm.version.version1", (("entityKey", "string", "vsm.version.version1", 0, None),("dependencyId", "string", "vsm.version.version1", 0, None),), (0, "string", "string"), None, ["vsm.fault.VServiceManagerFault", ]), ("createDependency", "CreateDependency", "vsm.version.version1", (("dependencyInfo", "vsm.DependencyInfo", "vsm.version.version1", 0, None),), (0, "string", "string"), None, ["vsm.fault.VServiceManagerFault", "vsm.fault.InvalidPowerState", "vsm.fault.VAppOptionsNotEnabled", ]), ("updateDependency", "UpdateDependency", "vsm.version.version1", (("dependencyInfo", "vsm.DependencyInfo", "vsm.version.version1", 0, None),), (0, "void", "void"), None, ["vsm.fault.VServiceManagerFault", "vsm.fault.InvalidPowerState", ]), ("reconfigureDependency", "ReconfigureDependency", "vsm.version.version1", (("entityKey", "string", "vsm.version.version1", 0, None),("dependencyId", "string", "vsm.version.version1", 0, None),("configuration", "string", "vsm.version.version1", 0, None),), (0, "void", "void"), None, ["vsm.fault.VServiceManagerFault", "vsm.fault.DependencyBound", ]), ("destroyDependency", "DestroyDependency", "vsm.version.version1", (("entityKey", "string", "vsm.version.version1", 0, None),("dependencyId", "string", "vsm.version.version1", 0, None),), (0, "void", "void"), None, ["vsm.fault.VServiceManagerFault", "vsm.fault.InvalidPowerState", ]), ("bind", "Bind", "vsm.version.version1", (("dependencyEntityKey", "string", "vsm.version.version1", 0, None),("dependencyId", "string", "vsm.version.version1", 0, None),("providerEntityKey", "string", "vsm.version.version1", 0, None),("providerId", "string", "vsm.version.version1", 0, None),), (0, "vsm.VServiceManager.BindResult", "vsm.VServiceManager.BindResult"), None, ["vsm.fault.VServiceManagerFault", "vsm.fault.DependencyAlreadyBoundToProvider", "vsm.fault.InvalidPowerState", ]), ("unbind", "Unbind", "vsm.version.version1", (("entityKey", "string", "vsm.version.version1", 0, None),("dependencyId", "string", "vsm.version.version1", 0, None),), (0, "void", "void"), None, ["vsm.fault.VServiceManagerFault", ]), ("validateBinding", "ValidateBinding", "vsm.version.version1", (("dependencyEntityKey", "string", "vsm.version.version1", 0, None),("configuration", "string", "vsm.version.version1", 0, None),("providerEntityKey", "string", "vsm.version.version1", 0, None),("providerId", "string", "vsm.version.version1", 0, None),), (0, "vsm.VServiceManager.BindResult", "vsm.VServiceManager.BindResult"), None, ["vsm.fault.VServiceManagerFault", ]), ("registerProvider", "RegisterProvider", "vsm.version.version1", (("provider", "vsm.ProviderInfo", "vsm.version.version1", 0, None),), (0, "void", "void"), None, ["vsm.fault.VServiceManagerFault", "vsm.fault.VServiceTypeNotUnique", ]), ("unregisterProvider", "UnregisterProvider", "vsm.version.version1", (("providerId", "string", "vsm.version.version1", 0, None),), (0, "void", "void"), None, ["vsm.fault.VServiceManagerFault", ]), ("configureProviderCallback", "ConfigureProviderCallback", "vsm.version.version1", (("providerId", "string", "vsm.version.version1", 0, None),("url", "string", "vsm.version.version1", 0, None),("sslThumbprint", "string", "vsm.version.version1", 0, None),), (0, "void", "void"), None, ["vsm.fault.VServiceManagerFault", ]), ("updatevServiceEnvironments", "UpdatevServiceEnvironments", "vsm.version.version1", (("providerId", "string", "vsm.version.version1", 0, None),("dependencyEntityKey", "string", "vsm.version.version1", 0, None),("dependencyId", "string", "vsm.version.version1", 0, None),("privateVServiceEnvironment", "string", "vsm.version.version1", 0, None),("publicVServiceEnvironment", "string", "vsm.version.version1", 0, None),), (0, "void", "void"), None, ["vsm.fault.VServiceManagerFault", "vsm.fault.DependencyNotBoundToProvider", ]), ("updateDependencyConfiguration", "UpdateDependencyConfiguration", "vsm.version.version1", (("providerId", "string", "vsm.version.version1", 0, None),("dependencyEntityKey", "string", "vsm.version.version1", 0, None),("dependencyId", "string", "vsm.version.version1", 0, None),("configuration", "string", "vsm.version.version1", 0, None),), (0, "void", "void"), None, ["vsm.fault.VServiceManagerFault", "vsm.fault.DependencyNotBoundToProvider", ])])
CreateEnumType("vsm.VServiceManager.BindingState", "VServiceManagerBindingState", "vsm.version.version1", ["red", "yellow", "green"])
CreateDataType("vsm.VServiceManager.BindResult", "VServiceManagerBindResult", "vmodl.DynamicData", "vsm.version.version1", [("bindingState", "string", "vsm.version.version1", 0), ("message", "string", "vsm.version.version1", 0), ("warning", "string[]", "vsm.version.version1", F_OPTIONAL), ("error", "string[]", "vsm.version.version1", F_OPTIONAL)])
CreateDataType("vsm.VServiceManager.QueryProvidersResult", "VServiceManagerQueryProvidersResult", "vmodl.DynamicData", "vsm.version.version1", [("providerInfo", "vsm.ProviderInfo", "vsm.version.version1", 0), ("validationResult", "vsm.VServiceManager.BindResult", "vsm.version.version1", 0)])
CreateDataType("vsm.fault.NoPermission", "FaultNoPermission", "vmodl.RuntimeFault", "vsm.version.version1", [("object", "vmodl.ManagedObject", "vsm.version.version1", 0), ("privilegeId", "string", "vsm.version.version1", 0)])
CreateDataType("vsm.fault.VServiceManagerFault", "FaultVServiceManagerFault", "vmodl.MethodFault", "vsm.version.version1", None)
CreateDataType("vsm.fault.VServiceTypeNotUnique", "FaultVServiceTypeNotUnique", "vsm.fault.VServiceManagerFault", "vsm.version.version1", None)
CreateDataType("vsm.fault.DependencyAlreadyBoundToProvider", "FaultDependencyAlreadyBoundToProvider", "vsm.fault.VServiceManagerFault", "vsm.version.version1", None)
CreateDataType("vsm.fault.DependencyBound", "FaultDependencyBound", "vsm.fault.VServiceManagerFault", "vsm.version.version1", None)
CreateDataType("vsm.fault.DependencyNotBoundToProvider", "FaultDependencyNotBoundToProvider", "vsm.fault.VServiceManagerFault", "vsm.version.version1", None)
CreateDataType("vsm.fault.InvalidPowerState", "FaultInvalidPowerState", "vsm.fault.VServiceManagerFault", "vsm.version.version1", None)
CreateDataType("vsm.fault.VAppOptionsNotEnabled", "FaultVAppOptionsNotEnabled", "vsm.fault.VServiceManagerFault", "vsm.version.version1", None)