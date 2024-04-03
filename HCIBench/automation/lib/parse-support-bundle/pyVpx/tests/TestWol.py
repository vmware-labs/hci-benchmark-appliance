#!/usr/bin/python

from __future__ import print_function

import sys
import atexit
from pyVmomi import Vim, Vmodl
from pyVim.connect import Connect, Disconnect
from optparse import OptionParser
from pyVim import folder
from pyVim import vm, host
from pyVim import invt
import time

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
    parser.add_option("-n", "--name", default="test-esx",
            help="DVSwitch name")
    (options, _) = parser.parse_args()
    return options

def getVswitchPnics(networkInfo, inUsePnics):
    """
    Append the list of in use vswitch pnics to inUsePnics and return
    a complete list
    """
    vswitches = networkInfo.vswitch
    for vswitch in vswitches:
        bondBridge = vswitch.spec.bridge
        if (bondBridge != None):
            inUsePnics.extend(bondBridge.nicDevice)
    return inUsePnics
def getVDSPnics(networkInfo, inUsePnics):
    """
    Append the list of in use dvs pnics to inUsePnics and return a
    a complete list
    """
    pswitches = networkInfo.proxySwitch
    for pswitch in pswitches:
        backing = pswitch.spec.backing
        if (backing != None):
            inUsePnics.extend(backing.pnicSpec.pnicDevice)
    return inUsePnics

def getFreeUplinks(networkInfo):
    """
    Get the list of uplinks that are free
    """
    allPnics = networkInfo.pnic
    wolPnics = []
    wolPnics = filter(lambda x: x.wakeOnLanSupported == True, allPnics)
    if (len(wolPnics) > 0):
        inUsePnics = []
        inUsePnics = getVswitchPnics(networkInfo, inUsePnics)
        inUsePnics = getVDSPnics(networkInfo, inUsePnics)
        return list(set(map(lambda x: x.device, wolPnics)) \
            .difference(set(inUsePnics)))
    return []

def checkInitialState(si):
    """
    Checks if there a WOL capable free uplinks in the system
    """
    networkSystem = host.GetHostSystem(si).configManager.networkSystem
    networkInfo = networkSystem.GetNetworkInfo()
    freePnics = getFreeUplinks(networkInfo)
    return freePnics

def GenerateIPConfig(ipAdd):
    ip = Vim.Host.IpConfig(dhcp = False,
              ipAddress = ipAdd,
              subnetMask = "255.255.255.252")
    return ip

def CreateVswitchSetup(si, name):
    """
    Create a vmotion nic and connect it to a vswitch without uplinks
    """
    networkSystem = host.GetHostSystem(si).configManager.networkSystem
    spec = Vim.Host.VirtualSwitch.Specification(numPorts = 128)
    vswitchConfig = Vim.Host.VirtualSwitch.Config(changeOperation = "add",
                                                  name = name,
                                                  spec = spec)
    pgSpec = Vim.Host.PortGroup.Specification(name = name,
                                              policy = Vim.Host.NetworkPolicy(),
                                              vswitchName = name)
    pgConfig = Vim.Host.PortGroup.Config(changeOperation = "add",
                                         spec = pgSpec)
    ipCfg = GenerateIPConfig("192.168.124.17")
    vnicSpec = Vim.Host.VirtualNic.Specification(ip = ipCfg,
                                                 portgroup = name)
    vnicConfig = Vim.Host.VirtualNic.Config(changeOperation = "add",
                                            spec = vnicSpec)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.vswitch.append(vswitchConfig)
    netCfg.portgroup.append(pgConfig)
    netCfg.vnic.append(vnicConfig)
    vnicList = networkSystem.UpdateNetworkConfig(netCfg, "modify")
    return vnicList.vnicDevice[0]

def CleanupVswitchSetup(si, name, vnicName):
    """
    Cleanup the vswitch test setup
    """
    networkSystem = host.GetHostSystem(si).configManager.networkSystem
    vswitchConfig = Vim.Host.VirtualSwitch.Config(changeOperation = "remove",
                                                  name = name)
    pgSpec = Vim.Host.PortGroup.Specification(name = name,
                                              policy = Vim.Host.NetworkPolicy(),
                                              vswitchName = name)
    pgConfig = Vim.Host.PortGroup.Config(changeOperation = "remove",
                                         spec = pgSpec)
    vnicConfig = Vim.Host.VirtualNic.Config(changeOperation = "remove",
                                            device = vnicName)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.vswitch.append(vswitchConfig)
    netCfg.portgroup.append(pgConfig)
    netCfg.vnic.append(vnicConfig)
    vnicList = networkSystem.UpdateNetworkConfig(netCfg, "modify")
    print("Cleaned up setup")

def SelectVmotionNic(si, vnic):
    """
    Mark a particular nic as the vmotion nic interface
    """
    vnicMgr = host.GetHostSystem(si).configManager.virtualNicManager
    vnicMgr.SelectVnic("vmotion", vnic)

def CheckExpectedWOLStatus(si, status):
    config = host.GetHostSystem(si).config
    if (config.wakeOnLanCapable != status):
       raise Exception("WOL doesn't match expected capability: %s" % config)
    print("Wol status is as expected")
    return True

def CreatePCFilter(pc, objType, objs):
   """ Create property collector filter for obj """
   # First create the object specification as the task object.
   objspecs = [Vmodl.Query.PropertyCollector.ObjectSpec(obj=obj)
                                                         for obj in objs]

   # Next, create the property specification as the state.
   propspec = Vmodl.Query.PropertyCollector.PropertySpec(
                                          type=objType, pathSet=[], all=True)

   # Create a filter spec with the specified object and property spec.
   filterspec = Vmodl.Query.PropertyCollector.FilterSpec()
   filterspec.objectSet = objspecs
   filterspec.propSet = [propspec]

   # Create the filter
   return pc.CreateFilter(filterspec, True)

def AttachPnic(si, name, pnic):
    """
    Attach a pnic to the vswitch
    """
    networkSystem = host.GetHostSystem(si).configManager.networkSystem
    bondBridge = Vim.Host.VirtualSwitch.BondBridge(nicDevice = [pnic])
    spec = Vim.Host.VirtualSwitch.Specification(numPorts = 128,
                                                bridge = bondBridge)
    vswitchConfig = Vim.Host.VirtualSwitch.Config(changeOperation = "edit",
                                                  name = name,
                                                  spec = spec)
    netCfg = Vim.Host.NetworkConfig()
    netCfg.vswitch.append(vswitchConfig)
    vnicList = networkSystem.UpdateNetworkConfig(netCfg, "modify")

def TestVswitchWOL(si, pnic, name):
    """
    Test that the WOL capability is reported correctly by vmotions nics backed
    by vswitches
    """
    vnic = CreateVswitchSetup(si, name)
    SelectVmotionNic(si, vnic)
    CheckExpectedWOLStatus(si, False)
    # Now add a wol capable pnic to the switch
    AttachPnic(si, name, pnic)
    # Hack, the uplink bounces so the first time around we might not read the
    # final state. Redesign this using the pc
    time.sleep(2)
    CheckExpectedWOLStatus(si, True)
    CleanupVswitchSetup(si, name, vnic)

def main(argv):
    """
    Tests WOL capability checks on the host
    A host is expected to report itself as WOL capable if there is atleast one
    WOL capable uplink backing a vmotion interface.
    Note: The test will not run if there is no free wol capable uplink to play
    around with
    """
    options = get_options()
    si = Connect(host=options.host,
                 user=options.user,
                 version="vim.version.version9",
                 pwd=options.password)
    atexit.register(Disconnect, si)
    freePnics = checkInitialState(si)
    if (len(freePnics) == 0):
        print("No free uplinks to test with")
    TestVswitchWOL(si, freePnics[0], options.name)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
