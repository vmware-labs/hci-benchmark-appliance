#!/usr/bin/python

"""
Issues a bunch of esxcli's to test server state invalidation.
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

   sys.argv = ["esxcli", "--server", options.host, "--user", options.user, "--password", options.password]
   sys.argv.extend(cliCmdString.split())

   MsgStdout("Executing: " + cliCmdString)

   try:
      result, exitCode = handler.HandleCmdline()
      if expectedError != None:
         if exitCode == 0 or not errorListener.matched:
            FailedStdout("Test FAILED executing: %s.   Expected but did not find %s." %
                         (cliCmdString, expectedError))
         else:
            MsgStdout("Matched expected error " + expectedError)
      else:
         if exitCode != 0:
            FailedStdout("Test FAILED executing: %s.\n -- Unexpected error." %
                         (cliCmdString,))
   except Exception as err:
      FailedStdout("Test FAILED: " + repr(err))

def main():
   """
   Issues a bunch of esxcli's to test server state invalidation.
   """

   global options
   status = "PASS"
   options = get_options()

   si = Connect(host=options.host,
                user=options.user,
                pwd=options.password)

   # @todo : add more validation logic
   try:
      TestCLI("esxcli command list", expectedError=None)

      TestCLI("system kernellog list", expectedError=None)

      TestCLI("network ip connection list", expectedError=None)

      TestCLI("network nic", expectedError=None)
      TestCLI("network nic list", expectedError=None)

      TestCLI("network vswitch standard add -P 123 -v refreshTestSw", expectedError=None)
      TestCLI("network vswitch standard remove -v refreshTestSw", expectedError=None)

      TestCLI("system kernellog set -l VisorFS -L 1", expectedError=None)

      #no longer valid
      #TestCLI("system kernellog getlevel -l VisorFS", expectedError=None)

      TestCLI("system syslog config logger set --id vpxa --rotate=9", expectedError=None)
      TestCLI("system syslog config get", expectedError=None)
      TestCLI("system syslog config logger list", expectedError=None)

      TestCLI("iscsi software set --enabled true", expectedError=None)
      TestCLI("iscsi software set --enabled false", expectedError=None)

      TestCLI("system welcomemsg set -m refreshTestWelcomeMsg", expectedError=None)
      TestCLI("system welcomemsg get", expectedError=None)

      TestCLI("storage filesystem automount", expectedError=None)

      TestCLI("network firewall set --default-action true", expectedError=None)
      TestCLI("network firewall set --enabled true", expectedError=None)
      TestCLI("network firewall set --enabled false", expectedError=None)
      TestCLI("network firewall set --default-action false", expectedError=None)

      TestCLI("system settings kernel list -o storageMaxPaths", expectedError=None)
      TestCLI("system settings kernel set -s storageMaxPaths -v 1023", expectedError=None)
      TestCLI("system settings kernel list -o storageMaxPaths", expectedError=None)
      TestCLI("system settings kernel set -s storageMaxPaths -v 1024", expectedError=None)

   except Exception as err:
      MsgStdout("Test FAILED: " + repr(err))
      status = "FAIL"

   MsgStdout("TEST RUN COMPLETE: " + status)

# Start program
if __name__ == "__main__":
    main()
