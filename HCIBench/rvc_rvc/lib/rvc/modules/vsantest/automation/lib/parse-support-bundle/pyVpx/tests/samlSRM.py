#!/usr/bin/python

#
# Basic end-to-end SAML token test using AliasManager
# and guestOps, using a simple cmdline app as a fake SSO server.
#
# This tests "allowLocalSystemImpersonationBypass" to allow
# SYSTEM to be used.
#
# If the pref isn't set, SystemError will be thrown.  If the pref is
# set, the test should pass and the temp directory should include
# vmware-SYSTEM as part of its path.
#
# Tweaking gUser below allows for a basic user that should work
# regardless of the pref setting, or a disabled user that will always
# fail given the matching disabled user in the guest.
#
# This requires at least 2.7 python, for subprocess.check_output()
#
# TODO: would be nice to not hard-code the path to samlgen.
#

from pyVmomi import Vim, Vmodl
from pyVim.helpers import Log
from guestOpsUtils import *
import subprocess


def cleanMapFile():
   Log("Clearing mapfile")
   try:
      result = aliasMgr.ListMappedAliases(virtualMachine, guestAuth)
   except Exception, e:
      raise e
   for a in result:
      try:
         Log("Clearing cert %s" % a.base64Cert)
         aliasMgr.RemoveAliasByCert(virtualMachine, guestAuth, a.username, a.base64Cert)
      except Exception, e:
         pass

def cleanUserFile(user):
   Log("Clearing alias store for user %s" % user)
   try:
      result = aliasMgr.ListAliases(virtualMachine, guestAuth, user)
   except Exception, e:
      raise e

   for a in result:
      try:
         Log("Clearing cert %s" % a.base64Cert)
         aliasMgr.RemoveAliasByCert(virtualMachine, guestAuth, user, a.base64Cert)
      except Exception, e:
         pass


def addAlias():
   Log("Adding a Mapped alias")
   nSubj = aliasDef.GuestAuthNamedSubject(name=gSubject)
   aInfo = aliasDef.GuestAuthAliasInfo(subject=nSubj, comment="This is a test comment")
   try:
      result = aliasMgr.AddAlias(virtualMachine, guestAuth, gUser, True, gCert, aInfo)
   except Exception, e:
      raise e

def doGuestOp(token):
   samlAuth = Vim.Vm.Guest.SAMLTokenAuthentication
   tokenAuth = samlAuth(token=token, interactiveSession=False)
   try:
      result = fileMgr.CreateTemporaryDirectory(virtualMachine, tokenAuth, "", "")
      Log("fileMgr.CreateTemporaryDirectory: %s" % result)
   except Exception, e:
      Log("guestOp failed: %s" % e)
      pass

def main():

   # Process command line
   options = get_options()

   global svcInst
   global virtualMachine
   global guestAdminAuth
   global guestAuth
   global guestAuthBad
   [svcInst, virtualMachine, guestAdminAuth,
    guestAuth, guestAuthBad] = init(options.host, options.user, options.password,
                                    options.vmname, options.vmxpath, options.guestuser,
                                    options.guestpassword, options.guestrootuser,
                                    options.guestrootpassword)


   # get the processManager object
   global procMgr
   procMgr = svcInst.content.guestOperationsManager.processManager

   # get the AliasManager object
   global aliasMgr
   aliasMgr = svcInst.content.guestOperationsManager.aliasManager
   global aliasDef
   aliasDef = Vim.Vm.Guest.AliasManager

   global fileMgr
   fileMgr = svcInst.content.guestOperationsManager.fileManager

   # The user to test against.  'options.guestuser' should be a valid
   # user and work.  'disabled' is expected to be a user that has been
   # disabled in the guest.  'SYSTEM' is the (English) name for the SYSTEM
   # account and should only work if "allowLocalSystemImpersonationBypass"
   # is set to true in the [guestoperations] section of tools.conf
   global gUser
   gUser="SYSTEM"
   #gUser=options.guestuser
   #gUser="disabled"

   global gSubject
   gSubject = "TestSubject"
   genCertCmd = "/dbc/pa-dbc1113/lemke/vmcore-main/bora-vmsoft/build/obj-x64/vgauth/Linux/vgauth/samlgen/samlgen -c"
   global gCert
   gCert = subprocess.check_output(genCertCmd, shell=True)

   Log("Read SSO cert")

   testNotReady(procMgr, virtualMachine, guestAuth)
   waitForTools(virtualMachine)

   cleanMapFile()
   cleanUserFile(gUser)

   addAlias()
   Log("Added alias")

   genTokenCmd = "/dbc/pa-dbc1113/lemke/vmcore-main/bora-vmsoft/build/obj-x64/vgauth/Linux/vgauth/samlgen/samlgen -s TestSubject -l 500"
   token = subprocess.check_output(genTokenCmd, shell=True)

   doGuestOp(token)

   cleanMapFile()
   cleanUserFile(gUser)


# Start program
if __name__ == "__main__":
   main()
   Log("SAML guestOps test completed")
