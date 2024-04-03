#!/usr/bin/python

#
# Example -
#  $VMTREE/vim/py/py.sh  $VMTREE/vim/py/tests/iSCSI_IPv6.py -h "10.112.187.15" -u "root" -p ""
#

from __future__ import print_function

import sys
import getopt
import re
import copy

from pyVmomi import Vim
from pyVmomi import Vmodl
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm, folder, invt, host
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import atexit

supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                  (["u:", "user="], "root", "User name", "user"),
                  (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                  (["n:", "name="], "vmhba2", "HBA name", "name"),
                  (["K:", "hba="], "key-vim.host.InternetScsiHba-vmhba2", "HBA Key", "key") ]

supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage") ]

args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
if args.GetKeyValue("usage") == True:
   args.Usage()
   sys.exit(0)

# Connect
si = SmartConnect(host=args.GetKeyValue("host"),
                  user=args.GetKeyValue("user"),
                  pwd=args.GetKeyValue("pwd"))
atexit.register(Disconnect, si)

key = args.GetKeyValue("key")
name = args.GetKeyValue("name")

configMgr = host.GetHostConfigManager(si);
storageSystem = configMgr.GetStorageSystem();

storageDeviceInfo = None

def GetHBA():
   storageDeviceInfo = storageSystem.GetStorageDeviceInfo();
   for h in storageDeviceInfo.GetHostBusAdapter():
      if h.key == key:
         return h

hba = GetHBA()
if hba is None:
   print("HBA %s not found!" % key)
   sys.exit(0)

caps = hba.ipCapabilities
print(caps)

def main():
   testIPv4()
   testIPv6()
   print("\n\n ********* Congratulations, all tests passed ***********\n\n")


def testIPv4():
   print("\n\n********** IPv4 Testing **********\n")

   print("Positive: Try to disable IPv4")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipProps.SetIpv4Enabled(False);

   try:
      storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
      h = GetHBA()
      if not h.ipProperties.ipv4Enabled:
         print("Passed")
      else:
         print("Failed")
         print(h.ipProperties)
         sys.exit(1)
   except Exception as e:
      print(e)
      print("Failed!")
      sys.exit(1)

   print("Positive: Try to set IPv4 address without setting IPv4Enabled to true")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipProps.SetAddress("192.168.1.10")
   ipProps.SetSubnetMask("255.255.255.0")

   try:
      storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
      h = GetHBA()
      if h.ipProperties.address == "192.168.1.10":
         print("Passed")
      else:
         print(h.ipProperties)
         print("Failed!")
         sys.exit(1)
   except Exception as e:
      print(e)
      print("Failed!")
      sys.exit(1)

   print("Positive: Try to set DHCPv4")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipProps.SetIpv4Enabled(True);
   ipProps.SetDhcpConfigurationEnabled(True)

   try:
      storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
      h = GetHBA()
      if h.ipProperties.dhcpConfigurationEnabled:
         print("Passed")
      else:
         print(h.ipProperties)
         print("Failed!")
         sys.exit(1)
   except Exception as e:
      print(e)
      print("Failed!")
      sys.exit(1)

   print("Positive: Try to disable DHCPv4 (without specifying IPv4Enabled)")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipProps.SetDhcpConfigurationEnabled(False)
   ipProps.SetAddress("192.168.1.11")
   ipProps.SetSubnetMask("255.255.255.0")

   try:
      storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
      h = GetHBA()
      if h.ipProperties.dhcpConfigurationEnabled == False and h.ipProperties.address == "192.168.1.11":
         print("Passed")
      else:
         print(h.ipProperties)
         print("Failed!")
         sys.exit(1)
   except Exception as e:
      print(e)
      print("Failed!")
      sys.exit(1)


   print("Negative: Try to set only address. It should fail.")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipProps.SetIpv4Enabled(True);
   ipProps.SetAddress("192.168.1.10")

   try:
      storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
      print("Failed!")
      sys.exit(1)
   except Exception as e:
      print(e)
      print("Passed")


def removeAllIPv6Address():
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipv6Props = Vim.Host.InternetScsiHba.IPv6Properties()
   ipProps.SetIpv6Enabled(True);

   address = []

   h = GetHBA()
   for aR in h.ipProperties.ipv6properties.iscsiIpv6Address:
      if aR.origin == "Static":
         a = Vim.Host.InternetScsiHba.IscsiIpv6Address()
         a.SetAddress(aR.address);
         a.SetPrefixLength(aR.prefixLength)
         a.SetOrigin(aR.origin)
         a.SetOperation("remove")
         address.append(a)

   print(address)

   ipv6Props.SetIscsiIpv6Address(address)
   ipProps.SetIpv6properties(ipv6Props);

   try:
      storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
      print("Passed")
   except Exception as e:
      print(e)
      print("Failed!")
      sys.exit(1)


def testIPv6():
   print("\n\n********** IPv6 Testing **********\n")

   print("Positive: Try to disable IPv6")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipProps.SetIpv6Enabled(False);

   try:
      storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
      h = GetHBA()
      if not h.ipProperties.ipv6Enabled:
         print("Passed")
      else:
         print("Failed")
         print(h.ipProperties)
         sys.exit(1)
   except Exception as e:
      print(e)
      print("Failed!")
      sys.exit(1)

   print("Positive: Try to set link local address")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipv6Props = Vim.Host.InternetScsiHba.IPv6Properties()
   ipProps.SetIpv6Enabled(True);
   ipProps.SetIpv6properties(ipv6Props);
   ipv6Props.SetIpv6LinkLocalAutoConfigurationEnabled(True);

   if (caps.ipv6LinkLocalAutoConfigurationSettable):
      print("\tIPv6 auto link local is supported, should be able to set it.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         h = GetHBA()
         if h.ipProperties.ipv6Enabled and h.ipProperties.ipv6properties.ipv6LinkLocalAutoConfigurationEnabled:
            print("Passed")
         else:
            print("Failed")
            print(h.ipProperties)
            sys.exit(1)
      except Exception as e:
         print(e)
         print("Failed!")
         sys.exit(1)
   else:
      print("\tIPv6 auto link local is not supported, auto link local configuration should fail.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         print("Failed")
         sys.exit(1)
      except Exception as e:
         print(e)
         print("Passed")

   print("Positive: Try to disable link local address")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipv6Props = Vim.Host.InternetScsiHba.IPv6Properties()
   ipProps.SetIpv6properties(ipv6Props);
   ipv6Props.SetIpv6LinkLocalAutoConfigurationEnabled(False);

   if (caps.ipv6LinkLocalAutoConfigurationSettable):
      print("\tIPv6 auto link local is supported, should be able to disable it.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         h = GetHBA()
         if not h.ipProperties.ipv6properties.ipv6LinkLocalAutoConfigurationEnabled:
            print("Passed")
         else:
            print("Failed")
            print(h.ipProperties)
            sys.exit(1)
      except Exception as e:
         print(e)
         print("Failed!")
         sys.exit(1)
   else:
      print("\tIPv6 auto link local is not supported, auto link local configuration should fail.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         print("Failed")
         sys.exit(1)
      except Exception as e:
         print(e)
         print("Passed")

   print("Positive: Try to set DHCPv6")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipv6Props = Vim.Host.InternetScsiHba.IPv6Properties()
   ipProps.SetIpv6Enabled(True);
   ipProps.SetIpv6properties(ipv6Props);
   ipv6Props.SetIpv6DhcpConfigurationEnabled(True);

   if (caps.ipv6DhcpConfigurationSettable):
      print("\tIPv6 DHCP is supported, should be able to set DHCPv6.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         h = GetHBA()
         if h.ipProperties.ipv6properties.ipv6DhcpConfigurationEnabled:
            print("Passed")
         else:
            print("Failed")
            print(h.ipProperties)
            sys.exit(1)
      except Exception as e:
         print(e)
         print("Failed!")
         sys.exit(1)
   else:
      print("\tIPv6 DHCP is not supported, DHCPv6 configuration should fail.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         print("Failed")
         sys.exit(1)
      except Exception as e:
         print(e)
         print("Passed")

   print("Positive: Try to set IPv6 router advertisement (without specifying IPv6Enabled)")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipv6Props = Vim.Host.InternetScsiHba.IPv6Properties()
   ipProps.SetIpv6properties(ipv6Props);
   ipv6Props.SetIpv6RouterAdvertisementConfigurationEnabled(True);

   if (caps.ipv6RouterAdvertisementConfigurationSettable):
      print("\tIPv6 Router Adv. is supported, should be able to set it.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         h = GetHBA()
         if h.ipProperties.ipv6properties.ipv6RouterAdvertisementConfigurationEnabled:
            print("Passed")
         else:
            print("Failed")
            print(h.ipProperties)
            sys.exit(1)
      except Exception as e:
         print(e)
         print("Failed!")
         sys.exit(1)
   else:
      print("\tIPv6 Router Adv. is not supported, Router Adv. configuration should fail.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         print("Failed")
         sys.exit(1)
      except Exception as e:
         print(e)
         print("Passed")

   print("Positive: Try to disable IPv6 router advertisement (without specifying IPv6Enabled)")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipv6Props = Vim.Host.InternetScsiHba.IPv6Properties()
   ipProps.SetIpv6properties(ipv6Props);
   ipv6Props.SetIpv6RouterAdvertisementConfigurationEnabled(False);

   if (caps.ipv6RouterAdvertisementConfigurationSettable):
      print("\tIPv6 Router Adv. is supported, should be able to disable it.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         h = GetHBA()
         if not h.ipProperties.ipv6properties.ipv6RouterAdvertisementConfigurationEnabled:
            print("Passed")
         else:
            print("Failed")
            print(h.ipProperties)
            sys.exit(1)
      except Exception as e:
         print(e)
         print("Failed!")
         sys.exit(1)
   else:
      print("\tIPv6 Router Adv. is not supported, Router Adv. configuration should fail.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         print("Failed")
         sys.exit(1)
      except Exception as e:
         print(e)
         print("Passed")

   print("Positive: Try to set IPv6 DHCP and router advertisement both")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipv6Props = Vim.Host.InternetScsiHba.IPv6Properties()
   ipProps.SetIpv6Enabled(True);
   ipProps.SetIpv6properties(ipv6Props);
   ipv6Props.SetIpv6RouterAdvertisementConfigurationEnabled(True);
   ipv6Props.SetIpv6DhcpConfigurationEnabled(True);

   if (caps.ipv6DhcpConfigurationSettable and
       caps.ipv6RouterAdvertisementConfigurationSettable):
      print("\tBoth methods are supported. Should be able to set them at the same time.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         h = GetHBA()
         if h.ipProperties.ipv6properties.ipv6RouterAdvertisementConfigurationEnabled and h.ipProperties.ipv6properties.ipv6DhcpConfigurationEnabled:
            print("Passed")
         else:
            print("Failed")
            print(h.ipProperties)
            sys.exit(1)
      except Exception as e:
         print(e)
         print("Failed!")
         sys.exit(1)
   else:
      print("\tEither of the method is not supported, simulteneous configuration should fail.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         print("Failed")
         sys.exit(1)
      except Exception as e:
         print(e)
         print("Passed")

   print("Positive: Try to set link local address")
   removeAllIPv6Address()
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipv6Props = Vim.Host.InternetScsiHba.IPv6Properties()
   ipProps.SetIpv6Enabled(True);

   address = []

   a = Vim.Host.InternetScsiHba.IscsiIpv6Address()
   a.SetAddress("FE80::10");
   a.SetPrefixLength(64);
   a.SetOrigin("Static")
   a.SetOperation("add")
   address.append(a)

   ipv6Props.SetIpv6LinkLocalAutoConfigurationEnabled(False);
   ipv6Props.SetIscsiIpv6Address(address)
   ipProps.SetIpv6properties(ipv6Props);

   if (caps.ipv6LinkLocalAutoConfigurationSettable):
      print("\tIPv6 auto link local is supported, should be able to set it.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         print("Passed")
      except Exception as e:
         print(e)
         print("Failed!")
         sys.exit(1)
   else:
      print("\tIPv6 auto link local is not supported, auto link local configuration should fail.")
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         print("Failed")
         sys.exit(1)
      except Exception as e:
         print(e)
         print("Passed")


   print("Positive: Try to set static address")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipv6Props = Vim.Host.InternetScsiHba.IPv6Properties()
   ipProps.SetIpv6Enabled(True);

   a = Vim.Host.InternetScsiHba.IscsiIpv6Address()
   a.SetAddress("::192.168.100.10");
   a.SetPrefixLength(64);
   a.SetOrigin("Static")
   a.SetOperation("add")
   address = []
   address.append(a)

   ipv6Props.SetIscsiIpv6Address(address)
   ipProps.SetIpv6properties(ipv6Props);

   if (caps.ipv6DhcpConfigurationSettable):
      ipv6Props.SetIpv6DhcpConfigurationEnabled(False);

   if (caps.ipv6RouterAdvertisementConfigurationSettable):
      ipv6Props.SetIpv6RouterAdvertisementConfigurationEnabled(False);

   try:
      storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
      print("Passed")
   except Exception as e:
      print(e)
      print("Failed!")
      sys.exit(1)

   print("Negative: Try setting link local address and configuring auto method also. It should fail.")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipv6Props = Vim.Host.InternetScsiHba.IPv6Properties()
   ipProps.SetIpv6Enabled(True);

   a = Vim.Host.InternetScsiHba.IscsiIpv6Address()
   a.SetAddress("FE80::10");
   a.SetPrefixLength(64);
   a.SetOrigin("Static")
   a.SetOperation("add")
   address = []
   address.append(a)

   ipv6Props.SetIpv6LinkLocalAutoConfigurationEnabled(True);
   ipv6Props.SetIscsiIpv6Address(address)
   ipProps.SetIpv6properties(ipv6Props);

   try:
      storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
      print("Failed")
      sys.exit(1)
   except Exception as e:
      print(e)
      print("Passed")

   print("Negative: Try to set static address with either or both auto configuration methods enabled. It should fail.")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipv6Props = Vim.Host.InternetScsiHba.IPv6Properties()
   ipProps.SetIpv6Enabled(True);

   a = Vim.Host.InternetScsiHba.IscsiIpv6Address()
   a.SetAddress("::192.168.100.10");
   a.SetPrefixLength(64);
   a.SetOrigin("Static")
   a.SetOperation("add")
   address = []
   address.append(a)

   ipv6Props.SetIscsiIpv6Address(address)
   ipProps.SetIpv6properties(ipv6Props);

   if (caps.ipv6DhcpConfigurationSettable):
      ipv6Props.SetIpv6DhcpConfigurationEnabled(True);

   if (caps.ipv6RouterAdvertisementConfigurationSettable):
      ipv6Props.SetIpv6RouterAdvertisementConfigurationEnabled(True);

   if (caps.ipv6DhcpConfigurationSettable or
       caps.ipv6RouterAdvertisementConfigurationSettable) :
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         print("Failed")
         sys.exit(1)
      except Exception as e:
         print(e)
         print("Passed")
   else:
      print("\tInvalid test as both auto configuration methods can not be set. Passing the test case.")
      print("Passed")


   print("Negative: Try to set Default gateway6 along with any/both auto configuration methods enabled. It should fail.")
   ipProps = Vim.Host.InternetScsiHba.IPProperties()
   ipv6Props = Vim.Host.InternetScsiHba.IPv6Properties()
   ipProps.SetIpv6Enabled(True);
   ipProps.SetIpv6properties(ipv6Props);

   defaultGWSet = False
   DHCPSet = False
   RouterAdvSet = False

   if (caps.ipv6DhcpConfigurationSettable):
      DHCPSet = True
      ipv6Props.SetIpv6DhcpConfigurationEnabled(True);

   if (caps.ipv6RouterAdvertisementConfigurationSettable):
      RouterAdvSet = True;
      ipv6Props.SetIpv6RouterAdvertisementConfigurationEnabled(True);

   if (caps.ipv6DefaultGatewaySettable):
      defaultGWSet = True;
      ipv6Props.SetIpv6DefaultGateway("::192.168.1.1");

   runTest = False;
   if (defaultGWSet and (DHCPSet or RouterAdvSet)):
      runTest = True;

   if (runTest):
      try:
         storageSystem.UpdateInternetScsiIPProperties(name, ipProps);
         print("Failed")
         sys.exit(1)
      except Exception as e:
         print(e)
         print("Passed")
   else:
      print("\tInvalid test as both auto configuration methods can not be set. Passing the test case.")
      print("Passed")



# Start program
if __name__ == "__main__":
    main()
