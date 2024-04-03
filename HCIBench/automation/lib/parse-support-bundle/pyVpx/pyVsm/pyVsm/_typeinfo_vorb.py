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
AddVersion("vorb.version.version1", "vorb", "1.0", 0, "")
AddVersionParent("vmodl.version.version0", "vmodl.version.version0")
AddVersionParent("vorb.version.version1", "vmodl.version.version0")
AddVersionParent("vorb.version.version1", "vorb.version.version1")

newestVersions.Add("vorb.version.version1")
ltsVersions.Add("vorb.version.version1")
dottedVersions.Add("vorb.version.version1")
oldestVersions.Add("vorb.version.version1")

CreateManagedType("vorb.DiskProvider", "VorbDiskProvider", "vmodl.ManagedObject", "vorb.version.version1", None, [("createVirtualDisk", "VorbCreateVirtualDisk", "vorb.version.version1", (("handle", "vorb.OpHandle", "vorb.version.version1", 0, None),("diskPath", "string", "vorb.version.version1", 0, None),("spec", "vorb.DiskProvider.VirtualDiskSpec", "vorb.version.version1", 0, None),), (0, "void", "void"), None, None)])
CreateEnumType("vorb.DiskProvider.VirtualDiskType", "VorbDiskProviderVirtualDiskType", "vorb.version.version1", ["preallocated", "thin", "rdm", "rdmp", "raw", "sparse2Gb", "thick2Gb", "eagerZeroedThick", "sparseMonolithic", "flatMonolithic", "thick"])
CreateEnumType("vorb.DiskProvider.VirtualDiskAdapterType", "VorbDiskProviderVirtualDiskAdapterType", "vorb.version.version1", ["ide", "busLogic", "lsiLogic"])
CreateDataType("vorb.DiskProvider.VirtualDiskSpec", "VorbDiskProviderVirtualDiskSpec", "vmodl.DynamicData", "vorb.version.version1", [("diskType", "string", "vorb.version.version1", 0), ("adapterType", "string", "vorb.version.version1", 0)])
CreateDataType("vorb.DiskProvider.FileBackedVirtualDiskSpec", "VorbDiskProviderFileBackedVirtualDiskSpec", "vorb.DiskProvider.VirtualDiskSpec", "vorb.version.version1", [("capacityKb", "long", "vorb.version.version1", 0)])
CreateDataType("vorb.DiskProvider.DeviceBackedVirtualDiskSpec", "VorbDiskProviderDeviceBackedVirtualDiskSpec", "vorb.DiskProvider.VirtualDiskSpec", "vorb.version.version1", [("device", "string", "vorb.version.version1", 0)])
CreateManagedType("vorb.OpHandle", "VorbOpHandle", "vmodl.ManagedObject", "vorb.version.version1", [("info", "vorb.OpHandle.OpInfo", "vorb.version.version1", 0, None)], [("waitForCompletion", "WaitForCompletion", "vorb.version.version1", (), (0, "void", "void"), None, None)])
CreateDataType("vorb.OpHandle.OpInfo", "VorbOpHandleOpInfo", "vmodl.DynamicData", "vorb.version.version1", [("id", "string", "vorb.version.version1", 0), ("state", "vorb.OpHandle.OpInfo.State", "vorb.version.version1", 0), ("progress", "int", "vorb.version.version1", F_OPTIONAL), ("error", "vorb.OpHandle.OpInfo.Error", "vorb.version.version1", F_OPTIONAL)])
CreateEnumType("vorb.OpHandle.OpInfo.State", "VorbOpHandleOpInfoState", "vorb.version.version1", ["unset", "running", "success", "error"])
CreateDataType("vorb.OpHandle.OpInfo.Error", "VorbOpHandleOpInfoError", "vmodl.DynamicData", "vorb.version.version1", [("errMsg", "string", "vorb.version.version1", 0), ("errCode", "int", "vorb.version.version1", 0)])
CreateManagedType("vorb.OpManager", "VorbOpManager", "vmodl.ManagedObject", "vorb.version.version1", None, [("createOpHandle", "VorbCreateOpHandle", "vorb.version.version1", (("opId", "string", "vorb.version.version1", 0, None),), (0, "vorb.OpHandle", "vorb.OpHandle"), None, None), ("destroyOpHandle", "VorbDestroyOpHandle", "vorb.version.version1", (("handle", "vorb.OpHandle", "vorb.version.version1", 0, None),), (0, "void", "void"), None, None)])
CreateManagedType("vorb.ServiceInstance", "VorbServiceInstance", "vmodl.ManagedObject", "vorb.version.version1", None, [("currentTime", "VorbCurrentTime", "vorb.version.version1", (), (0, "vmodl.DateTime", "vmodl.DateTime"), None, None)])
