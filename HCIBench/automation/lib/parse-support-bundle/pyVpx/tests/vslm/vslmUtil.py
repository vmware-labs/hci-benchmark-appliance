#!/usr/bin/python

import sys
import random

import pyVmomi
from pyVmomi import Vim, Vmodl, VmomiSupport, SoapStubAdapter
from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import arguments
from pyVim.vm import CreateQuickDummy
from pyVim import vm
from pyVim import vmconfig
from pyVim import host
from pyVim.helpers import Log,StopWatch
from pyVim.vimutil import InvokeAndTrackWithTask, InvokeAndTrack
import atexit
import random
import time

def InitLogger(LoggerIn= None):
   global Logger

   if not LoggerIn:
      Logger = Log
   else:
      Logger = LoggerIn

def Run(vsomgr, vmIn, datastoreIn, LoggerIn=None):
   global vsoMgrTest
   global datastore
   global vm1

   vsoMgrTest = VStorageObjectManagerTest(vsomgr, datastoreIn)
   datastore = datastoreIn
   vm1 = vmIn

   InitLogger(LoggerIn)

   LifeCycleTest()
   ListTest()
   CallbackTest(powerOn = False)
   CallbackTest(powerOn = True)

# Helper functions
def TestTearDown(vsoMgrTest, vmTest):
   Logger("\nTest clean up\n")

   if vmTest:
      vmTest.tearDown()

   if vsoMgrTest:
      vsoMgrTest.tearDown()

def checkTaskResult(task):
    if task.info.GetError():
       raise Exception("Task failed: %s" % (task.info.GetError()))

    Logger("Task result: %s " % (task.info.result))
    return task.info.result

def verifyId(vStorageObject):
   strId = vStorageObject.config.id.id;
   # VIM ID format: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" ("8-4-4-4-12")
   lens = [8, 4, 4, 4, 12]

   sigList = strId.split("-")
   if len(sigList) != 5:
      raise Exception('Invalid ID format: %s' % strId)

   for idx, val in enumerate(sigList):
      if len(val) != lens[idx]:
         raise Exception('Invalid ID format: %s' % strId)

def verifyIds(ids, idsExp):
   if len(ids) < len(idsExp):
      raise Exception('IDs lengths do not match: (%d), expected %d' % (len(ids), len(idsExp)))

   for id in idsExp:
      found = False
      for idI in ids:
         if idI.id == id.id:
            found = True
            break
      if not found:
         raise Exception('ID is missing in the list: %d' % id)

# Tests
def LifeCycleTest():
   Logger("LifeCycleTest Starts.")
   vmTest = None
   try:
      vStorageObject = vsoMgrTest.createDisk()
      vsoMgrTest.retrieve()

      vmTest = VMTest(vm1, vStorageObject, datastore)
      vmTest.attachDisk()
      vmTest.detachDisk()
      vsoMgrTest.delete()

      TestTearDown(vsoMgrTest, vmTest)
      Logger("LifeCycleTest passed")
   except Exception as e:
      TestTearDown(vsoMgrTest, vmTest)
      raise e

# Tests
def ListTest():
   Logger("ListTest Starts\n")
   vmTest = None
   try:
      ids = []

      for n in range(0, 5):
         vsobj = vsoMgrTest.createDisk()
         ids.append(vsobj.config.id)

      idsRet = vsoMgrTest.list()
      verifyIds(idsRet, ids)

      for id in ids:
         vsoMgrTest.setId(id)
         vsoMgrTest.delete()
         ids.remove(id)
         idsRet = vsoMgrTest.list()
         verifyIds(idsRet, ids)

      TestTearDown(vsoMgrTest, vmTest)
      Logger("ListTest passed")
   except Exception as e:
      TestTearDown(vsoMgrTest, vmTest)
      raise e

def CallbackTest(powerOn):
   Logger("CallbackTest Starts. powerOn = %s\n" % powerOn)
   vmTest = None
   try:
      vStorageObject = vsoMgrTest.createDisk()
      vsoMgrTest.retrieve()

      vmTest = VMTest(vm1, vStorageObject, datastore, fullTest = False, powerOn = powerOn)
      vmTest.attachDisk()
      vsoMgrTest.checkConsumer(vmTest.getVmUuid(), True)

      vmTest.detachDisk()
      vsoMgrTest.checkConsumer(vmTest.getVmUuid(), False)

      vmTest.attachDisk()
      vsoMgrTest.checkConsumer(vmTest.getVmUuid(), True)

      # vm snapshot
      newPath = vmTest.snapshot()
      vsoMgrTest.CheckNewPath(newPath)

      TestTearDown(None, vmTest)

      Logger("CallbackTest passed")
   except Exception as e:
      TestTearDown(None, vmTest)
      raise e

# Tests for VStorageObjectManager managed object
class VStorageObjectManagerTest:

   def __init__(self, vStorageObjMgr, datastore):
      self.vsoMgr = vStorageObjMgr
      self.ds = datastore
      self.id = None
      self.NoneDs = False
      self.snapId = None

   # For VC operations only
   def SetNoneDs(self, noneDs):
      self.NoneDs = noneDs

   def createDisk(self):
      Logger("\nCreateTest Start\n")

      spec = Vim.vslm.CreateSpec()
      spec.name = ("vdisk-%s" % random.randint(1,1000))
      spec.capacityInMB = 100

      backing = Vim.vslm.CreateSpec.DiskFileBackingSpec()
      backing.datastore = self.ds
      #backing.provisioningType = "eagerZeroedThick"

      spec.backingSpec = backing

      Logger("Create spec = %s " % (spec))
      task = InvokeAndTrackWithTask(self.vsoMgr.CreateDisk, spec)
      vStorageObj = checkTaskResult(task)
      if not vStorageObj:
         raise Exception("Task failed: No object created")

      verifyId(vStorageObj)
      self.id = vStorageObj.config.id
      Logger("Created vStorageObj = %s" % (vStorageObj))
      return vStorageObj

   def delete(self):
      Logger("\nDeleteTest Start\n")

      Logger("Id = %s" % (self.id))

      if self.NoneDs:
         task = InvokeAndTrackWithTask(self.vsoMgr.DeleteVStorageObject, self.id)
      else:
         task = InvokeAndTrackWithTask(self.vsoMgr.DeleteVStorageObject, self.id, self.ds)
      checkTaskResult(task)

   def retrieve(self, isExist = True):
      Logger("\nGetTest Start\n")

      if self.NoneDs:
         vStorageObj = self.vsoMgr.RetrieveVStorageObject(self.id)
      else:
         vStorageObj = self.vsoMgr.RetrieveVStorageObject(self.id, self.ds)

      if isExist:
         if not vStorageObj:
            raise Exception("Task failed: No object retrieved")
         Logger("Retrieved vStorageObj = %s" % (vStorageObj))
      else:
         if vStorageObj:
            raise Exception("Task failed: Unexpected object retrieved")
         Logger("Retrieved NULL, as expected")

   def list(self):
      Logger("\nListTest Start\n")

      if self.NoneDs:
         ids = self.vsoMgr.ListVStorageObject()
      else:
         ids = self.vsoMgr.ListVStorageObject(self.ds)
      return ids

   def setId(self, id):
      self.id = id


   def createSnapshot(self):
      Logger("\nCreateSnapshotTest Start\n")

      snapshot_name = ("snapshot-%s" % random.randint(1,1000))

      Logger("Create snapshot on fcd = %s with description = %s " \
                             % (self.id, snapshot_name))
      task = InvokeAndTrackWithTask(self.vsoMgr.CreateSnapshot, \
                                    self.id, self.ds, snapshot_name)
      snapId = checkTaskResult(task)
      if not snapId:
         raise Exception("Task failed: No snapshot created")

      # verifyId(snapId)
      self.snapId = snapId
      Logger("Created snapshot = %s" % (snapId))
      return snapId

   def deleteSnapshot(self):
      Logger("\nDeleteSnapshotTest Start\n")

      Logger("SnapshotId = %s" % (self.snapId))

      if not self.NoneDs:
         task = InvokeAndTrackWithTask(self.vsoMgr.DeleteSnapshot, \
                                    self.id, self.ds, self.snapId)
         checkTaskResult(task)

   def getFcdMetadata(self, isExist = True):
      Logger("\nGetFcdMetadata Start\n")

      metadata = self.vsoMgr.RetrieveVStorageObjectMetadata(self.id, self.ds)

      if isExist:
         if not metadata:
            raise Exception("Task failed: No metadata retrieved")
         Logger("Retrieved metadata = %s" % (metadata))
      else:
         if metadata:
            raise Exception("Task failed: Unexpected metadata retrieved")
         Logger("Retrieved NULL, as expected")

   def getFcdMetadataValue(self, snapId = None, isUpdated = False):
      Logger("\nGetFcdMetadataValue Start\n")

      key = "test_key"

      value = self.vsoMgr.RetrieveVStorageObjectMetadataValue(self.id, \
                                    self.ds, snapId, key)
      if not value:
         raise Exception("Task failed: No metadata value retrieved")

      expectedValue = "test_val_updated" if isUpdated else "test_val_added"
      if expectedValue != value:
         raise Exception("Task failed: Unexpected metadata retrieved")
      Logger("Retrieved value %s, as expected" % (value))

   def addFcdMetadata(self):
      Logger("\nAddFcdMetadataTest Start\n")

      metadata = [ vim.KeyValue(key="test_key", value="test_val_added") ]

      Logger("Add metadata = %s " % (metadata))
      if not self.NoneDs:
         task = InvokeAndTrackWithTask( \
                                 self.vsoMgr.UpdateVStorageObjectMetadata, \
                                 self.id, self.ds, metadata)
         checkTaskResult(task)
         Logger("Added metadata = %s" % (metadata))

   def updateFcdMetadata(self):
      Logger("\nUpdateFcdMetadataTest Start\n")

      metadata = [ vim.KeyValue(key="test_key", value="test_val_updated") ]

      Logger("Update metadata = %s " % (metadata))
      if not self.NoneDs:
         task = InvokeAndTrackWithTask( \
                                 self.vsoMgr.UpdateVStorageObjectMetadata, \
                                 self.id, self.ds, metadata)
         checkTaskResult(task)
         Logger("Updated metadata = %s" % (metadata))

   def deleteFcdMetadata(self):
      Logger("\nDeleteFcdMetadataTest Start\n")

      deleteKeys = [ "test_key" ]

      Logger("Delete metadata key = %s " % (deleteKeys))
      if not self.NoneDs:
         task = InvokeAndTrackWithTask( \
                                 self.vsoMgr.UpdateVStorageObjectMetadata, \
                                 self.id, self.ds, deleteKeys = deleteKeys)
         checkTaskResult(task)
         Logger("Deleted metadata key = %s" % (deleteKeys))

   def checkConsumer(self, vmInstanceUuid, isAttached = True):
      vStorageObj = self.vsoMgr.RetrieveVStorageObject(self.id, self.ds)
      if not vStorageObj:
         raise Exception("Task failed: No object retrieved")

      vConfig = vStorageObj.config;
      if isAttached:
         if len(vConfig.consumerId) == 0:
            raise Exception("Test failed: No consumers found in %s. vm id = %s " \
                             % (vConfig, vmInstanceUuid))
         if vConfig.consumerId[0].id != vmInstanceUuid:
            raise Exception("Test failed: consumer does not match: vm id = %s, " \
                            "vsobj.consumerId = %s" % (vmInstanceUuid, \
                            vConfig.consumerId[0].id))
      else:
        if len(vConfig.consumerId) != 0:
           raise Exception("Test failed: vStorageObject still has consumer set, " \
                           "vm id = %s, vsobj.consumerId = %s" %
                           (vmInstanceUuid, vConfig.consumerId))
      Logger("Verifying consumer - success")

   def CheckNewPath(self, newPath):
      vStorageObj = self.vsoMgr.RetrieveVStorageObject(self.id, self.ds)
      if not vStorageObj:
         raise Exception("Task failed: No object retrieved")

      vConfig = vStorageObj.config;
      Logger("VStorageObject path: %s" % (vConfig.backing.filePath))
      Logger("Expected path: %s" % (newPath))

      if vConfig.backing.filePath != newPath:
          raise Exception("Test failed: vStorageObject path %s does not match expected: %s" % \
                           (vConfig.backing.filePath, newPath))

      Logger("Verifying newPath - success")

   def tearDown(self):
      Logger("Cleanup disk")
      try:
         self.vsoMgr.DeleteVStorageObject(self.id, self.ds)
      except Exception as e:
         # ignore
         return

# Helpers of VM Attachment Tests
def createDummyVm(dsName):
   name = ("vm-%s" % random.randint(1,1000))
   vmRet = CreateQuickDummy(name, datastoreName=dsName, \
                           vmxVersion="vmx-13")
   return vmRet

def CheckTaskState(task, faultClass):
   try:
      WaitForTask(task)

      if faultClass:
         raise Exception("Test failed. Task succeeded, expected to fail with %s" \
                          % (faultClass.__name__))

      time.sleep(5)
      Logger("Test succeeded as expected")
   except Vmodl.MethodFault as failure:
      if not faultClass:
         raise Exception("Test failed. Task failed with %s, expected to succeed" \
                         % (failure. __class__.__name__))

      if not isinstance(failure, faultClass):
         raise Exception("Test Failed: got unexpected fault: %s [expected: %s]" \
                         % ( failure. __class__.__name__, faultClass.__name__))

      Logger("Test got expected fault: %s" % ( faultClass.__name__))

def checkVmDisk(vStorageObject, vmRef, attached):
   idExp = vStorageObject.config.id.id
   devices = vmconfig.CheckDevice(vmRef.config, Vim.Vm.Device.VirtualDisk)

   isAttached = False
   for dev in devices:

      if dev.backing.fileName == vStorageObject.config.backing.filePath:
         Logger("Find vm disk by fileName = %s " % (dev.backing.fileName))
         if dev.vDiskId.id == idExp:
            Logger("Verified IDs are identical")
            isAttached = True
            break
         else:
            raise Exception("Found attached disk ID does not match: \
                             vDiskId = %s, but expected = %s" % \
                             (dev.vDiskId.id, idExp))

   if attached != isAttached:
      raise Exception("Task failed: expected attached %r, but got %r" % \
                      (attached, isAttached))

# Tests for VM disk APIs
class VMTest:

   def __init__(self, vmIn, vStorageObject, datastore, fullTest = True, powerOn = False):
      if not vmIn:
         self.vm = createDummyVm(datastore.name)
      else:
         self.vm = vmIn
         Logger("VMTest, vm = %s\n" % (self.vm.name))
      self.vsobj = vStorageObject
      self.ds = datastore
      self.fullTest = fullTest

      if self.vm != vm1 and not fullTest:
         # VM with one scsi controller and disk
         cspec = Vim.Vm.ConfigSpec()
         cspec = vmconfig.AddScsiCtlr(cspec, cfgInfo = self.vm.config)
         capacityKB = 10 * 1024
      # Add eager-zeroed disk so it can be enabled multi-writter
         vmconfig.AddScsiDisk(cspec, cfgInfo = self.vm.config,
                              capacity = capacityKB,
                              datastorename = self.ds.name,
                              thin = False, scrub = True)
         InvokeAndTrack(self.vm.Reconfigure, cspec)

      if powerOn:
         Logger("Powering on VM ")
         vm.PowerOn(self.vm)
         time.sleep(2)

   def attachDisk(self):
      Logger("\nAttachDisk Start, vm = %s\n" % (self.vm.name))

      if not self.fullTest:
         self.attachDiskEz()
      else:
         self.attachDiskEx()

   def attachDiskEz(self):
      id = self.vsobj.config.id
      task = self.vm.AttachDisk(id, self.ds)
      CheckTaskState(task, None)
      checkVmDisk(self.vsobj, self.vm, True)

   def attachDiskEx(self):
      id = self.vsobj.config.id

      # On a VM w/o controller
      task = self.vm.AttachDisk(id, self.ds)
      CheckTaskState(task, Vim.Fault.MissingController)

      # VM with one scsi controller and disk
      cspec = Vim.Vm.ConfigSpec()
      cspec = vmconfig.AddScsiCtlr(cspec, cfgInfo = self.vm.config)
      capacityKB = 10 * 1024

      vmconfig.AddScsiDisk(cspec, cfgInfo = self.vm.config, capacity = capacityKB, datastorename=self.ds.name)
      InvokeAndTrack(self.vm.Reconfigure, cspec)

      disk = vmconfig.CheckDevice(self.vm.config, Vim.Vm.Device.VirtualDisk)[0]
      ctlrKey = disk.controllerKey
      unitNumber = disk.unitNumber

      task = self.vm.AttachDisk(id, self.ds, -99)
      CheckTaskState(task, Vim.Fault.InvalidController)

      task = self.vm.AttachDisk(id, self.ds, ctlrKey, unitNumber)
      CheckTaskState(task, Vmodl.Fault.InvalidArgument)

      task = self.vm.AttachDisk(id, self.ds)
      CheckTaskState(task, None)
      checkVmDisk(self.vsobj, self.vm, True)

      # VM with two SCSI controllers
      if self.vm != vm1:
         cspec = Vim.Vm.ConfigSpec()
         cspec = vmconfig.AddScsiCtlr(cspec, cfgInfo = self.vm.config)
         InvokeAndTrack(self.vm.Reconfigure, cspec)

         task = self.vm.AttachDisk(id, self.ds)
         CheckTaskState(task, Vim.Fault.MissingController)

   def detachDisk(self):
      Logger("\nDetachDisk Start, vm = %s\n" % (self.vm.name))
      id = self.vsobj.config.id

      task = self.vm.DetachDisk(id)
      CheckTaskState(task, None)
      checkVmDisk(self.vsobj, self.vm, False)

   def snapshot(self):
      Logger("\nVM createSnapshot Start, vm = %s\n" % (self.vm.name))
      ssName = ("ss-%s" % random.randint(1,1000))
      vm.CreateSnapshot(self.vm, ssName, "snaphost", False, False)
      time.sleep(5)

      devices = vmconfig.CheckDevice(self.vm.config, Vim.Vm.Device.VirtualDisk)
      newPath = ""
      for dev in devices:
         if dev.backing.parent and \
            dev.backing.parent.fileName == self.vsobj.config.backing.filePath:
            newPath = dev.backing.fileName
            break

      return newPath

   def getVmUuid(self):
      return self.vm.config.instanceUuid

   def tearDown(self):
      if self.vm and self.vm != vm1:
            Logger("Destroy VM")
            self.vm.PowerOff()
            self.vm.Destroy()
