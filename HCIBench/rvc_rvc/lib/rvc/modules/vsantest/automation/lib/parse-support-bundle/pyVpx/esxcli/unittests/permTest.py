#!/usr/bin/python

"""
Tests permission checking of esxcli invocations.

Requirements:
 * Connecting user needs privileges to create users/roles
"""

import sys
from __future__ import print_function
from pyVim.connect import Connect
from pyVim.invt import GetRootFolder
from optparse import OptionParser
from pyVmomi import Vim
from pyVim.account import CreatePosixUser, RemoveUser, GetRoleId, \
                          CreateRole, RemoveRole, GetAuthorizationManager
from esxcli.esxcli import CLIHandler, LogException

NO_PERMISSION_ERROR_MSG = "No permission to execute"
options = None

class CLIOutputListener():
   def __init__(self, errorToMatch):
      self.matched = False
      self.errorToMatch = errorToMatch

   def write(self, s):
      if self.matched:
         pass
      if (s.find(self.errorToMatch) != -1):
         self.matched = True

def get_options():
   """
   Supports the command-line arguments listed below
   """

   parser = OptionParser(add_help_option=False)
   parser.add_option("-h", "--host",
                     help="remote host to connect to")
   parser.add_option("-u", "--user",
                     default="root",
                     help="User name to use when connecting to hostd")
   parser.add_option("-p", "--password",
                     default="ca\$hc0w",
                     help="Password to use when connecting to hostd")
   parser.add_option("-t", "--test-user-name",
                     default="permTestUser",
                     help="User name of test user to create")
   parser.add_option("-i", "--posix-id-to-create",
                     help="Numeric POSIX id of user to create")
   parser.add_option("-d", "--description",
                     default="User created by createuser.py",
                     help="Description of user to create")
   parser.add_option("--with-password",
                     default="b1gd3m0#",
                     help="Password of test user to create")
   parser.add_option("--enable-shell-access",
                     action="store_true",
                     help="Grant shell access to new user")
   parser.add_option('-?', '--help', '--usage', action='help', help='Usage information')

   (options, _) = parser.parse_args()
   return options

def FailedStdout(s):
   print(s + "\nTEST RUN COMPLETE: FAIL", file=sys.__stdout__)
   sys.exit(1)

def MsgStdout(s):
   print(s, file=sys.__stdout__)

def TestCLI(cliCmdString, expectedError=None):
   " set up argv and invoke a CLI call via esxcli CLIHandler "
   global options

   handler = CLIHandler()

   if expectedError != None:
      errorListener = CLIOutputListener(expectedError)
      sys.stdout = errorListener

   sys.argv = ["esxcli", "--server", options.host, "--user", options.test_user_name, "--password", options.with_password]
   sys.argv.extend(cliCmdString.split())

   MsgStdout("Executing: " + cliCmdString)

   try:
      result, exitCode = handler.HandleCmdline()
      if expectedError != None:
         if exitCode == 0 or not errorListener.matched:
            FailedStdout("Test FAILED executing: %s.   Expected but did not find %s." %
                         (cliCmdString, expectedError))
         else:
            MsgStdout("Matched expected error: " + expectedError)
      else:
         if exitCode != 0:
            FailedStdout("Test FAILED executing: %s.\n -- Unexpected error." %
                         (cliCmdString,))
   except Exception as err:
      FailedStdout("Test FAILED: " + repr(err))

def main():
   """
   Test permissions checking of esxcli by repeated invocations on python
   esxcli.
   """

   global options
   status = "PASS"
   options = get_options()

   si = Connect(host=options.host,
                              user=options.user,
                              pwd=options.password)

   testUserName = options.test_user_name
   print("Creating user: " + testUserName)
   CreatePosixUser(name=testUserName,
                   password=options.with_password)

   privsToRemove = [
         "VirtualMachine.Interact.PowerOn",
         "VirtualMachine.Interact.PowerOff",
         "Global.Settings",
         "Host.Config.Settings",
         "Host.Config.AdvancedConfig",
         "Host.Config.Storage",
         ]

   # create a role like Admin, but with some privileges removed
   cliRoleId1 = CreateRole("CliTest", basedOnRoleName="Admin",
                           privsToAdd=[], privsToRemove=privsToRemove)

   # create a role like CliTest, but add/delete a privilege
   cliRoleId2 = CreateRole("CliTestAlt", basedOnRoleName="CliTest",
                           privsToAdd=["Host.Config.Settings", "Host.Config.AdvancedConfig"], privsToRemove=["Host.Config.Network"])

   am = GetAuthorizationManager(si=si)
   try:
      rootFolder = GetRootFolder(si=si)
      perm = Vim.AuthorizationManager.Permission()
      perm.principal = testUserName
      perm.group = False
      perm.propagate = True

      perm.roleId = cliRoleId1
      am.SetEntityPermissions(entity=rootFolder, permission=[perm])
      TestCLI("esxcli command list", expectedError=None)
      TestCLI("network", expectedError=None)
      TestCLI("system settings kernel list", expectedError=None)
      TestCLI("system module list", expectedError=None)
      TestCLI("storage nmp device list", expectedError=None)
      TestCLI("storage core plugin list", expectedError=None)
      TestCLI("system syslog config get", expectedError=None)
      TestCLI("system syslog config logger list", expectedError=None)
      TestCLI("system settings kernel set -s storageMaxPaths -v 1023", expectedError=NO_PERMISSION_ERROR_MSG)
      TestCLI("system syslog config logger set --id vpxa --rotate=9", expectedError=NO_PERMISSION_ERROR_MSG)

      perm.roleId = cliRoleId2
      am.SetEntityPermissions(entity=rootFolder, permission=[perm])
      TestCLI("esxcli command list", expectedError=None)
      TestCLI("system settings kernel set -s storageMaxPaths -v 1024", expectedError=None)
      TestCLI("system kernellog list", expectedError=None)
      TestCLI("network ip dns server add -s 1.2.3.4", expectedError=NO_PERMISSION_ERROR_MSG)
      TestCLI("system syslog config logger set --id vpxa --rotate=10", expectedError=None)

   except Exception as err:
      MsgStdout("Test FAILED: " + repr(err))
      status = "FAIL"
   finally:
      am.RemoveEntityPermission(entity=rootFolder, user=testUserName, isGroup=False)
      RemoveRole(cliRoleId1, True)
      RemoveRole(cliRoleId2, True)
      RemoveUser(name=testUserName)

   MsgStdout("TEST RUN COMPLETE: " + status)

# Start program
if __name__ == "__main__":
    main()
