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
AddVersion("phonehome.version.version1", "Phonehome", "version1", 0, "")
AddVersionParent("vmodl.version.version0", "vmodl.version.version0")
AddVersionParent("phonehome.version.version1", "vmodl.version.version0")
AddVersionParent("phonehome.version.version1", "phonehome.version.version1")

newestVersions.Add("phonehome.version.version1")
ltsVersions.Add("phonehome.version.version1")
dottedVersions.Add("phonehome.version.version1")
oldestVersions.Add("phonehome.version.version1")

CreateDataType("phonehome.data.ConsentConfiguration", "PhonehomeDataConsentConfiguration", "vmodl.DynamicData", "phonehome.version.version1", [("consentAccepted", "boolean", "phonehome.version.version1", 0), ("consentId", "int", "phonehome.version.version1", 0), ("owner", "string", "phonehome.version.version1", F_OPTIONAL)])
CreateDataType("phonehome.data.ConsentConfigurationData", "PhonehomeDataConsentConfigurationData", "vmodl.DynamicData", "phonehome.version.version1", [("consentConfigurations", "phonehome.data.ConsentConfiguration[]", "phonehome.version.version1", F_OPTIONAL), ("version", "string", "phonehome.version.version1", F_OPTIONAL)])
CreateDataType("phonehome.data.ProxySettings", "PhonehomeDataProxySettings", "vmodl.DynamicData", "phonehome.version.version1", [("hostname", "string", "phonehome.version.version1", 0), ("port", "int", "phonehome.version.version1", F_OPTIONAL), ("username", "string", "phonehome.version.version1", F_OPTIONAL), ("password", "string", "phonehome.version.version1", F_OPTIONAL | F_SECRET)])
CreateManagedType("phonehome.service.ConsentConfigurationService", "PhonehomeServiceConsentConfigurationService", "vmodl.ManagedObject", "phonehome.version.version1", None, [("get", "PhonehomeServiceConsentConfigurationService_Get", "phonehome.version.version1", (), (0, "phonehome.data.ConsentConfigurationData", "phonehome.data.ConsentConfigurationData"), "Authenticated", None), ("set", "PhonehomeServiceConsentConfigurationService_Set", "phonehome.version.version1", (("consentConfigs", "phonehome.data.ConsentConfigurationData", "phonehome.version.version1", 0, None),), (0, "void", "void"), "SSO.Administrator", None), ("validatePrivilegeForSet", "ValidatePrivilegeForSet", "phonehome.version.version1", (), (0, "void", "void"), "SSO.Administrator", None)])
CreateManagedType("phonehome.service.NetworkConfigurationService", "PhonehomeServiceNetworkConfigurationService", "vmodl.ManagedObject", "phonehome.version.version1", None, [("get", "PhonehomeServiceNetworkConfigurationService_Get", "phonehome.version.version1", (), (F_OPTIONAL, "phonehome.data.ProxySettings[]", "phonehome.data.ProxySettings[]"), "Authenticated", None), ("set", "PhonehomeServiceNetworkConfigurationService_Set", "phonehome.version.version1", (("proxySettings", "phonehome.data.ProxySettings[]", "phonehome.version.version1", F_OPTIONAL, None),), (0, "void", "void"), "SSO.Administrator", None)])
