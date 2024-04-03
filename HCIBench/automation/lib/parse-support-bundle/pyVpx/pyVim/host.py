## @file host.py
## @brief Utility functions for hosts
"""
Utility functions for hosts.

Detailed description (for [e]pydoc goes here)
"""

from pyVmomi import Vim
from pyVmomi.VmomiSupport import ResolveLinks


## @param si [in] Retrieve the root folder
def GetRootFolder(si):
    """
    Retrieve the root folder.

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : ManagedObjectReference to a Folder
    @return        : Reference to the top of the inventory managed by this
                     service.
    """

    content = si.RetrieveContent()
    rootFolder = content.GetRootFolder()
    return rootFolder


## @param si [in] Retrieve the fault tolerance manager
def GetFaultToleranceMgr(si):
    """
    Retrieve the fault tolerance manager.

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : ManagedObjectReference to a FaultToleranceManager
    @return        : The FaultToleranceManager for this ServiceInstance.
    """

    content = si.RetrieveInternalContent()
    ftMgr = content.GetFtManager()
    return ftMgr


## @param si [in] Retrieve the host folder
def GetHostFolder(si):
    """
    Retrieve the host folder.

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : ManagedObjectReference to a Folder
    @return        : A reference to the folder hierarchy that contains the
                     compute resources, including hosts and clusters.
    """

    content = si.RetrieveContent()
    dataCenter = content.GetRootFolder().GetChildEntity()[0]
    hostFolder = dataCenter.GetHostFolder()
    return hostFolder


## @param si [in] Retrieve the compute resource for the host
def GetComputeResource(si):
    """
    Retrieve the compute resource for the host.

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : ManagedObjectReference to a ComputeResource
    @return        :
    """

    hostFolder = GetHostFolder(si)
    computeResource = hostFolder.GetChildEntity()[0]
    return computeResource


## @param si [in] Retrieve the host system
def GetHostSystem(si):
    """
    Retrieve the host system.

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : ManagedObjectReference to a HostSystem
    @return        :
    """

    computeResource = GetComputeResource(si)
    hostSystem = computeResource.GetHost()[0]
    return hostSystem


## @param si [in] Retrieve the host config manager
def GetHostConfigManager(si):
    """
    Retrieve the host config manager.

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : ManagedObjectReference to a HostConfigManager.
    @return        :
    """

    hostSystem = GetHostSystem(si)
    configManager = hostSystem.GetConfigManager()
    return configManager


## @param si [in] Retrieve the host's virtual nic manager
def GetHostVirtualNicManager(si):
    """
    Retrieve the host VirtualNicManager

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : ManagedObjectReference to a VirtualNicManager
    @return        :
    """

    configMgr = GetHostConfigManager(si)
    vnicMgr = configMgr.GetVirtualNicManager()
    return vnicMgr


## @param si [in] Retrieve the host vmotion system
def GetHostVmotionSystem(si):
    """
    Retrieve the host vmotion system.

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : ManagedObjectReference to a VmotionSystem.
    @return        :
    """

    configMgr = GetHostConfigManager(si)
    vmotionSystem = configMgr.GetVmotionSystem()
    return vmotionSystem


## @param si [in] Retrieve the UUID of the host
def GetHostUuid(si):
    """
    Retrieve the UUID of the host.

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : str
    @return        : Hardware BIOS identification.
    """

    hostSystem = GetHostSystem(si)
    hwInfo = hostSystem.GetHardware()
    if hwInfo == None:
        raise Exception("Hardware info of host is NULL.")
    return hwInfo.GetSystemInfo().GetUuid()


## @param si [in] Retrieve the root resource pool of a host
def GetRootResourcePool(si):
    """
    Retrieve the root resource pool of a host.

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : ManagedObjectReference to a ResourcePool
    @return        : Reference to root resource pool.
    """

    computeRes = GetComputeResource(si)
    resPool = computeRes.GetResourcePool()
    return resPool


def GetNicIp(si, nicType):
    """
    Retrieve the IP associated with a specified Nic type on the host.

    @type    si         : ServiceInstance ManagedObject
    @param   si         :
    @type    nicType    : str
    @param   nicType    : Type of Nic
    @rtype              : str
    @return             : The IP address currently used by 
                          the specified nic type, if selected
    """

    vnicMgr = GetHostVirtualNicManager(si)
    netConfig = vnicMgr.QueryNetConfig(nicType)
    if netConfig == None:
        raise Exception("NetConfig is NULL.")
    vnicArr = ResolveLinks(netConfig.GetSelectedVnic(), netConfig)
    if len(vnicArr) < 1:
        raise Exception("No Nic configured for type " + nicType)
    ipConfig = vnicArr[0].GetSpec().GetIp()
    return ipConfig.GetIpAddress()


## @param si [in] Retrieve the VMotion IP of the host
def GetVMotionIP(si):
    """
    Retrieve the VMotion IP of the host.

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : str
    @return        : The IP address currently used by the VMotion NIC.
                     All IP addresses are specified using
                     IPv4 dot notation. For example,"192.168.0.1".
                     Subnet addresses and netmasks are specified using
                     the same notation.
    """

    return GetNicIp(si, Vim.Host.VirtualNicManager.NicType.vmotion)


## @param si [in] Retrieve the FT Logging Nic IP of the host
def GetLoggingIP(si):
    """
    Retrieve the FT Logging Nic IP of the host.

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : str
    @return        : The IP address currently used by the FT Logging NIC.
                     All IP addresses are specified using
                     IPv4 dot notation. For example,"192.168.0.1".
                     Subnet addresses and netmasks are specified using
                     the same notation.
    """

    return GetNicIp(si,
                    Vim.Host.VirtualNicManager.NicType.faultToleranceLogging)


## @param si [in] Retrieve the VMotionManager instance for a host
def GetVmotionManager(si):
    """
    Retrieve the VMotionManager instance for a host.

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : ManagedObjectReference to a VmotionManager.
    @return        :
    """

    vmotionMgr = Vim.Host.VMotionManager("ha-vmotionmgr", si._stub)
    return vmotionMgr


## @param si [in] Prints out host config information
def DumpHostConfig(si):
    """
    Dumps host config information to stdout.

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    """

    print("Host Configuration:")
    hostSystem = GetHostSystem(si)

    hostSummary = hostSystem.GetSummary()
    print("Host Summary:\n", hostSummary)

    hostRuntime = hostSystem.GetRuntime()
    print("Host Runtime:\n", hostRuntime)

    hostConfigManager = hostSystem.GetConfigManager()
    print(hostConfigManager)

    datastoreSystem = hostConfigManager.GetDatastoreSystem()

    datastoreList = hostSystem.GetDatastore()
    print(datastoreList)

    storageSystem = hostConfigManager.GetStorageSystem()
    # Broken because python wrappers don't handle @links correctly.
    # Loops in the structures break the python wrappers
    # storageConfig = storageSystem.GetStorageInfo()
    # print storageConfig

    networkSystem = hostConfigManager.GetNetworkSystem()
    networkInfo = networkSystem.GetNetworkInfo()
    print(networkInfo)


## @param si [in] Checks if host is a mockup
def IsHostMockup(si):
    """
    Checks if host is a mockup

    @type    si    : ServiceInstance ManagedObject
    @param   si    :
    @rtype         : boolean
    @return        : True if host is running in mockup mode, False otherwise
    """

    content = si.RetrieveContent()
    fullName = content.GetAbout().GetInstanceUuid()
    return (fullName != None and fullName.find("Mockup") != -1)
