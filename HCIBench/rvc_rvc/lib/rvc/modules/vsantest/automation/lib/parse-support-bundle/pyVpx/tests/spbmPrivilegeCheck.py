#!/usr/bin/python

"""Script to test SPBM Privilege validator.
"""

from __future__ import print_function

import Cookie
import getopt
import sys
from pyVmomi import Pbm, SoapStubAdapter, Vim, VmomiSupport
from pyVim import invt, connect, account
from pyVim.helpers import Log
import string

def modifyPermissions(authMgr, entity, userName, roleId, add):
   perm = Vim.AuthorizationManager.Permission()
   perm.principal = userName
   perm.group = False
   perm.propagate = True
   perm.roleId = roleId
   if (add):
      authMgr.SetEntityPermissions(entity=entity, permission=[perm])
   else:
      authMgr.RemoveEntityPermission(entity=entity, user=userName, isGroup=False)


def GetPbmServiceContent(vcHost, vcUser, vcPwd):
   try:
      Log(">>>>> Connecting to PBM: host=%s user=%s pwd=%s" % (vcHost, vcUser, vcPwd))
      vpxdStub = SoapStubAdapter(vcHost, path = "/sdk",
                              version = "vim.version.version9")

      si = Vim.ServiceInstance("ServiceInstance", vpxdStub)
      sm = si.RetrieveContent().GetSessionManager()

      sm.Login(vcUser, vcPwd, None)
      sessionCookie = vpxdStub.cookie.split('"')[1]
      VmomiSupport.GetRequestContext()["vcSessionCookie"] = sessionCookie

      pbmStub = SoapStubAdapter(host=vcHost, ns = "internalpbm/1.0",
                                path = "/pbm/sdk",
                                poolSize=0)
      pbmSi = Pbm.ServiceInstance("ServiceInstance", pbmStub)
      return pbmSi.RetrieveContent()
   except Exception as e:
      Log("!!!!! Failed to connect to PBM...")
      raise e


def validateAccess(host, user, pwd, expectError):
   try:
      serviceContent = GetPbmServiceContent(host, user, pwd)
      Log(">>>>> Connected to PBM")

      profileManager = serviceContent.profileManager
      Log(">>>>> got profileManager")
      storageType = Pbm.profile.ResourceType()
      storageType.SetResourceType("STORAGE")
      profileIds = profileManager.QueryProfile(storageType, "REQUIREMENT")
      Log(">>>>> profileManager 0 returned %s profiles " % len(profileIds))

   except Exception as e:
      Log(">>>>> Expect Error %s, exception: %s" % (expectError, e))
      if (not expectError):
         raise e
      return
   if (expectError):
      raise Exception ("!!!!!! Profilemanager should not return profiles. Exception expected.")


def runTest(vcHost, rootUser, rootPwd, testUser, testPassword):
   noPbmAdmin = None
   onlyPbm = None
   try:
      Log(">>>>> connecting pbm using: root")
      si = connect.Connect(host = vcHost, user=rootUser, pwd=rootPwd,
                  service="vpx", path="/sdk",
                  version="vim.version.version9")
      authMgr = account.GetAuthorizationManager(si)
      rootFolder = invt.GetRootFolder(si)

      pbmPrivileges = [
            "StorageProfile.View",
            "StorageProfile.Update"
            ]

      Log(">>>>>> creating role: NoPbmAdmin")
      # Everything but StorageProfile permissions
      noPbmAdmin = account.CreateRole("NoPbmAdmin", basedOnRoleName="Admin",
                              privsToAdd = [], privsToRemove = pbmPrivileges)

      Log(">>>>> creating role: OnlyPbm")
      # Only Storage profile permissions
      onlyPbm = account.CreateRole("OnlyPbm", basedOnRoleName = None,
                              privsToAdd = pbmPrivileges, privsToRemove = [])

      Log(">>>>> adding role : NoPbmAdmin to user")
      modifyPermissions(authMgr, rootFolder, testUser, noPbmAdmin, add = True)
      Log(">>>>> validating access with role : NoPbmAdmin")
      validateAccess(vcHost, testUser, testPassword, expectError = True)
      Log(">>>>> removing role : NoPbmAdmin from user")
      modifyPermissions(authMgr, rootFolder, testUser, noPbmAdmin, add = False)

      Log(">>>>> adding role : OnlyPbm to user")
      modifyPermissions(authMgr, rootFolder, testUser, onlyPbm, add = True)
      Log(">>>>> validating access with role : OnlyPbm")
      validateAccess(vcHost, testUser, testPassword, expectError = False)
      Log(">>>>> removing role : OnlyPbm from user")
      modifyPermissions(authMgr, rootFolder, testUser, onlyPbm, add = False)

      Log(">>>>> Done")

   except Exception as e:
      Log("!!!!!! Exception: %s " % e)
      raise e
   finally:
      if (noPbmAdmin):
         Log(">>>>> removing role: NoPbmAdmin")
         account.RemoveRole(noPbmAdmin, failIfUsed = False)
      if (onlyPbm):
         Log(">>>>> removing role: OnlyPbm")
         account.RemoveRole(onlyPbm, failIfUsed = False)


def Usage(msg="Unknown error"):
   print("Error: " + msg)
   print("Usage: spbmPrivilegeCheck [--u root_user] [--p root_password] --tu test_user --tp test_user_password vc_host_ip")
   sys.exit(1)


def main():
   vcUser="Administrator@vsphere.local"
   vcPwd="vmware"
   testUser=None
   testPwd=None

   try:
      opts,args = getopt.getopt(sys.argv[1:], None, ["u=", "p=", "tu=", "tp="])
   except getopt.GetoptError as err:
      print(str(err))
      Usage("Unknown arguments")

   if len(args) == 0:
      Usage("VC Host not specified")
   vcHost = args[0]

   for a,v in opts:
      if a=="-u":
         vcUser = v
      if a=="-p":
         vcPwd = v
      if a=="--tu":
         testUser = v
      if a=="--tp":
         testPwd = v
   Log(">>>>> test user: %s test pwd: %s " % (testUser, testPwd))
   if testUser is None or testPwd is None:
       Usage("test user/password not specified")

   runTest(vcHost, vcUser, vcPwd, testUser, testPwd)


# Start program
if __name__ == "__main__":
   main()
