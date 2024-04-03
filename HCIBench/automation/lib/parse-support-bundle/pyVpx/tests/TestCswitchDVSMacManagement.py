#!/usr/bin/python

from __future__ import print_function

import sys
from pyVmomi import Vim, VmomiSupport
from pyVmomi.VmomiSupport import LinkResolver, ResolveLinks
from pyVim.connect import SmartConnect, Disconnect
from optparse import OptionParser
from pyVim import folder
from pyVim import vm, host
from pyVim import arguments
from pyVim.helpers import Log, StopWatch
import atexit
import struct
import array
import os
import subprocess
import copy
import traceback

datastore=None

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
                      default="22 55 73 88 00 00 00 00-00 00 00 00 00 01 00 55",
                      help="DVSwitch id")
    parser.add_option("-n", "--name", default="cswitchDvs",
                      help="DVSwitch name")
    parser.add_option("-v", "--vmName", default="dvstestVMone",
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

def CfgMacLearningForgedTransmits(key, operation, type):
   pgConfigSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVPortgroupConfigSpec()
   pgConfigSpec.SetKey(key)
   pgConfigSpec.SetOperation(operation)
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
   PortCfg = Vim.Dvs.VmwareDistributedVirtualSwitch.VmwarePortConfigPolicy()
   macManagementPolicy = Vim.Dvs.VmwareDistributedVirtualSwitch.MacManagementPolicy()
   macLearningPolicy = Vim.Dvs.VmwareDistributedVirtualSwitch.MacLearningPolicy()
   macManagementPolicy.allowPromiscuous = False;
   macManagementPolicy.forgedTransmits = True;
   macLearningPolicy.enabled = True;
   macLearningPolicy.limit = 1024;
   macLearningPolicy.limitPolicy = "DROP";
   macManagementPolicy.macLearningPolicy = macLearningPolicy;
   PortCfg.SetMacManagementPolicy(macManagementPolicy)
   spec.SetDefaultPortConfig(PortCfg)
   pgConfigSpec.SetSpecification(spec)
   return pgConfigSpec

def CfgMacLearningWithoutForgedTransmits(key, operation, type):
   pgConfigSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVPortgroupConfigSpec()
   pgConfigSpec.SetKey(key)
   pgConfigSpec.SetOperation(operation)
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
   PortCfg = Vim.Dvs.VmwareDistributedVirtualSwitch.VmwarePortConfigPolicy()
   macManagementPolicy = Vim.Dvs.VmwareDistributedVirtualSwitch.MacManagementPolicy()
   macLearningPolicy = Vim.Dvs.VmwareDistributedVirtualSwitch.MacLearningPolicy()
   macManagementPolicy.allowPromiscuous = False;
   macManagementPolicy.forgedTransmits = False;
   macLearningPolicy.enabled = True;
   macLearningPolicy.limit = 1024;
   macLearningPolicy.limitPolicy = "DROP";
   macManagementPolicy.macLearningPolicy = macLearningPolicy;
   PortCfg.SetMacManagementPolicy(macManagementPolicy)
   spec.SetDefaultPortConfig(PortCfg)
   pgConfigSpec.SetSpecification(spec)
   return pgConfigSpec

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

def GetPnics(nics):
    if nics == None:
        return []
    nics = nics.split(',')
    return nics

def TestMacManagementProp():
   prodSpec = Vim.Dvs.ProductSpec(vendor="VMware", version = "6.6.0")
   # create a port for the early binding case.
   port1 = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
        portKey = "1000",
        name = "1000",
        connectionCookie = 5)
   uplinkPort1 = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
        portKey = "1",
        name = "uplink1",
        connectionCookie = 1)

   createSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSCreateSpec(
        uuid = options.uuid,
        name = options.name,
        backing = Vim.Dvs.HostMember.PnicBacking(),
        productSpec = prodSpec,
        maxProxySwitchPorts = 32,
        port=[port1, uplinkPort1],
        uplinkPortKey=["1"],
        modifyVendorSpecificDvsConfig = True,
        modifyVendorSpecificHostMemberConfig = False,
        switchIpAddress = "10.22.30.41"
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
   content = si.RetrieveContent()
   rootFolder = content.GetRootFolder()
   dc = rootFolder.childEntity[0]
   networkFolder = dc.networkFolder
   print('networkFolder %s' % networkFolder)
   dvs = None
   for child in networkFolder.childEntity:
      if (isinstance(child, Vim.DistributedVirtualSwitch) and child.uuid == options.uuid):
         dvs = child
   portgroupList = []
   pg1 = CfgMacLearningForgedTransmits("pg1", "add", "ephemeral")
   portgroupList.append(pg1)
   dvsManager.UpdateDVPortgroups(options.uuid, portgroupList)
   pg2 = CfgMacLearningWithoutForgedTransmits("pg2", "add", "ephemeral")
   portgroupList.append(pg2)

def main(argv):
    """
    Test does the following.
    - Creates a DVS.
      Creates a dvport and an uplink port
      Verifies mac management policy scenarios
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
    try:
       TestMacManagementProp()
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
