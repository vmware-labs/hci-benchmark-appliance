#!/usr/bin/python

from __future__ import print_function

import sys
from pyVmomi import Vim
from pyVim.connect import Connect, Disconnect
from optparse import OptionParser
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm, host
from pyVim import invt
from pyVim import vmconfig
from pyVim import vimutil
from pyVim import arguments
from pyVim.helpers import StopWatch
import time
import atexit

def get_options():
    """
    Supports the command-line arguments listed below
    """

    parser = OptionParser()
    parser.add_option("-H", "--host",
                      default="localhost",
                      help="remote host to connect to")
    parser.add_option("-u", "--user",
                      default="root",
                      help="User name to use when connecting to hostd")
    parser.add_option("-p", "--password",
                      default="",
                      help="Password to use when connecting to hostd")
    parser.add_option("-i", "--uuid",
                      default="74 65 73 74 00 00 00 00-00 00 00 00 00 00 00 01",
                      help="DVSwitch id")
    parser.add_option("-n", "--name", default="test-esx",
                      help="DVSwitch name")
    parser.add_option("-v", "--vmName", default="testVM",
                      help="vm name")
    parser.add_option("--nic",
                      help="the pnic to be used for the test")
    (options, _) = parser.parse_args()

    if options.uuid == None:
        parser.error("uuid needs to be specified")
    if options.name == None:
        parser.error("dvs name needs to be specified")
    return options

def setup(si, uuid, dvsName):
    """
    Setup a dvs with one early binding, one latebinding, two ephemeral and
    one uplink portgroup. Also creates 4 uplink ports 2 standalone and 2
    belonging to the uplink portgroup.
    """

    # Create the dvs.
    prodSpec = Vim.Dvs.ProductSpec(vendor="VMware",
                                   version="6.5.0")
    # create a port for the early binding case.
    port1 = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
        portKey = "1000",
        name = "1000",
        connectionCookie = 5)
    uplinkPort1 = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
        portKey = "1",
        name = "uplink1",
        connectionCookie = 1)
    uplinkPort2 = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
        portKey = "2",
        name = "uplink2",
        connectionCookie = 2)
    uplinkPort3 = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
        portKey = "3",
        name = "uplink3",
        connectionCookie = 3)
    createSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSCreateSpec(
        uuid = uuid,
        name = dvsName,
        backing = Vim.Dvs.HostMember.PnicBacking(),
        productSpec = prodSpec,
        maxProxySwitchPorts = 64,
        port=[port1, uplinkPort1, uplinkPort2, uplinkPort3],
        uplinkPortKey=["1","2", "3"],
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True
        )
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    ipfixConfig = Vim.Dvs.VmwareDistributedVirtualSwitch.IpfixConfig(activeFlowTimeout = 4,
        collectorIpAddress = "10.20.104.240",
        idleFlowTimeout = 4,
        internalFlowsOnly = True,
        samplingRate = 4
        )
    vmwsetting = Vim.Dvs.HostDistributedVirtualSwitchManager.VmwareDVSSettingSpec()
    vmwsetting.SetIpfixConfig(ipfixConfig)
    createSpec.SetVmwareSetting(vmwsetting)
    dvsManager.CreateDistributedVirtualSwitch(createSpec)

    # Create an early binding and a late binding portgroup.
    portgroupList = []
    pg = GeneratePortgroupCfg("pg1", "add", "ephemeral")
    portgroupList.append(pg)
    pg = GeneratePortgroupCfg("pg2", "add", "earlyBinding")
    portgroupList.append(pg)
    pg = GeneratePortgroupCfg("pg3", "add", "ephemeral")
    portgroupList.append(pg)
    pg = GeneratePortgroupCfg("pg4", "add", "lateBinding")
    portgroupList.append(pg)
    # Uplink portgroup
    pg = GeneratePortgroupCfg("pg5", "add", "ephemeral")
    portgroupList.append(pg)
    dvsManager.UpdateDVPortgroups(uuid, portgroupList)
    portDataList = [ ]
    portData1 = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
                portKey = "2",
                name = "uplink2",
                portgroupKey = "pg5",
                connectionCookie = 2)
    portData2 = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
                portKey = '3',
                name = "uplink3",
                portgroupKey = "pg5",
                connectionCookie = 3)

    portDataList.append(portData1)
    portDataList.append(portData2)
    dvsManager.UpdatePorts(uuid, portDataList)

def cleanupvm(vmName):
   print("cleaning up vm:'" + vmName + "'")
   vm1 = folder.Find(vmName)
   if vm1 is not None:
       try:
          vm.PowerOff(vm1)
       except Exception as e:
          print(e)
       try:
          vm.Destroy(vm1)
       except Exception as e:
          print(e)

def cleanup(si, uuid, vmName):
   """
   Remove the dvs created as part of the setup phase. Assumes no clients are connected.
   """
   cleanupvm(vmName)
   dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
   dvsManager.RemoveDistributedVirtualSwitch(uuid)

def IsBackingValid(devices):
    """
    Checks if the backing of the device is valid, i.e it has a dvPort and a cnxId assigned.
    """
    for device in devices:
        if isinstance(device.GetBacking(),\
            Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
    	    if (device.GetBacking().GetPort().GetPortKey() == None or
            device.GetBacking().GetPort().GetConnectionCookie == None or
            device.GetBacking().GetPort().GetConnectionCookie() == 0):
                return False
    return len(devices) != 0

def IsBackingPortNotAllocated(devices):
    """
    Checks if there is a dvs backed ethernet card and with no dvPort allocated.
    True if there is no dvPort allocated false if either a dvPort is allocated
    or if an dvs backed ethernet card is not found.
    """
    for device in devices:
        if isinstance(device.GetBacking(),\
            Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
    	    if (device.GetBacking().GetPort().GetPortKey() == None and
                device.GetBacking().GetPort().GetConnectionCookie() == None):
                return True
    return False


def GenerateDefaultPortSetting():
    """
    Generates default port settings for a portgroup matching VCs defaults.
    """
    cfg = Vim.Dvs.VmwareDistributedVirtualSwitch.VmwarePortConfigPolicy()
    bPolicy= Vim.BoolPolicy(inherited = False,
             value = False)
    iPolicy = Vim.IntPolicy(inherited = False,
             value = 10)
    cfg.SetBlocked(bPolicy)
    shaping = Vim.Dvs.DistributedVirtualPort.TrafficShapingPolicy(enabled = bPolicy)
    shaping.SetInherited(False)
    cfg.SetInShapingPolicy(shaping)
    cfg.SetOutShapingPolicy(shaping)
    cfg.SetIpfixEnabled(bPolicy)
    security = Vim.Dvs.VmwareDistributedVirtualSwitch.SecurityPolicy(allowPromiscuous = bPolicy,
                   forgedTransmits = bPolicy,
                   macChanges = bPolicy)
    security.SetInherited(False)
    cfg.SetSecurityPolicy(security)
    numericRange = Vim.NumericRange(start = 1,
                       end = 4094)
    vlan = Vim.Dvs.VmwareDistributedVirtualSwitch.TrunkVlanSpec()
    vlan.SetInherited(False)
    vlan.GetVlanId().append(numericRange)
    cfg.SetVlan(vlan)
    # Set failover policy
    bPolicy1 = Vim.BoolPolicy(inherited = False,
             value = True)
    failoverPolicy = Vim.Dvs.VmwareDistributedVirtualSwitch.UplinkPortTeamingPolicy()
    failoverPolicy.SetInherited(False)
    failureCriteria = Vim.Dvs.VmwareDistributedVirtualSwitch.FailureCriteria()
    failureCriteria.SetInherited(False)
    sPolicy = Vim.StringPolicy(inherited = False,
             value = "exact")
    failureCriteria.SetCheckSpeed(sPolicy)
    failureCriteria.SetFullDuplex(bPolicy1)
    failureCriteria.SetCheckErrorPercent(bPolicy1)
    failureCriteria.SetPercentage(iPolicy)
    failureCriteria.SetSpeed(iPolicy)

    teamingPolicy = Vim.StringPolicy()
    teamingPolicy.SetInherited(False)
    teamingPolicy.SetValue('loadbalance_srcid')
    failoverPolicy.SetPolicy(teamingPolicy)
    failoverPolicy.SetFailureCriteria(failureCriteria)
    cfg.SetUplinkTeamingPolicy(failoverPolicy)
    return cfg

def GeneratePortgroupCfg(key, operation, type):
    """
    Generates a default portgroup config of a given type and operation.
    Supproted types are latebinding, earlybinding, ephemeral
    """
    cfg = Vim.Dvs.HostDistributedVirtualSwitchManager.DVPortgroupConfigSpec()
    cfg.SetKey(key)
    cfg.SetOperation(operation)
    # Generate the spec.
    spec = Vim.Dvs.DistributedVirtualPortgroup.ConfigSpec()
    spec.SetName(key)
    spec.SetType(type)
    policy = Vim.Dvs.DistributedVirtualPortgroup.PortgroupPolicy(
                 blockOverrideAllowed = False,
                 livePortMovingAllowed = True,
                 portConfigResetAtDisconnect = False,
                 shapingOverrideAllowed = False,
                 vendorConfigOverrideAllowed = False)
    spec.SetNumPorts(16)
    spec.SetPolicy(policy)
    setting = GenerateDefaultPortSetting()
    spec.SetDefaultPortConfig(setting)
    cfg.SetSpecification(spec)
    return cfg

def TestSimulatedVcClone(vmName, uuid):
    """
    Test the code paths that VC excercises during cloning a VM with
    a dvs backing.
    """
    print("Testing hostd code corresponding to clone")
    cleanupvm(vmName)
    envBrowser = invt.GetEnv()
    config = vm.CreateQuickDummySpec(vmName)
    cfgOption = envBrowser.QueryConfigOption(None, None)
    # Add a nic backed by a dvs portgroup pair.
    config = vmconfig.AddDvPortBacking(config, "", uuid, 0, cfgOption, "invalidPg")
    try:
        vmFolder = invt.GetVmFolder()
        vimutil.InvokeAndTrack(vmFolder.CreateVm, config, invt.GetResourcePool(), None)
    except Vim.Fault.InvalidDeviceSpec:
        print("Test1: Caught invalid device spec as expected")
    else:
        raise "Test1: Create vm with invalid dvPortgroup backing didn't fail as expected"
    print("Test1: Create vm with invalid dvPortgroup backing failed as expected: PASS")

    config = vm.CreateQuickDummySpec(vmName)
    config = vmconfig.AddDvPortBacking(config, "", uuid, 0, cfgOption, "pg1")
    try:
        vmFolder = invt.GetVmFolder()
        vimutil.InvokeAndTrack(vmFolder.CreateVm, config, invt.GetResourcePool(), None)
    except Exception:
        print("Failed to clone a VM to connect to a dvPortgroup")
        raise
    print("Test2: Create vm with valid dvPort backing: PASS")

    # Create a VM only specifying the dvs uuid in its backing.
    vm1 = folder.Find(vmName)
    vm.Destroy(vm1)
    config = vm.CreateQuickDummySpec(vmName)
    config = vmconfig.AddDvPortBacking(config, "", uuid, None, cfgOption, "")
    try:
        vmFolder = invt.GetVmFolder()
        vimutil.InvokeAndTrack(vmFolder.CreateVm, config, invt.GetResourcePool(), None)
    except Exception:
        print("Failed to clone a VM to connected to a standalone port")
        raise
    myVm = folder.Find(vmName)
    devices = vmconfig.CheckDevice(myVm.GetConfig(), Vim.Vm.Device.VirtualEthernetCard)
    if not IsBackingPortNotAllocated(devices):
        print(devices)
        raise Exception ("Nic has a dvPort assigned to it or nic add failed")
    print("Test3: Create vm with valid dvs uuid specified in the dvsbacking (standalone): PASS")

    # Reconfigure a VM only specifying a dvs uuid in its backing
    for device in devices:
        if isinstance(device.GetBacking(),\
            Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            cspec = Vim.Vm.ConfigSpec()
            device.GetConnectable().SetConnected(True)
            device.SetUnitNumber(9)
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.add)
            break
    try:
        task = myVm.Reconfigure(cspec)
        WaitForTask(task)
    except Exception:
        print("Test4: failed to add a device with only dvs backing specified")
    print("Test4: Reconfig VM specifying only the dvsUuid in backing: PASS")

    print("Testing simulate vc clone done")

def TestEphemeral(vmName, uuid):
    """
    Test epehemeral portgroups.
    - Create a VM configure it to connect to an ephemeral portgroup.
    - Power on the VM and validate that backing is valid.
    - Hot add a nic to connect to an ephemeral portgroup and validate backing.
    - Poweroff and destroy the VM
    """
    print("Testing Ephemeral portgroup behaviour")
    cleanupvm(vmName)
    envBrowser = invt.GetEnv()
    config = vm.CreateQuickDummySpec(vmName)
    cfgOption = envBrowser.QueryConfigOption(None, None)
    # Add a latebinding dvPortgroup backed nic.
    config = vmconfig.AddDvPortBacking(config, "", uuid, 0, cfgOption, "pg1")
    try:
        vmFolder = invt.GetVmFolder()
        vimutil.InvokeAndTrack(vmFolder.CreateVm, config, invt.GetResourcePool(), None)
    except Exception as e:
        raise
    myVm = folder.Find(vmName)
    devices = vmconfig.CheckDevice(myVm.GetConfig(), Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Failed to add nic")
    if not IsBackingPortNotAllocated(devices):
        print(devices)
        raise Exception ("Nic has a dvPort assigned to it or nic add failed")
    print("Test 1: Create a vm with an ephemeral portgroup backing: PASS")
    vm.PowerOn(myVm)
    devices = vmconfig.CheckDevice(myVm.GetConfig(), Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Failed to add nic")
    if not IsBackingValid(devices):
        raise Exception("Invalid backing allocated")
    print("Test 2: powerOn VM with a ephemeral backing: PASS")
    # Remove and add hot add a nic device to a powered on VM.
    vm.PowerOff(myVm)
    for device in devices:
        if isinstance(device.GetBacking(),\
            Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.remove)
            break
    task = myVm.Reconfigure(cspec)
    WaitForTask(task)
    devices = vmconfig.CheckDevice(myVm.GetConfig(), Vim.Vm.Device.VirtualEthernetCard)
    if IsBackingValid(devices):
        print(devices)
        raise Exception("Remove of device failed.")
    # powerOn the VM and hot add the nic.
    vm.PowerOn(myVm)
    config = Vim.Vm.ConfigSpec()
    config = vmconfig.AddDvPortBacking(config, "", uuid, 0, cfgOption, "pg1")
    task = myVm.Reconfigure(config)
    WaitForTask(task)
    devices = vmconfig.CheckDevice(myVm.GetConfig(), Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Failed to add nic")
    if not IsBackingValid(devices):
        raise Exception("Invalid backing allocated")
    print("Test 3: remove and hot add nic to VM with a ephemeral backing: PASS")
    # Foundry issue wait for fix and then uncomment.
    time.sleep(10)
    for device in devices:
        if isinstance(device.GetBacking(),\
            Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            device.GetBacking().GetPort().SetPortgroupKey("pg3")
            device.GetBacking().GetPort().SetPortKey(None)
            device.GetBacking().GetPort().SetConnectionCookie(None)
            device.GetConnectable().SetConnected(True)
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
            break
    #task = myVm.Reconfigure(cspec)
    #WaitForTask(task)
    #devices = vmconfig.CheckDevice(myVm.GetConfig(), Vim.Vm.Device.VirtualEthernetCard)
    #if len(devices) < 1:
     #   raise Exception("Failed to edit nic")
    #if not IsBackingValid(devices):
     #   raise Exception("Invalid backing allocated")
    #print("Test4: Reconfig poweredon with a ephemeral backing: PASS")
    print("Ephemeral portgoup tests complete")

def TestLateBinding(vmName, uuid):
    """
     Create a VM and connect it to a latebinding portgroup.
     Poweron the VM. Validate that a dvPort has not been allocated for the VM.
     Reconfig the VM to connect to a ephemeral dvPortgroup validate that the VM
     has a valid backing.
     Reconfigure the VM to connect back to the latebinding portgroup the reconfig
     should fail.
     Reconfigure the VM to connect back to the latebinding portgroup with the
     device disconnected the connect should succeed.
    """
    cleanupvm(vmName)
    print("Testing latebinding portgroup behaviour")
    envBrowser = invt.GetEnv()
    config = vm.CreateQuickDummySpec(vmName)
    cfgOption = envBrowser.QueryConfigOption(None, None)
    # Add a latebinding dvPortgroup backed nic.
    config = vmconfig.AddDvPortBacking(config, "", uuid, 0, cfgOption, "pg4",
                                       type = 'vmxnet3')
    try:
        vmFolder = invt.GetVmFolder()
        vimutil.InvokeAndTrack(vmFolder.CreateVm, config, invt.GetResourcePool(), None)
    except Exception as e:
        raise
    myVm = folder.Find(vmName)
    devices = vmconfig.CheckDevice(myVm.GetConfig(), Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Failed to add nic")
    if not IsBackingPortNotAllocated(devices):
        raise Exception("dvPort allocated for a latebinding portgroup")
    print("Test1: Create VM with a latebinding portgroup backing: PASS")
    # power on the VM.
    vm.PowerOn(myVm)
    devices = vmconfig.CheckDevice(myVm.GetConfig(), Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Nic seems to be missing")
    if not IsBackingPortNotAllocated(devices):
        raise Exception("dvPort allocated for a latebinding portgroup after powerOn")
    print("Test2: Powering on a VM with a latebinding portgroup backing: PASS")

    # Reconfigure the VM to connect to an ephemeral backing.
    for device in devices:
        if isinstance(device.GetBacking(),\
            Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            device.GetBacking().GetPort().SetPortgroupKey("pg3")
            device.GetBacking().GetPort().SetPortKey(None)
            device.GetBacking().GetPort().SetConnectionCookie(None)
            device.GetConnectable().SetConnected(True)
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
            break
    task = myVm.Reconfigure(cspec)
    WaitForTask(task)
    devices = vmconfig.CheckDevice(myVm.GetConfig(), Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Failed to edit nic")
    if not IsBackingValid(devices):
        raise Exception("Invalid backing allocated")
    print("Test3: Reconfig poweredon with a ephemeral backing from a latebinding backing allocates a port: PASS")

    #Reconfig the VM to connect to a latebinding backing.
    for device in devices:
        if isinstance(device.GetBacking(),\
            Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            device.GetBacking().GetPort().SetPortgroupKey("pg4")
            device.GetBacking().GetPort().SetPortKey(None)
            device.GetBacking().GetPort().SetConnectionCookie(None)
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
            break
    try:
        task = myVm.Reconfigure(cspec)
        WaitForTask(task)
    except Vim.Fault.InvalidDeviceSpec:
        print("Caught invalid device backing")
    print("Test4: Reconfig powered on VM to connect to a latebinding backing fails as expected: PASS")

    # reconfigure the VM to connect to a latebinding portgroup and disconnect the device.
    for device in devices:
        if isinstance(device.GetBacking(),\
            Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            device.GetBacking().GetPort().SetPortgroupKey("pg4")
            device.GetBacking().GetPort().SetPortKey(None)
            device.GetBacking().GetPort().SetConnectionCookie(None)
            device.GetConnectable().SetConnected(False)
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
            break
    task = myVm.Reconfigure(cspec)
    WaitForTask(task)
    devices = vmconfig.CheckDevice(myVm.GetConfig(), Vim.Vm.Device.VirtualEthernetCard)
    if not IsBackingPortNotAllocated(devices):
        print(devices)
        raise Exception ("Nic has a dvPort assigned to it or nic add failed")
    print("Test5: Reconfig powered on VM to connect to a latebinding backing with device disconnected: PASS")
    print("Late binding tests complete")

def TestEarlyBinding(vmName, uuid):
    """
    Test early binding portgroup behaviour
    - Create a VM with a nic connecting to an early binding portgroup and start connected to true
      fails
    - Create a VM with a nic connecting to an early binding portgroup and start connected to false
      succeeds
    - Poweron the created VM succeds.
    - Reconfigure the VM to connect to an invalid port fails.
    - Hot add of device connected to an early binding portgroup fails.
    - Reconfigure the VM to connect to an early binding portgroup when device is not connected succeeds
    - Reconfigure a powered on VM to connect to an early binding portgroup when device is connected fails.
    """

    print("Testing early binding portgroup behaviour")
    cleanupvm(vmName)
    envBrowser = invt.GetEnv()
    config = vm.CreateQuickDummySpec(vmName)
    cfgOption = envBrowser.QueryConfigOption(None, None)
    # Add a earlybinding dvPortgroup backed nic.
    config = vmconfig.AddDvPortBacking(config, "", uuid, 0, cfgOption, "pg2")
    try:
        vmFolder = invt.GetVmFolder()
        vimutil.InvokeAndTrack(vmFolder.CreateVm, config, invt.GetResourcePool(), None)
    except Vim.Fault.InvalidDeviceSpec:
        print("Caught invalid device backing as expected")
    print("Test 1: Creating a device backed by an early binding portgroup with"
          "startConnected = true fails as expected: PASS")
    config = vm.CreateQuickDummySpec(vmName)
    cfgOption = envBrowser.QueryConfigOption(None, None)
    # Add an earlybinding dvPortgroup backed nic.
    config = vmconfig.AddDvPortBacking(config, "", uuid, 0, cfgOption, "pg2", False)
    vmFolder = invt.GetVmFolder()
    vimutil.InvokeAndTrack(vmFolder.CreateVm, config, invt.GetResourcePool(), None)
    myVm = folder.Find(vmName)
    devices = vmconfig.CheckDevice(myVm.GetConfig(), Vim.Vm.Device.VirtualEthernetCard)
    if not IsBackingPortNotAllocated(devices):
        print(devices)
        raise Exception ("Nic has a dvPort assigned to it or nic add failed")
    print("Test 2: Creating a device backed by and early binding portgroup with"
          "startConnected = false succeeds: PASS")
    myVm = folder.Find(vmName)
    vm.PowerOn(myVm)
    devices = vmconfig.CheckDevice(myVm.GetConfig(), Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("nic not present")
    if not IsBackingPortNotAllocated(devices):
        print(devices)
        raise Exception ("Nic has a dvPort assigned to it or nic add failed")
    print("Test 3: Power on VM succeeds: PASS")
    # Reconfigure the VM to connect to an invalid port.
    for device in devices:
        if isinstance(device.GetBacking(),\
            Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            device.GetBacking().GetPort().SetPortKey("100")
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
            break
    try:
        task = myVm.Reconfigure(cspec)
        WaitForTask(task)
    except Vim.Fault.InvalidDeviceSpec:
        print("Caught invalid device backing")
    print("Test 4: Reconfig a VM to connect to an invalid dvPort fails as expected: PASS")

    # Add a device to connect to an early binding portgroup with no dvPort specified.
    config = Vim.Vm.ConfigSpec()
    config = vmconfig.AddDvPortBacking(config, "", uuid, 0, cfgOption, "pg2")
    try:
        task = myVm.Reconfigure(config)
        WaitForTask(task)
    except Vim.Fault.InvalidDeviceSpec:
        print("Caught invalid device backing")
    print("Test 4: Hot add of a device to connect to an earlybinding portgroup fails as expected: PASS")

    # Reconfigure device to connect to an early binding portgroup.
    for device in devices:
        if isinstance(device.GetBacking(),\
            Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            device.GetBacking().GetPort().SetPortgroupKey("pg2")
            device.GetBacking().GetPort().SetPortKey(None)
            device.GetBacking().GetPort().SetConnectionCookie(None)
            device.GetConnectable().SetConnected(True)
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
            break
    try:
        task = myVm.Reconfigure(cspec)
        WaitForTask(task)
    except Vim.Fault.InvalidDeviceSpec:
        print("Caught invalid device backing")
    print("Test 5: Reconfig a VM to connect to an early binding portgroup fails as expected: PASS")

    # Reconfigure a device to disconnected state and connect to an early binding dvPortgroup.
    for device in devices:
        if isinstance(device.GetBacking(),\
            Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            device.GetBacking().GetPort().SetPortgroupKey("pg2")
            device.GetBacking().GetPort().SetPortKey(None)
            device.GetBacking().GetPort().SetConnectionCookie(None)
            device.GetConnectable().SetConnected(False)
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
            break
    task = myVm.Reconfigure(cspec)
    WaitForTask(task)
    if not IsBackingPortNotAllocated(devices):
        print(devices)
        raise Exception ("Nic has a dvPort assigned to it or nic add failed")
    print("Test6 complete: Reconfig powered on VM to connect to a earlybinding backing with device disconnected: PASS")
    print("EarlyBinding tests complete")

def GenerateIPConfig(ipAdd):
    ip = Vim.Host.IpConfig(dhcp = False,
              ipAddress = ipAdd,
              subnetMask = "255.255.255.0")
    return ip

def GenerateIpV6Config():
    ipv6 = Vim.Host.IpConfig.IpV6AddressConfiguration(autoConfigurationEnabled = True,
               dhcpV6Enabled = False)

    ip = Vim.Host.IpConfig(dhcp = False,
             ipV6Config = ipv6)
    return ip

def CleanupVmknic(networkSystem, vmknic):
    networkSystem.RemoveVirtualNic(vmknic)

def TestVmknics(si, uuid):
    # Add vmknic to a latebinding portgroup with binding on host.
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    ipCfg = GenerateIPConfig("1.1.1.2")
    dvPort = Vim.Dvs.PortConnection(portgroupKey = "pg1",
                 switchUuid = uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    try:
        vmknic = networkSystem.AddVirtualNic("", spec)
    except Exception:
        print("Failed to add a vmknic to a ephemeral portgroup")
        raise
    print("Test 1: Add a vmknic to a ephemeral portgroup: PASS")

    # Edit vmknic to bind to a latebinding portgroup.
    dvPort = Vim.Dvs.PortConnection(portgroupKey = "pg3",
                 switchUuid = uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    try:
        networkSystem.UpdateVirtualNic(vmknic, spec)
    except Exception:
        print("Failed to reconnect a vmknic to a latebinding portgroup")
        raise
    print("Test 2: Reconnect a vmknic to a latebinding portgroup: PASS")

    # Edit vmknic to bind to a port that exists.
    dvPort = Vim.Dvs.PortConnection(portKey = "1000",
                 connectionCookie = 5,
                 switchUuid = uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    try:
        networkSystem.UpdateVirtualNic(vmknic, spec)
    except Exception:
        print("Failed to reconnect a vmknic to a dvPort")
        raise
    print("Test 3: Reconnect a vmknic to a dvPort: PASS")

    # Edit vmknic to bind to an early binding portgroup. This should fail.
    dvPort = Vim.Dvs.PortConnection(portgroupKey = "pg2",
                 switchUuid = uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    try:
        networkSystem.UpdateVirtualNic(vmknic, spec)
    except Exception:
        print("Test 4: Reconnect a vmknic to an earlybinding portgroup: PASS")
    CleanupVmknic(networkSystem, vmknic)
    return

def TestUpdateNetworkConfigVnics(si, uuid):
    # Add two vmknics binding to latebinding portgroups.
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    op = "modify"
    netCfg = Vim.Host.NetworkConfig()
    ipCfg = GenerateIPConfig("1.1.1.2")
    dvPort = Vim.Dvs.PortConnection(portgroupKey = "pg1",
                 switchUuid = uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    vnicCfg = Vim.Host.VirtualNic.Config(changeOperation = "add",
                  portgroup = "",
                  spec = spec)
    ipCfg = GenerateIPConfig("1.1.1.3")
    netCfg.GetVnic().append(vnicCfg)
    dvPort = Vim.Dvs.PortConnection(portgroupKey = "pg3",
                 switchUuid = uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    vnicCfg = Vim.Host.VirtualNic.Config(changeOperation = "add",
                  portgroup = "",
                  spec = spec)
    #netCfg.GetVnic().append(vnicCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception:
        print("Test 1: Failed to add vmknics to dvs")
        raise
    vmknics = result.GetVnicDevice()
    print("Test 1: Add vmknics to DVS: PASS")

    # Edit two vmknics one binding to a different portgroup and the other to
    # a dvPort.
    netCfg = Vim.Host.NetworkConfig()
    dvPort = Vim.Dvs.PortConnection(portgroupKey = "pg3",
                 switchUuid = uuid)
    spec = Vim.Host.VirtualNic.Specification(distributedVirtualPort = dvPort)
    vnicCfg = Vim.Host.VirtualNic.Config(
                  device = vmknics[0],
                  changeOperation = "edit",
                  portgroup = "",
                  spec = spec)
    #netCfg.GetVnic().append(vnicCfg)
    dvPort = Vim.Dvs.PortConnection(portKey = "1000",
                 connectionCookie = 5,
                 switchUuid = uuid)
    spec = Vim.Host.VirtualNic.Specification(distributedVirtualPort = dvPort)
    vnicCfg = Vim.Host.VirtualNic.Config(
                  device = vmknics[0],
                  changeOperation = "edit",
                  portgroup = "",
                  spec = spec)
    netCfg.GetVnic().append(vnicCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
        print("Test 2: Edit vmknics: PASS")
    except Exception:
        print("Test 2: Failed to edit vmknics")
    for vmknic in vmknics:
        CleanupVmknic(networkSystem, vmknic)
    return

def GenerateProxyCfg(uuid, pnicDevice, portKey = "", portgroupKey = "",
                     cnxId = 0):
    pnicSpec = Vim.Dvs.HostMember.PnicSpec(pnicDevice = pnicDevice,
                   uplinkPortKey = portKey,
                   uplinkPortgroupKey = portgroupKey,
                   connectionCookie = cnxId)
    pnicBacking = Vim.Dvs.HostMember.PnicBacking(pnicSpec = [pnicSpec])
    spec = Vim.Host.HostProxySwitch.Specification(backing = pnicBacking)
    proxyCfg = Vim.Host.HostProxySwitch.Config(changeOperation = "edit",
                                               spec = spec,
                                               uuid = uuid)
    return proxyCfg
def UnlinkPnics(networkSystem, uuid):
    spec = Vim.Host.HostProxySwitch.Specification()
    proxyCfg = Vim.Host.HostProxySwitch.Config(changeOperation = "edit",
                                               spec = spec,
                                               uuid = uuid)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    networkSystem.UpdateNetworkConfig(netCfg, "modify")

def TestUpdateNetworkConfigPnics(si, uuid, vmnic):

    print("Test updateNetworkConfig for a single uplink")
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    op = "modify"
    UnlinkPnics(networkSystem, uuid)

    # Link the pnic to a predefined uplink port connection id pair.

    proxyCfg = GenerateProxyCfg(uuid, vmnic, "1", "", 1)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception:
        print("Test 1: Failed to add pnics to dvs: FAIL")
        raise
    print("Test 1: Link the pnic to an uplink port connection id pair: Pass")
    UnlinkPnics(networkSystem, uuid)

    # autopick a free uplink port to connect the pnic to.
    proxyCfg = GenerateProxyCfg(uuid, vmnic)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception:
        print("Test 2: Failed to add pnics to dvs")
        raise
    print("Test 2: Autopick a free uplink port to connect the pnic to: Pass")
    UnlinkPnics(networkSystem, uuid)

    # pick a free uplink port from a particular portgroup to link the pnic to.

    proxyCfg = GenerateProxyCfg(uuid, vmnic, "", "pg5")
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception:
        print("Test 3: Failed to add pnics to dvs")
        raise
    print("Test 3: pick a free uplink port from a particular portgroup: Pass")
    UnlinkPnics(networkSystem, uuid)
    # Link the pnic to connect to a specified dvPort.
    proxyCfg = GenerateProxyCfg(uuid, vmnic, "1", "")
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception:
        print("Test 4: Failed to link the pnic to a specified dvPort")
        raise
    print("Test 4: Link the pnic to a specified dvPort: Pass")
    UnlinkPnics(networkSystem, uuid)

    # Try linking the uplink to a portgroup that doesn't have an uplink port.
    proxyCfg = GenerateProxyCfg(uuid, vmnic, "", "pg2")
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception:
        print("Test 5: Caught expected exception suitable pnic unavailable: PASS")
    print("Testing updateNetworkConfig for a single uplink complete")
    return

def TestUpdateNetworkConfigPnicsExtended(si, uuid, pnicList):
    # Test to verify if nic ordering is working correctly.
    # Generate three pnicSpecs.
    # 1 - No portgroup or port specified.
    # 2 - Portgroup specified.
    # 3 - Port specified.
    print("Test updateNetwork config for multiple uplinks")
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    op = "modify"
    UnlinkPnics(networkSystem, uuid)
    pnicSpec1 = Vim.Dvs.HostMember.PnicSpec(pnicDevice = pnicList[0])
    pnicSpec2 = Vim.Dvs.HostMember.PnicSpec(pnicDevice = pnicList[1],
                    uplinkPortgroupKey = "pg5")
    pnicSpec3 = Vim.Dvs.HostMember.PnicSpec(pnicDevice = pnicList[2],
                    uplinkPortKey = "3")
    pnicBacking = Vim.Dvs.HostMember.PnicBacking(pnicSpec = [pnicSpec1, pnicSpec2, pnicSpec3])
    spec = Vim.Host.HostProxySwitch.Specification(backing = pnicBacking)
    proxyCfg = Vim.Host.HostProxySwitch.Config(changeOperation = "edit",
                                               spec = spec,
                                               uuid = uuid)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception:
        print("Test 1: Caught exception suitable pnic unavailable: FAIL")
        raise
    print("Test 1: Add 3 nics: PASS")

    UnlinkPnics(networkSystem, uuid)
    pnicBacking = Vim.Dvs.HostMember.PnicBacking(pnicSpec = [pnicSpec1, pnicSpec2, pnicSpec3])
    proxyCfg.GetSpec().SetBacking(pnicBacking)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception:
        print("Test 2: Caught exception suitable pnic unavailable: FAIL")
        raise
    print("Test 2: Add 3 nics in different order: PASS")

def ValidateEarlyBindingPgState(pgName):
    myPg = folder.FindPg(pgName)
    config = myPg.GetConfig()
    if config.GetDefaultPortConfig() != None:
       raise Exception("config for static pg was persisted")
    policy = config.GetPolicy()
    if policy.GetLivePortMovingAllowed() != False:
       raise Exception("policy for static pg was persisted: %s" % policy)

def ValidateEphemeralPgState(pgName):
    myPg = folder.FindPg(pgName)
    config = myPg.GetConfig()
    if config.GetDefaultPortConfig() == None:
       raise Exception("config for ephemeral pg was not persisted")
    policy = config.GetPolicy()
    if policy.GetLivePortMovingAllowed() != False:
       raise Exception("policy for ephemeral pg was persisted: %s" % policy)


def TestDVSLimits(si, uuid, dvsName):
    # Create the dvs.
    prodSpec = Vim.Dvs.ProductSpec(vendor="VMware", version = "6.5.0")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    createSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSCreateSpec(
        uuid = uuid,
        name = dvsName,
        backing = Vim.Dvs.HostMember.PnicBacking(),
        productSpec = prodSpec,
        maxProxySwitchPorts = 64,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True
        )
    vmwsetting = Vim.Dvs.HostDistributedVirtualSwitchManager.VmwareDVSSettingSpec()
    createSpec.SetVmwareSetting(vmwsetting)

    dvsManager.CreateDistributedVirtualSwitch(createSpec)
    portgroupList = []
    numIter = 512
    print("testing early binding portgroups limits")
    for i in range(numIter):
       name = "pg" + str(i)
       pg = GeneratePortgroupCfg(name, "add", "earlyBinding")
       portgroupList.append(pg)
    bigClock = StopWatch()
    dvsManager.UpdateDVPortgroups(uuid, portgroupList)
    bigClock.finish("creating " + str(numIter) + " static pgs")
    ValidateEarlyBindingPgState(name)
    cleanup(si, uuid, "")
    print("testing ephemeral binding portgroups limits")
    dvsManager.CreateDistributedVirtualSwitch(createSpec)
    portgroupList = []
    j = 0
    for j in range(numIter):
       name = "pg" + str(j)
       pg = GeneratePortgroupCfg(name, "add", "ephemeral")
       portgroupList.append(pg)
    bigClock = StopWatch()
    dvsManager.UpdateDVPortgroups(uuid, portgroupList)
    bigClock.finish("creating " + str(numIter) + " ephemeral pgs")
    ValidateEphemeralPgState(name)
    cleanup(si, uuid, "")

def GenerateNetRMSpec(poolKey, shareLevel, limit, shareVal = 0):
    allocInfo = Vim.Dvs.NetworkResourcePool.AllocationInfo()
    shares = Vim.SharesInfo(level = shareLevel,
                            shares = shareVal)
    allocInfo.SetLimit(limit)
    allocInfo.SetShares(shares)
    spec = Vim.Dvs.NetworkResourcePool.ConfigSpec()
    spec.SetKey(poolKey)
    spec.SetAllocationInfo(allocInfo)
    return spec

def TestNetRmSettings(si, uuid):
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    poolKeys = ["management", "nfs", "vm"]
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = uuid,
        networkResourcePoolKeys = poolKeys,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True
        )
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(uuid)
    print(returnedConfigSpec)

    # Test the setting of per uplink net rm settings
    uplinkResourceSpecs = []
    uplinkResourceSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.UplinkPortResourceSpec()
    uplinkResourceSpec.SetUplinkPortKey("1")
    specs = []
    spec = GenerateNetRMSpec("management", Vim.SharesInfo.Level.custom, 100, 5)
    specs.append(spec)
    spec = GenerateNetRMSpec("nfs", Vim.SharesInfo.Level.custom, 20, 6)
    specs.append(spec)
    spec = GenerateNetRMSpec("vm", Vim.SharesInfo.Level.custom, 32, 7)
    specs.append(spec)
    uplinkResourceSpec.SetConfigSpec(specs)
    uplinkResourceSpecs.append(uplinkResourceSpec)
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = uuid,
        uplinkPortResourceSpec = uplinkResourceSpecs,
	modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True)
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(uuid)
    print(returnedConfigSpec)
    # TODO add some negative test cases.
    # Do some automated comparisons.

def TestNetRmEnable(si, uuid):
    print("Testing enable net rm")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    origSpec = dvsManager.RetrieveDvsConfigSpec(uuid)
    if origSpec.GetEnableNetworkResourceManagement() == True:
        raise Exception("Test failed: Netrm is enabled by default on the vDS")
    print("Test 1: Validate default netrm policy is False: PASS")

    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = uuid,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True,
        enableNetworkResourceManagement = True
        )
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec =  dvsManager.RetrieveDvsConfigSpec(uuid)
    if returnedConfigSpec.GetEnableNetworkResourceManagement() == False:
        raise Exception("Failed to enable netrm for vDS")
    print("Test 2: Enable netrm on vDS: PASS")
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = uuid,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True,
        enableNetworkResourceManagement = False
        )
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec =  dvsManager.RetrieveDvsConfigSpec(uuid)
    if returnedConfigSpec.GetEnableNetworkResourceManagement() == True:
        raise Exception("Failed to disable netrm by for vDS")
    print("Test 3: Disable netrm on vDS: PASS")

def TestVnicUpdate(si, uuid):
    print("Testing vnic update of backing and ipCfg in the same spec")
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    # create a dummy vnic
    netCfg = Vim.Host.NetworkConfig()
    dvPort = Vim.Dvs.PortConnection(portKey = "1000",
                 connectionCookie = 5,
                 switchUuid = uuid)
    ipCfg = GenerateIPConfig("192.168.10.2")
    vnicSpec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
                distributedVirtualPort = dvPort)
    try:
        vmknic = networkSystem.AddVirtualNic("", nic = vnicSpec)
    except Exception:
        print("Failed to add dummy vmknic to dvs")
        raise
    # Invoke update network config with the same backing.
    newIp = "192.168.10.3"
    newIpCfg = GenerateIPConfig(newIp)
    newVnicSpec = Vim.Host.VirtualNic.Specification(ip = newIpCfg)
    try:
        networkSystem.UpdateVirtualNic(vmknic, nic = newVnicSpec)
    except Exception as e:
        print("Test 1: Test to check UpdateVirtualNic for vnic update failed")
        raise
    # Validate that the ip actually changed.
    newVnics = networkSystem.GetNetworkInfo().GetVnic()
    for newVnic in newVnics:
        if newVnic.GetDevice() == vmknic:
            if newVnic.GetSpec().GetIp().GetIpAddress() != newIp:
                raise Exception("Test 1: Ip address not updated failed")
    CleanupVmknic(networkSystem, vmknic)
    print("Test1: Test to check UpdateVirtualNic for vnic update passed")
    return

def GetPnics(nics):
    if nics == None:
        return []
    nics = nics.split(',')
    return nics

def main():
    """
    Test does the following.
    - Creates a DVS.
    - Creates a latebinding (w binding on host) and an early binding portgroup.
    - Creates a VM with a portgroup backing.
    For latebinding option.
    - Powers on the VM with latebinding portgroups verifies a
      new port gets allocated.
    - Hot adds a nic to a powered on vm and verifies that the backing is valid.
    - Reconfigures the VM by adding an ethernet device backed by a latebinding pg
      and verfies the backing is valid
    - Powers off the VM.
    For early binding VM.
    - Creates a VM connecting to an existing dvPort.
    - Reconfigures the VM by adding a device connecting to a new dvPort. Verifies
      that the reconfigure fails.
    - Reconfigures a VM to connect to a early binding portgroup.
      Verifies that it fails.

    """
    options = get_options()
    pnicList = GetPnics(options.nic)
    si = Connect(host=options.host,
                 user=options.user,
                 version="vim.version.version9",
                 pwd=options.password)
    atexit.register(Disconnect, si)
    if (options.vmName == None) :
        options.vmName = "testVM"
    try:
       print("cleaning up")
       cleanup(si, options.uuid, options.vmName)
    except Exception as e:
       print("checked for vm from previous run")
    setup(si, options.uuid, options.name)
    try:
        TestVnicUpdate(si, options.uuid)
        TestNetRmEnable(si, options.uuid)
        TestEphemeral(options.vmName, options.uuid)
        TestLateBinding(options.vmName, options.uuid)
        TestEarlyBinding(options.vmName, options.uuid)
        TestVmknics(si, options.uuid)
        TestUpdateNetworkConfigVnics(si, options.uuid)
        if (len(pnicList) > 0):
            TestUpdateNetworkConfigPnics(si, options.uuid, pnicList[0])
        TestSimulatedVcClone(options.vmName, options.uuid)
        if (len(pnicList) >= 3):
           TestUpdateNetworkConfigPnicsExtended(si, options.uuid, pnicList)
        TestNetRmSettings(si, options.uuid)
        cleanup(si, options.uuid, options.vmName)
        TestDVSLimits(si, options.uuid, options.name)
    except Exception as e:
        cleanup(si, options.uuid, options.vmName)
        raise

    try:
        # just in case
        cleanup(si, options.uuid, options.vmName)
    except Exception as e:
        pass
    print("DONE.")
    return 0

# Start program
if __name__ == "__main__":
    main()
