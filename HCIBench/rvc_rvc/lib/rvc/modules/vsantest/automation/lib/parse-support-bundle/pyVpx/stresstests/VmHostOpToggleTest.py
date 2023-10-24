import sys
import unittest

import stresstest
from stresstest import LoopIndependent, LoopConflict
from stressHostOp import vmHostOpToggle
import stressutil

from pyVim.connect import Connect
from pyVim import folder
from pyVim import vm

class HostOpToggleTestCase(unittest.TestCase):
   def setUp(self):
      self.host, self.numClients, self.loopLimit = stressutil.processLoopArgs()
      
      si = Connect(self.host)
      self.vmList = folder.GetAll()
      vm.PowerOffAllVms(self.vmList)
      self.setUpArgs()

   def tearDown(self):
      pass
      
   def setUpArgs(self):
      self.vmLists = stressutil.splitList(self.vmList,self.numClients)
      self.args = [{'host':self.host,
                    'vmlist':vmList} for vmList in self.vmLists]

   def testIndependent(self):
      li = LoopIndependent(op=vmHostOpToggle, args=self.args
                           , limit=self.loopLimit)
      li.run()
      li.printResults()
      
   def testConflictSymmetric(self):
      lc = LoopConflict(ops=[vmHostOpToggle]*2, args=self.args
                        , limit=self.loopLimit)
      lc.run()
      lc.printResults()

   def testConflictSymmetricNoSync(self):
      lc = LoopConflict(ops=[vmHostOpToggle]*2, args=self.args
                        , limit=self.loopLimit
                        , sync=False)
      lc.run()
      lc.printResults()
      
   def testConflictAsymmetric(self):
      lc = LoopConflict(ops=[vmHostOpOn,vmDelDisk], args=self.args
                        , limit=self.loopLimit
                        , sync=False)
      lc.run()
      lc.printResults()



if __name__ == "__main__":
   # set the check interval to a low number to increase concurrency for I/O bound ops
   sys.setcheckinterval(1)
   hostOpToggleSuite = unittest.TestSuite();
   hostOpToggleSuite.addTest(HostOpToggleTestCase("testIndependent"))
   # hostOpToggleSuite.addTest(HostOpToggleTestCase("testConflictSymmetric"))
   # hostOpToggleSuite.addTest(HostOpToggleTestCase("testConflictSymmetricNoSync"))
   # hostOpToggleSuite.addTest(HostOpToggleTestCase("testConflictAsymmetric"))
   """ or, simply say - """
   # hostOpToggleSuite = unittest.MakeSuite(HostOpToggleTestCase)
   unittest.TextTestRunner(verbosity=2).run(hostOpToggleSuite)
