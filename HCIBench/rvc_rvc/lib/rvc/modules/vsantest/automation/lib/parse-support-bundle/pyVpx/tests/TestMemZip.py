#!/usr/bin/python

from __future__ import print_function

import sys
import unittest
from pyVmomi import Vim, Vmodl
from pyVim.connect import Connect, Disconnect
from optparse import OptionParser
from pyVim import folder
from pyVim import host

"""
   Memory Compression QuickStats VIM API Test

   Usage:

   ../py.sh TestMemZip.py -H <host name/ip> -u <user name> -p <password>


   Before running the test - log into visor/esx box and enable memory
   compression by invoking:

   esxcfg-advcfg -s 1 /Mem/MemZipEnable

   Then create several vms (I used memtest86.iso to boot them).  Total
   amount of memory allocated to all of them should be greater than
   host memory size.   Power vms on. Then run this test - compressed
   memory size should be greater than 0.

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

class TestCompressedMemoryQuickStats(unittest.TestCase):

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


   def tearDown(self):
      """
      Reset test suite
      """
      Disconnect(self.si)


   def runTest(self):
      self.TestVMQuickStats()
      self.TestRPQuickStats()


   def TestVMQuickStats(self):
      """
      Check if all the precreated powered-on Vms use compressed
      memory.
      """
      content = self.si.RetrieveContent()
      rootFolder = content.GetRootFolder()
      dataCenter = rootFolder.GetChildEntity()[0]
      vmFolder = dataCenter.vmFolder
      self.assertTrue(len(vmFolder.childEntity) > 0)
      for vm in vmFolder.childEntity:
         self.assertTrue(vm.summary.quickStats.compressedMemory > 0)
         print('compressedMemory: %d' % vm.summary.quickStats.compressedMemory)


   def TestRPQuickStats(self):
      """
      This is not being used now as hostd does not
      set up resource pool quickstats.
      """
      content = self.si.RetrieveContent()
      rootFolder = content.GetRootFolder()
      dataCenter = rootFolder.GetChildEntity()[0]
      hostFolder = dataCenter.hostFolder
      for c in hostFolder.childEntity:
         print(c)
         if isinstance(c, Vim.ComputeResource):
            pool = c.resourcePool
            # print(pool.summary)


def main(argv):
    """
    Test Memory Compression Quick Stats
    """
    options = get_options()
    test = TestCompressedMemoryQuickStats();
    test.setOptions(options)
    suite = unittest.TestSuite()
    suite.addTest(test)
    unittest.TextTestRunner(verbosity=2).run(suite)


# Start program
if __name__ == "__main__":
    main(sys.argv[1:])

