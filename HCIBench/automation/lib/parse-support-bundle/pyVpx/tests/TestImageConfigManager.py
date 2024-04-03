#!/usr/bin/python
# requires python 3
import sys, time
import unittest
from pyVmomi import Vim, Vmodl
from pyVmomi.VmomiSupport import newestVersions
from pyVim.connect import Connect, Disconnect
from optparse import OptionParser
from pyVim import folder
from pyVim import host

"""
   Host Image Config Manager VIM API Test

   Usage:

   ../py.sh TestImageConfigManager.py -H <host name/ip> -u <user name -p <password>

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


class TestImageConfigManager(unittest.TestCase):

   def setOptions(self, options):
      """
      Command line options
      """
      self.options = options

   def setUp(self):
      """
      Setting test suite
      """
      options = get_options()

      self.si = Connect(host=self.options.host,
                        user=self.options.user,
                        version=newestVersions.GetName("vim"),
                        pwd=self.options.password)
      content = self.si.RetrieveContent()
      rootFolder = content.GetRootFolder()
      dataCenter = rootFolder.GetChildEntity()[0]
      hostFolder = dataCenter.hostFolder
      host = hostFolder.childEntity[0]
      self.hostSystem = host.host[0]
      configManager = self.hostSystem.GetConfigManager()
      self.imageConfigManager = configManager.GetImageConfigManager()
      self.hostConfigInfo = self.hostSystem.config

   def tearDown(self):
      """
      Reset test suite
      """
      Disconnect(self.si)

   def runTest(self):
      self.test_getacceptance()
      self.test_getprofileinfo()
      self.test_setacceptance()
      self.test_FetchSoftwarePackages()
      self.test_InstallDate()

   def test_getacceptance(self):
      self.assertTrue(self.imageConfigManager != None)
      acceptance = self.imageConfigManager.QueryHostAcceptanceLevel()
      print("\nHost acceptance level: %s" % acceptance)

   def test_getprofileinfo(self):
      self.assertTrue(self.imageConfigManager != None)
      profile = self.imageConfigManager.QueryHostImageProfile()
      print("\nHost profile name: %s" % profile.name)
      print("\nHost profile vendor: %s" % profile.vendor)

   def test_setacceptance(self):
      self.assertTrue(self.imageConfigManager != None)
      self.assertRaises(Vim.fault.HostConfigFault,
                        self.imageConfigManager.UpdateAcceptanceLevel,
                        "blah - not a valid level")

   def test_FetchSoftwarePackages(self):
      self.assertTrue(self.imageConfigManager != None)
      vibs = self.imageConfigManager.FetchSoftwarePackages()
      print("\nHave %d vibs installed" % (len(vibs)))
      self.assertTrue(len(vibs) > 0)
      print("\nExample entry: %s" % (str(vibs[0])))

   def test_InstallDate(self):
      self.assertTrue(self.imageConfigManager != None)
      when = self.imageConfigManager.InstallDate()
      print("\nHost software inception date: %s" % (when))

def main(argv):
    """
    Test Host Cache Configuration Manager VModl API
    """
    options = get_options()
    test = TestImageConfigManager()
    test.setOptions(options)
    suite = unittest.TestSuite()
    suite.addTest(test)
    unittest.TextTestRunner(verbosity=2).run(suite)


# Start program
if __name__ == "__main__":
    main(sys.argv[1:])
