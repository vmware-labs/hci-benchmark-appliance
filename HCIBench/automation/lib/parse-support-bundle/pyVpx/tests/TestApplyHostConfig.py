#!/usr/bin/python
import sys, time
import unittest
from pyVmomi import Vim, Vmodl
from pyVim.connect import Connect, Disconnect
from optparse import OptionParser
from pyVim import folder
from pyVim import host
from pyVim.task import WaitForTask

"""
   Host Cache Configuration Management / Host Profiles interoperability test

   Usage:

   ../py.sh TestApplyHostConfig.py -H <host name/ip> -u <user name -p <password>

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


class TestApplyHostConfig(unittest.TestCase):

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
      self.cacheConfigManager = configManager.cacheConfigurationManager
      self.hostProfileEngine = self.internalContent.hostProfileEngine
      self.profileManager = self.hostProfileEngine.hostProfileManager

   def tearDown(self):
      """
      Reset test suite
      """
      Disconnect(self.si)

   def runTest(self):
      self.TestApplyEmptyConfig()

   def TestApplyEmptyConfig(self):
      """
      Applies an empty config and check if property update on
      CacheConfigurationManager is fired.
      """

      self.assertTrue(self.cacheConfigManager != None,
                      "cacheConfigManager should not be None")

      self.assertTrue(self.profileManager != None,
                      "profileManager should not be None")

      # Prepare property collector

      objSpec = Vmodl.Query.PropertyCollector.ObjectSpec(
                     obj = self.cacheConfigManager,
                     skip = False,
                     selectSet = [])
      propSpec = Vmodl.Query.PropertyCollector.PropertySpec(
                     type = self.cacheConfigManager.__class__,
                     all = False,
                     pathSet = ["cacheConfigurationInfo"])
      filterSpec = Vmodl.Query.PropertyCollector.FilterSpec(
                     propSet = [ propSpec ],
                     objectSet = [ objSpec ])
      filter = self.content.propertyCollector.CreateFilter(filterSpec, False)

      # First initial call
      updateSet = self.content.propertyCollector.WaitForUpdates()
      version = updateSet.version

      # ApplyHostConfig

      spec = Vim.Host.ConfigSpec()
      task = self.profileManager.ApplyHostConfig(configSpec = spec)
      WaitForTask(task)

      self.assertTrue(task.info.state == 'success',
                      "Reconfiguration task should succeed")

      # Set up wait time and trigger update
      waitSpec = Vmodl.Query.PropertyCollector.WaitOptions()
      waitSpec.maxWaitSeconds = 5
      updateSet = self.content.propertyCollector.WaitForUpdatesEx(version,
                                                                  waitSpec)
      self.assertTrue(updateSet != None,
                      "we should get property collector update")


def main(argv):
    """
    Test property update on CacheManager after ApplyHostConfig is called
    """
    options = get_options()
    test = TestApplyHostConfig()
    test.setOptions(options)
    suite = unittest.TestSuite()
    suite.addTest(test)
    unittest.TextTestRunner(verbosity=2).run(suite)


# Start program
if __name__ == "__main__":
    main(sys.argv[1:])
