#!/usr/bin/env python
'''
ToggleOp implementation for VM power ops
'''
import threading
from operator import xor
from stresstest import ToggleOp
from pyVim import connect, vm, host
from pyVmomi import Vim
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import invt
from pyVim.invt import *


def GetRootFolder(si):
    content = si.RetrieveContent()
    rootFolder = content.GetRootFolder()
    return rootFolder

def GetHostFolder(si):
    content = si.RetrieveContent()
    dataCenter = content.GetRootFolder().GetChildEntity()[0]
    hostFolder = dataCenter.GetHostFolder()
    return hostFolder

def GetComputeResource(si):
    hostFolder = GetHostFolder(si)
    computeResource = hostFolder.GetChildEntity()[0]
    return computeResource

def GetHostSystem(si):
    computeResource = GetComputeResource(si)
    hostSystem = computeResource.GetHost()[0]
    return hostSystem

def GetHostConfigManager(si):
    hostSystem = GetHostSystem(si)
    configManager = hostSystem.GetConfigManager()
    return configManager

class vmHostOpToggle(ToggleOp):

   """
   Toggles VM power on and power off functions
   """
   def __init__(self, args):
      ToggleOp.__init__(self, args)
      self.si = connect.Connect(args['host'])

   def on(self):
      try:
	hostSystem = GetHostSystem(self.si)
	hostConfigManager = hostSystem.GetConfigManager()
	print "Got host system"

	networkSystem = hostConfigManager.GetNetworkSystem()
	networkCfg = networkSystem.GetNetworkConfig()
	print "Network Config : "
	print networkCfg
	
	storageSystem = hostConfigManager.GetStorageSystem()
	storageConfig = storageSystem.GetStorageInfo()
	print "Storage Config : "
    	print storageConfig

	storageDevice = storageSystem.GetStorageDevice()
	print "Storage Device : "
    	print storageDevice
	
	self.success = True
        print self.getClientId() + " on successful"
      except Exception, e:
	print "Failed test due to exception ", e
        print self.getClientId() + " on failed"
        self.success = False
   
   def off(self):
      try:
         self.success = True
         print self.getClientId() + " off successful"
      except:
         self.success = False
         print self.getClientId() + " off failed"

   def syncPreWait(self, barrier):
      """
      save the success flag in barrier.data
      """
      if barrier.data is None: barrier.data = [self.success]
      else: barrier.data.append(self.success)
   def syncPreOpen(self, barrier):
      """
      exactly one client must be successful, so xor over the success
      flags of all clients.
      """
      self.syncPreWait(barrier)
      xsuccess = False
      for success in barrier.data:
         xsuccess = xor(xsuccess, success)
      barrier.data = []
      return xsuccess


