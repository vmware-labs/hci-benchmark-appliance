#!/usr/bin/python

import unittest

import sys
from pyVmomi import Vim
from pyVim.connect import Connect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm
import time

class PowerOpTests(unittest.TestCase):
      
      vmname = "PowerOpVM"      
      v1 = None

      def setUp(self):
	  # Need a vm for base power operations. Create a simple one
	  Connect("jairam-esx")
	  self.vmname = folder.FindUniqueName(self.vmname)
	  self.v1 = vm.CreateQuickDummy(self.vmname, 1)

      def tearDown(self):
          if self.v1 != None:
	     vm.Delete(self.vmname)
	   
      def testPowerCycle(self):
	  vm.PowerOn(self.v1)
	  time.sleep(2)
	  vm.Suspend(self.v1)
	  time.sleep(2)
	  vm.PowerOn(self.v1)
	  time.sleep(2)
	  vm.Reset(self.v1)
	  time.sleep(2)
	  vm.PowerOff(self.v1)
	  time.sleep(2)

      def testSimplePowerCycle(self):
	  vm.PowerOn(self.v1)
	  time.sleep(2)
	  vm.PowerOff(self.v1)
	  time.sleep(2)	  


# Start program
if __name__ == "__main__":
   unittest.main()
