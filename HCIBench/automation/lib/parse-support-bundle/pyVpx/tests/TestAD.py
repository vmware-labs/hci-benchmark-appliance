#!/usr/bin/python

from __future__ import print_function

import sys
import time
import getopt
#import pyVmacore
from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim.host import GetHostSystem
from pyVim import arguments
import atexit

status = "PASS"
# The host should automatically add ESX Admins group from AD
userGroup = "esx admins"

#
# Test for the ActiveDirectory related routines of AuthenticationManager
#

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["d:", "domain="], "tesla.kozaboza.com", "AD domain",
                      "domain"),
                     (["x:", "aduser="], "administrator", "AD username",
                      "aduser"),
                     (["y:", "adpass="], "ca$hc0w", "Password for the AD user",
                      "adpass"),
                     (["z:", "adname="], "tesla", "AD domain name", "adname"),
                     (["P:", "P="], "10.23.33.251",
                      "IP of the domain controller", "ip"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Connect
   si = SmartConnect(host=args.GetKeyValue("host"),
                     user=args.GetKeyValue("user"),
                     pwd=args.GetKeyValue("pwd"))
   atexit.register(Disconnect, si)

   global status
   status = "PASS"

   # Set primary dns
   try:
      host = GetHostSystem(si)
      networkSystem = host.GetConfigManager().GetNetworkSystem()
      dnsConfig = networkSystem.dnsConfig
      ipAddress = args.GetKeyValue("ip")
      dnsAddress = dnsConfig.address
      if len(dnsAddress) > 0:
         dnsConfig.address[0] = ipAddress
      else:
         dnsConfig.address.append(ipAddress)
      networkSystem.UpdateDnsConfig(dnsConfig)
   except Exception as e:
      print("Can't change the primary dns of the host...")
      print("Caught exception: " + str(e))
      status = "FAIL"
      return

   # Process command line
   numiter = int(args.GetKeyValue("iter"))

   for i in range(numiter):
      try:
         host = GetHostSystem(si)
         authMan = host.GetConfigManager().GetAuthenticationManager()
         stores = authMan.GetSupportedStore()

         ad = None
         for i in stores:
            if isinstance(i, Vim.Host.ActiveDirectoryAuthentication):
               ad = i

         if ad == None:
            print("Can't find the ActiveDirectoryAuthenticationManager...")
            status = "FAIL"
            return


         #
         # try to join the domain with invalid credentials, should fail
         #
         try:
            task = ad.JoinDomain(args.GetKeyValue("domain"), "qwerty", "uiop")
            WaitForTask(task)
            print("Joined a domain with wrong credentials...")
            status = "FAIL"
            return
         except Exception:
            pass

         #
         # try to join the domain with the supplied credentials, should succeed
         #
         try:
            task = ad.JoinDomain(args.GetKeyValue("domain"), args.GetKeyValue("aduser"), args.GetKeyValue("adpass"))
            WaitForTask(task)
         except Exception as e:
            print("Can't join the domain...")
            raise

         #
         # try to join the domain again, should fail
         #
         try:
            task = ad.JoinDomain(args.GetKeyValue("domain"), args.GetKeyValue("aduser"), args.GetKeyValue("adpass"))
            WaitForTask(task)
            print("Rejoining the domain should have failed...")
            status = "FAIL"
            return
         except Exception:
            pass

         #
         # try to lookup aduser in the user dir, there should be at least one match.
         # don't use exact match because it won't go through ldap, but through getpwnam_r.
         #
         ud = si.RetrieveServiceContent().GetUserDirectory()
         searchResults = \
            ud.RetrieveUserGroups(args.GetKeyValue("domain"), # domain
                                  userGroup,
                                  None, # belongsToGroup
                                  None, # belongsToUser
                                  False, # exactMatch
                                  True, # findUsers
                                  True) # findGroups
         if len(searchResults) < 1:
            print("User search failed...")
            status = "FAIL"
            return

         #
         # give userGroup read only permissions
         #
         permission = Vim.AuthorizationManager.Permission()
         permission.group = True
         permission.principal = args.GetKeyValue("adname") + "\\" + userGroup
         permission.propagate = True
         permission.roleId = -2 # ROLE_READONLY_ID

         permissionArr = [permission]

         am = si.RetrieveServiceContent().GetAuthorizationManager()
         rf = si.RetrieveServiceContent().GetRootFolder()
         am.SetEntityPermissions(rf, permissionArr)

         #
         # try to leave the domain with force=false, should fail
         #
         try:
            task = ad.LeaveCurrentDomain(False)
            WaitForTask(task)
            print("Leaving the domain should have failed...")
            status = "FAIL"
            return
         except Exception:
            pass

         #
         # try to leave the domain with force=true, should succeed
         #
         try:
            task = ad.LeaveCurrentDomain(True)
            WaitForTask(task)
         except Exception:
            print("Can't leave the domain...")
            raise

      except Exception as e:
         print("Caught exception : " + str(e))
         status = "FAIL"

# Start program
if __name__ == "__main__":
    main()
    print("Test status: " + status)
    print("ActiveDirectory Tests completed")
