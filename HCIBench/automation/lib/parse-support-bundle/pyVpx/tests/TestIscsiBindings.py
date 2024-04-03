#!/usr/bin/python
#
# TestIscsiBindings.py -
#
#   Validates iSCSI binding and migration API additions
#
from __future__ import print_function

import sys
from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
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
import operator

loglevel = 1

#
# Basic verification of getting candidate vnics for a vmhba
#   - Test: QueryCandidateNics with valid vmhba
#   - Test: QueryCandidateNics with invalid vmhba
#
def TestQueryCandidateNics(si, vmhbaList):
    print("TESTCASE: TestQueryCandidateNics")

    iscsiManager = host.GetHostSystem(si).GetConfigManager().iscsiManager

    """ POSITIVE TEST 1 - Get validate vmhba's vnic candidates """
    print("  TEST: TestQueryCandidateNics - positive test 1")
    for vmhba in vmhbaList:
        vnics = iscsiManager.QueryCandidateNics(vmhba)
        for vnic in vnics:
            print("   %s -> %s", (vmhba, vnic.vnicDevice))
            if loglevel >= 1:
               print("*** IscsiPortInfo = %s" % vnic)

        print("    --- PASS ---")

    """ NEGATIVE TEST 1 - Get invalidate vmhba's vnic candidates """
    print("  TEST: TestQueryCandidateNics - negative test 1")
    bad_adapter = "blah"
    try:
        vnics = iscsiManager.QueryCandidateNics(bad_adapter)
        print("    --- FAIL ---")
    except Exception as e:
       print("    --- PASS ---")

#
# Basic verification of getting bound vnics for a vmhba
#   - Test: QueryBoundVnics with valid vmhba
#   - Test: QueryBoundVnics with invalid vmhba
#
def TestQueryBoundVnics(si, vmhbaList):
    print("TESTCASE: TestQueryBoundVnics")

    iscsiManager = host.GetHostSystem(si).GetConfigManager().iscsiManager

    """ POSITIVE TEST 1 - Get validate vmhba's bound vnic """
    print("  TEST: TestQueryBoundVnics - positive test 1")
    for vmhba in vmhbaList:
        vnics = iscsiManager.QueryBoundVnics(vmhba)
        for vnic in vnics:
            print("    %s -> %s", (vmhba, vnic.vnicDevice))
            if loglevel >= 1:
               print("*** IscsiPortInfo = %s" % vnic)
        print("    --- PASS ---")

    """ NEGATIVE TEST 1 - Get invalidate vmhba's bound vnic """
    print("  TEST: TestQueryBoundVnics - negative test 1")
    bad_adapter = "blah"
    try:
        vnics = iscsiManager.QueryBoundVnics(bad_adapter)
        print("    --- FAIL ---")
    except Exception:
       print("    --- PASS ---")

#
# Test binding and unbinding of a vnic
#   - Test: BindVnic with valid vmhba
#   - Test: BindVnic with invalid vmhba
#   - Test: BindVnic with valid vnic
#   - Test: BindVnic with invalid vnic
#   - Test: UnbindVnic with valid vmhba
#   - Test: UnbindVnic with invalid vmhba
#   - Test: UnbindVnic with valid vnic
#   - Test: UnbindVnic with invalid vnic
#
#   NOTE: This test case assumes there are two vmhba each with a
#         path to the same LUN allowing unbinding and binding to
#         occur.
#
def TestBindVnic(si, vmhbaList):
    print("TESTCASE: TestBindVnic")
    bad_vmhba    = "blah"
    good_vmhba   = vmhbaList[0]
    bad_vnic   = "blah"
    vnicList   = []
    good_vnic  = ""

    iscsiManager = host.GetHostSystem(si).GetConfigManager().iscsiManager

    """ PREP 1 - Get bound vnic for vmhba[0] """
    print("  PREP: BindVnic - prep 1")
    try:
        vnicList = iscsiManager.QueryBoundVnics(good_vmhba)
        good_vnic = vnicList[0].GetVnicDevice()
        print("    --- PASS ---")
    except Exception:
        print("    --- FAIL ---")
        return -1

    """ NEGATIVE TEST 1 - Unbind vnic from invalid vmhba """
    print("  TEST: BindVnic - negative test 1")
    try:
        iscsiManager.UnbindVnic(bad_vmhba, good_vnic)
        print("    --- FAIL ---")
    except Exception:
        print("    --- PASS ---")

    """ NEGATIVE TEST 2 - Unbind invalid vnic from vmhba """
    print("  TEST: BindVnic - negative test 2")
    try:
        vnic = "blah"
        iscsiManager.UnbindVnic(good_vmhba, bad_vnic)
        print("    --- FAIL ---")
    except Exception as e:
        print("    --- PASS ---")

    """ POSITIVE TEST 1 - Unbind vmnic from first vmhba """
    print("  TEST: BindVnic - positive test 1")
    try:
        iscsiManager.UnbindVnic(good_vmhba, good_vnic, 1)
        print("    --- PASS ---")
    except Exception as e:
        print("    --- FAIL ---")
        if loglevel >= 1:
            print("*** Exception = %s" % e)
        return -1

    """ POSITIVE TEST 2 - Validate bound vnics is empty for vmhba """
    print("  PREP: BindVnic - positive test 2")
    try:
        empty_vnics = iscsiManager.QueryBoundVnics(good_vmhba)
        if (len(empty_vnics) <= 0):
            print("    --- PASS ---")
        else:
            print("    --- FAIL ---")
    except Exception:
        print("    --- FAIL ---")
        return -1

    """ NEGATIVE TEST 3 - Bind vnic from invalid vmhba """
    print("  TEST: BindVnic - negative test 3")
    try:
        bad_vmhba = "blah"
        iscsiManager.BindVnic(bad_vmhba, good_vnic)
        print("    --- FAIL ---")
    except Exception:
        print("    --- PASS ---")

    """ NEGATIVE TEST 4 - Bind invalid vnic from vmhba """
    print("  TEST: BindVnic - negative test 4")
    try:
        vnic = "blah"
        iscsiManager.BindVnic(good_vmhba, bad_vnic)
        print("    --- FAIL ---")
    except Exception:
        print("    --- PASS ---")

    """ POSITIVE TEST 4 - Bind vmnic from first vmhba """
    print("  TEST: BindVnic - positive test 4")
    try:
        iscsiManager.BindVnic(good_vmhba, good_vnic)
        print("    --- PASS ---")
    except Exception:
        print("    --- FAIL ---")

    """ NEGATIVE TEST 5 - Bind vmnic again from first vmhba """
    print("  TEST: BindVnic - positive test 4")
    try:
        iscsiManager.BindVnic(good_vmhba, good_vnic)
        print("    --- FAIL ---")
    except Exception as e:
        print("    --- PASS ---")
        if loglevel >= 1:
            print("*** Exception = %s" % e)
        return -1

#
# Test binding and unbinding of a vnic
#   - Test: Walks networkSystem object and evaulates all vnic in
#           the system to verify if the iscsiManager QueryVnicStatus
#           is set properly.
#
def TestQueryVnicStatus(si, vmhbaList):
    print("TESTCASE: TestQueryVnicStatus")

    iscsiManager  = host.GetHostSystem(si).GetConfigManager().iscsiManager
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem

    """ POSITIVE TEST 1 - Verify TestQueryVnicStatus is correct """
    print("  TEST: TestQueryVnicStatus - positive test 1")
    netVnicList = networkSystem.networkInfo.vnic
    for netVnic in netVnicList:
        print("   %s" % netVnic.GetDevice())
        iscsiMatch = 0

        for vmhba in vmhbaList:
            iscsiVnicList = iscsiManager.QueryBoundVnics(vmhba)
            for iscsiVnic in iscsiVnicList:
                if netVnic.GetDevice() == iscsiVnic.vnicDevice:
                    iscsiMatch = 1
                    break
            if iscsiMatch == 1:
                break

        iscsiStatus = iscsiManager.QueryVnicStatus(netVnic.GetDevice())
        if loglevel >= 1:
            print("*** IscsiStatus = %s" % iscsiStatus)

        found = 0
        for faultCode in iscsiStatus.reason:
            if loglevel >= 1:
                print("*** reason = %s" % faultCode)

            if (isinstance(faultCode, Vim.Fault.IscsiFaultVnicInUse)):
                found = 1

        if found == 1:
            if iscsiMatch == 1:
               print("    --- PASS ---")
            else:
               print("    --- FAIL ---")
        else:
            if iscsiMatch == 1:
               print("    --- FAIL ---")
            else:
               print("    --- PASS ---")

#
#
#

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

    failoverPolicy.SetFailureCriteria(failureCriteria)
    cfg.SetUplinkTeamingPolicy(failoverPolicy)
    return cfg

#
#
#

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

#
#
#
def createDvs(si, uuid, dvsName):
    """
    Setup a dvs with one early binding, one latebinding, two ephemeral and
    one uplink portgroup. Also creates 4 uplink ports 2 standalone and 2
    belonging to the uplink portgroup.
    """

    # Create the dvs.
    prodSpec = Vim.Dvs.ProductSpec(vendor="VMware")
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

#
# Test update network config disconnect/reconnect event
#
def TestUpdateNeworkConfig(si, vmhbaList, uuid):
    print("TESTCASE: TestUpdateNetworkConfig")

    iscsiManager  = host.GetHostSystem(si).GetConfigManager().iscsiManager
    networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
    op = "modify"

    """ POSITIVE TEST 1 - Verify TestUpdateNetworkConfig is correct """
    print("  TEST: TestUpdateNetworkConfig - positive test 1")
    for vmhba in vmhbaList:
       print("    vmhba=%s" % vmhba)
       iscsiVnicList = iscsiManager.QueryBoundVnics(vmhba)
       for iscsiVnic in iscsiVnicList:
          print("     iscsiVnic=%s" % iscsiVnic.vnicDevice)
          networkConfig = networkSystem.networkConfig
          for netVnic in networkConfig.vnic:
             print("      netVnic=%s" % netVnic.GetDevice())
             if iscsiVnic.vnicDevice == netVnic.GetDevice():
                print("       match")
                origPortgroup = netVnic.spec.portgroup

                try:
                   print("  TEST: TestUpdateNetworkConfig - positive test 1 - migrate")
                   newNetworkConfig = Vim.Host.NetworkConfig()
                   newDvsPort = Vim.Dvs.PortConnection(portgroupKey = "pg1",
                                switchUuid = uuid)
                   newSpec = Vim.Host.VirtualNic.Specification(
                      distributedVirtualPort = newDvsPort)
                   newVnicConfig = Vim.Host.VirtualNic.Config(
                      changeOperation = "edit",
                      device = netVnic.GetDevice(),
                   #  portgroup = "")
                      spec = newSpec)
                   newNetworkConfig.GetVnic().append(newVnicConfig)
                   result = networkSystem.UpdateNetworkConfig(newNetworkConfig, op)
                except Exception:
                   print("  TEST: TestUpdateNetworkConfig - positive test 1 - migrate (failed)")
                   return -1

                try:
                   print("  TEST: TestUpdateNetworkConfig - positive test 1 - restore")
                   newNetworkConfig = Vim.Host.NetworkConfig()
                   newSpec = Vim.Host.VirtualNic.Specification(
                      portgroup = origPortgroup)
                   newVnicConfig = Vim.Host.VirtualNic.Config(
                      changeOperation = "edit",
                      device = netVnic.GetDevice(),
                      spec = newSpec)
                   newNetworkConfig.GetVnic().append(newVnicConfig)
                   result = networkSystem.UpdateNetworkConfig(newNetworkConfig, op)
                except Exception:
                   print("  TEST: TestUpdateNetworkConfig - positive test 1 - restore (failed)")
                   return -1


#
# Split adapter options in a list
#
def GetAdapters(adapters):
    if adapters == None:
        return []
    adapters = adapters.split(',')
    return adapters

#
# Cleanup
#
def cleanup(si, uuid):
   """
   Remove the dvs created as part of the setup phase. Assumes no clients are connected.
   """
   dvsManager = si.RetrieveInternalContent().hostDistributedVirtualSwitchManager
   dvsManager.RemoveDistributedVirtualSwitch(uuid)

#
# Generic get_options handling
#
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
    parser.add_option("-d", "--adapter",
                      help="Storage adapter list ex. vmhba#,vmhba#")

    (options, _) = parser.parse_args()

    if options.adapter == None:
        parser.error("Storage adapter needs to be specified")
    return options


#
# Test does the following.
#   - Basic verification of bound vnics
#   - Basic verification of candidate vnics
#   - Binding and unbinding of vnics
#   - Validate QueryVnicStatus
#
def main():
    """ Get and validate options """
    options = get_options()

    vmhbaList = GetAdapters(options.adapter)
    if (len(vmhbaList) <= 1):
        print("FAIL: Atleast two adapters must be specified.")
        return -1

    """ Connect to vmodl """
    si = SmartConnect(host=options.host,
                      user=options.user,
                      pwd=options.password)
    atexit.register(Disconnect, si)

    createDvs(si, options.uuid, options.name)
    """ Start tests """
    try:
        #TestQueryCandidateNics(si, vmhbaList)
        #TestQueryBoundVnics(si, vmhbaList)
        #TestAddVnic(si, vmhbaList)
        #TestQueryVnicStatus(si, vmhbaList)
        TestUpdateNeworkConfig(si, vmhbaList, options.uuid)

    except Exception as e:
        cleanup(si, options.uuid)
        print()
        return -1

    cleanup(si, options.uuid)
    print("DONE.")
    return 0

# Start program
if __name__ == "__main__":
    sys.exit(main())
