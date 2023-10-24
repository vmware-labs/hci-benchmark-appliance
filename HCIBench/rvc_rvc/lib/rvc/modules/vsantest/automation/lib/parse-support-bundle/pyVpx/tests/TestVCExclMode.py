#!/usr/bin/python

from __future__ import print_function

import sys, time
import unittest
from pyVmomi import Vim, Vmodl
from pyVim.connect import SmartConnect, Disconnect
from optparse import OptionParser
from pyVim import folder
from pyVim import vm, host

"""
   Test feature availability when host is getting in and out of
   VC Exclusive API mode (operation lockdown mode).

   Usage:

   ../py.sh TestVCExclMode.py -H <host name/ip> -u <user name -p <password>

"""

SERVERIP = "127.0.0.1"
TESTVM = "VCETESTVM"
TESTVM_RENAMED = "VCETESTVM-RENAMED"
TESTVM_TODESTROY = "VCETESTVM-TODESTROY"
TESTRP = "VCETESTRP"
TESTRP_TODESTROY = "VCETESTRP-TODESTROY"
TESTRP_RENAMED = "VCETESTRP-RENAMED"
TESTRP_CHILD = "VCETESTRP-CHILD"
TESTRP_CHILD2 = "VCETESTRP-CHILD2"

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


class TestVCExclMode(unittest.TestCase):

   def assertRaises(self, exception, callable, *args, **kwargs):
      if (exception != None):
         super(TestVCExclMode, self).assertRaises(exception,
                               callable, *args, **kwargs)
      else:
         try:
            callable(*args, **kwargs)
         except Exception as e:
            print(callable)
            print(e)
            self.assertTrue(e != None, "unexpected exception: %s" % e)


   def createResourceConfigSpec(self):
      spec = Vim.ResourceConfigSpec()
      spec.cpuAllocation = Vim.ResourceAllocationInfo()
      spec.cpuAllocation.shares = Vim.SharesInfo()
      spec.cpuAllocation.shares.level = Vim.SharesInfo.Level.normal
      spec.cpuAllocation.shares.shares = 4000
      spec.cpuAllocation.reservation = long(0)
      spec.cpuAllocation.limit = long(-1)
      spec.cpuAllocation.expandableReservation = True

      spec.memoryAllocation = Vim.ResourceAllocationInfo()
      spec.memoryAllocation.shares = Vim.SharesInfo()
      spec.memoryAllocation.shares.level = Vim.SharesInfo.Level.normal
      spec.memoryAllocation.shares.shares = 4000
      spec.memoryAllocation.reservation = long(0)
      spec.memoryAllocation.limit = long(-1)
      spec.memoryAllocation.expandableReservation = True

      return spec

   def createTestResourcePool(self, name):
      """
      Create test resource pool under the root
      (host/user) pool. All this configuration information
      is not really required.
      """

      return self.rootRP.CreateResourcePool(name, self.createResourceConfigSpec())

   def createTestVM(self, name):
      """
      Create test vm in the root (host/user)
      resource pool.
      """
      vm.CreateQuickDummy(name, 3, diskSizeInMB = 4096)
      return self.searchIndex.FindByInventoryPath("ha-datacenter/vm/" + name)


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

      self.si = SmartConnect(host=self.options.host,
                             user=self.options.user,
                             pwd=self.options.password)
      self.content = self.si.RetrieveContent()
      self.searchIndex = self.content.searchIndex
      rootFolder = self.content.GetRootFolder()
      dataCenter = rootFolder.GetChildEntity()[0]
      hostFolder = dataCenter.hostFolder
      host = hostFolder.childEntity[0]
      self.hostSystem = host.host[0]
      configManager = self.hostSystem.GetConfigManager()
      self.powerSystem = configManager.GetPowerSystem()
      self.hostConfigInfo = self.hostSystem.config
      self.rootRP = host.resourcePool

      # Assume that this operation does not fail
      self.hostSystem.UpdateManagementServerIp(None)

      self.testVM = self.createTestVM(TESTVM)
      self.testVMToDestroy = self.createTestVM(TESTVM_TODESTROY)
      self.testRP = self.createTestResourcePool(TESTRP)
      self.testRPChild = self.createTestResourcePool(TESTRP_CHILD)
      self.testRP.MoveInto([ self.testRPChild ])
      self.testRPToDestroy = self.createTestResourcePool(TESTRP_TODESTROY)

   def tearDown(self):
      """
      Reset test suite
      """

      # Assume that this operation does not fail
      self.hostSystem.UpdateManagementServerIp(None)

      try:
         self.testVM.Destroy()
      except:
         pass

      try:
         self.testRP.Destroy()
      except:
         pass

      Disconnect(self.si)


   def runTest(self):
      self.TestVCManagedMode()
      self.TestDisabledMethodPropertyCollect()


   def TestRPRename(self, expectedException):
      # print("RP Rename")
      self.assertRaises(expectedException,
                        self.testRP.Rename, TESTRP_RENAMED)
      self.assertRaises(expectedException,
                        self.testRP.Rename, TESTRP)

   def TestVMRename(self, expectedException):
      # print("VM Rename")
      self.assertRaises(expectedException,
                        self.testVM.Rename, TESTVM_RENAMED)
      self.assertRaises(expectedException,
                        self.testVM.Rename, TESTVM)


   def TestRPReload(self, expectedException):
      # print("RP Reload")
      self.assertRaises(expectedException,
                        self.testRP.Reload)

   def TestVMReload(self, expectedException):
      # print("VM Reload")
      self.assertRaises(expectedException,
                        self.testVM.Reload)


   def TestRPDestroy(self, expectedException):
      # print("RP Destroy")
      self.assertRaises(expectedException,
                        self.testRPToDestroy.Destroy)


   def TestVMDestroy(self, expectedException):
      # print("VM Destroy")
      self.assertRaises(expectedException,
                        self.testVMToDestroy.Destroy)


   def TestRPUpdateConfig(self, expectedException):
      # print("RP UpdateConfig")
      self.assertRaises(expectedException,
                        self.testRP.UpdateConfig,
                        self.createResourceConfigSpec())


   def TestRPMoveInto(self, expectedException):
      # print("RP MoveInto")
      list = [ self.testVM ]
      self.assertRaises(expectedException,
                        self.testRP.MoveInto, list)
      self.assertRaises(expectedException,
                        self.rootRP.MoveInto, list)


   def TestRPUpdateChildResourceConfiguration(self, expectedException):
      # print("RP UpdateChildResourceConfiguration")
      spec = self.createResourceConfigSpec()
      spec.entity = self.testRPChild
      list = [ spec ]
      self.assertRaises(expectedException,
                        self.testRP.UpdateChildResourceConfiguration,
                        list)


   def TestRPCreateResourcePool(self, expectedException):
      # print("RP CreateResourcePool")
      self.assertRaises(expectedException,
                        self.testRP.CreateResourcePool,
                        TESTRP_CHILD2,
                        self.createResourceConfigSpec())


   def TestRPDestroyChildren(self, expectedException):
      # print("RP DestroyChildren")
      self.assertRaises(expectedException,
                        self.testRP.DestroyChildren)


   def TestRPCreateVApp(self, expectedException):
      # print("RP CreateVApp")
      vAppSpec = Vim.VApp.VAppConfigSpec()
      self.assertRaises(expectedException,
                        self.testRP.CreateVApp,
                        "VAPP",
                        self.createResourceConfigSpec(),
                        vAppSpec,
                        None)



   def TestRPCreateVM(self, expectedException):
      # print("RP CreateVM")
      # Correct config values don't really matter here
      vmConfigSpec = Vim.Vm.ConfigSpec()
      self.assertRaises(expectedException,
                        self.testRP.CreateVm,
                        vmConfigSpec,
                        None)


   def TestRPRegisterVM(self, expectedException):
      # print("RP RegisterVM")
      path = self.testVM.summary.config.vmPathName
      name = self.testVM.summary.config.name
      self.assertRaises(expectedException,
                        self.testRP.RegisterVm,
                        path,
                        name,
                        None)


   def TestRPImportVApp(self, expectedException):
      # print("RP ImportVApp")
      """
      Real value is not really important here
      """
      spec = Vim.ImportSpec()
      self.assertRaises(None,
                        self.testRP.ImportVApp,
                        spec)


   def TestAllMethods(self, expectedException):
      self.TestRPRename(expectedException)
      self.TestVMRename(None)
      self.TestRPReload(expectedException)
      self.TestVMReload(None)
      self.TestRPMoveInto(expectedException)
      self.TestRPUpdateChildResourceConfiguration(expectedException)
      self.TestRPCreateResourcePool(expectedException)
      self.TestRPDestroyChildren(expectedException)
      self.TestRPCreateVApp(expectedException)
      self.TestRPCreateVM(expectedException)
      self.TestRPRegisterVM(expectedException)
      self.TestRPImportVApp(expectedException)
      self.TestRPDestroy(expectedException)
      self.TestVMDestroy(None)



   def TestVCManagedMode(self):
      """
      Check behavior in VC managed mode.
      """

      # Assume that initial stats in unmanaged mode
      self.assertTrue(self.hostSystem.summary.managementServerIp == None,
                      "management server ip should be initially None")

      try:
         self.hostSystem.UpdateManagementServerIp(SERVERIP)
      except Exception as e:
         self.assertTrue(e == None,
                         "UpdateManagementServerIp should not throw: %s" % e )

      self.assertTrue(self.hostSystem.summary.managementServerIp == SERVERIP,
                      "mainagement server ip should match expected value")

      self.TestAllMethods(Vim.Fault.HostAccessRestrictedToManagementServer)

      # Reset it back to unmanaged mode
      try:
         self.hostSystem.UpdateManagementServerIp(None)
      except Exception as e:
         self.assertTrue(e == None,
                   "UpdateManagementServerIp(reset) should not throw: %s" % e )

      self.testVMToDestroy = self.createTestVM(TESTVM_TODESTROY)

      self.TestRPRename(None)
      self.TestVMRename(None)
      self.TestRPReload(None)
      self.TestVMReload(None)
      self.TestRPMoveInto(None)
      self.TestRPUpdateChildResourceConfiguration(None)
      self.TestRPCreateResourcePool(None)
      self.TestRPDestroyChildren(None)
      self.TestRPCreateVApp(Vmodl.Fault.NotSupported)
      self.TestRPCreateVM(None)
      self.TestRPRegisterVM(None)
      self.TestRPImportVApp(Vmodl.Fault.NotSupported)
      self.TestRPDestroy(None)
      self.TestVMDestroy(None)


   def TestDisabledMethodPropertyCollect(self):
      disabledMethods = self.testRP.disabledMethod

      objSpec = Vmodl.Query.PropertyCollector.ObjectSpec(obj = self.testRP,
                                                         skip = False,
                                                         selectSet = [])
      propSpec = Vmodl.Query.PropertyCollector.PropertySpec(type = self.testRP.__class__,
                                                            all = False,
                                                            pathSet = ["disabledMethod"])
      filterSpec = Vmodl.Query.PropertyCollector.FilterSpec(propSet = [ propSpec ],
                                                            objectSet = [ objSpec ])
      filter = self.content.propertyCollector.CreateFilter(filterSpec, False)

      # First initial call
      updateSet = self.content.propertyCollector.WaitForUpdates()
      version = updateSet.version

      self.hostSystem.UpdateManagementServerIp("127.0.0.1")

      # Set up wait time and trigger update
      waitSpec = Vmodl.Query.PropertyCollector.WaitOptions()
      waitSpec.maxWaitSeconds = 5
      updateSet = self.content.propertyCollector.WaitForUpdatesEx(version,
                                                                  waitSpec)
      self.assertTrue(updateSet != None,
                      "we should get property collector update")
      if (updateSet != None):
         version = updateSet.version
         self.hostSystem.UpdateManagementServerIp(None)
         updateSet = self.content.propertyCollector.WaitForUpdatesEx(version,
                                                                     waitSpec)
         self.assertTrue(updateSet != None,
                        "we should get property collector update again")


def main(argv):
    """
    Test feature availability when host is in and out of
    VC API Exclusive mode (operation lockdown mode).
    """
    options = get_options()
    test = TestVCExclMode()
    test.setOptions(options)
    suite = unittest.TestSuite()
    suite.addTest(test)
    unittest.TextTestRunner(verbosity=2).run(suite)


# Start program
if __name__ == "__main__":
    main(sys.argv[1:])
