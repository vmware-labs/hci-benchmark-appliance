#!/usr/bin/python

import unittest

import sys
from pyVmomi import Vim
from connect import Connect
from task import WaitForTask
import folder
import vm
import time
import logging

class VmLifecycleTests(unittest.TestCase):
      
      vmname = "LifecycleVm"      
      v1 = None
      vmCfgFile = None
      vmName = None
      pool = None
      logger = None

      def setUp(self):
         # Need a vm for base power operations. Create a simple one
         Connect(host="localhost", user="administrator")
         self.vmname = folder.FindUniqueName(self.vmname)
         logging.basicConfig(level=logging.DEBUG)
         self.logger = logging.getLogger("")

      def tearDown(self):
         if self.v1 is not None:
	        vm.Delete(self.v1)
	   
      def testLifeCycle(self):
         self.logger.debug("Creating new VM")
         self.v1 = vm.CreateQuickDummy(self.vmname, 1)
         self.vmCfgFile = self.v1.GetConfig().GetFiles().GetVmPathName()
         self.pool = self.v1.GetResourcePool()
         self.vmName = self.v1.GetConfig().GetName()
         self.logger.debug("Created VM " + self.vmCfgFile)

         self.logger.debug("Powering on VM")
         vm.PowerOn(self.v1)
         self.logger.debug("Powering off VM")
         vm.PowerOff(self.v1)
         ## Do some reconfiguring now
         self.logger.debug("Powering on VM")
         vm.PowerOn(self.v1)
         self.logger.debug("Suspending VM")
         vm.Suspend(self.v1)
         self.logger.debug("Powering on VM")
         vm.PowerOn(self.v1)
         self.logger.debug("Taking a snapshot of a VM")
         vm.CreateSnapshot(self.v1, "LifecycleSnapshot", "test snapshot")
         self.logger.debug("Powering off the VM")
         vm.PowerOff(self.v1)
         self.logger.debug("Reverting VM to current snapshot")
         vm.RevertToCurrentSnapshot(self.v1)
         self.logger.debug("Powering off VM")
         vm.PowerOff(self.v1)
         self.logger.debug("Removing all snapshots for the VM")
         vm.RemoveAllSnapshots(self.v1)
         self.logger.debug("Unregistering VM")
         folder.Unregister(self.vmCfgFile)
         self.logger.debug("Registering VM")
         folder.Register(self.vmCfgFile, pool=self.pool)
         self.v1 = folder.Find(self.vmName)
         self.logger.debug("Destroying the VM")
         vm.Destroy(self.v1)
         self.v1 = None


# Start program
if __name__ == "__main__":
   unittest.main()
