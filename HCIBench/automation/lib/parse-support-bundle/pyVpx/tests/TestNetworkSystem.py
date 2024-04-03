#!/usr/bin/python

"""
   Properties
   ==========
   Name                 Type                               Value
   ====                 ====                               =====
   value                vim.CustomFieldsManager.Value[]
   availableField       vim.CustomFieldsManager.FieldDef[]
   capabilities         vim.host.NetCapabilities           capabilities
   networkInfo          vim.host.NetworkInfo               networkInfo
   offloadCapabilities  vim.host.NetOffloadCapabilities    offloadCapabilities
   networkConfig        vim.host.NetworkConfig             networkConfig
   dnsConfig            vim.host.DnsConfig                 dnsConfig
   ipRouteConfig        vim.host.IpRouteConfig             ipRouteConfig
   consoleIpRouteConfig vim.host.IpRouteConfig             Unset

   Methods
   =======
   Return Type                                    Name
   ===========                                    ====
   void                                           addPortGroup
   string                                         addVirtualNic
   void                                           addVirtualSwitch
   void                                           commitTransaction
   anyType                                        invokeHostTransactionCall: updatePhysicalNicLinkSpeed, updateNetworkConfig, updateIpRouteTableConfig, applyDvs, applyDVPort, updatePorts
   vim.host.NetworkSystem.HostOpaqueNetworkData[] performHostOpaqueNetworkDataOperation
   vim.host.PhysicalNic.NetworkHint[]             queryNetworkHint
   void                                           refresh
   void                                           removePortGroup
   void                                           removeVirtualNic
   void                                           removeVirtualSwitch
   void                                           setCustomValue
   void                                           updateConsoleIpRouteConfig
   void                                           updateDnsConfig
   void                                           updateIpRouteConfig
   void                                           updateIpRouteTableConfig
   vim.host.NetworkConfig.Result                  updateNetworkConfig
   void                                           updatePhysicalNicLinkSpeed
   void                                           updatePortGroup
   void                                           updateServiceConsoleVirtualNic
   void                                           updateVirtualNic
   void                                           updateVirtualSwitch
"""

import sys
import time
import atexit
import traceback
from optparse import OptionParser
from pyVim.connect import SmartConnect, Disconnect
from pyVim import folder, vm, host

from pyVmomi import vim, vmodl


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
    parser.add_option("-t", "--test",
                      help="The name of the subtest to run; otherwise all tests")
    parser.add_option("--nocleanup",
                      help="Dont do cleanup", action='store_true')
    parser.add_option("-s", "--vsName",
                      default="testvs",
                      help="Virtual switch name to use")
    parser.add_option("-g", "--pgName",
                      default="testPG",
                      help="Virtual port group name to use")
    parser.add_option("-v", "--vmName",
                      default="testVM",
                      help="Virtual machine name to use")
    (options, _) = parser.parse_args()
    return options

def cleanup(si, options, force=False):
   '''
      Try to remove everything possible.
      General cleanup, that can be called after every test.
      This should not throw or fail.
   '''

   if options.nocleanup and not force:
      print("Not doing cleanup as requested")
      return

   vm1 = folder.Find(options.vmName)
   if vm1 != None:
       try:
          vm.PowerOff(vm1)
       except Exception as e:
          pass
       vm.Destroy(vm1)

   networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
   try:
      networkSystem.RemoveVirtualSwitch(vswitchName=options.vsName)
   except Exception as e:
      pass

def FindVSwitch(si, vsName):
   '''
      Find a virtual switch in the NetworkSystem.
      This exercises the properties of the NetworkSystem MO, also.
   '''
   networkInfo = host.GetHostSystem(si).GetConfigManager().GetNetworkSystem().networkInfo
   vswitches = networkInfo.GetVswitch()
   for vswitch in vswitches:
      if vswitch.name == vsName:
         return vswitch
   return None


def FindPGroup(si, pgName):
   '''
      Find a port group in the NetworkSystem.
      This exercises the properties of the NetworkSystem MO, also.
   '''
   networkInfo = host.GetHostSystem(si).GetConfigManager().GetNetworkSystem().networkInfo
   pgroups = networkInfo.GetPortgroup()
   for portgroup in pgroups:
      if portgroup.GetSpec().GetName() == pgName:
         return portgroup
   return None


def TestAddVirtualSwitch(si, options):
   '''
      Test NetworkSystem.addVirtualSwitch.
      Check for possible exceptions.
   '''

   print("Testing vim.host.NetworkSystem.addVirtualSwitch")

   networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem

   print("Test1: Adding virtual switch " + options.vsName)
   networkSystem.AddVirtualSwitch(vswitchName=options.vsName)
   if not FindVSwitch(si, options.vsName):
     raise Exception("Unable to find the switch in the network info")
   print("Test1: Adding virtual switch: PASS")

   print("Test2: Adding virtual switch " + options.vsName + " again")
   try:
      networkSystem.AddVirtualSwitch(vswitchName=options.vsName)
      print("Test2: Adding virtual switch again: FAILED")
   except vim.fault.AlreadyExists as e:
      print("Test2: Adding virtual switch again failed with vim.fault.AlreadyExists as expected: PASS")
   else:
      raise Exception("Create duplicate vswitch didn't fail as expected")

   print("Test3: Adding virtual switch with name too big")
   try:
      # vswitchName with 33 characters - according to Vmodl maximum is 32
      networkSystem.AddVirtualSwitch(vswitchName="123456789012345678901234567890123")
      print("Test3: Adding virtual switch: FAILED")
   except vmodl.fault.InvalidArgument as e:
      print("Test3: Adding virtual switch failed with vim.fault.InvalidArgument as expected: PASS")
   else:
      raise Exception("Didn't fail as expected")


def TestAddPortGroup(si, options):
   '''
      Test NetworkSystem.addPortGroup.
      Check for possible exceptions.
   '''

   print("Testing vim.host.NetworkSystem.addPortGroup")
   networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
   # Setup
   networkSystem.AddVirtualSwitch(vswitchName=options.vsName)

   print("Test1: Adding port group " + options.pgName + " to virtual switch " + options.vsName)
   spec = vim.host.PortGroup.Specification(name=options.pgName,
                                           vlanId=0,
                                           vswitchName=options.vsName,
                                           policy=vim.host.NetworkPolicy())
   networkSystem.AddPortGroup(portgrp=spec)
   print("Test1: Add port group: PASS")

   print("Test2: Adding port group " + options.pgName + " again")
   try:
      networkSystem.AddPortGroup(spec)
      print("Test2: Adding port group again: FAILED")
   except vim.fault.AlreadyExists as e:
      print("Test2: Adding port group again failed with vim.fault.AlreadyExists as expected: PASS")
   else:
      raise Exception("Create duplicate pgroup didn't fail as expected")

   print("Test3: Adding port group " + options.pgName + " to missing vswitch")
   invalidSpec = vim.host.PortGroup.Specification(name=options.pgName + "Unique",
                                                  vlanId=0,
                                                  # vswitchName with 33 characters - according to Vmodl maximum is 32
                                                  vswitchName="123456789012345678901234567890123",
                                                  policy=vim.host.NetworkPolicy())
   try:
      networkSystem.AddPortGroup(invalidSpec)
      print("Test3: Adding port group to missing virtual switch: FAILED")
   except vim.fault.NotFound as e:
      print("Test3: Adding port group to missing virtual switch failed with vim.fault.NotFound as expected: PASS")
   else:
      raise Exception("Adding port group to missing virtual switch didn't fail as expected")

   print("Test4: Adding port group " + options.pgName + "4096 with vlanId=4096")
   invalidSpec = vim.host.PortGroup.Specification(name=options.pgName + "4096",
                                                  vlanId=4096,
                                                  vswitchName=options.vsName,
                                                  policy=vim.host.NetworkPolicy())
   try:
      networkSystem.AddPortGroup(invalidSpec)
      print("Test4: Adding port group with vlanId=4096: FAILED")
   except vmodl.fault.InvalidArgument as e:
      print("Test4: Adding port group with vlanId=4096 failed with vim.fault.InvalidArgument as expected: PASS")
   else:
      raise Exception("Adding port group with vlanId=4096 didn't fail as expected")


def TestRemovePortGroup(si, options):
   '''
      Test NetworkSystem.removePortGroup.
      Check for possible exceptions.
   '''

   print("Testing vim.host.NetworkSystem.removePortGroup")
   networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
   # Setup
   networkSystem.AddVirtualSwitch(vswitchName=options.vsName)
   spec = vim.host.PortGroup.Specification(name=options.pgName,
                                           vlanId=0,
                                           vswitchName=options.vsName,
                                           policy=vim.host.NetworkPolicy())
   networkSystem.AddPortGroup(portgrp=spec)

   print("Test1: Removing port group " + options.pgName)
   networkSystem.RemovePortGroup(options.pgName)
   print("Test1: Remove port group: PASS")


def TestRemoveVirtualSwitch(si, options):
   '''
      Test NetworkSystem.removeVirtualSwitch.
      Check for possible exceptions.
   '''

   print("Testing vim.host.NetworkSystem.removeVirtualSwitch")

   networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
   # Setup
   networkSystem.AddVirtualSwitch(vswitchName=options.vsName)

   print("Test1: Removing non-existent virtual switch")
   try:
      # Using this name, because TestAddVirtualSwitch guarantees that it can not be created
      networkSystem.RemoveVirtualSwitch(vswitchName="123456789012345678901234567890123")
      print("Test1: Removing non-existent virtual switch: FAILED")
   except vim.fault.NotFound as e:
      print("Test1: Removing non-existent virtual switch failed with vim.fault.NotFound as expected: PASS")
   else:
      raise Exception("Removing non-existent virtual switch didn't fail as expected")

   print("Test2: Removing virtual switch " + options.vsName)
   networkSystem.RemoveVirtualSwitch(vswitchName=options.vsName)
   print("Test2: Removing virtual switch: PASS")


def TestNetworkPolicy(si, options):
   print("Testing network policy")
   networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
   # Setup
   networkSystem.AddVirtualSwitch(vswitchName=options.vsName)

   pgSpec = vim.host.PortGroup.Specification(
      name=options.pgName,
      vlanId=0,
      vswitchName=options.vsName,
      policy = vim.host.NetworkPolicy(
         security=vim.host.NetworkPolicy.SecurityPolicy(
            allowPromiscuous=True,
            macChanges=True,
            forgedTransmits=True
         )
      )
   )

   print("Test 1: Adding port group %s with policy: %s" % (options.pgName, str(pgSpec.GetPolicy())))
   networkSystem.AddPortGroup(pgSpec)

   portgroup = FindPGroup(si, options.pgName)
   if not portgroup:
     raise Exception("Unable to find the port group in the network info")

   if not ValidateNetworkSecurityPolicy(pgSpec.GetPolicy().GetSecurity(),
                                        portgroup.GetComputedPolicy().GetSecurity()):
     raise Exception("NetworkSecurityPolicy config doesn't match runtime")
   print("Test 1: NetworkPolicy config matches runtime: PASS")


def CreateNetworkPolicy():
   return vim.host.NetworkPolicy(
      nicTeaming = vim.host.NetworkPolicy.NicTeamingPolicy(
         failureCriteria = vim.host.NetworkPolicy.NicFailureCriteria(
            checkSpeed = "minimum",
            checkDuplex = False,
            fullDuplex = False,
            checkErrorPercent = False,
            percentage = 0,
            speed = 10,
            checkBeacon = False
         ),
         reversePolicy = True,
         notifySwitches = False,
         rollingOrder = True,
         nicOrder = vim.host.NetworkPolicy.NicOrderPolicy(),
         policy = "loadbalance_srcid"
      ),
      security = vim.host.NetworkPolicy.SecurityPolicy(
         allowPromiscuous = True,
         macChanges = False,
         forgedTransmits = False
      ),
      shapingPolicy = vim.host.NetworkPolicy.TrafficShapingPolicy(
         enabled = False
      )
   )


def ValidateNetworkSecurityPolicy(inSecurityPolicy, outSecurityPolicy):
   def ValidateNetworkSecurityPolicyInt(inSecurityPolicy, outSecurityPolicy):
      if inSecurityPolicy:
         if outSecurityPolicy:
            if (inSecurityPolicy.allowPromiscuous != outSecurityPolicy.allowPromiscuous or
                inSecurityPolicy.macChanges != outSecurityPolicy.macChanges or
                inSecurityPolicy.forgedTransmits != outSecurityPolicy.forgedTransmits):
               return False
         else:
            return False
      elif outSecurityPolicy:
         return False
      return True
   if not ValidateNetworkSecurityPolicyInt(inSecurityPolicy, outSecurityPolicy):
      print('ValidateNetworkSecurityPolicy failed: inPolicy=%s\noutPolicy=%s' % (inSecurityPolicy, outSecurityPolicy))
      return False
   return True


def ValidateNetworkPolicy(inPolicy, outPolicy):
   def ValidateNetworkPolicyInt(inPolicy, outPolicy):
      inTeamingPolicy = inPolicy.GetNicTeaming()
      outTeamingPolicy = outPolicy.GetNicTeaming()
      if inTeamingPolicy:
         if outTeamingPolicy:
            if (inTeamingPolicy.reversePolicy != outTeamingPolicy.reversePolicy or
                inTeamingPolicy.policy != outTeamingPolicy.policy or
                inTeamingPolicy.notifySwitches != outTeamingPolicy.notifySwitches or
                inTeamingPolicy.rollingOrder != outTeamingPolicy.rollingOrder):
               return False
         else:
            return False
      elif outTeamingPolicy:
         return False

      inNicFC = inTeamingPolicy.GetFailureCriteria()
      outNicFC = outTeamingPolicy.GetFailureCriteria()
      if inNicFC:
         if outNicFC:
            if (inNicFC.checkSpeed != outNicFC.checkSpeed or
                inNicFC.speed != outNicFC.speed or
                inNicFC.checkDuplex != outNicFC.checkDuplex or
                inNicFC.fullDuplex != outNicFC.fullDuplex or
                inNicFC.checkErrorPercent != outNicFC.checkErrorPercent or
                inNicFC.percentage != outNicFC.percentage or
                inNicFC.checkBeacon != outNicFC.checkBeacon):
               return False
         else:
            return False
      elif outNicFC:
         return False

      inNicOrder = inTeamingPolicy.GetNicOrder()
      outNicOrder = outTeamingPolicy.GetNicOrder()
      if inNicOrder:
         if outNicOrder:
            if (inNicOrder.activeNic != outNicOrder.activeNic or
                inNicOrder.standbyNic != outNicOrder.standbyNic):
               return False
         else:
            return False
      elif outNicOrder:
         return False

      inSecurityPolicy = inPolicy.GetSecurity()
      outSecurityPolicy = outPolicy.GetSecurity()
      if not ValidateNetworkSecurityPolicy(inSecurityPolicy, outSecurityPolicy):
         return False

      inShapingPolicy = inPolicy.GetShapingPolicy()
      outShapingPolicy = outPolicy.GetShapingPolicy()
      if inShapingPolicy:
         if outShapingPolicy:
            if (inShapingPolicy.enabled != outShapingPolicy.enabled or
                inShapingPolicy.averageBandwidth != outShapingPolicy.averageBandwidth or
                inShapingPolicy.burstSize != outShapingPolicy.burstSize or
                inShapingPolicy.peakBandwidth != outShapingPolicy.peakBandwidth):
               return False
         else:
            return False
      elif outShapingPolicy:
         return False

      return True

   if not ValidateNetworkPolicyInt(inPolicy, outPolicy):
      print('ValidateNetworkPolicy failed: inPolicy=%s\noutPolicy=%s' % (inPolicy, outPolicy))
      return False
   return True


def TestDerivedNetworkPolicy(si, options):
   print("Testing derived NetworkPolicy for portgroup")
   networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem

   #TestDerivedNetworkPolicy AddVirtualSwitch
   vsSpec = vim.host.VirtualSwitch.Specification(
      mtu = 1500,
      numPorts = 100,
      policy = CreateNetworkPolicy()
   )
   print("Test 1: Adding virtual switch %s with policy: %s" % (options.vsName, str(vsSpec.GetPolicy())))
   networkSystem.AddVirtualSwitch(vswitchName=options.vsName, spec=vsSpec)

   #TestDerivedNetworkPolicy AddPortGroup
   pgSpec = vim.host.PortGroup.Specification(
      name = options.pgName,
      vlanId = 0,
      vswitchName = options.vsName,
      policy = vim.host.NetworkPolicy(
         nicTeaming = vim.host.NetworkPolicy.NicTeamingPolicy(
            failureCriteria = vim.host.NetworkPolicy.NicFailureCriteria()
         ),
         security = vim.host.NetworkPolicy.SecurityPolicy(),
         shapingPolicy = vim.host.NetworkPolicy.TrafficShapingPolicy(),
         offloadPolicy = vim.host.NetOffloadCapabilities()
      )
   )
   print("Test 1: Adding port group " + options.pgName + " to virtual switch " + options.vsName)
   networkSystem.AddPortGroup(pgSpec)

   #TestDerivedNetworkPolicy GetnetworkInfo
   portgroup = FindPGroup(si, options.pgName)
   if not portgroup:
     raise Exception("Unable to find the port group in the network info")

   if not ValidateNetworkPolicy(vsSpec.GetPolicy(),
                                portgroup.GetComputedPolicy()):
     raise Exception("Portgroup with derived NetworkPolicy config doesn't match runtime")
   print("Test 1: Portgroup with derived NetworkPolicy config matches runtime: PASS")


def ValidateVirtualSwitchSpec(inSpec, outSpec):
   if (inSpec.GetMtu() != outSpec.GetMtu() or
       inSpec.GetNumPorts() != outSpec.GetNumPorts()):
      print('ValidateVirtualSwitchSpec failed: inSpec=%s\outSpec=%s' % (vsSpec, vswitch))
      return False
   return True


def TestUpdateVirtualSwitch(si, options):
   print("Testing update virtual switch")
   networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem

   #TestUpdateVirtualSwitch: Setup
   vsSpec = vim.host.VirtualSwitch.Specification(
      mtu = 1500,
      numPorts = 100
   )
   print("Adding virtual switch %s with 100 ports and MTU=1500" % (options.vsName))
   networkSystem.AddVirtualSwitch(vswitchName=options.vsName, spec=vsSpec)

   print("Test 1: Updating the virtual switch to 150 ports and MTU=1000")
   vsNewSpec = vim.host.VirtualSwitch.Specification(
      mtu = 1280,
      numPorts = 150
   )
   networkSystem.UpdateVirtualSwitch(vswitchName=options.vsName, spec=vsNewSpec)
   vswitch = FindVSwitch(si, options.vsName)
   if not vswitch:
      raise Exception("Virtual switch not found in NetworkInfo")
   if not ValidateVirtualSwitchSpec(vsNewSpec, vswitch.GetSpec()):
      raise Exception("Virtual switch spec doesn't match runtime")
   print("Test 1: Updating the virtual switch: PASS")

   print("Test 2: Updating non-existent virtual switch")
   try:
      # Using this name, because TestAddVirtualSwitch guarantees that it can not be created
      networkSystem.UpdateVirtualSwitch(vswitchName="123456789012345678901234567890123", spec=vsSpec)
      print("Test 2: Updating non-existent virtual switch: FAILED")
   except vim.fault.NotFound as e:
      print("Test 2: Updating non-existent virtual switch failed with vim.fault.NotFound as expected: PASS")
   else:
      raise Exception("Updating non-existent virtual switch didn't fail as expected")

   print("Test 3: Updating virtual switch with wrong values")
   try:
      vsNewSpec = vim.host.VirtualSwitch.Specification(
         mtu = 1, # minimum is 1280
         numPorts = 150
      )
      networkSystem.UpdateVirtualSwitch(vswitchName=options.vsName, spec=vsNewSpec)
      print("Test 3: Updating virtual switch with wrong values: FAILED")
   except vim.fault.PlatformConfigFault as e:
      print("Test 3: Updating virtual switch with wrong values failed with vim.fault.PlatformConfigFault as expected: PASS")
   else:
      raise Exception("Updating virtual switch with wrong values didn't fail as expected")


def ValidatePortGroupSpec(inSpec, portgroup):
   if (inSpec.GetName() != portgroup.GetSpec().GetName() or
       inSpec.GetVswitchName() != portgroup.GetSpec().GetVswitchName() or
       inSpec.GetVlanId() != portgroup.GetSpec().GetVlanId()):
      return False
   if not ValidateNetworkPolicy(inSpec.GetPolicy(), portgroup.GetComputedPolicy()):
      return False
   return True


def TestUpdatePortGroup(si, options):
   print("Testing update port group")
   networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem

   # Setup
   networkSystem.AddVirtualSwitch(vswitchName=options.vsName)

   spec = vim.host.PortGroup.Specification(name=options.pgName,
                                           vlanId=0,
                                           vswitchName=options.vsName,
                                           policy=vim.host.NetworkPolicy())
   networkSystem.AddPortGroup(portgrp=spec)

   newName = options.pgName + "2"
   print("Test1: Try updating port group " + options.pgName + " in virtual switch " + options.vsName)
   newSpec = vim.host.PortGroup.Specification(name=newName,
                                              vlanId=1,
                                              vswitchName=options.vsName,
                                              policy=CreateNetworkPolicy()
                                             )
   networkSystem.UpdatePortGroup(pgName=options.pgName, portgrp=newSpec)
   portgroup = FindPGroup(si, newName)
   if not portgroup:
      raise Exception("Unable to find the port group in the network info")
   if not ValidatePortGroupSpec(newSpec, portgroup):
      raise Exception("Port group spec doesn't match runtime")
   print("Test1: Updating port group: PASS")

   print("Test 2: Updating non-existent port group")
   try:
      # Using this name, because TestAddVirtualSwitch guarantees that it can not be created
      networkSystem.UpdatePortGroup(pgName=options.pgName + "3", portgrp=newSpec)
      print("Test 2: Updating non-existent port group: FAILED")
   except vim.fault.NotFound as e:
      print("Test 2: Updating non-existent port group failed with vim.fault.NotFound as expected: PASS")
   else:
      raise Exception("Updating non-existent port group didn't fail as expected")


def main(argv):
   """

   """
   options = get_options()

   si = SmartConnect(host=options.host,
                     user=options.user,
                     pwd=options.password)
   atexit.register(Disconnect, si)

   networkSystem = host.GetHostSystem(si).GetConfigManager().networkSystem
   # Just to be sure, but testing vim.host.NetworkSystem.Refresh, also.
   networkSystem.Refresh()

   result = -1
   try:
      print("Check for remnants from previous run")
      cleanup(si, options, force=True)
   except Exception as e:
      print(e)
      raise # cleanup should never throw

   try:
      if options.test:
         globals()["Test" + options.test](si, options)
         cleanup(si, options)
      else:
         TestAddVirtualSwitch(si, options)
         cleanup(si, options)
         result = -2
         TestAddPortGroup(si, options)
         cleanup(si, options)
         result = -3
         TestRemovePortGroup(si, options)
         cleanup(si, options)
         result = -4
         TestRemoveVirtualSwitch(si, options)
         cleanup(si, options)
         result = -5
         TestNetworkPolicy(si, options)
         cleanup(si, options)
         result = -6
         TestDerivedNetworkPolicy(si, options)
         cleanup(si, options)
         result = -7
         TestUpdateVirtualSwitch(si, options)
         cleanup(si, options)
         result = -8
         TestUpdatePortGroup(si, options)
         cleanup(si, options)

      result = 0
      print("DONE.")
   except Exception as e:
      print("Got exception during execution")
      print(e)
      traceback.print_exc()
      print("FAILED.")

   return result

# Start program
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
