#!/usr/bin/python

from __future__ import print_function

import sys
import os
from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import Vmodl
from pyVim.host import GetHostSystem
from pyVim.helpers import Log
from optparse import OptionParser
import unittest

"""
   Test hostd handling of various vmomi calls when unauthenticated.

   Usage:

   ../py.sh TestVCExclMode.py -H <host name/ip> -u <user name -p <password>

"""

class TestAnon(unittest.TestCase):

   def setOptions(self, options):
       """
       Command line options
       """
       self.options = options

   def setUp(self):
       """
       Setting test suite
       """
       self.si = SmartConnect(host=self.options.host,
                              user=self.options.user,
                              pwd=self.options.pwd,
                              port=self.options.port)
       self.authenticated = 1

       print("Retriving some MOs while authenticated:")
       self.content = self.si.RetrieveContent()
       rootFolder = self.content.GetRootFolder()
       dataCenter = rootFolder.GetChildEntity()[0]
       hostFolder = dataCenter.hostFolder
       host = hostFolder.childEntity[0]
       self.hostSystem = host.host[0]
       self.vmFolder = dataCenter.vmFolder
       self.configManager = self.hostSystem.GetConfigManager()

       internalContent = self.si.RetrieveInternalContent()
       hostProfileEngine = internalContent.hostProfileEngine
       self.hostProfileManager = hostProfileEngine.hostProfileManager

       self.storageResourceManager = self.content.storageResourceManager
       self.dvsManager = self.si.RetrieveInternalContent().hostDistributedVirtualSwitchManager

       print(repr(self.hostProfileManager))
       print(repr(self.storageResourceManager))
       print(repr(self.dvsManager))
       print(repr(self.vmFolder))

       Disconnect(self.si)
       self.authenticated = 0
       self.si = None

   def tearDown(self):
       if self.authenticated:
           Disconnect(self.si)

   def test_task_methods_with_null_arguments(self):
       # todo : test non anonymous methods with null arguments
       pass

   def test_retrieve_various(self):
       si = SmartConnect(host=self.options.host,
                         user=self.options.user,
                         pwd=self.options.pwd,
                         port=self.options.port)
       Disconnect(si)
       try:
           internalContent = si.RetrieveInternalContent()
           content = si.RetrieveContent()
       except Exception as e:
           self.fail("Unexpected exception for anon-allowable calls: %s" % e)
           pass

       try:
           uptime = self.hostSystem.RetrieveHardwareUptime()
       except Vim.Fault.NotAuthenticated as e:
           Log("Caught NotAuthenticated exception: %s" % e)
           pass

   def test_invalid_login(self):
       print("test_invalid_login")
       for i in range(self.options.num_bad_logins):
           try:
               print("iteration: " + repr(i))
               bad_pwd = self.options.pwd + "JUNK"
               si = SmartConnect(host=self.options.host,
                            user=self.options.user,
                            pwd=bad_pwd,
                            port=self.options.port)

               Disconnect(si)
           except Vim.Fault.InvalidLogin as e:
               Log("Caught InvalidLogin exception")
               pass
           else:
               self.fail('InvalidLogin not thrown')

   def runTest(self):
      self.test_invalid_login()
      self.test_retrieve_various()
      #self.test_task_methods_with_null_arguments()

def get_options():
    # Can't use built-in help option because -h is used for hostname
    parser = OptionParser(add_help_option=False)
    parser.add_option('-h', '--host', dest='host', help='Host name', default='localhost')
    parser.add_option('-u', '--user', dest='user', help='User name', default='root')
    parser.add_option('-p', '--pwd', dest='pwd', help='Password')
    parser.add_option('-o', '--port', dest='port', help='Port', default=443, type='int')
    parser.add_option('-n', '--numbadlogins', dest='num_bad_logins',
                      help='Number of bad login attempts', default=1, type='int')
    parser.add_option('-?', '--help', '--usage', action='help', help='Usage information')
    (options, _) = parser.parse_args()
    return options

def main(argv):
    options = get_options()
    test = TestAnon()
    test.setOptions(options)
    suite = unittest.TestSuite()
    suite.addTest(test)
    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == "__main__":
    main(sys.argv[1:])
