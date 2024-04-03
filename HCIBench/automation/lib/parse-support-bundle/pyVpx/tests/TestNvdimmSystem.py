#!/usr/bin/python
from __future__ import print_function
import sys, time
import unittest
import traceback
from pyVmomi import Vim, Vmodl
from pyVim import task
from pyVim.connect import SmartConnect, Disconnect
from optparse import OptionParser
from pyVim import folder
from pyVim import host

"""
   Host NVDIMM Management VIM API Test

   Tests host NVDIMM management API's by matching it with VSI obtained
   information.

   Usage:

   ../py.sh TestNvdimmSystem.py -H <host name/ip> -u <user name -p <password>

"""

verbose=3
logInfo=2
logVerbose=3

def VerboseLog(logLevel, message, msgend='\n'):
    if (logLevel >= verbose):
        print(message, end=msgend)

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


class TestNvdimmSystem(unittest.TestCase):

   def setOptions(self, options):
      """
      Command line options
      """
      self.options = options

   def setUp(self):
      """
      Setting test suite
      """
      global vsi
      import vmware.vsi as vsi

      options = get_options()

      self.si = SmartConnect(host=self.options.host,
                             user=self.options.user,
                             pwd=self.options.password)
      self.hostSystem = host.GetHostSystem(self.si)
      self.nvdimmSystem = self.hostSystem.GetConfigManager().GetNvdimmSystem()

   def tearDown(self):
      """
      Reset test suite
      """
      Disconnect(self.si)

   def runTest(self):
      self.assertIsNotNone(self.nvdimmSystem,
                      "nvd system should not be None")

      self.TestGetNvdimmInfo()
      """
      Negative test cases
      """
      self.TestIncorrectCreateNamespace()
      self.TestIncorrectDeleteNamespace()


   def checkDeviceHealth(self, vsiHealth, health):
      """
      Check device health status
      """
      if vsiHealth == 0:
         self.assertEqual(health, "NvdimmSystem.normal.healthStatus",
                          "Health status summary did not match vsi summary")
      elif vsiHealth == 1:
         self.assertEqual(health, "NvdimmSystem.maintenanceNeeded.healthStatus",
                          "Health status summary did not match vsi summary")
      elif vsiHealth == 2:
         self.assertEqual(health, "NvdimmSystem.performanceDegraded.healthStatus",
                          "Health status summary did not match vsi summary")
      elif vsiHealth == 4:
         self.assertEqual(health, "NvdimmSystem.wpDataLoss.healthStatus",
                          "Health status summary did not match vsi summary")
      elif vsiHealth == 8:
         self.assertEqual(health, "NvdimmSystem.allDataLoss.healthStatus",
                          "Health status summary did not match vsi summary")
      else:
         raise Exception("Health status summary invalid")


   def checkNsHealthStatus(self, vsiHealth, health):
      """
      Check Namespace health status
      """
      if vsiHealth == 0:
         self.assertEqual(health, "normal",
                          "Namespace health status did not match vsi"
                          " health status")
      elif vsiHealth == 1:
         self.assertEqual(health, "missing",
                          "Namespace health status did not match vsi"
                          " health status")
      elif vsiHealth == 2:
         self.assertEqual(health, "labelMissing",
                          "Namespace health status did not match vsi"
                          " health status")
      elif vsiHealth == 3:
         self.assertEqual(health, "interleaveBroken",
                          "Namespace health status did not match vsi"
                          " health status")
      elif vsiHealth == 4:
         self.assertEqual(health, "labelInconsistent",
                          "Namespace health status did not match vsi"
                          " health status")
      else:
         raise Exception("Health status summary invalid")


   def checkRangeType(self, vsiRangeType, rangeType):
      """
      Check Interleave set range type
      """
      if vsiRangeType == 0:
         self.assertEqual(rangeType, "volatileRange",
                          "Interleave set range type did not match"
                          " vsi range type")
      elif vsiRangeType == 1:
         self.assertEqual(rangeType, "persistentRange",
                          "Interleave set range type did not match"
                          " vsi range type")
      elif vsiRangeType == 2:
         self.assertEqual(rangeType, "controlRange",
                          "Interleave set range type did not match"
                          " vsi range type")
      elif vsiRangeType == 3:
         self.assertEqual(rangeType, "blockWindowRange",
                          "Interleave set range type did not match"
                          " vsi range type")
      elif vsiRangeType == 4:
         self.assertEqual(rangeType, "volatileVirtualDiskRange",
                          "Interleave set range type did not match"
                          " vsi range type")
      elif vsiRangeType == 5:
         self.assertEqual(rangeType, "volatileVirtualCDRange",
                          "Interleave set range type did not match"
                          " vsi range type")
      elif vsiRangeType == 6:
         self.assertEqual(rangeType, "persistentVirtualDiskRange",
                          "Interleave set range type did not match"
                          " vsi range type")
      elif vsiRangeType == 7:
         self.assertEqual(rangeType, "persistentVirtualCDRange",
                          "Interleave set range type did not match"
                          " vsi range type")
      else:
         raise Exception("Range type invalid")


   def checkNamespaceType(self, vsiNsType, nsType):
      """
      Check Namespace type
      """
      if vsiNsType == 0:
         self.assertEqual(nsType, "blockNamespace",
                          "Namespace type did not match"
                          " vsi namespace type")
      elif vsiNsType == 1:
         self.assertEqual(nsType, "persistentNamespace",
                          "Namespace type did not match"
                          " vsi namespace type")
      else:
         raise Exception("Namespace type invalid")


   def checkNamespaceState(self, vsiState, state):
      """
      Check state of interleave set or namespace
      """
      if vsiState == 0:
         self.assertEqual(state, "invalid",
                          "State unusable did not match vsi type")
      elif vsiState == 1:
         self.assertEqual(state, "notInUse",
                          "State usable did not match vsi type")
      elif vsiState == 2:
         self.assertEqual(state, "inUse",
                          "State invalid did not match vsi type")
      else:
         raise Exception("Invalid state")


   def checkInterleaveSetState(self, vsiState, state):
      """
      Check state of interleave set or namespace
      """
      if vsiState == 0:
         self.assertEqual(state, "invalid",
                          "State unusable did not match vsi type")
      elif vsiState == 1:
         self.assertEqual(state, "active",
                          "State usable did not match vsi type")
      else:
         raise Exception("Invalid state")


   def TestGetNvdimmInfo(self):
      """
      Get details of all NVDIMM information including
      interleave sets and namespace details.
      """
      global vsi

      nvdinfo = self.nvdimmSystem.GetNvdimmSystemInfo()
      self.TestSummary(nvdinfo.summary)
      self.TestDimmList(nvdinfo.dimms)
      self.TestDimmInfo(nvdinfo.dimmInfo)
      self.TestInterleavesetList(nvdinfo.interleaveSet)
      self.TestInterleavesetInfo(nvdinfo.iSetInfo)
      self.TestNamespaceList(nvdinfo.namespace)
      self.TestNamespaceDetails(nvdinfo.nsDetails)


   def TestSummary(self, summary):
      """
      Gets summary of NVDIMMs in the system
      """
      global vsi

      self.assertIsNotNone(summary,
                      "NVD summary should not be None")

      # Get NVDIMM Summary through VSI call
      summaryVsi = vsi.get("/hardware/nvd/system/summary")
      self.assertIsNotNone(summaryVsi,
                      "Summary obtained via VSI should not be None")

      self.assertEqual(summaryVsi['numDimms'], summary.numDimms,
                      "Number of dimms did not match vsi summary")

      self.checkDeviceHealth(summaryVsi['healthStatus'], summary.healthStatus)

      self.assertEqual(summaryVsi['totalCapacity'],
                       summary.totalCapacity,
                       "Total capacity of dimms did not match vsi summary")
      self.assertEqual(summaryVsi['persistentCapacity'],
                       summary.persistentCapacity,
                       "Persistent capacity of dimms did not match vsi summary")
      self.assertEqual(summaryVsi['availablePersistentCapacity'],
                       summary.availableCapacity,
                       "Available persistent capacity of dimms did not match"
                       " vsi summary")
      self.assertEqual(summaryVsi['numInterleavesets'],
                       summary.numInterleavesets,
                       "Number of interleave sets did not match vsi summary")
      self.assertEqual(summaryVsi['numNamespaces'],
                       summary.numNamespaces,
                       "Number of namespaces did not match vsi summary")


   def TestDimmList(self, dimms):
      """
      Test NVDIMM list
      """
      global vsi

      self.assertIsNotNone(dimms,
                      "NVDIMM list should not be None")

      # Get NVDIMM list through VSI call
      dimmsVsi = vsi.list("/hardware/nvd/dimm")
      self.assertIsNotNone(dimmsVsi,
                      "NVDIMM list obtained via VSI should not be None")

      # Loop lists to check if dimm handles are the same
      for d,v in zip(dimms, dimmsVsi):
         # Convert dimm handle in hex to zero filled hex format
         dimmstr = "{0:#0{1}x}".format(d, 10)
         self.assertEqual(dimmstr, v,
                          "Dimm Handle did not match vsi dimm handle")


   def TestDimmHealthinfo(self, stateFlags, healthinfo, vsiHealthinfo):
      """
      Test NVDIMM health information
      XXX: To be completed when we have updates on health information reporting
      """
      # Match hostd health information with VSI obtained information
      """
      self.checkDeviceHealth(vsiHealthinfo['healthStatus'],
                             healthinfo.healthStatus)
      """


   def TestDimmInfo(self, dimminfo):
      """
      Test NVDIMM Information
      """
      global vsi

      self.assertIsNotNone(dimminfo,
                      "NVDIMM Information should not be None")

      # Loop lists to check if dimminfo contents are the same
      for d in dimminfo:
         # Get NVDIMM Information through VSI call
         dimmstr = "{0:#0{1}x}".format(d.dimmHandle, 10)
         v = vsi.get('/hardware/nvd/dimm/%s/dimminfo' % dimmstr)
         self.assertIsNotNone(v, "NVDIMM information obtained via VSI should"
                                 " not be None")

         self.assertEqual(d.dimmHandle, v['dimmHandle'],
                          "Dimm Handle did not match vsi dimm handle")

         self.assertEqual(d.totalCapacity, v['totalCapacity'],
                          "Total Capacity did not match vsi dimm information")
         self.assertEqual(d.persistentCapacity, v['persistentCapacity'],
                          "Persistent Capacity did not match vsi"
                          " dimm information")
         self.assertEqual(d.availablePersistentCapacity,
                          v['availablePersistentCapacity'],
                          "Available Persistent Capacity did not match vsi"
                          " dimm information")
         self.assertEqual(d.volatileCapacity, v['volatileCapacity'],
                          "Volatile Capacity did not match vsi dimm"
                          " information")
         self.assertEqual(d.availableVolatileCapacity,
                          v['availableVolatileCapacity'],
                          "Available Volatile Capacity did not match vsi"
                          " dimm information")

         # Get list of regions part of DIMM
         regionList = vsi.list('/hardware/nvd/dimm/%s/region' % dimmstr)
         self.assertIsNotNone(regionList,
                              "Region list cannot be none")

         stateFlags = 0
         """
         Get vsi region information and match with hostd obtained
         region information.
         """
         for vsiregion,r in zip(regionList, d.regionInfo):
            regionInfo = vsi.get('/hardware/nvd/dimm/%s/region/%s/regioninfo'
                                 % (dimmstr, vsiregion))
            self.assertIsNotNone(regionInfo,
                                 "Region information cannot be none")

            self.assertEqual(r.regionId, regionInfo['id'],
                             "Region ID does not match")
            self.assertEqual(r.setId, regionInfo['setId'],
                             "Setid does not match vsi information")
            self.checkRangeType(regionInfo['type'], r.rangeType);
            self.assertEqual(r.startAddr, regionInfo['startAddr'],
                       "Region start address does not match vsi information")
            self.assertEqual(r.size, regionInfo['size'],
                             "Region Size does not match vsi information")
            self.assertEqual(r.offset, regionInfo['offset'],
                             "Region offset does not match vsi information")
            stateFlags = stateFlags | regionInfo['stateFlags']

         ## Get NVDIMM topology
         vsiTopo = vsi.get('/hardware/nvd/dimm/%s/topology' % dimmstr)
         ## Test NVDIMM representation string
         self.assertIsNotNone(vsiTopo,
                              "Topology can not be null")
         self.assertEqual(vsiTopo['representationStr'], d.representationString,
                          "Representation string does not match vsi information")

         ## Check health information for DIMM
         vsiHealth = vsi.get('/hardware/nvd/dimm/%s/healthinfo' % dimmstr)
         self.assertIsNotNone(vsiHealth,
                              "Health information cannot be none")
         self.TestDimmHealthinfo(stateFlags, d.healthInfo, vsiHealth)


   def TestInterleavesetList(self, sets):
      """
      Test NVDIMM Interleaveset list
      """
      global vsi

      self.assertIsNotNone(sets,
                      "NVDIMM interleave sets should not be None")

      # Get NVDIMM interleave set list through VSI call
      setVsi = vsi.list('/hardware/nvd/interleaveset')
      self.assertIsNotNone(setVsi,
            "NVDIMM Interleave set list obtained via VSI should not be None")

      # Loop lists to check if interleave set contents are the same
      for s,v in zip(sets, setVsi):
         setidstr = "{0:#0{1}x}".format(s, 10)
         self.assertEqual(setidstr, v,
                          "Interleave set ID did not match vsi healthinfo")


   def TestInterleavesetInfo(self, setinfo):
      """
      Test NVDIMM Interleaveset information
      """
      global vsi

      self.assertIsNotNone(setinfo,
                      "NVDIMM Interleave set properties should not be None")

      # Loop lists to check if interleave set property contents are the same
      for s in setinfo:
         # Get NVDIMM interleave set properties through VSI call
         setidstr = "{0:#0{1}x}".format(s.setId, 10)
         v = vsi.get('/hardware/nvd/interleaveset/%s/properties' %
                     setidstr)
         self.assertIsNotNone(v,
               "NVDIMM interleave set properties obtained via VSI should"
               " not be None")

         self.assertEqual(s.setId, v['id'],
                         "Interleave set ID did not match vsi set property")
         self.checkRangeType(v['type'], s.rangeType);
         self.assertEqual(s.baseAddress, v['baseAddress'],
                          "Interleave set Base Address did not match vsi"
                          " set property")
         self.assertEqual(s.size, v['size'],
                          "Interleave set size did not match vsi set property")
         self.assertEqual(s.availableSize, v['availableSize'],
                          "Interleave set available size did not match vsi"
                          " set property")

         self.checkInterleaveSetState(v['state'], s.state)
         dimmList = vsi.list('/hardware/nvd/interleaveset/%s/dimm' %
                             setidstr)
         self.assertIsNotNone(dimmList,
               "List of dimms part of interleave set obtained via VSI should"
               " not be None")

         for d,l in zip(s.deviceList, dimmList):
            # Match device list
            dimmstr = "{0:#0{1}x}".format(d, 10)
            self.assertEqual(dimmstr, l,
                         "Interleave set dimm ID did not match vsi"
                         " device list")


   def TestNamespaceList(self, ns):
      """
      Test NVDIMM Namespace list
      """
      global vsi

      self.assertIsNotNone(ns,
                      "NVDIMM namespace list should not be None")

      # Get NVDIMM namespace list through VSI call
      nsVsi = vsi.list("/hardware/nvd/namespace")
      self.assertIsNotNone(nsVsi,
            "NVDIMM namespace list obtained via VSI should not be None")

      # Loop lists to check if dimm handles are the same
      for n,v in zip(ns, nsVsi):
         self.assertEqual(n.uuid, v,
               "Namespace UUID did not match vsi namespace UUID")



   def TestNamespaceDetails(self, nsdetails):
      """
      Test NVDIMM Namespace information
      """
      global vsi

      self.assertIsNotNone(nsdetails,
                      "NVDIMM Namespace details should not be None")

      # Loop lists to check if namespace details are the same
      for d in nsdetails:
         # Get NVDIMM interleave set properties through VSI call
         v = vsi.get('/hardware/nvd/namespace/%s/details' %
                     (d.uuid))
         self.assertIsNotNone(v,
               "NVDIMM namespace details obtained via VSI should not be None")

         discover = {
               'friendlyName': d.friendlyName,
               'guid': d.uuid
               }
         self.assertEqual(discover, v['discovery'],
                          "Namespace discovery did not match vsi"
                          " namespace details")

         self.assertEqual(d.size, v['size'],
                          "Namespace size did not match vsi"
                          " namespace details")
         self.checkNamespaceType(v['type'], d.type);
         self.checkNsHealthStatus(v['healthStatus'], d.namespaceHealthStatus)
         self.assertEqual(d.interleavesetID, v['interleavesetID'],
                          "Namespace interleaveset ID did not match vsi"
                          " namespace details")
         self.checkNamespaceState(v['state'], d.state)


   def TestIncorrectCreateNamespace(self):
      """
      Incorrect namespace create test with invalid permission.
      """
      create = Vim.Host.NvdimmSystem.PMemNamespaceCreateSpec()
      self.assertIsNotNone(create,
                      "Create cannot be none")
      create.size = 1024
      create.interleavesetID = 1234

      try:
         create_task = self.nvdimmSystem.CreatePMemNamespace(create)
         task.WaitForTask(create_task)
         VerboseLog(logVerbose, create_task.info.error)
         self.assertTrue(create_task.info.result == None)
      except Vim.Fault.InvalidHostState as e:
         pass
      else:
         raise "Create persistent namespace succeded unexpectedly"
         VerboseLog(logVerbose, traceback.format_exc())


   def TestIncorrectDeleteNamespace(self):
      """
      Incorrect namespace delete test with invalid UUID of
      namespace and permission.
      """
      dele = Vim.Host.NvdimmSystem.NamespaceDeleteSpec()
      self.assertIsNotNone(dele,
                      "Delete cannot be none")
      dele.uuid = "78563412-3412-7856-1234-567812345678"

      try:
         delete_task = self.nvdimmSystem.DeleteNamespace(dele)
         task.WaitForTask(delete_task)
         VerboseLog(logVerbose, delete_task.info.error)
         self.assertTrue(delete_task.info.result == None)
      except Vim.Fault.InvalidHostState as e:
         pass
      except Vim.Fault.NotFound as e:
         pass
      except Vmodl.Fault.SystemError as e:
         # This is raised in VmkNvdimmSystemProviderImpl::DeleteNamespace
         # when no GPT exists.
         pass
      else:
         raise "Delete namespace succeded unexpectedly"
         VerboseLog(logVerbose, traceback.format_exc())


def main(argv):
    """
    Test Host NVDIMM Management VModl API
    """
    options = get_options()
    test = TestNvdimmSystem()
    test.setOptions(options)
    suite = unittest.TestSuite()
    suite.addTest(test)
    unittest.TextTestRunner(verbosity=2).run(suite)


# Start program
if __name__ == "__main__":
    main(sys.argv[1:])
