#!/usr/bin/python

from __future__ import print_function

import sys
from pyVmomi import Vim, VmomiSupport
from pyVmomi.VmomiSupport import LinkResolver, ResolveLinks
from pyVim.connect import SmartConnect, Disconnect
from optparse import OptionParser
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm, host
from pyVim import invt
from pyVim import vmconfig
from pyVim import vimutil
from pyVim import arguments
from pyVim.helpers import Log, StopWatch
import time
import atexit
import operator
import fcntl
import struct
import array
import os
import subprocess
import copy
import traceback
import featureState

datastore=None

#
# The following tests need to be added.
# - Tests to set and get pvlan settings.
# - Tests to set and get dvMirror settings.
# - Tests to validate settings for netRm
# - Tests to set and get overlay settings.
# - Set and get port settings for vlans.
# - Add the ability to detect free pnics and run the pnic tests.


def python2to3Encode(val):
    """
    Encode the contents if Python 3
    @param val: Value to be encoded
    @return: Return encoded value if Python 3, else 'val' otherwise
    """

    if sys.version_info[0] >= 3:
       val = val.encode()
    return val


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
    parser.add_option("-v", "--vmName", default="dvstestVM",
                      help="vm name")
    parser.add_option("-d", "--vmfs", default=None,
                      help="vmfs volume")
    parser.add_option("--nic",
                      help="the pnic to be used for the test")
    parser.add_option("--test",
                      help="the name of the subtest to run")
    parser.add_option("--nocleanup",
                      help="dont do cleanup", action='store_true')
    parser.add_option("--simulatorOnly", action='store_true',
                      help="Only runs tests that work in host simulator")
    (options, _) = parser.parse_args()

    if options.uuid == None:
        parser.error("uuid needs to be specified")
    if options.name == None:
        parser.error("dvs name needs to be specified")
    global datastore
    if options.vmfs == None:
       datastore = None
    else:
       datastore = options.vmfs

    return options

def createDvs():
    """
    Setup a dvs with one early binding, one latebinding, two ephemeral and
    one uplink portgroup. Also creates 4 uplink ports 2 standalone and 2
    belonging to the uplink portgroup.
    """

    # Create the dvs.
    prodSpec = Vim.Dvs.ProductSpec(vendor="VMware", version = "6.5.0")
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
        uuid = options.uuid,
        name = options.name,
        backing = Vim.Dvs.HostMember.PnicBacking(),
        productSpec = prodSpec,
        maxProxySwitchPorts = 64,
        port=[port1, uplinkPort1, uplinkPort2, uplinkPort3],
        uplinkPortKey=["1","2", "3"],
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True,
        switchIpAddress = "10.20.30.40"
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
    dvsManager.UpdateDVPortgroups(options.uuid, portgroupList)
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
    dvsManager.UpdatePorts(options.uuid, portDataList)

def GenerateIPConfig(ipAdd):
    ip = Vim.Host.IpConfig(dhcp = False,
              ipAddress = ipAdd,
              subnetMask = "255.255.255.252")
    return ip

def GenerateIpV6Config():
    ipv6 = Vim.Host.IpConfig.IpV6AddressConfiguration(autoConfigurationEnabled=True,
                                                      dhcpV6Enabled=False)
    ip = Vim.Host.IpConfig(dhcp=False, ipV6Config=ipv6)
    return ip

def CleanupVmknic(networkSystem, vmknic):
    networkSystem.RemoveVirtualNic(vmknic)

def cleanup(dvsUuidList):
   """
   Remove the dvs created as part of the setup phase. Assumes no clients are connected.
   """
   if options.nocleanup:
      print("Not doing cleanup as requested")
      return
   vm1 = folder.Find(options.vmName)
   if vm1 != None:
       try:
           vm.PowerOff(vm1)
       except Exception as e:
           pass
       vm.Destroy(vm1)

   dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
   # If list is None, script collapses here
   if dvsUuidList != None:
      for dvsUuid in dvsUuidList:
         try:
            dvsManager.RemoveDistributedVirtualSwitch(dvsUuid)
         except Exception as e:
            print(e)
      del dvsUuidList[:]

   try:
      dvsManager.RemoveDistributedVirtualSwitch(options.uuid)
   except Exception as e:
      print(e)

def IsBackingValid(devices):
    """
    Checks if the backing of the device is valid, i.e it has a dvPort and a cnxId assigned.
    """
    for device in devices:
        if isinstance(device.GetBacking(),
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
        if isinstance(device.GetBacking(),
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
    shaping = Vim.Dvs.DistributedVirtualPort.TrafficShapingPolicy(
                  enabled = bPolicy)
    shaping.SetInherited(False)
    cfg.SetInShapingPolicy(shaping)
    cfg.SetOutShapingPolicy(shaping)
    cfg.SetIpfixEnabled(bPolicy)
    security = Vim.Dvs.VmwareDistributedVirtualSwitch.SecurityPolicy(
                   allowPromiscuous = bPolicy,
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
    failoverPolicy = \
        Vim.Dvs.VmwareDistributedVirtualSwitch.UplinkPortTeamingPolicy()
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

    reversePolicy = Vim.BoolPolicy()
    reversePolicy.SetInherited(False)
    reversePolicy.SetValue(True)
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

def TestSimulatedVcClone():
    """
    Test the code paths that VC excercises during cloning a VM with
    a dvs backing.
    """
    print("Testing hostd code corresponding to clone")
    envBrowser = invt.GetEnv()
    config = vm.CreateQuickDummySpec(options.vmName, datastoreName = datastore)
    cfgOption = envBrowser.QueryConfigOption(None, None)
    # Add a nic backed by a dvs portgroup pair.
    config = vmconfig.AddDvPortBacking(config, "", options.uuid, 0, cfgOption,
                                       "invalidPg")
    try:
        vm.CreateFromSpec(config)
    except Exception as e:
        print("Test1: Caught exception as expected")
    else:
        raise Exception("Test1: Create vm with invalid dvPortgroup backing didn't fail as expected")
    print("Test1: Create vm with invalid dvPortgroup backing failed as expected: PASS")

    config = vm.CreateQuickDummySpec(options.vmName, datastoreName = datastore)
    config = vmconfig.AddDvPortBacking(config, "", options.uuid, 0,
                                       cfgOption, "pg1")
    try:
        myVm = vm.CreateFromSpec(config)
    except Exception as e:
        print("Failed to create a VM to connect to a dvPortgroup")
        raise
    vm.Destroy(myVm)
    print("Test2: Create vm with valid dvPort backing: PASS")

    # Create a VM only specifying the dvs uuid in its backing.
    config = vm.CreateQuickDummySpec(options.vmName, datastoreName = datastore)
    config = vmconfig.AddDvPortBacking(config, "", options.uuid, None,
                                       cfgOption, "")
    try:
        myVm = vm.CreateFromSpec(config)
    except Exception as e:
        print("Failed to create a VM to connected to a standalone port")
        raise
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if not IsBackingPortNotAllocated(devices):
        print(devices)
        raise Exception ("Nic has a dvPort assigned to it or nic add failed")
    print("Test3: Create vm with valid dvs uuid specified in the dvsbacking (standalone): PASS")

    # Reconfigure a VM only specifying a dvs uuid in its backing
    for device in devices:
        if isinstance(device.GetBacking(),
                      Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            cspec = Vim.Vm.ConfigSpec()
            device.GetConnectable().SetConnected(True)
            device.SetUnitNumber(9)
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.add)
            break
    try:
        vm.Reconfigure(myVm, cspec)
    except Exception as e:
        print("Test4: failed to add a device with only dvs backing specified")
    print("Test4: Reconfig VM specifying only the dvsUuid in backing: PASS")

    vm.Destroy(myVm)
    print("Testing simulate vc clone done")

def TestEphemeral():
    """
    Test epehemeral portgroups.
    - Create a VM configure it to connect to an ephemeral portgroup.
    - Power on the VM and validate that backing is valid.
    - Hot add a nic to connect to an ephemeral portgroup and validate backing.
    - Poweroff and destroy the VM
    """
    print("Testing Ephemeral portgroup behaviour")
    envBrowser = invt.GetEnv()
    config = vm.CreateQuickDummySpec(options.vmName, datastoreName = datastore)
    cfgOption = envBrowser.QueryConfigOption(None, None)
    # Add a latebinding dvPortgroup backed nic.
    config = vmconfig.AddDvPortBacking(config, "", options.uuid, 0, cfgOption,
                                       "pg1", type = 'vmxnet3')
    try:
        myVm = vm.CreateFromSpec(config)
    except Exception as e:
        raise
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Failed to add nic")
    if not IsBackingPortNotAllocated(devices):
        print(devices)
        raise Exception ("Nic has a dvPort assigned to it or nic add failed")
    print("Test 1: Create a vm with an ephemeral portgroup backing: PASS")
    vm.PowerOn(myVm)
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Failed to add nic")
    if not IsBackingValid(devices):
        raise Exception("Invalid backing allocated")
    print("Test 2: powerOn VM with a ephemeral backing: PASS")
    # Remove and add hot add a nic device to a powered on VM.
    vm.PowerOff(myVm)
    for device in devices:
        if isinstance(device.GetBacking(),
                      Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.remove)
            break
    vm.Reconfigure(myVm, cspec)
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if IsBackingValid(devices):
        print(devices)
        raise Exception("Remove of device failed.")
    # powerOn the VM and hot add the nic.
    vm.PowerOn(myVm)
    config = Vim.Vm.ConfigSpec()
    config = vmconfig.AddDvPortBacking(config, "", options.uuid, 0, cfgOption,
                                       "pg1", type = 'vmxnet3')
    vm.Reconfigure(myVm, config)
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Failed to hotadd nic")
    if not IsBackingValid(devices):
        raise Exception("Invalid backing allocated")
    print("Test 3: remove and hot add nic to VM with a ephemeral backing: PASS")
    # Foundry issue wait for fix and then uncomment.
    for device in devices:
        if isinstance(device.GetBacking(),
                      Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            device.GetBacking().GetPort().SetPortgroupKey("pg3")
            device.GetBacking().GetPort().SetPortKey(None)
            device.GetBacking().GetPort().SetConnectionCookie(None)
            device.GetConnectable().SetConnected(True)
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
            break
    vm.Reconfigure(myVm, cspec)
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Failed to edit nic")
    if not IsBackingValid(devices):
        raise Exception("Invalid backing allocated")
    print("Test 4: Reconfig poweredon with a ephemeral backing: PASS")
    vm.PowerOff(myVm)
    vm.Destroy(myVm)
    print("Ephemeral portgoup tests complete")

def TestZombiePorts():
    """
    Test zombie port after hot add/disconnect.
    - Create a VM configure it to connect to an ephemeral portgroup.
    - Power on the VM with vmxnet3 and e1000e vNICs connected.
    - Hot add a vNIC.
    - Disconnet the first two vNICs.
    - Hot add another vNIC.
    - Check that zombie ports are not left over in the system.
    - Poweroff and destroy the VM.
    """
    envBrowser = invt.GetEnv()
    config = vm.CreateQuickDummySpec(options.vmName, datastoreName = datastore)
    cfgOption = envBrowser.QueryConfigOption(None, None)

    # Add two latebinding dvPortgroup backed nics.
    config = vmconfig.AddDvPortBacking(config, "", options.uuid, 0, cfgOption,
                                       "pg1", True, "vmxnet3")
    config = vmconfig.AddDvPortBacking(config, "", options.uuid, 0, cfgOption,
                                       "pg1", True, "e1000e")
    try:
        myVm = vm.CreateFromSpec(config)
    except Exception as e:
        raise
    vm.PowerOn(myVm)
    # hot add a vNIC
    config = Vim.Vm.ConfigSpec()
    config = vmconfig.AddDvPortBacking(config, "", options.uuid, 0, cfgOption,
                                       "pg1")
    vm.Reconfigure(myVm, config)
    # disconnect two vNICs
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    for device in devices:
       if isinstance(device, Vim.Vm.Device.VirtualVmxnet3) or isinstance(device, Vim.Vm.Device.VirtualE1000e):
          print('disconnecting a Vmxnet3/e1000e device connected to %s' % device.GetBacking().GetPort().GetPortKey())
          device.GetConnectable().SetConnected(False)
          cspec = Vim.Vm.ConfigSpec()
          vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
          vm.Reconfigure(myVm, cspec)
    # hot add another vNIC
    config = Vim.Vm.ConfigSpec()
    config = vmconfig.AddDvPortBacking(config, "", options.uuid, 0, cfgOption, "pg1")
    vm.Reconfigure(myVm, config)
    # check ZOMBIE ports
    status,output = subprocess.getstatusoutput("/sbin/net-dvs -l | grep ZOMBIE")
    if len(output) > 0:
       print(output)
       raise Exception("ZOMBIE port found after hot add/disconnect")
    vm.PowerOff(myVm)
    vm.Destroy(myVm)
    print("ZOMBIE port test complete")

def TestLateBinding():
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
    print("Testing latebinding portgroup behaviour")
    envBrowser = invt.GetEnv()
    config = vm.CreateQuickDummySpec(options.vmName, datastoreName = datastore)
    cfgOption = envBrowser.QueryConfigOption(None, None)
    # Add a latebinding dvPortgroup backed nic.
    config = vmconfig.AddDvPortBacking(config, "", options.uuid, 0, cfgOption,
                                       "pg4", type = 'vmxnet3')
    try:
        myVm = vm.CreateFromSpec(config)
    except Exception as e:
        raise
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Failed to add nic")
    if not IsBackingPortNotAllocated(devices):
        raise Exception("dvPort allocated for a latebinding portgroup")
    print("Test1: Create VM with a latebinding portgroup backing: PASS")
    # power on the VM.
    vm.PowerOn(myVm)
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Nic seems to be missing")
    if not IsBackingPortNotAllocated(devices):
        raise Exception("dvPort allocated for a latebinding portgroup after "
                        "powerOn")
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
    vm.Reconfigure(myVm, cspec)
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Failed to edit nic")
    if not IsBackingValid(devices):
        raise Exception("Invalid backing allocated")
    print("Test3: Reconfig poweredon with a ephemeral backing from a "
          "latebinding backing allocates a port: PASS")

    #Reconfig the VM to connect to a latebinding backing.
    for device in devices:
        if isinstance(device.GetBacking(),
                      Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            device.GetBacking().GetPort().SetPortgroupKey("pg4")
            device.GetBacking().GetPort().SetPortKey(None)
            device.GetBacking().GetPort().SetConnectionCookie(None)
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
            break
    try:
        vm.Reconfigure(myVm, cspec)
    except Exception as e:
        print("VM reconfigure failed")
    print("Test4: Reconfig powered on VM to connect to a latebinding backing "
          "fails as expected: PASS")

    # reconfigure the VM to connect to a latebinding portgroup and disconnect the device.
    for device in devices:
        if isinstance(device.GetBacking(),
                      Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            device.GetBacking().GetPort().SetPortgroupKey("pg4")
            device.GetBacking().GetPort().SetPortKey(None)
            device.GetBacking().GetPort().SetConnectionCookie(None)
            device.GetConnectable().SetConnected(False)
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
            break
    vm.Reconfigure(myVm, cspec)
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if not IsBackingPortNotAllocated(devices):
        print(devices)
        raise Exception ("Nic has a dvPort assigned to it or nic add failed")
    print("Test5: Reconfig powered on VM to connect to a latebinding backing "
          "with device disconnected: PASS")
    vm.PowerOff(myVm)
    vm.Destroy(myVm)
    print("Late binding tests complete")

def TestEarlyBinding():
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
    envBrowser = invt.GetEnv()
    config = vm.CreateQuickDummySpec(options.vmName, datastoreName = datastore)
    cfgOption = envBrowser.QueryConfigOption(None, None)
    # Add a earlybinding dvPortgroup backed nic.
    config = vmconfig.AddDvPortBacking(config, "", options.uuid, 0, cfgOption,
                                       "pg2")
    try:
        myVm = vm.CreateFromSpec(config)
    except Exception as e:
        print("Create VM failed as expected")
    else:
        raise Exception("Test1: Create a device backed by an early binding portgroup didn't fail as expected")
    print("Test 1: Creating a device backed by an early binding portgroup with" \
          "startConnected = true fails as expected: PASS")
    config = vm.CreateQuickDummySpec(options.vmName, datastoreName = datastore)
    cfgOption = envBrowser.QueryConfigOption(None, None)
    # Add an earlybinding dvPortgroup backed nic.
    config = vmconfig.AddDvPortBacking(config, "", options.uuid, 0, cfgOption,
                                       "pg2", False)
    myVm = vm.CreateFromSpec(config)
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if not IsBackingPortNotAllocated(devices):
        print(devices)
        raise Exception ("Nic has a dvPort assigned to it or nic add failed")
    print("Test 2: Creating a device backed by and early binding portgroup with" \
          "startConnected = false succeeds: PASS")
    vm.PowerOn(myVm)
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("nic not present")
    if not IsBackingPortNotAllocated(devices):
        print(devices)
        raise Exception ("Nic has a dvPort assigned to it or nic add failed")
    print("Test 3: Power on VM succeeds: PASS")
    # Reconfigure the VM to connect to an invalid port.
    for device in devices:
        if isinstance(device.GetBacking(),
                      Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            device.GetBacking().GetPort().SetPortKey("100")
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
            break
    try:
        vm.Reconfigure(myVm, cspec)
    except Exception as e:
        print("VM reconfigure failed")
    print("Test 4: Reconfig a VM to connect to an invalid dvPort fails as expected: PASS")

    # Add a device to connect to an early binding portgroup with no dvPort specified.
    config = Vim.Vm.ConfigSpec()
    config = vmconfig.AddDvPortBacking(config, "", options.uuid, 0, cfgOption,
                                       "pg2")
    try:
        vm.Reconfigure(myVm, config)
    except Exception as e:
        print("VM reconfigure failed")
    print("Test 4: Hot add of a device to connect to an earlybinding portgroup fails as expected: PASS")

    # Reconfigure device to connect to an early binding portgroup.
    for device in devices:
        if isinstance(device.GetBacking(),
            Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            device.GetBacking().GetPort().SetPortgroupKey("pg2")
            device.GetBacking().GetPort().SetPortKey(None)
            device.GetBacking().GetPort().SetConnectionCookie(None)
            device.GetConnectable().SetConnected(True)
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
            break
    try:
        vm.Reconfigure(myVm, cspec)
    except Exception as e:
        print("VM reconfigure failed")
    print("Test 5: Reconfig a VM to connect to an early binding portgroup fails as expected: PASS")

    # Reconfigure a device to disconnected state and connect to an early binding dvPortgroup.
    for device in devices:
        if isinstance(device.GetBacking(),
            Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            device.GetBacking().GetPort().SetPortgroupKey("pg2")
            device.GetBacking().GetPort().SetPortKey(None)
            device.GetBacking().GetPort().SetConnectionCookie(None)
            device.GetConnectable().SetConnected(False)
            cspec = Vim.Vm.ConfigSpec()
            vmconfig.AddDeviceToSpec(cspec, device, Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
            break
    vm.Reconfigure(myVm, cspec)
    if not IsBackingPortNotAllocated(devices):
        print(devices)
        raise Exception ("Nic has a dvPort assigned to it or nic add failed")
    print("Test6 complete: Reconfig powered on VM to connect to a earlybinding "
          "backing with device disconnected: PASS")
    vm.PowerOff(myVm)
    vm.Destroy(myVm)
    print("EarlyBinding tests complete")

def TestVmknicTag():
    '''
    Tests to verify adding/removing/query tags for vmkNics
    '''
    # Add vmknic
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    ipCfg = GenerateIPConfig("192.168.124.17")
    dvPort = Vim.Dvs.PortConnection(portKey = "1000",
                 connectionCookie = 5,
                 switchUuid = options.uuid)

    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    try:
        vmknic = networkSystem.AddVirtualNic("", spec)
    except Exception as e:
        print("Failed to add a vmknic to dvPort 1000")
        raise

    vNicManager = host.GetHostSystem(si).GetConfigManager().virtualNicManager
    tags = ["vmotion",
            "faultToleranceLogging",
            "vSphereReplication",
            "vSphereReplicationNFC",
            "management"]
    for tag in tags:
       if UpdateVmknicTag(vNicManager, tag, vmknic):
          print('Pass tag test for: %s' % tag)
       else:
          str = "Failed on tag test for: " + tag
          CleanupVmknic(networkSystem, vmknic)
          raise Exception(str)

    # Delete new added vmkNic
    CleanupVmknic(networkSystem, vmknic)
    print("Pass vmknic tag test for all types of tag.")


def UpdateVmknicTag(vNicManager, tag, vmknic):
    # Add tag for vmknic
    vNicManager.SelectVnic(tag, vmknic)
    netConfig = vNicManager.QueryNetConfig(tag)
    vNics = ResolveLinks(netConfig.GetSelectedVnic(), netConfig)
    vNicNames = []
    for vNic in vNics:
       vNicNames.append(vNic.GetDevice())

    if vmknic in vNicNames:
       print('Successfully add tag: %s' % tag)
    else:
       print('Failed to add tag: %s' % tag)
       return False

    # Remove tag from vmknic
    vNicManager.DeselectVnic(tag, vmknic)
    netConfig = vNicManager.QueryNetConfig(tag)
    vNics = ResolveLinks(netConfig.GetSelectedVnic(), netConfig)
    del vNicNames[:]
    if vNicNames != None:
       for vNic in vNics:
          vNicNames.append(vNic.GetDevice())

    if vmknic not in vNicNames:
       print('Successfully remove tag: %s' % tag)
    else:
       print('Failed to remove tag: %s' % tag)
       return False

    return True


def TestVmknics():
    '''
    Tests to exercise the UpdateVirtualNic apis in tandem with specific dvPortgroup configurations
    - Tests: Connect and reconnect to ephemeral portgroups, reconnects to specific dvPorts
    - Validates connecting to an early binding portgroup fails.
    '''
    # Add vmknic to a latebinding portgroup with binding on host.
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    ipCfg = GenerateIPConfig("192.168.124.17")
    dvPort = Vim.Dvs.PortConnection(portgroupKey = "pg1",
                 switchUuid = options.uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    try:
        vmknic = networkSystem.AddVirtualNic("", spec)
    except Exception as e:
        print("Failed to add a vmknic to a ephemeral portgroup")
        raise
    print("Test 1: Add a vmknic to a ephemeral portgroup: PASS")

    # Edit vmknic to bind to an ephemeral portgroup.
    dvPort = Vim.Dvs.PortConnection(portgroupKey = "pg3",
                 switchUuid = options.uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    try:
        networkSystem.UpdateVirtualNic(vmknic, spec)
    except Exception as e:
        print("Failed to reconnect a vmknic to an ephemeral portgroup")
        raise
    print("Test 2: Reconnect a vmknic to a ephemeral portgroup: PASS")

    # Edit vmknic to bind to a port that exists.
    dvPort = Vim.Dvs.PortConnection(portKey = "1000",
                 connectionCookie = 5,
                 switchUuid = options.uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    try:
        networkSystem.UpdateVirtualNic(vmknic, spec)
    except Exception as e:
        print("Failed to reconnect a vmknic to a dvPort")
        raise
    print("Test 3: Reconnect a vmknic to a dvPort: PASS")

    # Edit vmknic to bind to an early binding portgroup. This should fail.
    dvPort = Vim.Dvs.PortConnection(portgroupKey = "pg2",
                 switchUuid = options.uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    try:
        networkSystem.UpdateVirtualNic(vmknic, spec)
    except Exception as e:
        print("Test 4: Reconnect a vmknic to an earlybinding portgroup: PASS")
    print("Test 4: Reconnect a vmknic to an earlybinding portgroup: PASS")

    # Exercise NetworkSystem.UpdateIpRouteConfig code path
    origIpRouteConfig = networkSystem.GetIpRouteConfig()
    newIpRouteConfig = copy.deepcopy(origIpRouteConfig)
    newIpRouteConfig.defaultGateway = "127.0.0.1" # invalid gateway
    try:
       networkSystem.UpdateIpRouteConfig(newIpRouteConfig)
    except Exception as e:
       print("Test 5: got expected exception when setting default gateway as 127.0.0.1")

    try:
       networkSystem.UpdateIpRouteConfig(origIpRouteConfig)
    except Exception as e:
       print("Failed to update ipRouteCfg to the host")
       raise

    updatedIpRouteConfig = networkSystem.GetIpRouteConfig()
    if (origIpRouteConfig.defaultGateway != updatedIpRouteConfig.defaultGateway):
       print("Test 5: Failed to update ipRouteConfig to the host, result mismatch")
       raise Exception("IpRouteConfig mismatch")
    print("Test 5: Updating host IpRouteConfig: PASS")

    # Exercise NetworkSystem.UpdateIpRouteTableConfig code path
    newRoute = Vim.Host.IpRouteTableConfig()
    newIpRouteEntry = Vim.Host.IpRouteEntry()
    newIpRouteEntry.SetGateway("192.168.10.53")
    newIpRouteEntry.SetNetwork("192.168.10.0")
    newIpRouteEntry.SetPrefixLength(24)
    newIpRouteOp = []
    ipRouteOp = Vim.Host.IpRouteOp()
    ipRouteOp.SetChangeOperation("add")
    ipRouteOp.SetRoute(newIpRouteEntry)
    newIpRouteOp.append(ipRouteOp)
    newRoute.SetIpRoute(newIpRouteOp)
    try:
       networkSystem.UpdateIpRouteTableConfig(newRoute)
    except Exception as e:
       print("Test 6: got expected exception when adding ipRoute 192.168.10.53")

    print("Test 6: Updating host IpRouteTableConfig: PASS")
    CleanupVmknic(networkSystem, vmknic)
    return

def TestNetworkRollbackAPIs(si, commit, dvsName, dvsUuid, dvsUuidList,
                            transactionIndex):
   '''
    Tests to exercise the rollback apis that are supported in InvokeHostTransactionCall
    - Validates rollback apis
    - if commit is true, all actions will be comitted by hostd; else all actions will
      be rolled back
   '''
   defaultTimeout = 10
   print('TestNetworkRollbackAPIs commit = %s' % commit)
   networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
   dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager

   # Exercise NetworkSystem.UpdateIpRouteConfig code path
   origIpRouteConfig = networkSystem.GetIpRouteConfig()
   newIpRouteConfig = copy.deepcopy(origIpRouteConfig)
   newIpRouteConfig.defaultGateway = "127.0.0.1" # invalid gateway
   try:
      transactionIndex += 1
      networkSystem.InvokeHostTransactionCall(str(transactionIndex), defaultTimeout,
         "updateIpRouteConfig", newIpRouteConfig, None, None, None)
   except Exception as e:
      print("Test 1: got expected exception when setting default gateway as 127.0.0.1")

   try:
      transactionIndex += 1
      networkSystem.InvokeHostTransactionCall(str(transactionIndex),
                                              defaultTimeout,
                                              "updateIpRouteConfig",
                                              origIpRouteConfig, None,
                                              None, None)
      if commit:
         networkSystem.CommitTransaction(str(transactionIndex))
   except Exception as e:
      print("Failed to update ipRouteCfg to the host")
      raise
   print("Test 1: set host IpRouteConfig: PASS")

   prodSpec = Vim.Dvs.ProductSpec(vendor="VMware",
                                  version = "7.0.0")

   createSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSCreateSpec(
       uuid = dvsUuid,
       name = dvsName,
       backing = Vim.Dvs.HostMember.PnicBacking(),
       productSpec = prodSpec,
       maxProxySwitchPorts = 128,
       modifyVendorSpecificDvsConfig = True,
       modifyVendorSpecificHostMemberConfig = True
       )
   vmwsetting = Vim.Dvs.HostDistributedVirtualSwitchManager.VmwareDVSSettingSpec()
   createSpec.SetVmwareSetting(vmwsetting)
   try:
      if commit:
         transactionIndex += 1
         networkSystem.InvokeHostTransactionCall(str(transactionIndex),
                                                 defaultTimeout,
                                                 "createDistributedVirtualSwitch",
                                                 createSpec, None, None, None)
         networkSystem.CommitTransaction(str(transactionIndex))
         print("Test 2: create distributed virtual switch: PASS")
      else:
         dvsManager.CreateDistributedVirtualSwitch(createSpec)
      dvsUuidList.append(dvsUuid)
   except Exception as e:
      print("Failed to create distributed virtual switch")
      raise


   configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
       uuid = dvsUuid,
       maxProxySwitchPorts = 256,
       modifyVendorSpecificDvsConfig = True,
       modifyVendorSpecificHostMemberConfig = True,
       enableNetworkResourceManagement = False
       )
   vmwsetting = Vim.Dvs.HostDistributedVirtualSwitchManager.VmwareDVSSettingSpec()
   vmwsetting.SetMaxMtu(9000)
   configSpec.SetVmwareSetting(vmwsetting)
   try:
      transactionIndex += 1
      networkSystem.InvokeHostTransactionCall(str(transactionIndex),
                                              defaultTimeout,
                                              "reconfigureDistributedVirtualSwitch",
                                              configSpec, None, None, None)
      if commit:
         networkSystem.CommitTransaction(str(transactionIndex))
   except Exception as e:
      print("Failed to reconfigure distributed virtual switch")
      raise
   print("Test 3: reconfigure distributed virtual switch: PASS")

   vssConfigSpec = Vim.host.VirtualSwitch.Specification(
                   #bridge = Vim.Host.VirtualSwitch.BondBridge(),
                   mtu = 1500,
                   numPorts = 256
                   )
   networkSystem.AddVirtualSwitch("rollbackVss", vssConfigSpec)
   pgpolicy = Vim.Host.NetworkPolicy()
   portgroupSpec = Vim.host.PortGroup.Specification(
                   name = "rollbackpg",
                   policy = pgpolicy,
                   vswitchName = "rollbackVss"
                   )
   networkSystem.AddPortGroup(portgroupSpec)
   portgroupSpec.SetVlanId(201)
   try:
      transactionIndex += 1
      networkSystem.InvokeHostTransactionCall(str(transactionIndex),
                                              defaultTimeout,
                                              "updatePortGroup", "rollbackpg",
                                              portgroupSpec, None, None)
      if commit:
         networkSystem.CommitTransaction(str(transactionIndex))
   except Exception as e:
      print("Failed to update virtual switch portgroup")
      networkSystem.RemovePortGroup("rollbackpg")
      networkSystem.RemoveVirtualSwitch("rollbackVss")
      raise
   print("Test 4: update virtual switch portgroup: PASS")

   nicSpec = Vim.Host.VirtualNic.Specification(ip=GenerateIPConfig("192.168.124.18"),
                                               mtu=9000,
                                               portgroup="rollbackpg",
                                               tsoEnabled=True)
   nic = ""
   try:
      transactionIndex += 1
      nic = networkSystem.InvokeHostTransactionCall(str(transactionIndex),
                                                    defaultTimeout,
                                                    "addVirtualNic", "rollbackpg",
                                                    nicSpec, None, None)
      if commit:
         networkSystem.CommitTransaction(str(transactionIndex))
         nicSpec.SetMtu(1500)
         transactionIndex += 1
         networkSystem.InvokeHostTransactionCall(str(transactionIndex),
                                                 defaultTimeout,
                                                 "updateVirtualNic",
                                                 nic, nicSpec, None, None)
         networkSystem.CommitTransaction(str(transactionIndex))
         transactionIndex += 1
         networkSystem.InvokeHostTransactionCall(str(transactionIndex),
                                                 defaultTimeout,
                                                 "removeVirtualNic",
                                                 nic, None, None, None)
         networkSystem.CommitTransaction(str(transactionIndex))
   except Exception as e:
      print("Failed to add/update virtual NIC")
      networkSystem.RemovePortGroup("rollbackpg")
      networkSystem.RemoveVirtualSwitch("rollbackVss")
      raise
   print("Test 5: add/update virtual NIC: PASS")

   vssConfigSpec.SetMtu(9000)
   try:
      transactionIndex += 1
      networkSystem.InvokeHostTransactionCall(str(transactionIndex),
                                              defaultTimeout,
                                              "updateVirtualSwitch", "rollbackVss",
                                              vssConfigSpec, None, None)
      if commit:
         networkSystem.CommitTransaction(str(transactionIndex))
   except Exception as e:
      print("Failed to update virtual switch")
      networkSystem.RemoveVirtualSwitch("rollbackVss")
      raise
   if not commit:
      time.sleep(defaultTimeout + 5) # wait all rollback operations to finish
   networkSystem.RemovePortGroup("rollbackpg")
   networkSystem.RemoveVirtualSwitch("rollbackVss")
   print("Test 6: update virtual switch: PASS")

def GenerateStackInstance(stackKey, stackName, routing):
    dnsConfig1 = Vim.Host.DnsConfig()
    stackInstance = Vim.Host.NetStackInstance(key = stackKey,
        name = stackName, dnsConfig = dnsConfig1,
        ipRouteConfig = routing,
        requestedMaxNumberOfConnections = 1000,
        congestionControlAlgorithm = "cubic")
    return stackInstance

def TestUpdateNetworkConfigMultipleStackInstance(si, uuid):

    print("MultipleTcpipStackInstanceTest start..")

    #
    # Add one stack instance into recent configuration
    #
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    origIpRouteConfig = networkSystem.GetIpRouteConfig()
    newIpRouteConfig = copy.deepcopy(origIpRouteConfig)
    newIpRouteConfig.defaultGateway = "192.168.124.18"

    changeMode = "modify"
    opAdd = "add"
    instanceKey = "unittest"
    nameAdd = "unittest00"
    stackInstanceAdd = GenerateStackInstance(instanceKey, nameAdd,
                                             newIpRouteConfig)
    netCfg = Vim.Host.NetworkConfig()
    specAdd = Vim.Host.NetworkConfig.NetStackSpec(netStackInstance=stackInstanceAdd,
                                                  operation=opAdd)

    netCfg.GetNetStackSpec().append(specAdd)
    try:
        networkSystem.UpdateNetworkConfig(netCfg, changeMode)
    except Exception as e:
        raise
    info = networkSystem.GetNetworkInfo().GetNetStackInstance()
    bAdd = False
    for instanceItem in info:
        if instanceItem.GetKey() == instanceKey:
            bAdd = True
    if bAdd != True:
        raise Exception("Test 1: Add stack instance : FAIL")
    else:
        print("Test 1: Add stack instance : PASS")

    #
    # Edit stack instance into recent configuration
    #
    opEdit = "edit"
    nameEdit = "unittest01"
    stackInstanceEdit = GenerateStackInstance(instanceKey, nameEdit,
                                              newIpRouteConfig)
    specEdit = Vim.Host.NetworkConfig.NetStackSpec(netStackInstance=stackInstanceEdit,
                                                   operation=opEdit)
    netCfgEdit = Vim.Host.NetworkConfig()
    netCfgEdit.GetNetStackSpec().append(specEdit)
    try:
        networkSystem.UpdateNetworkConfig(netCfgEdit, changeMode)
    except Exception as e:
        raise
    print("Test 2: Edit stack instance : PASS")

    #
    # Remove stack instance created.
    #
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    origIpRouteConfig = networkSystem.GetIpRouteConfig()
    newIpRouteConfig = copy.deepcopy(origIpRouteConfig)

    changeMode = "modify"
    instanceKey = "unittest"
    opRemove = "remove"
    stackInstanceRemove = GenerateStackInstance(instanceKey, nameEdit, newIpRouteConfig)
    specRemove = Vim.Host.NetworkConfig.NetStackSpec(netStackInstance=stackInstanceRemove,
                                                     operation=opRemove)
    netCfgRemove = Vim.Host.NetworkConfig()
    netCfgRemove.GetNetStackSpec().append(specRemove)
    try:
        networkSystem.UpdateNetworkConfig(netCfgRemove, changeMode)
    except Exception as e:
        raise
    print("Test 3: Remove stack instance : PASS")

    #
    # Add one vmkNic into instance created
    #
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    ipCfg = GenerateIPConfig("192.168.124.18")
    dvPort = Vim.Dvs.PortConnection(portgroupKey = "pg1",
        switchUuid = uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
        distributedVirtualPort = dvPort)
    spec.SetNetStackInstanceKey("defaultTcpipStack");
    try:
        vmknic = networkSystem.AddVirtualNic("", spec)
        networkSystem.RemoveVirtualNic(vmknic)
    except Exception as e:
        print("Test 4: Add and remove a vmknic which bounds existing stack instance: FAIL")
        raise
    print("Test 4: Add and remove a vmknic which bounds existing stack instance: PASS")

    print("MultipleTcpipStackInstanceTest end..")

    return


def TestUpdateNetworkConfigVnics():
    # Add two vmknics binding to latebinding portgroups.
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    op = "modify"
    vmknames = ["vmk10", "vmk11"]
    netCfg = Vim.Host.NetworkConfig()
    ipCfg = GenerateIPConfig("192.168.124.18")
    dvPort = Vim.Dvs.PortConnection(portgroupKey = "pg1",
                 switchUuid = options.uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    vnicCfg = Vim.Host.VirtualNic.Config(changeOperation = "add",
                  device = vmknames[0],
                  portgroup = "",
                  spec = spec)
    ipCfg = GenerateIPConfig("192.168.124.19")
    netCfg.GetVnic().append(vnicCfg)
    dvPort = Vim.Dvs.PortConnection(portgroupKey = "pg3",
                 switchUuid = options.uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    vnicCfg = Vim.Host.VirtualNic.Config(changeOperation = "add",
                  device = vmknames[1],
                  portgroup = "",
                  spec = spec)
    netCfg.GetVnic().append(vnicCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception as e:
        print("Test 1: Failed to add vmknics to dvs")
        raise
    vmknics = result.GetVnicDevice()
    if ValidateVmkNames(vmknames, vmknics):
       print("Test 1: Add vmknics to DVS: PASS")
    else:
       raise Exception("Test 1: Add vmknics to DVS: FAIL")

    # Edit two vmknics one binding to a different portgroup and the other to
    # a dvPort.
    netCfg = Vim.Host.NetworkConfig()
    dvPort = Vim.Dvs.PortConnection(portKey = "1000",
                 connectionCookie = 5,
                 switchUuid = options.uuid)
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
    except Exception as e:
        print("Test 2: Failed to edit vmknics")
    for vmknic in vmknics:
        print(vmknic)
        CleanupVmknic(networkSystem, vmknic)
    return

def GenerateProxyCfg(pnicDevice, portKey = "", portgroupKey = "",
                     cnxId = 0):
    pnicSpec = Vim.Dvs.HostMember.PnicSpec(pnicDevice = pnicDevice,
                   uplinkPortKey = portKey,
                   uplinkPortgroupKey = portgroupKey,
                   connectionCookie = cnxId)
    pnicBacking = Vim.Dvs.HostMember.PnicBacking(pnicSpec = [pnicSpec])
    spec = Vim.Host.HostProxySwitch.Specification(backing = pnicBacking)
    proxyCfg = Vim.Host.HostProxySwitch.Config(changeOperation = "edit",
                                               spec = spec,
                                               uuid = options.uuid)
    return proxyCfg
def UnlinkPnics(networkSystem):
    spec = Vim.Host.HostProxySwitch.Specification()
    proxyCfg = Vim.Host.HostProxySwitch.Config(changeOperation = "edit",
                                               spec = spec,
                                               uuid = options.uuid)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    networkSystem.UpdateNetworkConfig(netCfg, "modify")

def TestUpdateNetworkConfigPnics():

    print("Test updateNetworkConfig for a single uplink")
    vmnic = pnicList[0]
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    op = "modify"
    UnlinkPnics(networkSystem)

    # Link the pnic to a predefined uplink port connection id pair.

    proxyCfg = GenerateProxyCfg(vmnic, "1", "", 1)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception as e:
        print("Test 1: Failed to add pnics to dvs: FAIL")
        raise
    print("Test 1: Link the pnic to an uplink port connection id pair: Pass")
    UnlinkPnics(networkSystem)

    # autopick a free uplink port to connect the pnic to.
    proxyCfg = GenerateProxyCfg(vmnic)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception as e:
        print("Test 2: Failed to add pnics to dvs")
        raise
    print("Test 2: Autopick a free uplink port to connect the pnic to: Pass")
    UnlinkPnics(networkSystem)

    # pick a free uplink port from a particular portgroup to link the pnic to.

    proxyCfg = GenerateProxyCfg(vmnic, "", "pg5")
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception as e:
        print("Test 3: Failed to add pnics to dvs")
        raise
    print("Test 3: pick a free uplink port from a particular portgroup: Pass")
    UnlinkPnics(networkSystem)
    # Link the pnic to connect to a specified dvPort.
    proxyCfg = GenerateProxyCfg(vmnic, "1", "")
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception as e:
        print("Test 4: Failed to link the pnic to a specified dvPort")
        raise
    print("Test 4: Link the pnic to a specified dvPort: Pass")
    UnlinkPnics(networkSystem)

    # Try linking the uplink to a portgroup that doesn't have an uplink port.
    proxyCfg = GenerateProxyCfg(vmnic, "", "pg2")
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception as e:
        print("Test 5: Caught expected exception suitable pnic unavailable: PASS")
    print("Testing updateNetworkConfig for a single uplink complete")
    return

def TestUpdateNetworkConfigPnicsExtended():
    # Test to verify if nic ordering is working correctly.
    # Generate three pnicSpecs.
    # 1 - No portgroup or port specified.
    # 2 - Portgroup specified.
    # 3 - Port specified.
    print("Test updateNetwork config for multiple uplinks")
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    op = "modify"
    UnlinkPnics(networkSystem)
    pnicSpec1 = Vim.Dvs.HostMember.PnicSpec(pnicDevice = pnicList[0])
    pnicSpec2 = Vim.Dvs.HostMember.PnicSpec(pnicDevice = pnicList[1],
                    uplinkPortgroupKey = "pg5")
    pnicSpec3 = Vim.Dvs.HostMember.PnicSpec(pnicDevice = pnicList[2],
                    uplinkPortKey = "3")
    pnicBacking = Vim.Dvs.HostMember.PnicBacking(pnicSpec=[pnicSpec1,
                                                           pnicSpec2,
                                                           pnicSpec3])
    spec = Vim.Host.HostProxySwitch.Specification(backing = pnicBacking)
    proxyCfg = Vim.Host.HostProxySwitch.Config(changeOperation = "edit",
                                               spec = spec,
                                               uuid = options.uuid)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception as e:
        print("Test 1: Caught exception suitable pnic unavailable: FAIL")
        raise
    print("Test 1: Add 3 nics: PASS")

    UnlinkPnics(networkSystem)
    pnicBacking = Vim.Dvs.HostMember.PnicBacking(pnicSpec=[pnicSpec1,
                                                           pnicSpec2,
                                                           pnicSpec3])
    proxyCfg.GetSpec().SetBacking(pnicBacking)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxyCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception as e:
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

def TestDVSLimits(dvsName):
    # Create the dvs.
    prodSpec = Vim.Dvs.ProductSpec(vendor="VMware",
                                   version = "5.1.0")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    createSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSCreateSpec(
        uuid = options.uuid,
        name = dvsName,
        backing = Vim.Dvs.HostMember.PnicBacking(),
        productSpec = prodSpec,
        maxProxySwitchPorts = 64,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True
        )

    dvsManager.CreateDistributedVirtualSwitch(createSpec)
    portgroupList = []
    numIter = 500
    print("testing early binding portgroups limits")
    for i in range(numIter):
       name = "pg" + str(i)
       pg = GeneratePortgroupCfg(name, "add", "earlyBinding")
       portgroupList.append(pg)
    bigClock = StopWatch()
    dvsManager.UpdateDVPortgroups(options.uuid, portgroupList)
    bigClock.finish("creating " + str(numIter) + " static pgs")
    cleanup("")
    print("testing ephemeral binding portgroups limits")
    dvsManager.CreateDistributedVirtualSwitch(createSpec)
    totalClock = StopWatch()
    for k in range(20):
        portgroupList = []
        j = 0
        for j in range(numIter):
            name = "pg" + str(k) + "_" + str(j)
            pg = GeneratePortgroupCfg(name, "add", "ephemeral")
            portgroupList.append(pg)
        bigClock = StopWatch()
        dvsManager.UpdateDVPortgroups(options.uuid, portgroupList)
        bigClock.finish("creating " + str(numIter) + " ephemeral pgs")
    totalClock.finish("Overall time")
    bigClock = StopWatch()
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    bigClock.finish("Get config time")
    cleanup("")

def GenerateNetRMSpec(poolKey, shareLevel, limit, priority, shareVal = 0):
    allocInfo = Vim.Dvs.NetworkResourcePool.AllocationInfo()
    shares = Vim.SharesInfo(level = shareLevel,
                            shares = shareVal)
    allocInfo.SetLimit(limit)
    allocInfo.SetShares(shares)
    allocInfo.SetPriorityTag(priority)
    spec = Vim.Dvs.NetworkResourcePool.ConfigSpec()
    spec.SetKey(poolKey)
    spec.SetAllocationInfo(allocInfo)
    return spec

def ValidateVmkNames(inNames, outNames):
    '''
    Verify that the vmknic names are the same for input and output
    '''
    if (len(inNames) != len(outNames)):
       return False
    for index in range(len(inNames)):
       if inNames[index] != outNames[index]:
          return False
    return True

def ValidateShareInfo(inShares, outShares):
    '''
    Verify that the shares for the netrm settings are the same for the in
    and out settings.
    '''
    return (inShares.GetShares() == outShares.GetShares() and \
            inShares.GetLevel() == outShares.GetLevel())

def ValidateAllocInfo(inAlloc, outAlloc):
    '''
    Verify that the allocation info for the net rm settings are the same for
    inAlloc and outAlloc
    '''
    return ((inAlloc.GetLimit() == outAlloc.GetLimit()) and
       (inAlloc.GetPriorityTag() == outAlloc.GetPriorityTag()) and \
             ValidateShareInfo(inAlloc.GetShares(), outAlloc.GetShares()))

def ValidateNetRmSpec(inSpec, outSpec, portKey):
    '''
    Verify that the inspec is the same as the outspec
    '''
    outRmSpec = []
    for perUplinkSpec in outSpec:
       if (perUplinkSpec.GetUplinkPortKey() == portKey):
           outRmSpec = perUplinkSpec.GetConfigSpec()

    if (len(inSpec) != len(outRmSpec)):
        print("%s, %s" % (inSpec, outRmSpec))
        return False
    inSpec.sort(key = operator.attrgetter('key'))
    outRmSpec.sort(key = operator.attrgetter('key'))
    for i in range(len(inSpec)):
       if (inSpec[i].GetKey() != outRmSpec[i].GetKey()):
           print("key mismatch")
           print('INspec %s' % inSpec[i])
           print('Outspec %s' % outRmSpec[i])
           return False
       if (ValidateAllocInfo(inSpec[i].GetAllocationInfo(), \
           outRmSpec[i].GetAllocationInfo()) == False):
           print("alloc mismatch")
           print('%s, %s' % (inSpec[i], outRmSpec[i]))
           return False
    return True

def ValidatePoolKeys(inKeys, outKeys):
    '''
    Verify that the pool keys match for in and out
    '''
    if (len(inKeys) != len(outKeys)):
        return False
    for i in range(len(inKeys)):
       if (inKeys[i] != outKeys[i]):
           print('%s, %s' % (inKeys[i], outKeys[i]))
           return False
    return True

def TestNetRmSettings():
    '''
    Sets the configuration settings for netrm and verifies that the values
    read back match the ones that were set.
    '''
    print("Testing set network rm")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    poolKeys = ["management", "nfs", "virtualMachine"]
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        #networkResourcePoolKeys = poolKeys,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True
        )
    for i in poolKeys:
        configSpec.GetNetworkResourcePoolKeys().append(i)
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    if (ValidatePoolKeys(configSpec.GetNetworkResourcePoolKeys(),
        returnedConfigSpec.GetNetworkResourcePoolKeys()) == False):
        print("Test 1: Failed to update the list of pool keys vDS")
        raise Exception("Net rm tests failed")
    print("Test 1: Update list of pool keys for vDS: PASS")

    # Test the setting of per uplink net rm settings
    uplinkResourceSpecs = []
    uplinkResourceSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.UplinkPortResourceSpec()
    uplinkResourceSpec.SetUplinkPortKey("1")
    specs = []
    spec = GenerateNetRMSpec("management", Vim.SharesInfo.Level.custom, 100, 2, 5)
    specs.append(spec)
    spec = GenerateNetRMSpec("nfs", Vim.SharesInfo.Level.custom, 20, 2, 6)
    specs.append(spec)
    spec = GenerateNetRMSpec("virtualMachine", Vim.SharesInfo.Level.custom, 32, 2, 7)
    specs.append(spec)
    uplinkResourceSpec.SetConfigSpec(specs)
    uplinkResourceSpecs.append(uplinkResourceSpec)
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        uplinkPortResourceSpec = uplinkResourceSpecs,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True)
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    if (ValidateNetRmSpec(specs, \
                          returnedConfigSpec.GetUplinkPortResourceSpec(), "1")):
        print("Test 2: Update per uplink share settings: PASS")
    else:
        print("Test 2: Failed to validate uplink share settings: FAIL")
        raise Exception("Net rm tests failed")
    portKey = "3"
    portData = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
               portKey = portKey)
    rpKey = "nfs"
    resPoolKey = Vim.StringPolicy(inherited = False,
                                  value = rpKey)
    portSetting = Vim.Dvs.DistributedVirtualPort.Setting(
        networkResourcePoolKey = resPoolKey)
    portData.SetSetting(portSetting)
    dvsManager.UpdatePorts(options.uuid, [portData])
    returnedPort = dvsManager.FetchPortState(options.uuid, [portKey])
    if (len(returnedPort) != 1):
        raise Exception("Invalid portdata length returned")
    returnedSetting = returnedPort[0].GetSetting()
    if (returnedSetting.GetNetworkResourcePoolKey().GetValue() != rpKey):
        raise Exception("Invalid rpKey recvd")
    print("Test 3: Verify the pool to port association: PASS")

def TestTrafficFilter():
    '''
    Sets a ruleset for trafficfilter and verifies that the values
    read back match the ones that were set.
    '''
    print("Testing set traffic filter ruleset")

    # Need a running port to set ruleset on, lets use vmknic

    # Add vmknic to a latebinding portgroup with binding on host.
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    ipCfg = GenerateIPConfig("192.168.124.17")
    dvPort = Vim.Dvs.PortConnection(portKey = "1000",
                 connectionCookie = 5,
                 switchUuid = options.uuid)
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    try:
        vmknic = networkSystem.AddVirtualNic("", spec)
    except Exception as e:
        print("Failed to add a vmknic for trafficfilter")
        raise

    print("Test 1: Add a vmknic for trafficfilter: PASS")


    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager

    # Test the setting of traffic filter
    portKey = "1000"
    portData = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
               portKey = portKey)
    portSetting = Vim.Dvs.DistributedVirtualPort.Setting()


    policy = Vim.Dvs.DistributedVirtualPort.FilterPolicy()
    policy.SetInherited(False)

    configs = [Vim.Dvs.DistributedVirtualPort.TrafficFilterConfig()]

    configs[0].SetAgentName("dvfilter-generic-vmware")
    configs[0].SetOnFailure("failClosed")

    print("Making Ruleset")
    ruleset = Vim.Dvs.TrafficRuleset()

    ruleset.SetEnabled(True)

    print("Making Rule")
    rules = [Vim.Dvs.TrafficRule()]

    print("Making Rule")
    rules.append(Vim.Dvs.TrafficRule())

    print("Making MacQualifier")
    qualifier = Vim.Dvs.TrafficRule.MacQualifier()
    sourceAddress = Vim.SingleMac()
    sourceAddress.SetAddress("98:76:54:32:10:91")
    qualifier.SetSourceAddress(sourceAddress)

    maskQualifier = Vim.Dvs.TrafficRule.MacQualifier()
    sourceRange = Vim.MacRange()
    sourceRange.SetAddress("01:23:45:67:89:10")
    sourceRange.SetMask("00:FF:00:FF:F8:01")
    maskQualifier.SetSourceAddress(sourceRange)

    print("Setting Qualifiers")
    rules[0].SetQualifier([qualifier])
    rules[0].SetSequence(1)

    rules[1].SetQualifier([maskQualifier])
    rules[1].SetSequence(0)

    print("Making/Setting Action")
    rules[0].SetAction(Vim.Dvs.TrafficRule.DropAction())


    print("Setting Rules")
    ruleset.SetRules(rules)
    print("Setting Ruleset")
    configs[0].SetTrafficRuleset(ruleset)
    print("Setting Config")
    policy.SetFilterConfig(configs)

    portSetting.SetFilterPolicy(policy)

    portData.SetSetting(portSetting)
    dvsManager.UpdatePorts(options.uuid, [portData])
    print("Successfully did UpdatePorts")
    returnedPort = dvsManager.FetchPortState(options.uuid, [portKey])
    if (len(returnedPort) != 1):
        raise Exception("Invalid portdata length returned")
    returnedSetting = returnedPort[0].GetSetting()

    # XXX: For now just print the setting, later do more validation
    print(returnedSetting)
    returnedRuleset = returnedSetting.filterPolicy.filterConfig[0].trafficRuleset
    if (len(returnedRuleset.rules) != 2):
        raise Exception("Wrong number of returned rules, expecting 2 got " +\
                        str(len(returnedRuleset.rules)))

    if (not (returnedRuleset.rules[0].qualifier[0].sourceAddress.address ==
             "01:23:45:67:89:10") and
             (returnedRuleset.rules[0].qualifier[0].sourceAddress.mask ==
             "00:ff:00:ff:f8:01") and
             (returnedRuleset.rules[1].qualifier[0].sourceAddress.address ==
             "98:76:54:32:10:91")):
       raise Exception("Programmed rules don't match expected results")

    if options.nocleanup:
       print("Leaving filter installed since nocleanup was specified")
       return

    print("Removing filter")
    policy.SetFilterConfig([])
    dvsManager.UpdatePorts(options.uuid, [portData])
    returnedPort = dvsManager.FetchPortState(options.uuid, [portKey])
    if (len(returnedPort) != 1):
        raise Exception("Invalid portdata length returned")

    print("Removing vmknic")
    CleanupVmknic(networkSystem, vmknic)

    print("Test 3: Verify the traffic filter rules are set on port: PASS")
    return

def TestDVSIP():
    '''
    Sets the configuration settings for DVS IP and verifies that the values
    read back match the ones that were set.
    '''
    print("Testing DVS IP")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True,
        switchIpAddress = "10.20.1.1"
        )
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    if (configSpec.GetSwitchIpAddress() == returnedConfigSpec.GetSwitchIpAddress()):
        print("Test 1: Set DVS IP Address: PASS")
    else:
        print("Test 1: Failed to set DVS IP Address")
        raise Exception("DVS IP tests failed")
    return

def TestNetRmEnable():
    print("Testing enable net rm")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    origSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    if origSpec.GetEnableNetworkResourceManagement() == True:
        raise Exception("Test failed: Netrm is enabled by default on the vDS")
    print("Test 1: Validate default netrm policy is False: PASS")

    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True,
        enableNetworkResourceManagement = True
        )
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec =  dvsManager.RetrieveDvsConfigSpec(options.uuid)
    if returnedConfigSpec.GetEnableNetworkResourceManagement() == False:
        raise Exception("Failed to enable netrm for vDS")
    print("Test 2: Enable netrm on vDS: PASS")
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True,
        enableNetworkResourceManagement = False
        )
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec =  dvsManager.RetrieveDvsConfigSpec(options.uuid)
    if returnedConfigSpec.GetEnableNetworkResourceManagement() == True:
        raise Exception("Failed to disable netrm by for vDS")
    print("Test 3: Disable netrm on vDS: PASS")

def TestVnicUpdate():
    print("Testing vnic update of backing and ipCfg in the same spec")
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    op = "modify"
    # create a dummy vnic
    netCfg = Vim.Host.NetworkConfig()
    dvPort = Vim.Dvs.PortConnection(portKey = "1000",
                 connectionCookie = 5,
                 switchUuid = options.uuid)
    ipCfg = GenerateIPConfig("192.168.10.2")
    spec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
               distributedVirtualPort = dvPort)
    vnicCfg = Vim.Host.VirtualNic.Config(changeOperation = "add",
                  portgroup = "",
                  spec = spec)
    netCfg.GetVnic().append(vnicCfg)
    try:
        result = networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception as e:
        print("Failed to add dummy vmknic to dvs")
        raise
    vmknic = result.GetVnicDevice()
    # Invoke update network config with the same backing.
    vnicCfg.SetChangeOperation("edit")
    vnicCfg.SetDevice(vmknic[0])
    newIp = "192.168.10.3"
    ipCfg = GenerateIPConfig(newIp)
    vnicCfg.GetSpec().SetIp(ipCfg)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetVnic().append(vnicCfg)
    try:
        networkSystem.UpdateNetworkConfig(netCfg, op)
    except Exception as e:
        print("Test 1: Test to check updateNetworkConfig vnic update failed")
        raise
    # Validate that the ip actually changed.
    newVnics = networkSystem.GetNetworkInfo().GetVnic()
    for newVnic in newVnics:
        if newVnic.GetDevice() == vmknic[0]:
            if newVnic.GetSpec().GetIp().GetIpAddress() != newIp:
                raise Exception("Test 1: Ip address not updated failed")
    CleanupVmknic(networkSystem, vmknic[0])
    print("Test1: Test to check updateNetworkConfig vnic update passed")

def CompareOpaqueBlobs(origBlob, newBlob):
    '''
    Compares the list of opaque key value pairs as part of the vendor specific
    config.
    '''
    if (len(origBlob) != len(newBlob)):
    	raise Exception('propList does not match: %s, %s'
         % (str(len(origBlob)), str(len(newBlob))))
    for i in range(len(origBlob)):
        if ((origBlob[i].key != newBlob[i].key) or \
           (origBlob[i].opaqueData != newBlob[i].opaqueData)):
            print("mismatch in opaque blob")
            print("orig: %s" % origBlob)
            print("new: %s" % newBlob)
            raise Exception("Blob mismatch")
    return True

def CompareKeyValues(origBlob, newBlob):
    '''
    Compares the list of key value pairs as part of port extra config.
    '''
    if (len(origBlob) != len(newBlob)):
        raise Exception("propList does not match: %s, %s "
            % (str(len(origBlob)), str(len(newBlob))))
    for i in range(len(origBlob)):
        if ((origBlob[i].key != newBlob[i].key) or \
           (origBlob[i].value != newBlob[i].value)):
            print("mismatch in keyvalue blob")
            print("orig: %s" % origBlob)
            print("new: %s" % newBlob)
            raise Exception("Blob mismatch")
    return True

def TestOpaqueProperties():
    '''
    Test opaque data set and get for dvs level configuration.
    '''
    print("Testing set and get opaque properties")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True
        )
    existedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    existedBlob = existedConfigSpec.GetVendorSpecificDvsConfig()
    configSpec.SetVendorSpecificDvsConfig(existedBlob)

    blob = Vim.Dvs.KeyedOpaqueBlob(key = "com.vmware.test.dvsUnitTest",
                                   opaqueData = "dvs level opaque data")
    configSpec.GetVendorSpecificDvsConfig().append(blob)

    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    returnedBlob = returnedConfigSpec.GetVendorSpecificDvsConfig()
    CompareOpaqueBlobs(configSpec.GetVendorSpecificDvsConfig(),
                       returnedConfigSpec.GetVendorSpecificDvsConfig())
    print("Test1: Verify switch wide global settings: Pass")

    blobHost = Vim.Dvs.KeyedOpaqueBlob(key = "com.vmware.test.dvsUnitTestHost",
                   opaqueData = "dvs host member level opaque data")
    configSpec.GetVendorSpecificHostMemberConfig().append(blobHost)
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    returnedBlob = returnedConfigSpec.GetVendorSpecificDvsConfig()
    CompareOpaqueBlobs(configSpec.GetVendorSpecificDvsConfig(),
                       returnedConfigSpec.GetVendorSpecificDvsConfig())
    print("Test2: Verify host proxy switch wide settings: Pass")

    portKey = "3"
    blobSetting = Vim.Dvs.KeyedOpaqueBlob(opaqueData ="dvPort level opaque data: setting",
                                          key="com.vmware.test.dvsPortSettingTest")
    portData = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
               portKey = portKey)
    vendorSpecificConfig = Vim.Dvs.DistributedVirtualPort.VendorSpecificConfig(
                               inherited = False)
    vendorSpecificConfig.SetKeyValue([blobSetting])
    portSetting = Vim.Dvs.DistributedVirtualPort.Setting(
                      vendorSpecificConfig = vendorSpecificConfig)
    portData.SetSetting(portSetting)

    blobState = Vim.Dvs.KeyedOpaqueBlob(key="com.vmware.test.dvsPortStateTest",
                                        opaqueData="dvPort level opaque data: state")
    portStats = Vim.Dvs.PortStatistics()
    portState = Vim.Dvs.DistributedVirtualPort.State(stats = portStats)
    portState.SetVendorSpecificState([blobState])
    portData.SetState(portState)
    dvsManager.UpdatePorts(options.uuid, [portData])
    returnedPort = dvsManager.FetchPortState(options.uuid, [portKey])
    if (len(returnedPort) != 1):
        raise Exception("Invalid portdata length returned")
    returnedState = returnedPort[0].GetState()
    CompareOpaqueBlobs(portState.GetVendorSpecificState(),
                       returnedState.GetVendorSpecificState())
    print("Test3: Verify switch port vendor specific state: Pass")

    returnedSetting = returnedPort[0].GetSetting()
    CompareOpaqueBlobs(portSetting.GetVendorSpecificConfig().GetKeyValue(),
                       returnedSetting.GetVendorSpecificConfig().GetKeyValue())
    print("Test4: Verify switch port vendor specific setting: Pass")

    portKey = "3"
    portData = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
               portKey = portKey)
    externalId = Vim.KeyValue(key="com.vmware.port.extraConfig.vnic.external.id",
                              value="c61-m22-s18-p3-w1234")
    portData.SetExtraConfig([externalId])
    dvsManager.UpdatePorts(options.uuid, [portData])
    returnedPort = dvsManager.FetchPortState(options.uuid, [portKey])
    if (len(returnedPort) != 1):
       raise Exception("Invalid portdata length returned")
    returnedExtraConfig = returnedPort[0].GetExtraConfig()
    CompareKeyValues([externalId], returnedExtraConfig)
    print("Test5: Verify switch port extra config: Pass")
    print("Verified opaque data plumbing")


def CompareBinaryData(origData, newData):
   return (origData == newData)

def CompareOpaqueData(origData, newData):
    '''
    Compares the list of opaque key value pairs as part of the opaque channel
    '''
    if (len(origData) != len(newData)):
        print('%s, %s' % (origData, newData))
        raise Exception("Error in original data")
    for i in range(len(origData)):
        if ((origData[i].key != newData[i].key) or \
            (CompareBinaryData(origData[i].opaqueData, newData[i].opaqueData) \
             == False)):
            print('%s, %s' % (origData, newData))
            raise Exception("Error in OpaqueData")
    return True


def TestOpaqueChannel():
    '''
    Test opaque channel set and get for host and port level configuration.
    '''
    print("Testing set and get opaque data")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True
        )
    dvsblob = Vim.Dvs.OpaqueData(key = "com.vmware.test.dvsOpaqueChannelTest",
                                 opaqueData = \
                                 VmomiSupport.binary(python2to3Encode("010")))
    dvslist = Vim.Dvs.OpaqueData.OpaqueDataList()
    dvslist.SetOpaqueData([dvsblob])
    configSpec.SetDvsOpaqueDataList(dvslist)
    blob = Vim.Dvs.OpaqueData(key = "com.vmware.test.hostOpaqueChannelTest",
                              opaqueData = \
                              VmomiSupport.binary(python2to3Encode("001")))
    list = Vim.Dvs.OpaqueData.OpaqueDataList()
    list.SetOpaqueData([blob])
    configSpec.SetHostOpaqueDataList(list)
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    returnedDvsBlob = returnedConfigSpec.GetDvsOpaqueDataList()
    CompareOpaqueData(configSpec.GetDvsOpaqueDataList().GetOpaqueData(),
                      returnedDvsBlob.GetOpaqueData())
    returnedBlob = returnedConfigSpec.GetHostOpaqueDataList()
    CompareOpaqueData(configSpec.GetHostOpaqueDataList().GetOpaqueData(),
                      returnedBlob.GetOpaqueData())
    print("Test 1: Testing dvs & host level opaque channel: Pass")
    portBlob = Vim.Dvs.OpaqueData(key = "com.vmware.test.portOpaqueChannelTest",
                                  opaqueData = \
                                  VmomiSupport.binary(python2to3Encode("100")))
    portKey = "3"
    portData = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
               portKey = portKey)
    list.SetOpaqueData([portBlob])
    portData.SetOpaqueDataList(list)
    dvsManager.UpdatePorts(options.uuid, [portData])
    returnedPort = dvsManager.FetchPortState(options.uuid, [portKey])
    if (len(returnedPort) != 1):
        raise Exception("Invalid portData length")
    returnedBlob = returnedPort[0].GetOpaqueDataList()
    CompareOpaqueData(portData.GetOpaqueDataList().GetOpaqueData(),
                      returnedBlob.GetOpaqueData())
    print("Test 2: Testing port level opaque channel: Pass")

    cfgSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVPortgroupConfigSpec()
    cfgSpec.SetKey("pg5")
    cfgSpec.SetOperation("edit")
    cfgSpec.SetOpaqueDataList(list)
    dvsManager.UpdateDVPortgroups(options.uuid, [cfgSpec])
    pgList = dvsManager.RetrieveDVPortgroupConfigSpec(options.uuid, [cfgSpec.key])
    if (len(pgList) != 1):
        raise Exception("Invalid portgroup list")
    for pg in pgList:
        if pg.key == cfgSpec.key:
            CompareOpaqueData(cfgSpec.GetOpaqueDataList().GetOpaqueData(),
                              pg.GetOpaqueDataList().GetOpaqueData())
    print("Test 3: Testing epehemeral portgroup opaque channel: Pass")

def GetPnics(nics):
    if nics == None:
        return []
    nics = nics.split(',')
    return nics

def TestPortgroupPersist():
    '''
    Test adds an ephemeral portgroup to a vDS.
    NetworkRefresh is called and we verify that the pg still
    exists
    '''

    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    pgName = "persistPg"
    pg = GeneratePortgroupCfg(pgName, "add", "ephemeral")
    dvsManager.UpdateDVPortgroups(options.uuid, [pg])
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    networkSystem.Refresh()
    time.sleep(2)
    ValidateEphemeralPgState(pgName)
    print("Test 1: Test to validate pg persistence passed")

def CloseCharDevice(devFd):
    try:
        os.close(devFd)
    except OSError as err:
        raise Exception("unable to close char dev")

def addOptTLV(key, value, tlvLen, tlvNum, tlvBuf):
    MAX_LLDP_OPT_TLV_LEN = 1500
    keyLen = len(key) + 1
    valLen = len(value) + 1
    # the length should not exceed the max length
    if (tlvLen + 8 + keyLen + valLen >= MAX_LLDP_OPT_TLV_LEN):
        return
    tlvBuf += struct.pack('H', keyLen)
    tlvBuf += struct.pack(('%i' %keyLen) + 's', python2to3Encode(key))
    tlvBuf += struct.pack('H', valLen)
    tlvBuf += struct.pack(('%i' %valLen) + 's', python2to3Encode(value))
    tlvLen += 8 + keyLen + valLen
    tlvNum += 1
    return tlvLen,tlvNum,tlvBuf

def TestLLDP():
    '''
    Sets the parsed LLDP packet info in /vmfs/devices/char/vmkdriver/cdp and get the info from networkHint
    '''
    print("Testing LLDP")
    # Get idle Pnics
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    networkInfo = networkSystem.GetNetworkInfo()
    pnics = networkInfo.GetPnic()
    usedPnics = []
    linkResolver = LinkResolver(networkInfo)
    for vSwitch in networkInfo.vswitch:
        for vSwitchUsedPnic in linkResolver.ResolveLinks(vSwitch.pnic):
            usedPnics.append(vSwitchUsedPnic)
    for proxySwitch in networkInfo.proxySwitch:
        for proxySwitchUsedPnic in linkResolver.ResolveLinks(proxySwitch.pnic):
            usedPnics.append(proxySwitchUsedPnic)
    idlePnics = []
    for pnic in pnics:
        if (not (pnic in usedPnics)):
            idlePnics.append(pnic)
    if (len(idlePnics) > 0):
        testPnic = idlePnics[0]
    else:
        raise Exception("LLDP Test can not be done, need an extra pnic!")
    proxySwitchCfg = GenerateProxyCfg(testPnic.device, "2", "pg5")
    netCfg = Vim.Host.NetworkConfig()
    netCfg.GetProxySwitch().append(proxySwitchCfg)
    op = "modify"
    # Add an idle Pnic to DVS
    networkSystem.UpdateNetworkConfig(netCfg, op)
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True,
        )
    ldpConfig = Vim.Host.LinkDiscoveryProtocolConfig(
        protocol = Vim.Host.LinkDiscoveryProtocolConfig.ProtocolType.lldp,
        operation = Vim.Host.LinkDiscoveryProtocolConfig.OperationType.listen
        )
    vmwsetting = Vim.Dvs.HostDistributedVirtualSwitchManager.VmwareDVSSettingSpec()
    vmwsetting.SetLinkDiscoveryProtocolConfig(ldpConfig)
    configSpec.SetVmwareSetting(vmwsetting)
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    # Set the DVS to LLDP listen mode
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    pnic = testPnic.device

    # constants
    VMK_DEVICE_NAME_MAX_LENGTH    = '32'
    LLDPCONFIG_MAX_LEN            = '256'
    MAX_LLDP_OPT_TLV_LEN          = '1500'
    CDP_MODE_LLDP                 = 1
    CDP_STATUS_LISTEN             = 1
    CDP_IOCCMD_SETSTATE           = 2
    uplinkName        = pnic
    cdpFile           = '/vmfs/devices/char/vmkdriver/cdp'
    # optional TLVs
    OPTTLV_PortDesc               = 'Port Description'
    OPTTLV_SysName                = 'System Name'
    OPTTLV_SysDesc                = 'System Description'
    OPTTLV_SysCaps                = 'Enabled Capabilities'
    OPTTLV_ManageAddr             = 'Management Address'
    OPTTLV_802_1_VlanID           = 'Vlan ID'
    OPTTLV_802_3_MTU              = 'MTU'
    # values for LLDP state
    timeout           = 60 #kernel won't process this value, so we don't have to validate this value
    samples           = 100
    chassisID         = 'VMware-faked-platform'
    portID            = 'port1'
    ttl               = 180 #the value will decrease every second, so we don't have to validate this value
    tlvNum            = 0
    tlvLen            = 0
    tlvBuf            = python2to3Encode('')
    '''
    build the buffer. It's a Cdp_IOCData structure,
    defined in cdp.h. Fields are filled one by one.
    '''
    # Cdp_IOCData.name
    buf =  struct.pack(VMK_DEVICE_NAME_MAX_LENGTH + 's',
                       python2to3Encode(uplinkName))
    # Cdp_IOCData.dpConfig.mode
    # Though it is defined as a uint8, it occupies 4 bytes
    # because of alignment
    buf += struct.pack('I', CDP_MODE_LLDP)
    # Cdp_IOCData.dpConfig.status
    # enum also occupies 4 bytes
    buf += struct.pack('I', CDP_STATUS_LISTEN)
    # Cdp_IOCData.dpConfig.timeout
    # Actually timeout is not passed to hostd, so it could
    # be arbitrary value
    buf += struct.pack('I', timeout) #lldpTimeout
    buf += struct.pack('I', timeout) #cdpTimeout
    # Cdp_IOCData.dpConfig.samples
    # it could be arbitrary value
    buf += struct.pack('I', samples)
    # Cdp_IOCData.dpConfig.config.lldp.chassisID
    buf += struct.pack(LLDPCONFIG_MAX_LEN + 's', python2to3Encode(chassisID))
    # Cdp_IOCData.dpConfig.config.lldp.portID
    buf += struct.pack(LLDPCONFIG_MAX_LEN + 's', python2to3Encode(portID))
    # Cdp_IOCData.dpConfig.config.lldp.timeToLive
    buf += struct.pack('I', ttl)

    # add optional TLVs
    portDesc = 'Test Port'
    sysName = 'Fake Test Platform'
    sysDesc = 'This is for testing'
    sysCaps = '2'
    manageAddr = '10.0.0.1'
    vlanID = '3000'
    mtu = '1500'
    tlvLen, tlvNum, tlvBuf = addOptTLV(OPTTLV_PortDesc, portDesc, tlvLen, tlvNum, tlvBuf)
    tlvLen, tlvNum, tlvBuf = addOptTLV(OPTTLV_SysName, sysName, tlvLen, tlvNum, tlvBuf)
    tlvLen, tlvNum, tlvBuf = addOptTLV(OPTTLV_SysDesc, sysDesc, tlvLen, tlvNum, tlvBuf)
    tlvLen, tlvNum, tlvBuf = addOptTLV(OPTTLV_SysCaps, sysCaps, tlvLen, tlvNum, tlvBuf) # bridge
    tlvLen, tlvNum, tlvBuf = addOptTLV(OPTTLV_ManageAddr, manageAddr, tlvLen, tlvNum, tlvBuf)
    tlvLen, tlvNum, tlvBuf = addOptTLV(OPTTLV_802_1_VlanID, vlanID, tlvLen, tlvNum, tlvBuf)
    tlvLen, tlvNum, tlvBuf = addOptTLV(OPTTLV_802_3_MTU, mtu, tlvLen, tlvNum, tlvBuf)
    # Cdp_IOCData.dpConfig.config.lldp.optTLVNum
    buf += struct.pack('I', tlvNum)
    # Cdp_IOCData.dpConfig.config.lldp.optTLVLen
    buf += struct.pack('I', tlvLen)
    # Cdp_IOCData.dpConfig.config.lldp.optTLVBuf
    buf += struct.pack(MAX_LLDP_OPT_TLV_LEN + 's', tlvBuf)
    # Cdp_IOCData.pktLen
    # This field should be 0
    buf += struct.pack('i', 0)

    try:
        devFd = os.open(cdpFile, os.O_WRONLY)
    except OSError as err:
        raise Exception("unable to open cdp char dev")
    try:
        fcntl.ioctl(devFd, CDP_IOCCMD_SETSTATE, array.array('B', buf))
    except IOError as err:
        CloseCharDevice(devFd)
        raise Exception("CDP packet writing error")
    CloseCharDevice(devFd)
    # Build a dictionary to store LLDPInfo
    testLLDPInfo = {}
    testLLDPInfo['chassisId'] = chassisID
    testLLDPInfo['portId'] = portID
    testLLDPInfo['Samples'] = samples
    testLLDPInfo[OPTTLV_PortDesc] = portDesc
    testLLDPInfo[OPTTLV_SysName] = sysName
    testLLDPInfo[OPTTLV_SysDesc] = sysDesc
    testLLDPInfo[OPTTLV_ManageAddr] = manageAddr
    testLLDPInfo[OPTTLV_802_1_VlanID] = vlanID
    testLLDPInfo[OPTTLV_802_3_MTU] = mtu
    testDeviceCapability = Vim.Host.PhysicalNic.CdpDeviceCapability(
        router = False,
        transparentBridge = True,
        sourceRouteBridge = False,
        networkSwitch = False,
        host = False,
        igmpEnabled = False,
        repeater = False
        )
    testLLDPInfo[OPTTLV_SysCaps] = testDeviceCapability
    # Get LLDP packet info
    nHints = networkSystem.QueryNetworkHint([pnic])
    lldpInfo = None
    for nHint in nHints:
        if (nHint.device == pnic):
            lldpInfo = nHint.lldpInfo
            break
    if (lldpInfo is not None and ValidateLLDPInfo(lldpInfo, testLLDPInfo)):
        print("Test 1: Validate LLDP Info: PASS")
    else:
        print("Test 1: Failed to validate LLDP Info")
        raise Exception("LLDP tests failed")
    return

def ValidateLLDPInfo(lldpInfo, testLLDPInfo):
    if (lldpInfo.chassisId != testLLDPInfo['chassisId'] or \
        lldpInfo.portId != testLLDPInfo['portId']):
        return False
    for keyAnyValue in lldpInfo.parameter:
        if (keyAnyValue.key == 'TimeOut'):
            continue
        if (keyAnyValue.key != 'Enabled Capabilities'):
            if (keyAnyValue.value != testLLDPInfo[keyAnyValue.key]):
                print(keyAnyValue.key)
                return False
        else:
            getCapability = keyAnyValue.value
            setCapability = testLLDPInfo[keyAnyValue.key]
            if (getCapability.router != setCapability.router or
                getCapability.transparentBridge != setCapability.transparentBridge or
                    getCapability.sourceRouteBridge != setCapability.sourceRouteBridge or
                getCapability.networkSwitch != setCapability.networkSwitch or
                getCapability.host != setCapability.host or
                getCapability.igmpEnabled != setCapability.igmpEnabled or
                getCapability.repeater != setCapability.repeater):
                return False
    return True

def TestHealthCheck():
    '''
    Sets the commands for HealthCheck and verifies that the values read
    back match the ones that were set
    '''
    print("Testing HealthCheck")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    vlanMtuCheckCmd = Vim.Dvs.VmwareDistributedVirtualSwitch.VlanMtuHealthCheckConfig(
        enable = True,
        interval = 30,
        )
    teamingCheckCmd = Vim.Dvs.VmwareDistributedVirtualSwitch.TeamingHealthCheckConfig(
        enable = True,
        interval = 60,
        )
    healthCheckCmd = [vlanMtuCheckCmd, teamingCheckCmd]
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        healthCheckConfig = healthCheckCmd,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True,
        )
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    returnedHealthCheckConfig = returnedConfigSpec.GetHealthCheckConfig()
    if (ValidateHealthCheckCmd(
            healthCheckCmd,
            returnedHealthCheckConfig)):
        print("Test 1: Set HealthCheck command: PASS")
    else:
        print("Test 1: Failed to set HealthCheck command")
        raise Exception("HealthCheck test failed")
    return

def ValidateHealthCheckCmd(inConfig, outConfig):
    '''
    Verify that the HealthCheck match for in and out
    '''
    for i in range(0, len(inConfig)):
        if (inConfig[i].enable != outConfig[i].enable or \
            inConfig[i].interval != outConfig[i].interval):
            return False
    return True

def TestNetFlow():
    '''
    Sets the configuration settings for NetFlow and verifies that the values
    read back match the ones that were set.
    '''
    print("Testing NetFlow")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True,
        )
    ipfixConfig = Vim.Dvs.VmwareDistributedVirtualSwitch.IpfixConfig(
        activeFlowTimeout = 250,
        collectorIpAddress = "10.20.30.40",
        collectorPort = 2,
        observationDomainId = 1234,
        idleFlowTimeout = 20,
        internalFlowsOnly = True,
        samplingRate = 500
        )
    vmwsetting = Vim.Dvs.HostDistributedVirtualSwitchManager.VmwareDVSSettingSpec()
    vmwsetting.SetIpfixConfig(ipfixConfig)
    configSpec.SetVmwareSetting(vmwsetting)
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    returnedVmwareSetting = returnedConfigSpec.GetVmwareSetting()
    returnedIpfixConfig = returnedVmwareSetting.GetIpfixConfig()
    if (ValidateNetFlowSpec(
            ipfixConfig,
            returnedIpfixConfig)):
        print("Test 1: Set NetFlow settings: PASS")
    else:
        print("Test 1: Failed to set NetFlow settings")
        raise Exception("NetFlow tests failed")
    return

def ValidateNetFlowSpec(inConfig, outConfig):
    '''
    Verify that the IpfixConfig match for in and out
    '''
    return (inConfig.GetActiveFlowTimeout() == outConfig.GetActiveFlowTimeout() and
            inConfig.GetCollectorIpAddress() == outConfig.GetCollectorIpAddress() and
            inConfig.GetCollectorPort() == outConfig.GetCollectorPort() and
            inConfig.GetObservationDomainId() == outConfig.GetObservationDomainId() and
            inConfig.GetIdleFlowTimeout() == outConfig.GetIdleFlowTimeout() and
            inConfig.GetInternalFlowsOnly() == outConfig.GetInternalFlowsOnly() and
            inConfig.GetSamplingRate() == outConfig.GetSamplingRate())

def TestIPv6ForNetFlow():
    '''
    Sets IPv6 configuration settings for NetFlow and verifies that the values
    read back match the ones that were set.
    '''
    print("Testing IPv6 for NetFlow")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True,
        )
    ipfixConfig = Vim.Dvs.VmwareDistributedVirtualSwitch.IpfixConfig(
        activeFlowTimeout = 250,
        collectorIpAddress = "fec0::b18e",
        collectorPort = 2,
        observationDomainId = 400,
        idleFlowTimeout = 20,
        internalFlowsOnly = True,
        samplingRate = 500
        )
    vmwsetting = Vim.Dvs.HostDistributedVirtualSwitchManager.VmwareDVSSettingSpec()
    vmwsetting.SetIpfixConfig(ipfixConfig)
    configSpec.SetVmwareSetting(vmwsetting)
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    returnedVmwareSetting = returnedConfigSpec.GetVmwareSetting()
    returnedIpfixConfig = returnedVmwareSetting.GetIpfixConfig()
    if (ValidateNetFlowSpec(
            ipfixConfig,
            returnedIpfixConfig)):
        print("Test 1: Set IPv6 settings for NetFlow: PASS")
    else:
        print("Test 1: Failed to set IPv6 settings for NetFlow")
        raise Exception("IPv6 for NetFlow tests failed")
    return

def TestMulticastFilteringMode():
    '''
    Sets the configuration settings for Multicast Filtering Mode and verifies that
    the values read back match the ones that were set.
    '''
    print("Testing Multicast Filtering Mode")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True
        )
    inMode = "snooping"
    vmwsetting = Vim.Dvs.HostDistributedVirtualSwitchManager.VmwareDVSSettingSpec()
    vmwsetting.SetMulticastFilteringMode(inMode)
    configSpec.SetVmwareSetting(vmwsetting)
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    returnedVmwareSetting = returnedConfigSpec.GetVmwareSetting()
    returnedMode = returnedVmwareSetting.GetMulticastFilteringMode()
    if (inMode == returnedMode):
        print("Test 1: Set Multicast Filtering Mode: PASS")
    else:
        print("Test 1: Failed to Set Multicast Filtering Mode")
        raise Exception("MulticastFilteringMode tests failed")
    return

def TestDVMirror():
    '''
    Sets the configuration settings for DVMirror after MN version on port level
    and verifies that the values read back match the ones that were set.
    '''
    print("Testing DVMirror after MN version")

    # 1. Session type: dvPort
    srcPortOut = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        portKey = ["1000"]
        )
    dstPort = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        portKey = ["1"],
        )
    session1 = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanSession(
        key = "DvPortMirror",
        name = "SessionType:DvPort",
        enabled = False,
        sourcePortTransmitted = srcPortOut,
        destinationPort = dstPort,
        encapsulationVlanId = 1024,
        stripOriginalVlan = True,
        mirroredPacketLength = 512,
        normalTrafficAllowed = False,
        sessionType = "dvPortMirror",
        samplingRate = 3,
        )

    # 2. Session type: RSpanSource
    srcPortIn = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        portKey = ["2"]
        )
    dstPort = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        uplinkPortName = ["uplink1"]
        )
    session2 = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanSession(
        key = "RSpanSource",
        name = "SessionType:RSpanSource",
        enabled = False,
        sourcePortReceived = srcPortIn,
        destinationPort = dstPort,
        encapsulationVlanId = 1024,
        mirroredPacketLength = 512,
        normalTrafficAllowed = False,
        sessionType = "remoteMirrorSource",
        samplingRate = 3,
        )

    # 3. Session type: RSpanDest
    srcPortIn = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        vlans = [100]
        )
    dstPort = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        portKey = ["3"]
        )
    session3 = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanSession(
        key = "RSpanDest",
        name = "SessionType:RSpanDest",
        enabled = False,
        sourcePortReceived = srcPortIn,
        destinationPort = dstPort,
        encapsulationVlanId = 1024,
        mirroredPacketLength = 512,
        normalTrafficAllowed = False,
        sessionType = "remoteMirrorDest",
        samplingRate = 3,
        )

    # 4. Session type: ERSpanSource
    srcPortIn = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        portKey = ["4"]
        )
    dstPort = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        ipAddress = ["10.116.3.1"]
        )
    session4 = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanSession(
        key = "ERSpanSource",
        name = "SessionType:ERSpanSource",
        enabled = False,
        sourcePortReceived = srcPortIn,
        destinationPort = dstPort,
        encapsulationVlanId = 1024,
        mirroredPacketLength = 512,
        normalTrafficAllowed = False,
        sessionType = "encapsulatedRemoteMirrorSource",
        samplingRate = 3,
        )

    # 5. Session type: MixedDest
    srcPortIn = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        portKey = ["5"]
        )
    dstPort = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        portKey = ["6"],
        uplinkPortName = ["uplink3"]
        )
    session5 = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanSession(
        key = "MixedDest",
        name = "SessionType:MixedDest",
        enabled = False,
        sourcePortReceived = srcPortIn,
        destinationPort = dstPort,
        encapsulationVlanId = 1024,
        mirroredPacketLength = 512,
        normalTrafficAllowed = False,
        sessionType = "mixedDestMirror",
        samplingRate = 3,
        )

    # 6. Session type: ERSpanSource, Encapsulation type: ERSPAN3
    srcPortIn = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        portKey = ["7"]
        )
    dstPort = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        ipAddress = ["10.116.3.111"]
        )
    session6 = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanSession(
        key = "ERSpanSource_ERSPAN3",
        name = "SessionType:ERSpanSource_ERSPAN3",
        enabled = False,
        sourcePortReceived = srcPortIn,
        destinationPort = dstPort,
        encapsulationVlanId = 1024,
        mirroredPacketLength = 512,
        normalTrafficAllowed = False,
        sessionType = "encapsulatedRemoteMirrorSource",
        samplingRate = 3,
        encapType = "erspan3",
        erspanId = 500,
        erspanCOS = 2,
        erspanGraNanosec = False,
        )

    sessionList = [session1, session2, session3, session4, session5, session6]

    mirrorPort = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
        portKey = "1024",
        name = "mirror port",
        connectionCookie = 30,
        vspanConfig = sessionList)

    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    dvsManager.UpdatePorts(options.uuid, [mirrorPort])
    returnedPortDataList = dvsManager.FetchPortState(options.uuid,
                                                     [mirrorPort.portKey])
    returnedPortData = returnedPortDataList[0]
    returnedSessionList = returnedPortData.GetVspanConfig()

    print("print spec in: %s" % sessionList)
    print("print spec out: %s" % returnedSessionList)

    if (ValidateVspanSessionList(sessionList, returnedSessionList)):
        print("Test 1: Set DVMirror settings: PASS")
    else:
        print("Test 1: Failed to set DVMirror settings")
        raise Exception("DVMirror Tests failed")
    print("Test 1: Set DVMirror settings: PASS")
    return

def ValidateVspanSessionList(inSessionList, outSessionList):
    if (len(inSessionList) != len(outSessionList)):
       print("session num wrong: %s, %s" % (str(len(inSessionList)), str(len(outSessionList))))
       return False
    for i in range(0, len(inSessionList)):
       print("inSession Key: %s" % inSessionList[i].key)
       for j in range (0, len(outSessionList)):
           if (outSessionList[j].key == inSessionList[i].key):
               print("outSession Key: %s" % outSessionList[j].key)
               if (not ValidateVspanSession(inSessionList[i], outSessionList[j])):
                   print("this session mismatches: %s" % str(i))
                   return False
               print("this session matches: %s" % i)
               break
    return True

def ValidateVspanSession(inVspanSession, outVspanSession):
    '''
    Verify that the VspanSession match for in and out
    '''
    result = (inVspanSession.GetKey() == outVspanSession.GetKey() and
              inVspanSession.GetName() == outVspanSession.GetName() and
              inVspanSession.GetEnabled() == outVspanSession.GetEnabled() and
              inVspanSession.GetEncapsulationVlanId() == outVspanSession.GetEncapsulationVlanId() and
              inVspanSession.GetStripOriginalVlan() == outVspanSession.GetStripOriginalVlan() and
              inVspanSession.GetMirroredPacketLength() == outVspanSession.GetMirroredPacketLength() and
              inVspanSession.GetNormalTrafficAllowed() == outVspanSession.GetNormalTrafficAllowed() and
              inVspanSession.GetSessionType() == outVspanSession.GetSessionType() and
              inVspanSession.GetSamplingRate() == outVspanSession.GetSamplingRate() and
              ValidateVspanPorts(inVspanSession.GetSourcePortTransmitted(), outVspanSession.GetSourcePortTransmitted()) and
              ValidateVspanPorts(inVspanSession.GetSourcePortReceived(), outVspanSession.GetSourcePortReceived()) and
              ValidateVspanPorts(inVspanSession.GetDestinationPort(), outVspanSession.GetDestinationPort()))
    if inVspanSession.GetEncapType() != None:
       result = result and \
                inVspanSession.GetEncapType() == outVspanSession.GetEncapType()
       print("encapType:%s" % outVspanSession.GetEncapType())
    if inVspanSession.GetErspanId() != None:
       result = result and \
                inVspanSession.GetErspanId() == outVspanSession.GetErspanId()
       print("erspanID:%s" % outVspanSession.GetErspanId())
    if inVspanSession.GetErspanCOS() != None:
       result = result and \
                inVspanSession.GetErspanCOS() == outVspanSession.GetErspanCOS()
       print("erspanCOS:%s" % outVspanSession.GetErspanCOS())
    if inVspanSession.GetErspanGraNanosec() != None:
       result = result and \
                inVspanSession.GetErspanGraNanosec() == outVspanSession.GetErspanGraNanosec()
       print("erspanGraNanosec:%s" % outVspanSession.GetErspanGraNanosec())
    return result


def ValidateVspanPorts(inVspanPorts, outVspanPorts):
    '''
    Verify that the VspanPorts match for in and out
    '''
    print("inVspanPorts: %s" % inVspanPorts)
    print("outVspanPorts: %s" % outVspanPorts)
    if (inVspanPorts == None and outVspanPorts == None):
        print("both in and out VspanPorts are NULL")
        return True
    return (inVspanPorts.GetPortKey() == outVspanPorts.GetPortKey() and
            inVspanPorts.GetUplinkPortName() == outVspanPorts.GetUplinkPortName() and
            inVspanPorts.GetVlans() == outVspanPorts.GetVlans() and
            inVspanPorts.GetIpAddress() == outVspanPorts.GetIpAddress() and
            inVspanPorts.GetWildcardPortConnecteeType() == outVspanPorts.GetWildcardPortConnecteeType())


def TestMNDVMirror():
    '''
    Sets the configuration settings for DVMirror in MN on VDS level and verifies
    that the values read back match the ones that were set.
    '''
    print("Testing DVMirror in MN")

    testSourcePortTransmitted = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        portKey = ["1000"]
        )
    testSourcePortReceived = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        wildcardPortConnecteeType = ["vmVnic"]
        )
    expectSourcePortReceived = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        wildcardPortConnecteeType = ["vmVnic"]
        )
    testDestinationPort = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        portKey = ["1"],
        )
    expectDestinationPort = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanPorts(
        portKey = ["1"]
        )
    testVspanSession = Vim.Dvs.VmwareDistributedVirtualSwitch.VspanSession(
        key = "Session1",
        name = "TestVspanSession",
        description = "DVS Unit Tests used DVMirror session",
        enabled = False,
        sourcePortTransmitted = testSourcePortTransmitted,
        sourcePortReceived = testSourcePortReceived,
        destinationPort = testDestinationPort,
        encapsulationVlanId = 1024,
        stripOriginalVlan = True,
        mirroredPacketLength = 512,
        normalTrafficAllowed = False
        )
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True,
        )
    vmwsetting = Vim.Dvs.HostDistributedVirtualSwitchManager.VmwareDVSSettingSpec()
    vmwsetting.SetVspanConfig([testVspanSession])
    vmwsetting.SetPromiscuousModeVspanSession(testVspanSession.GetKey())
    configSpec.SetVmwareSetting(vmwsetting)
    print("About to do Reconfigure")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    returnedVmwareSetting = returnedConfigSpec.GetVmwareSetting()
    returnedVspanSession = returnedVmwareSetting.GetVspanConfig()[0]
    print(returnedVspanSession)
    print(testVspanSession)
    # Set the except result
    testVspanSession.SetSourcePortReceived(expectSourcePortReceived)
    testVspanSession.SetDestinationPort(expectDestinationPort)
    if (returnedVmwareSetting.GetPromiscuousModeVspanSession() == testVspanSession.GetKey() and
        ValidateMNVspanSession(
            returnedVspanSession,
            testVspanSession)):
        print("Test 1: Set MN DVMirror settings: PASS")
    else:
        print("Test 1: Failed to set MN DVMirror settings")
        raise Exception("MN DVMirror Tests failed")
    return

def ValidateMNVspanSession(inVspanSession, outVspanSession):
    '''
    Verify that the VspanSession match for in and out in MN version
    '''
    return (inVspanSession.GetKey() == outVspanSession.GetKey() and
            inVspanSession.GetName() == outVspanSession.GetName() and
            inVspanSession.GetEnabled() == outVspanSession.GetEnabled() and
            inVspanSession.GetEncapsulationVlanId() == outVspanSession.GetEncapsulationVlanId() and
            inVspanSession.GetStripOriginalVlan() == outVspanSession.GetStripOriginalVlan() and
            inVspanSession.GetMirroredPacketLength() == outVspanSession.GetMirroredPacketLength() and
            inVspanSession.GetNormalTrafficAllowed() == outVspanSession.GetNormalTrafficAllowed() and
            ValidateMNVspanPorts(inVspanSession.GetSourcePortTransmitted(), outVspanSession.GetSourcePortTransmitted()) and
            ValidateMNVspanPorts(inVspanSession.GetSourcePortReceived(), outVspanSession.GetSourcePortReceived()) and
            ValidateMNVspanPorts(inVspanSession.GetDestinationPort(), outVspanSession.GetDestinationPort()))

def ValidateMNVspanPorts(inVspanPorts, outVspanPorts):
    '''
    Verify that the VspanPorts match for in and out
    '''
    return (inVspanPorts.GetPortKey() == outVspanPorts.GetPortKey() and
            inVspanPorts.GetUplinkPortName() == outVspanPorts.GetUplinkPortName() and
            inVspanPorts.GetWildcardPortConnecteeType() == outVspanPorts.GetWildcardPortConnecteeType())

def TestIdempotentAPI():
    '''
    Test the featrue of TestIdempotentAPI
    '''
    print("Test IdempotentAPI")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    # Test ApplyDVPort()
    # Add a port via ApplyDVPort()
    origPortKeys = dvsManager.RetrieveDVPort(options.uuid)
    lacpEnable = Vim.BoolPolicy(
        inherited = False,
        value = True
        )
    lacpMode = Vim.StringPolicy(
        inherited = False,
        value = "active"
        )
    newLacpPolicy = Vim.Dvs.VmwareDistributedVirtualSwitch.UplinkLacpPolicy(
        enable = lacpEnable,
        mode = lacpMode
        )
    portSetting = Vim.Dvs.VmwareDistributedVirtualSwitch.VmwarePortConfigPolicy(
        lacpPolicy = newLacpPolicy
        )
    portIdempotent = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
        portKey = "500",
        name = "IdempotentAPITestPort",
        connectionCookie = 10,
        setting = portSetting
        )
    dvsManager.ApplyDVPort(options.uuid, [portIdempotent])
    currentPortKeys = dvsManager.RetrieveDVPort(options.uuid)

    if (currentPortKeys.count(portIdempotent.portKey) == 1):
        print("Test 1: Test ApplyDVPort()'s add function: PASS")
    else:
        print("Test 1: Failed to add port via ApplyDVPort()")
        raise Exception("IdempotentAPI tests failed")

    returnPortData = dvsManager.FetchPortState(options.uuid, [portIdempotent.portKey])[0]
    returnPortSetting = returnPortData.GetSetting()
    returnLacpPolicy = returnPortSetting.GetLacpPolicy()
    if ((returnLacpPolicy.enable.inherited == newLacpPolicy.enable.inherited and
        returnLacpPolicy.enable.value == newLacpPolicy.enable.value) and
        (returnLacpPolicy.mode.inherited == newLacpPolicy.mode.inherited and
        returnLacpPolicy.mode.value == newLacpPolicy.mode.value)):
        print("Test 1: Test ApplyDVPort() to add LACP configuration: PASS")
    else:
        print("Test 1: Failed to set LACP config via ApplyDVPort()")
        raise Exception("IdempotentAPI tests failed")

    # Update a port's setting via ApplyDVPort()
    origPortData = dvsManager.FetchPortState(options.uuid, [portIdempotent.portKey])[0]
    origSetting = origPortData.GetSetting()
    blockedPolicy = Vim.BoolPolicy(
        inherited = False,
        value = True
        )
    origSetting.SetBlocked(blockedPolicy)
    origPortData.SetSetting(origSetting)
    dvsManager.ApplyDVPort(options.uuid, [origPortData])
    returnedPortData = dvsManager.FetchPortState(options.uuid, [portIdempotent.portKey])[0]
    returnedSetting = returnedPortData.GetSetting()
    returnedBlockedPolicy = returnedSetting.GetBlocked()
    if (returnedBlockedPolicy.inherited == blockedPolicy.inherited and
        returnedBlockedPolicy.value == blockedPolicy.value):
        print("Test 2: Test ApplyDVPort()'s update function: PASS")
    else:
        print("Test 2: Failed to update port setting via ApplyDVPort()")
        raise Exception("IdempotentAPI tests failed")
    # Test FetchPortState()
    returnedState = returnedPortData.GetState()
    if (returnedState.GetRuntimeInfo() == None):
        print("Test 3: Failed to validate FetchPortState()'s option argument")
        raise Exception("FetchPortState() error")
    returnedPortData = dvsManager.FetchPortState(options.uuid,
                                                 [portIdempotent.portKey],
                                                 Vim.Dvs.HostDistributedVirtualSwitchManager.FetchPortOption.statsOnly)[0]
    returnedState = returnedPortData.GetState()
    if (returnedState.GetRuntimeInfo() != None):
        print("Test 3: Failed to validate FetchPortState()'s option argument")
        raise Exception("FetchPortState() error")
    returnedPortData = dvsManager.FetchPortState(options.uuid,
                                                 [portIdempotent.portKey],
                                                 Vim.Dvs.HostDistributedVirtualSwitchManager.FetchPortOption.runtimeInfoOnly)[0]
    returnedState = returnedPortData.GetState()
    if (returnedState.GetRuntimeInfo() != None):
        print("Test 3: Test FetchPortState()'s option argument: PASS")
    else:
        print("Test 3: Failed to validate FetchPortState()'s option argument")
        raise Exception("FetchPortState() error")
    # Test ApplyDVPortList()
    dvsManager.ApplyDVPortList(options.uuid, origPortKeys)
    returnedPortKeys = dvsManager.RetrieveDVPort(options.uuid)
    if (origPortKeys == returnedPortKeys):
        print("Test 4: Test ApplyDVPortList(): PASS")
    else:
        print("Test 4: Failed to delete a port via ApplyDVPortList()")
        raise Exception("IdempotentAPI tests failed")

    # Test ApplyDVPortgroup()
    # Add a portgroup via ApplyDVPortgroup()
    origPortGroups = dvsManager.RetrieveDVPortgroup(options.uuid)
    testPortGroupKey = "IdempotentAPITestPortGroup"
    pgIdempotent = GeneratePortgroupCfg(testPortGroupKey, "add", "ephemeral")
    dvsManager.ApplyDVPortgroup(options.uuid, [pgIdempotent])
    currentPortGroups = dvsManager.RetrieveDVPortgroup(options.uuid)
    if (currentPortGroups.count(testPortGroupKey) == 1):
        print("Test 5: Test ApplyDVPortgroup()'s add function: PASS")
    else:
        print("Test 5: Failed to add portgroup via ApplyDVPortgroup()")
        raise Exception("IdempotentAPI tests failed")
    # Update a portgroup via ApplyDVPortgroup()
    origPortGroupSpec = dvsManager.RetrieveDVPortgroupConfigSpec(options.uuid, [testPortGroupKey])[0]
    print(origPortGroupSpec)
    origPGConfigSpec = origPortGroupSpec.GetSpecification()
    origPGConfigSpec.SetType(Vim.Dvs.DistributedVirtualPortgroup.PortgroupType.earlyBinding)
    origPortGroupSpec.SetSpecification(origPGConfigSpec)
    dvsManager.ApplyDVPortgroup(options.uuid, [origPortGroupSpec])
    returnedPortGroupSpec = dvsManager.RetrieveDVPortgroupConfigSpec(options.uuid, [testPortGroupKey])[0]
    print(returnedPortGroupSpec)
    if (returnedPortGroupSpec.GetSpecification().GetType() == origPGConfigSpec.GetType()):
        print("Test 6: Test ApplyDVPortgroup()'s update function: PASS")
    else:
        print("Test 6: Failed to update portgroup via ApplyDVPortgroup()")
        raise Exception("IdempotentAPI tests failed")
    # Test ApplyDVPortgroupList()
    dvsManager.ApplyDVPortgroupList(options.uuid, origPortGroups)
    returnedPortGroups = dvsManager.RetrieveDVPortgroup(options.uuid)
    if (origPortGroups == returnedPortGroups):
        print("Test 7: Test ApplyDVPortgroupList(): PASS")
    else:
        print("Test 7: Failed to validate ApplyDVPortgroupList()")
        raise Exception("IdempotentAPI tests failed")

    # Test ApplyDvs()
    # Add a DVS via ApplyDvs()
    origDVSList = dvsManager.GetDistributedVirtualSwitch()
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
    testProductSpec = Vim.Dvs.ProductSpec(
        name = "VMwareDVS",
        vendor = "VMware",
        version = "6.5.0"
        )
    TestDvsUuid = "74 65 73 74 00 00 00 00-00 00 00 00 00 00 00 02"
    TestDvsSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSCreateSpec(
        uuid = TestDvsUuid,
        name = "IdempotentAPITestDVS",
        backing = Vim.Dvs.HostMember.PnicBacking(),
        maxProxySwitchPorts = 64,
        port=[port1, uplinkPort1, uplinkPort2, uplinkPort3],
        uplinkPortKey=["1","2", "3"],
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True,
        productSpec = testProductSpec
        )
    vmwsetting = Vim.Dvs.HostDistributedVirtualSwitchManager.VmwareDVSSettingSpec()
    TestDvsSpec.SetVmwareSetting(vmwsetting)
    dvsManager.ApplyDvs([TestDvsSpec])
    currentDVSList = dvsManager.GetDistributedVirtualSwitch()
    if (currentDVSList.count(TestDvsUuid) == 1):
        print("Test 8: Test ApplyDvs()'s add function: PASS")
    else:
        print("Test 8: Failed to add DVS via ApplyDvs()")
        raise Exception("IdempotentAPI tests failed")
    origSpec = dvsManager.RetrieveDvsConfigSpec(TestDvsUuid)
    print(origSpec)
    # Update a DVS via ApplyDvs()
    testDVSIP = "10.112.113.114"
    TestDvsSpec.SetSwitchIpAddress(testDVSIP)
    dvsManager.ApplyDvs([TestDvsSpec])
    returnedSpec = dvsManager.RetrieveDvsConfigSpec(TestDvsUuid)
    print(returnedSpec)
    if (returnedSpec.GetSwitchIpAddress() == TestDvsSpec.GetSwitchIpAddress()):
        print("Test 9: Test ApplyDvs()'s update function: PASS")
    else:
        print("Test 9: Failed to update DVS via ApplyDvs()")
        raise Exception("IdempotentAPI tests failed")
    # Test ApplyDvsList()
    dvsManager.ApplyDvsList(origDVSList)
    returnedDVSList = dvsManager.GetDistributedVirtualSwitch()
    if (origDVSList == returnedDVSList):
        print("Test 10: Test ApplyDvsList(): PASS")
    else:
        print("Test 10: Failed to validate ApplyDvsList()")
        raise Exception("IdempotentAPI tests failed")


def TestStandalonePort():
    """
    Create a VM and connect it to a standalone port
    Verify that the connection was successful
    """
    print("Testing standalone portgroup")
    envBrowser = invt.GetEnv()
    print("Creating quickDummySpec with datastore %s" % datastore)
    config = vm.CreateQuickDummySpec(options.vmName, datastoreName = datastore)
    config = vmconfig.AddDvPortBacking(config, "1000", options.uuid, 5)
    try:
        myVm = vm.CreateFromSpec(config)
    except Exception as e:
        print("Failed to connect standalone port to VM")
        raise
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if len(devices) < 1:
        raise Exception("Failed to add nic")
    if not IsBackingValid(devices):
        raise Exception("Backing port is not reported as expected")
    vm.PowerOn(myVm)
    devices = vmconfig.CheckDevice(myVm.GetConfig(),
                                   Vim.Vm.Device.VirtualEthernetCard)
    if not IsBackingValid(devices):
        raise Exception("Backing port is not reported as expected after powerOn")
    print("Test 1: Testing standalone port VM connection: PASS")
    vm.PowerOff(myVm)
    vm.Destroy(myVm)

def TestOPLACP():
    '''
    Sets the configuration settings for LACP in OP on VDS level and verifies
    that the values read back match the ones that were set.
    '''
    print("Testing LACP in OP")

    testLag = Vim.Dvs.VmwareDistributedVirtualSwitch.LacpGroupConfig(
        key = "123",
        name = "TestLag1",
        mode = "active",
        uplinkNum = 4,
        loadbalanceAlgorithm = "srcMac"
        )
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = options.uuid,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True
        )
    vmwsetting = Vim.Dvs.HostDistributedVirtualSwitchManager.VmwareDVSSettingSpec()
    vmwsetting.SetLacpGroupConfig([testLag])
    configSpec.SetVmwareSetting(vmwsetting)
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    returnedConfigSpec = dvsManager.RetrieveDvsConfigSpec(options.uuid)
    returnedVmwareSetting = returnedConfigSpec.GetVmwareSetting()
    returnedLag = returnedVmwareSetting.GetLacpGroupConfig()[0]
    print(returnedLag)
    if (ValidateOPLACP(
            returnedLag,
            testLag)):
        print("Test 1: Set Link Aggregation group: PASS")
    else:
        print("Test 1: Failed to set Link Aggregation group")
        raise Exception("OP LACP Tests failed")
    return

def ValidateOPLACP(inLag, outLag):
    '''
    Verify that the LACP group match for in and out in OP
    '''
    return (inLag.GetKey() == outLag.GetKey() and \
            inLag.GetName() == outLag.GetName() and \
            inLag.GetMode() == outLag.GetMode() and \
            inLag.GetUplinkNum() == outLag.GetUplinkNum() and \
            inLag.GetLoadbalanceAlgorithm() == outLag.GetLoadbalanceAlgorithm())

def TestOpaqueDvs():
    uuid = "b2 92 12 50 38 2c 99 5d-2a e4 56 c5 c6 fb e6 03"
    name = "xxx"
    prodSpec = Vim.Dvs.ProductSpec(vendor="VMware", version = "6.5.0")
    dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager

    # use two uplink ports
    uplinkPort1 = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
        portKey = "uplink1",
        connectionCookie = 0)
    uplinkPort2 = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
        portKey = "uplink2",
        connectionCookie = 0)

    # create the proxyswitch
    createSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSCreateSpec(
        uuid = uuid,
        name = name,
        backing = Vim.Dvs.HostMember.PnicBacking(),
        productSpec = prodSpec,
        maxProxySwitchPorts = 64,
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = True,
        port=[uplinkPort1, uplinkPort2],
        uplinkPortKey=["uplink1"],
        )
    ec = Vim.KeyValue(key="com.vmware.extraconfig.opaqueDvs", value="true")
    createSpec.SetExtraConfig([ec])
    vmwsetting = Vim.Dvs.HostDistributedVirtualSwitchManager.VmwareDVSSettingSpec()
    createSpec.SetVmwareSetting(vmwsetting)
    dvsManager.CreateDistributedVirtualSwitch(createSpec)

    # connect the pnic
    if (len(pnicList) > 1):
        pnicSpec = Vim.Dvs.HostMember.PnicSpec(pnicDevice = pnicList[1],
                   uplinkPortKey = "uplink1",
                   connectionCookie = 0)
        pnicBacking = Vim.Dvs.HostMember.PnicBacking(pnicSpec = [pnicSpec])

        configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
            uuid = uuid,
            backing = pnicBacking,
            )
        dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)

    # disconnect the pnic
    configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
        uuid = uuid,
        backing = Vim.Dvs.HostMember.PnicBacking(),
        )
    dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)

    # destroy the proxyswitch
    dvsManager.RemoveDistributedVirtualSwitch(uuid)

def main(argv):
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
    global options
    options = get_options()
    dvsUuidList = []
    transactionIndex = 0
    global pnicList
    pnicList = GetPnics(options.nic)
    global si
    si = SmartConnect(host=options.host,
                      user=options.user,
                      pwd=options.password)
    atexit.register(Disconnect, si)
    if (options.vmName == None) :
        options.vmName = "testVM"
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    networkSystem.Refresh()
    try:
       print("cleaning up")
       cleanup(None)
    except Exception as e:
       print(e)
       print("checked for vm from previous run")
    createDvs()
    featureState.init()
    try:
       if options.test:
          # XXX: Broken for NetworkRollbackAPIs
          globals()["Test" + options.test]()
       else:
          TestVmknicTag()
          TestStandalonePort()
          TestIdempotentAPI()
          # Disable switch security test till the branch is stable to run
          # test-esx -n hostd/dvsUnitTests.py, and fully tested this test
          # in local dev box. Will Enable soon.
          #TestSwitchSecurity()
          TestDVSIP()
          if (options.host == "localhost"):
             TestLLDP()
          TestNetFlow()
          TestIPv6ForNetFlow()
          TestMulticastFilteringMode()
          if not options.simulatorOnly:
             TestHealthCheck()
             TestDVMirror()
             TestMNDVMirror()
             TestOpaqueProperties()
             TestVnicUpdate()
             TestEphemeral()
             TestOpaqueChannel()
          TestNetRmEnable()
          if os.uname()[0].lower() == 'vmkernel':
             TestZombiePorts()
          TestLateBinding()
          TestEarlyBinding()
          TestVmknics()
          TestUpdateNetworkConfigVnics()
          if (len(pnicList) > 0):
             TestUpdateNetworkConfigPnics()
          TestSimulatedVcClone()
          if (len(pnicList) >= 3):
             TestUpdateNetworkConfigPnicsExtended()
          TestNetRmSettings()
          TestPortgroupPersist()
          TestOPLACP()
          TestOpaqueDvs()
          if not options.simulatorOnly:
             TestTrafficFilter()
             TestNetworkRollbackAPIs(si, True,
                   "rollbackTestsWithCommit",
                   "74 65 73 74 00 00 00 00-00 00 00 00 00 00 00 04",
                   dvsUuidList,
                   transactionIndex)
             TestNetworkRollbackAPIs(si, False,
                   "rollbackTestsWOCommit",
                   "74 65 73 74 00 00 00 00-00 00 00 00 00 00 00 03",
                   dvsUuidList,
                   transactionIndex)

        #TestDVSLimits()
    except Exception as e:
        print("Got exception during execution")
        print(e)
        traceback.print_exc()
        cleanup(dvsUuidList)
        return -1
    cleanup(dvsUuidList)
    print("DONE.")
    return 0

# Start program
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
