#!/usr/bin/python

from __future__ import print_function

import sys, time
import unittest
import subprocess
from pyVmomi import Vim, Vmodl
from pyVim.connect import Connect, Disconnect
from optparse import OptionParser
from pyVim import folder
from pyVim import host
from pyVim.task import WaitForTask

"""
   ESXCLI -> host advanced options update test

   Usage:

   ../py.sh TestEsxCLI.py -H <host name/ip> -u <username> -p <password>

"""

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
    (options, _) = parser.parse_args()
    return options


class TestEsxCLI(unittest.TestCase):

   def setOptions(self, options):
      """
      Command line options
      """
      self.options = options

   def run_command(self, cmdLine):
      """
      Executes a local shell command.
      """
      print("\nRunning " + cmdLine)
      p = subprocess.Popen(cmdLine, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      outdata, errdata = p.communicate()
      self.assertTrue(errdata != None,
                      "Error running remote esxcli command (%s):\n%s" % (cmdLine,errdata))
      return outdata

   def run_remote_command(self, cmd):
      """
      Executes a command remotely via ssh.
      Assumes you've got password-less login already set up.
      """
      return self.run_command("ssh %s@%s 'sh -lc \"%s\"'" % (self.options.user, self.options.host, cmd))

   def setUp(self):
      """
      Setting test suite
      """
      options = get_options()

      self.si = Connect(host=self.options.host,
                        user=self.options.user,
                        version="vim.version.version9",
                        pwd=self.options.password)
      self.content = self.si.RetrieveContent()
      self.internalContent = self.si.RetrieveInternalContent()
      rootFolder = self.content.GetRootFolder()
      dataCenter = rootFolder.GetChildEntity()[0]
      hostFolder = dataCenter.hostFolder
      host = hostFolder.childEntity[0]
      self.hostSystem = host.host[0]
      configManager = self.hostSystem.GetConfigManager()
      self.advOptions = configManager.advancedOption

   def tearDown(self):
      """
      Reset test suite
      """
      Disconnect(self.si)

   def runTest(self):
      self.test_esx_cli()

   def test_esx_cli(self):
      """
      Applies an empty config and check if property update on
      CacheConfigurationManager is fired.
      """

      self.assertTrue(self.advOptions != None,
                      "cacheConfigManager should not be None")

      # Prepare property collector

      objSpec = Vmodl.Query.PropertyCollector.ObjectSpec(
                     obj = self.advOptions,
                     skip = False,
                     selectSet = [])
      propSpec = Vmodl.Query.PropertyCollector.PropertySpec(
                     type = self.advOptions.__class__,
                     all = False,
                     pathSet = ["setting"])
      filterSpec = Vmodl.Query.PropertyCollector.FilterSpec(
                     propSet = [ propSpec ],
                     objectSet = [ objSpec ])
      pc_filter = self.content.propertyCollector.CreateFilter(filterSpec, False)

      # First initial call
      updateSet = self.content.propertyCollector.WaitForUpdates()
      version = updateSet.version

      option_key = "Disk.MaxLUN"
      option_value = filter(lambda x: x.key == option_key, self.advOptions.setting)[0]
      value =int(option_value.value)

      cmd = "esxcli system settings advanced set -o /%s -i %d" %\
            (option_key.replace(".","/"), value-1)
      self.run_remote_command(cmd)

      # Set up wait time and trigger update
      waitSpec = Vmodl.Query.PropertyCollector.WaitOptions()
      waitSpec.maxWaitSeconds = 5
      updateSet = self.content.propertyCollector.WaitForUpdatesEx(version,
                                                                  waitSpec)
      # restores old value regardless of outcome
      cmd = "esxcli system settings advanced set -o /%s -i %d" %\
            (option_key.replace(".","/"), value)
      self.run_remote_command(cmd)

      self.assertTrue(updateSet != None,
                      "we should get property collector update")

      object_set = filter(lambda x: x.obj._wsdlName == "OptionManager",
                       updateSet.filterSet[0].objectSet)[0]

      option_value = filter(lambda x: x.key == option_key, object_set.changeSet[0].val)[0]
      self.assertTrue(option_value.value == value-1)

def main(argv):
    """
    Test property update on configManager.advancedOption after ESXCLI is called
    """
    options = get_options()
    test = TestEsxCLI()
    test.setOptions(options)
    suite = unittest.TestSuite()
    suite.addTest(test)
    unittest.TextTestRunner(verbosity=2).run(suite)


# Start program
if __name__ == "__main__":
    main(sys.argv[1:])
