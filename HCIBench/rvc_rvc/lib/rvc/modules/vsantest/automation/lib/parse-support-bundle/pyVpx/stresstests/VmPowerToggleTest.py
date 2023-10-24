import sys
import unittest

import stresstest
from stresstest import LoopIndependent, LoopConflict
from stressopsVm import vmPowerToggle, vmPowerOn, vmPowerOff
import stressutil

from pyVim.connect import Connect
from pyVim import folder
from pyVim import vm

class PowerToggleTestCase(unittest.TestCase):
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
      li = LoopIndependent(op=vmPowerToggle, args=self.args
                           , limit=self.loopLimit)
      li.run()
      li.printResults()
      
   def testConflictSymmetric(self):
      lc = LoopConflict(ops=[vmPowerToggle]*2, args=self.args
                        , limit=self.loopLimit)
      lc.run()
      lc.printResults()

   def testConflictSymmetricNoSync(self):
      lc = LoopConflict(ops=[vmPowerToggle]*2, args=self.args
                        , limit=self.loopLimit
                        , sync=False)
      lc.run()
      lc.printResults()
      
   def testConflictAsymmetric(self):
      lc = LoopConflict(ops=[vmPowerOn,vmPowerOff], args=self.args
                        , limit=self.loopLimit
                        , sync=False)
      lc.run()
      lc.printResults()



if __name__ == "__main__":
   # set the check interval to a low number to increase concurrency for I/O bound ops
   sys.setcheckinterval(1)
   powerToggleSuite = unittest.TestSuite();
   powerToggleSuite.addTest(PowerToggleTestCase("testIndependent"))
   # powerToggleSuite.addTest(PowerToggleTestCase("testConflictSymmetric"))
   # powerToggleSuite.addTest(PowerToggleTestCase("testConflictSymmetricNoSync"))
   # powerToggleSuite.addTest(PowerToggleTestCase("testConflictAsymmetric"))
   """ or, simply say - """
   # powerToggleSuite = unittest.MakeSuite(PowerToggleTestCase)
   unittest.TextTestRunner(verbosity=2).run(powerToggleSuite)
