#!/usr/bin/python

"""
Copyright 2016-2022 VMware, Inc.  All rights reserved. -- VMware Confidential

A set of simple tests to exercise support for VM encryption. These
test must be targetted at an ESX host.
"""

import atexit
import os
import subprocess
import sys
import time
import uuid
from collections import namedtuple

# Publically available
from pyVmomi import Vim, Vmodl
from pyVim.connect import SmartConnect, Disconnect, SetSi

# VMware internal helpers
from pyVim import arguments
from pyVim import host
from pyVim import folder
from pyVim import vm, vmconfig
from pyVim.task import WaitForTask
from pyVim.helpers import Log, StopWatch, MemoryLeakChecker
from pyVim.account import CreateRole, RemoveRole, GetRoleId

# The vimcrypto package was factored out of this file, and importing
# all function names is easier than fixing a lot of lines.
from vimcrypto import *

_testName = "VMcrypt"
_status = "FAIL"
_hostname = None
_runObjTests = True

##############################################################################
##
## Feature check.
##
## (Adapted from pyVigorTemplate.py.)
##
##############################################################################

def CreateFeatureDictFromFile(fileName, delimiter='='):
   if fileName is None or not os.path.exists(fileName):
      return None
   d = {}
   try:
      with open(fileName, 'r') as f:
         for line in f:
            key, val = line.split(delimiter, 1)
            key = key.strip()
            val = val.strip().lower()
            state = val == 'enabled'
            d[key] = state
   except IOError:
      raise Exception('Failed to open feature file %s' % fileName)
   return d

class ESXFeatureCheck(dict):
   """Helper class to initialize and check for feature states."""
   def __init__(self, value=None):
      self._useCfgFile = value is not None
      if self._useCfgFile:
         for key in value:
            self.__setitem__(key, value[key])

   def __getattr__(self, name):
      if self._useCfgFile:
         if name in self:
            return self[name]
      else:
         # When branches are near a release state, vsphereFeatures.cfg is
         # removed. Python site-packages contains a featureState module to use
         # instead during this time. See PR1638856.
         try:
            import featureState

            if name in featureState.featureNameList:
               return getattr(featureState, name)
         except ImportError:
            pass

      return True

featureFile = '/etc/vmware/vsphereFeatures/vsphereFeatures.cfg'
featureStateOf = ESXFeatureCheck(CreateFeatureDictFromFile(featureFile))

def IsLocalhostESX():
   return os.uname()[0] == "VMkernel"

def VerifyException(operation, exception, msg=None, msgid=None):
   try:
      operation()
   except exception as e:
      if msg:
         if not msg in e.msg:
            raise
      if msgid:
         for locMsg in e.faultMessage:
            if locMsg.key == msgid:
               break
         else:
            raise
   else:
      raise Exception("Encryption operation succeeded.")

def VerifyExceptionLocked(operation, keyId, providerId):
   try:
      operation()
   except Vim.Fault.EncryptionKeyRequired as e:
      def _findMsgId(msgid):
         for locMsg in e.faultMessage:
            if locMsg.key == msgid:
               break
         else:
            raise
      _findMsgId("msg.hostd.vmState.locked")
      if providerId:
         _findMsgId("msg.hostd.vmState.lockedProviderId")
      if keyId:
         _findMsgId("msg.hostd.vmState.lockedKeyId")
         cryptoKeyId = CreateCryptoKeyId(keyId, providerId)
         if not e.requiredKey or len(e.requiredKey) != 1:
            raise
         if not MatchCryptoKeyId(e.requiredKey[0], cryptoKeyId):
            raise
   else:
      raise Exception("Encryption operation succeeded.")

def _VerifyPowerStates(vm1, verify):
   verify()
   current = vm1.runtime.powerState
   if current == Vim.VirtualMachine.PowerState.poweredOn:
      vm.PowerOff(vm1)
      verify()
      vm.PowerOn(vm1)
   elif current == Vim.VirtualMachine.PowerState.poweredOff:
      vm.PowerOn(vm1)
      verify()
      vm.PowerOff(vm1)
   else:
      assert current == Vim.VirtualMachine.PowerState.suspended

def VerifyEncryptedVM(vm1, obj, keyId, providerId):
   _VerifyPowerStates(vm1, lambda: VerifyEncrypted(obj, keyId, providerId))

def VerifyNotEncryptedVM(vm1, obj):
   _VerifyPowerStates(vm1, lambda: VerifyNotEncrypted(obj))
   VerifyNotEncryptedDisks(vm1)

def VerifyConnectionState(vm1, connectionState):
   if vm1.runtime.connectionState != connectionState:
      raise ValueError("Unexpected connection state: %s" %
                       vm1.runtime.connectionState)

def VerifyCryptoState(vm1, cryptoState):
   if vm1.runtime.cryptoState != cryptoState:
      raise ValueError("Unexpected crypto state: %s" %
                       vm1.runtime.cryptoState)

def WithRetry(operation):
   # Hostd reloads the VM in the background when keys are added to
   # CryptoManager. This is lame but we must tolerate it...
   tries = 100
   while True:
      try:
         operation()
         break
      except Exception:
         tries -= 1
         if tries == 0:
            raise
      time.sleep(1)

def PowerCycle(vm1):
   vm.PowerOn(vm1)
   vm.PowerOff(vm1)

def FindDatastoreObject(dsName, si):
   hs = host.GetHostSystem(si)
   datastores = hs.GetDatastore()
   for ds in datastores:
      if (ds.name == dsName):
         return ds
   raise Exception("Error finding datastore object: %s" % dsName)

def InExtraConfig(extraConfig, key):
   for item in extraConfig:
      if item.key == key:
         return True
   return False

def GetExtraConfig(extraConfig, key):
   for item in extraConfig:
      if item.key == key:
         return item.value
   raise Exception("'%s' not in extraConfig" % key)

def AddExtraConfig(extraConfig, key, value):
   extraConfig += [Vim.Option.OptionValue(key=key, value=value)]

def CreateVirtualDisk(vdiskMgr, diskPath, diskSpec):
   task = vdiskMgr.CreateVirtualDisk(diskPath, None, diskSpec)
   WaitForTask(task)
   return task.info.result

def CopyVirtualDisk(vdiskMgr, srcPath, dstPath, diskSpec):
   task = vdiskMgr.CopyVirtualDisk(srcPath, None, dstPath, None,
                                   diskSpec, False);
   WaitForTask(task)
   return task.info.result

def CreateVirtualDiskSpec(policy=None, cryptoSpec=None):
   diskSpec = Vim.VirtualDiskManager.FileBackedVirtualDiskSpec()
   diskSpec.diskType = "thin"
   diskSpec.adapterType = "lsiLogic"
   diskSpec.capacityKb = 4 * 1024
   diskSpec.crypto = cryptoSpec
   diskSpec.profile = vmconfig.CreateProfileSpec(policy)
   return diskSpec

def TestSanity(si, vm1, keyId, providerId):
   """Verify absolute minimum functionality.
   """
   # Confirm that the VM is not initially encrypted.
   VerifyNotEncrypted(vm1.config)

   # Confirm that the VM can be encrypted.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedVM(vm1, vm1.config, keyId, providerId)

   # Add an encrypted disk to the VM.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # Power cycle to make sure the VMX can find the keys.
   PowerCycle(vm1)

   # Decrypt the disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecDecrypt()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultEmptyPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyNotEncryptedDisks(vm1)

   # Delete the disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   vm.Reconfigure(vm1, configSpec)

   # Confirm that the VM can be decrypted.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecDecrypt()
   vm.Reconfigure(vm1, configSpec)
   VerifyNotEncryptedVM(vm1, vm1.config)

   # Power cycle to make sure the VM has a sane config.
   PowerCycle(vm1)

def TestCreateVm(si, vmname, dsName, keep, keyId, providerId):
   """Create an encrypted VM with one encrypted disk.
   """
   # Create an encrypted VM with one encrypted disk.
   configSpec = vmconfig.CreateDefaultSpec(name=vmname,
                                           datastoreName=dsName)
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   configSpec.crypto = cryptoSpec
   vmconfig.AddScsiCtlr(configSpec)
   vmconfig.AddScsiDisk(configSpec, datastorename=dsName,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm1 = vm.CreateFromSpec(configSpec)

   # Confirm that the VM is encrypted.
   VerifyEncrypted(vm1.config, keyId, providerId)

   # Confirm that the disk is encrypted.
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # Power cycle for verification.
   PowerCycle(vm1)

   if not keep:
      vm.Destroy(vm1)

def TestCloneVm(si, vmname, dsName, keep, keyId, providerId):
   """Create an encrypted VM and then make a copy.

   Hostd doesn't implement the Vim clone or relocate APIs, but we still
   want to test those code paths without needing VC. This test creates
   a very simple VM, and then creates a second VM with the same same
   encryption bundle as the first VM.
   """
   def _runTest(vm1):
      # Clones are often created from a snapshot point.
      vm.CreateSnapshot(vm1, "Encrypted", None, memory=False)
      snap1 = vm1.snapshot.currentSnapshot
      VerifyEncrypted(snap1.config, keyId, providerId)

      # Get the encryption bundle from the first VM.
      bundle = GetExtraConfig(snap1.config.extraConfig, "encryption.bundle")

      # Create a second VM with the same encryption state as the first.
      configSpec = vmconfig.CreateDefaultSpec(name="%s-encrypt" %vmname,
                                              datastoreName=dsName)
      cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
      configSpec.crypto = cryptoSpec
      AddExtraConfig(configSpec.extraConfig, "encryption.bundle", bundle)
      vm2 = vm.CreateFromSpec(configSpec)
      VerifyEncrypted(vm2.config, keyId, providerId)

      # Power cycle for verification.
      PowerCycle(vm2)

      if not keep:
         vm.Destroy(vm2)


      # Create a VM with the first VM encryption state decrypted.
      configSpec = vmconfig.CreateDefaultSpec(name="%s-decrypt" %vmname,
                                              datastoreName=dsName)
      cryptoSpec = CreateCryptoSpecDecrypt()
      configSpec.crypto = cryptoSpec
      AddExtraConfig(configSpec.extraConfig, "encryption.bundle", bundle)
      vm3 = vm.CreateFromSpec(configSpec)
      VerifyNotEncrypted(vm3.config)

      # Power cycle for verification.
      PowerCycle(vm3)

      if not keep:
         vm.Destroy(vm3)

      # Generate new keyID to use for recrypt and rekey.
      cryptoMgr = si.RetrieveContent().cryptoManager
      newKeyId, newProviderId, cryptoKey = CreateCryptoKeyDefault()
      cryptoMgr.AddKeys([cryptoKey])

      # Create a VM with the first VM encryption state rekeyed with new keys.
      configSpec = vmconfig.CreateDefaultSpec(name="%s-rekey" %vmname,
                                              datastoreName=dsName)
      cryptoSpec = CreateCryptoSpecRekey(newKeyId, newProviderId)
      configSpec.crypto = cryptoSpec
      AddExtraConfig(configSpec.extraConfig, "encryption.bundle", bundle)
      vm4 = vm.CreateFromSpec(configSpec)
      VerifyEncrypted(vm4.config, newKeyId, newProviderId)

      # Power cycle for verification.
      PowerCycle(vm4)

      if not keep:
         vm.Destroy(vm4)

      # Create a VM with the first VM encryption state recrypted with new keys.
      configSpec = vmconfig.CreateDefaultSpec(name="%s-recrypt" %vmname,
                                              datastoreName=dsName)
      cryptoSpec = CreateCryptoSpecRecrypt(newKeyId, newProviderId)
      configSpec.crypto = cryptoSpec
      AddExtraConfig(configSpec.extraConfig, "encryption.bundle", bundle)
      vm5 = vm.CreateFromSpec(configSpec)
      VerifyEncrypted(vm5.config, newKeyId, newProviderId)

      # Power cycle for verification.
      PowerCycle(vm5)

      if not keep:
         vm.Destroy(vm5)

   # Create a very simple encrypted VM; no disks.
   configSpec = vmconfig.CreateDefaultSpec(name=vmname,
                                           datastoreName=dsName)
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   configSpec.crypto = cryptoSpec
   vm1 = vm.CreateFromSpec(configSpec)
   VerifyEncrypted(vm1.config, keyId, providerId)

   # Power-cycle the VM so that metadata files are created (e.g. nvram).
   PowerCycle(vm1)

   _runTest(vm1)
   vm.PowerOn(vm1)
   _runTest(vm1)
   vm.PowerOff(vm1)

   if not keep:
      vm.Destroy(vm1)

def TestRekey(si, vm1, keyId, providerId):
   """Verify that the VM container and disks can be rekeyed.
   """
   # Confirm that the VM is not initially encrypted.
   VerifyNotEncrypted(vm1.config)

   # Confirm that the VM can be encrypted.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedVM(vm1, vm1.config, keyId, providerId)

   # Add an encrypted disk to the VM.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # Add a new key for powered off testing.
   newKeyId, newProviderId, newCryptoKey = CreateCryptoKeyDefault()
   cryptoMgr = si.RetrieveContent().cryptoManager
   cryptoMgr.AddKeys([newCryptoKey])

   # Rekey the VM while powered off.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecRekey(newKeyId, newProviderId)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedVM(vm1, vm1.config, newKeyId, newProviderId)

   # Rekey the disk while powered off.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   rekeySpec = CreateCryptoSpecRekey(newKeyId, newProviderId)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation, crypto=rekeySpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedDisks(vm1, newKeyId, newProviderId)

   # Add a new key for powered on testing.
   newKeyId, newProviderId, newCryptoKey = CreateCryptoKeyDefault()
   cryptoMgr = si.RetrieveContent().cryptoManager
   cryptoMgr.AddKeys([newCryptoKey])

   # Power on the VM to test powered on rekey.
   vm.PowerOn(vm1)

   # Rekey the VM while powered on.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecRekey(newKeyId, newProviderId)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedVM(vm1, vm1.config, newKeyId, newProviderId)

   # Rekey the disk while powered on.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   rekeySpec = CreateCryptoSpecRekey(newKeyId, newProviderId)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation, crypto=rekeySpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedDisks(vm1, newKeyId, newProviderId)

   # Power-off to leave it in the initial configuration.
   vm.PowerOff(vm1)

   # Delete the disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   vm.Reconfigure(vm1, configSpec)

   # Decrypt the VM to leave it in the initial configuration.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecDecrypt()
   vm.Reconfigure(vm1, configSpec)
   VerifyNotEncrypted(vm1.config)

def TestRekeySnapshots(si, vm1, keyId, providerId):
   """Verify VM and disk rekey behavior with snapshots.
   """
   # Confirm that the VM is not initially encrypted.
   VerifyNotEncrypted(vm1.config)

   # Add a disk and power-cycle to make snapshots more interesting.
   configSpec = Vim.Vm.ConfigSpec()
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config)
   vm.Reconfigure(vm1, configSpec)
   PowerCycle(vm1)

   # Encrypt the VM and take a snapshot tree before rekey.
   EncryptVM(vm1, keyId, providerId)
   vm.CreateSnapshot(vm1, "Encrypted", None)
   vm.CreateSnapshot(vm1, "Encrypted", None)

   # Add a new key for powered off testing.
   newKeyId1, newProviderId1, newCryptoKey1 = CreateCryptoKeyDefault()
   cryptoMgr = si.RetrieveContent().cryptoManager
   cryptoMgr.AddKeys([newCryptoKey1])

   # Rekey the VM with snapshots while powered off.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecRekey(newKeyId1, newProviderId1)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedVM(vm1, vm1.config, newKeyId1, newProviderId1)
   VerifyEncrypted(vm1.snapshot.currentSnapshot.config, newKeyId1,
                   newProviderId1)

   # Rekey the disk with snapshots while powered off.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   rekeySpec = CreateCryptoSpecRekey(newKeyId1, newProviderId1)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation, crypto=rekeySpec)

   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedDisks(vm1, newKeyId1, newProviderId1)

   # Add a new key for powered on testing.
   newKeyId2, newProviderId2, newCryptoKey2 = CreateCryptoKeyDefault()
   cryptoMgr.AddKeys([newCryptoKey2])

   # Power on the VM to test powered on rekey.
   vm.PowerOn(vm1)

   # Rekey the VM with snapshots while powered on.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecRekey(newKeyId2, newProviderId2)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedVM(vm1, vm1.config, newKeyId2, newProviderId2)
   VerifyEncrypted(vm1.snapshot.currentSnapshot.config, newKeyId2,
                   newProviderId2)

   # Rekey the disk with snapshots while powered on.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   rekeySpec = CreateCryptoSpecRekey(newKeyId2, newProviderId2)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation, crypto=rekeySpec)

   vm.Reconfigure(vm1, configSpec),
   VerifyEncryptedDisks(vm1, newKeyId2, newProviderId2)

   # Restore the VM to the original state and power-cycle for sanity.
   vm.PowerOff(vm1)
   vm.RemoveAllSnapshots(vm1)
   DecryptVM(vm1)
   PowerCycle(vm1)

   # Delete the disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   vm.Reconfigure(vm1, configSpec)

def TestNoOp(si, vm1, keyId, providerId):
   """Verify that a CryptoSpecNoOp does not encrypt.
   """
   # Confirm that the VM is not initially encrypted.
   VerifyNotEncrypted(vm1.config)

   for i in range(2):
      noopSpec = CreateCryptoSpecNoOp()

      # Edit the VM and add a disk with a NoOp crypto spec.
      configSpec = Vim.Vm.ConfigSpec()
      configSpec.crypto = noopSpec
      vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config, datastorename=dsName,
                           crypto=noopSpec)
      vm.Reconfigure(vm1, configSpec)
      VerifyNotEncrypted(vm1.config)

      # Edit a disk with a NoOp crypto spec.
      disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
      configSpec = Vim.Vm.ConfigSpec()
      operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
      vmconfig.AddDeviceToSpec(configSpec, disk, operation, crypto=noopSpec)
      vm.Reconfigure(vm1, configSpec)
      VerifyNotEncryptedDisks(vm1)

      # No operation specified means a no-op. Decrypt will be ignored.
      disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
      configSpec = Vim.Vm.ConfigSpec()
      operation = None
      decryptSpec = CreateCryptoSpecDecrypt()
      vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                               policy=DefaultCryptoPolicy(), crypto=decryptSpec)
      vm.Reconfigure(vm1, configSpec)
      VerifyNotEncryptedDisks(vm1)

      # Delete the disk.
      disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
      configSpec = Vim.Vm.ConfigSpec()
      fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
      vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
      vm.Reconfigure(vm1, configSpec)

      # Do it again with the VM powered on.
      if vm1.runtime.powerState == Vim.VirtualMachine.PowerState.poweredOff:
         vm.PowerOn(vm1)

   # Power-off to leave it in the initial configuration.
   vm.PowerOff(vm1)

def TestKeyNotFound(si, vm1, keyId, providerId):
   """Verify encryption failure when a key is not found.
   """
   # Confirm that the VM is not initially encrypted.
   VerifyNotEncrypted(vm1.config)

   # Try encrypting with a bogus key identifier.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt("xzy", "abc")
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.GenericVmConfigFault,
                   msg="The specified key was not found.")
   VerifyNotEncrypted(vm1.config)

   # Encrypt the VM before encrypting disks.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncrypted(vm1.config, keyId, providerId)

   # Rekey VM while powered off with a bogus identifier.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecRekey("xzy", "abc")
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.GenericVmConfigFault,
                   msg="The specified key was not found.")
   VerifyEncrypted(vm1.config, keyId, providerId)

   # Rekey VM while powered on with a bogus identifier.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecRekey("xzy", "abc")
   vm.PowerOn(vm1)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.GenericVmConfigFault,
                   msg="The specified key was not found.")
   VerifyEncrypted(vm1.config, keyId, providerId)
   vm.PowerOff(vm1)
   VerifyEncrypted(vm1.config, keyId, providerId)

   # Try adding a disk with a bogus key identifier.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt("xzy", "abc")
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vmodl.Fault.SystemError,
                   msg="Error creating disk Key locator")
   VerifyNotEncryptedDisks(vm1)

   # Add an encrypted disk to the VM.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # Rekey the disk while powered off with a bogus identifier.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   rekeySpec = CreateCryptoSpecRekey("xzy", "abc")
   vmconfig.AddDeviceToSpec(configSpec, disk, operation, crypto=rekeySpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.GenericVmConfigFault,
                   msg="Key locator error")
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # Rekey the disk while powered on with a bogus identifier.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   rekeySpec = CreateCryptoSpecRekey("xzy", "abc")
   vmconfig.AddDeviceToSpec(configSpec, disk, operation, crypto=rekeySpec)
   vm.PowerOn(vm1)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.GenericVmConfigFault,
                   msg="Key locator error")
   VerifyEncryptedDisks(vm1, keyId, providerId)
   vm.PowerOff(vm1)
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # Decrypt the disk so that we can test enabling encryption.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecDecrypt()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultEmptyPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyNotEncryptedDisks(vm1)

   # Encrypt the disk with a bogus identifier.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt("xzy", "abc")
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vmodl.Fault.SystemError,
                   msg="Key locator error")
   VerifyNotEncryptedDisks(vm1)

   # Delete the added disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   vm.Reconfigure(vm1, configSpec)

   # Decrypt the VM to leave it in the initial configuration.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecDecrypt()
   vm.Reconfigure(vm1, configSpec)
   VerifyNotEncrypted(vm1.config)

def TestKeyNoProvider(si, vm1, keyId, providerId):
   """Verify encryption success when a key provider is not specified.
   """
   cryptoMgr = si.RetrieveContent().cryptoManager

   # Confirm that the VM is not initially encrypted.
   VerifyNotEncrypted(vm1.config)

   # Add a disk and power-cycle to make things more interesting.
   configSpec = Vim.Vm.ConfigSpec()
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config)
   vm.Reconfigure(vm1, configSpec)
   PowerCycle(vm1)

   # Create a key that has no providerId specified for encryption.
   keyId = uuid.uuid4().hex
   cryptoKey = CreateCryptoKeyPlain(keyId, None)
   cryptoMgr.AddKeys([cryptoKey])

   # Encrypt the entire VM while powered off.
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, None)
   ChangeVMEncryption(vm1, cryptoSpec, DefaultCryptoPolicy())
   VerifyAllEncryptedDisks(vm1, keyId, None)
   VerifyEncryptedVM(vm1, vm1.config, keyId, None)

   # Create a key that has no providerId specified for deep recrypt.
   keyId = uuid.uuid4().hex
   cryptoKey = CreateCryptoKeyPlain(keyId, None)
   cryptoMgr.AddKeys([cryptoKey])

   # Recrypt the VM while powered off.
   cryptoSpec = CreateCryptoSpecRecrypt(keyId, None)
   ChangeVMEncryption(vm1, cryptoSpec, DefaultCryptoPolicy())
   VerifyAllEncryptedDisks(vm1, keyId, None)
   VerifyEncryptedVM(vm1, vm1.config, keyId, None)

   # Create a key that has no providerId specified for shallow recrypt.
   keyId = uuid.uuid4().hex
   cryptoKey = CreateCryptoKeyPlain(keyId, None)
   cryptoMgr.AddKeys([cryptoKey])

   # Rekey the VM while powered off.
   cryptoSpec = CreateCryptoSpecRekey(keyId, None)
   ChangeVMEncryption(vm1, cryptoSpec, DefaultCryptoPolicy())
   VerifyAllEncryptedDisks(vm1, keyId, None)
   VerifyEncryptedVM(vm1, vm1.config, keyId, None)

   # Another key that has no providerId specified for shallow recrypt.
   keyId = uuid.uuid4().hex
   cryptoKey = CreateCryptoKeyPlain(keyId, None)
   cryptoMgr.AddKeys([cryptoKey])

   # Rekey the VM while powered on.
   cryptoSpec = CreateCryptoSpecRekey(keyId, None)
   vm.PowerOn(vm1)
   ChangeVMEncryption(vm1, cryptoSpec, DefaultCryptoPolicy())
   VerifyAllEncryptedDisks(vm1, keyId, None)
   VerifyEncrypted(vm1.config, keyId, None)
   vm.PowerOff(vm1)
   VerifyEncrypted(vm1.config, keyId, None)

   # Add a new disk with no provider Id.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, None)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyAllEncryptedDisks(vm1, keyId, None)

   # A 'scrubbed' with no key provider takes a different path in hostd.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, None)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config, scrub=True,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyAllEncryptedDisks(vm1, keyId, None)

   # Delete the three added disks.
   for i in range(3):
      disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
      configSpec = Vim.Vm.ConfigSpec()
      fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
      vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
      vm.Reconfigure(vm1, configSpec)

   # Decrypt the VM to leave it in the initial configuration.
   DecryptVM(vm1)

def TestNoKey(si, vmname, dsName, keep, keyId, providerId):
   """Verify that a VM can be managed when the key is missing.

   When the key for a VM is missing on a host, the VM can still be
   registered. It will fail to power-on, but can be reloaded and
   deleted.
   """
   cryptoMgr = si.RetrieveContent().cryptoManager

   # Use our own keys because we'll be removing them; one for the
   # VM and one for the disks.
   keyId1, providerId1, cryptoKey1 = CreateCryptoKeyDefault()
   keyId2, providerId2, cryptoKey2 = CreateCryptoKeyDefault()
   keyIds = [CreateCryptoKeyId(keyId1, providerId1),
             CreateCryptoKeyId(keyId2, providerId2)]

   cryptoMgr.AddKeys([cryptoKey1, cryptoKey2])

   # First we create a simple encrypted VM with one disk, and perform
   # no other operations on it. We verify that this simple VM can be
   # deleted when no keys are available.
   configSpec = vmconfig.CreateDefaultSpec(name="%s-nokey" % vmname,
                                           datastoreName=dsName)
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId1, providerId1)
   vmconfig.AddScsiCtlr(configSpec)
   vmconfig.AddScsiDisk(configSpec, datastorename=dsName,
                        policy=DefaultCryptoPolicy(),
                        crypto=CreateCryptoSpecEncrypt(keyId2, providerId2))
   vm1 = vm.CreateFromSpec(configSpec)
   VerifyEncrypted(vm1.config, keyId1, providerId1)
   VerifyEncryptedDisks(vm1, keyId2, providerId2)

   # Remove the keys, and verify that the VM can be deleted from disk
   # even when the .vmx file is locked.
   VerifyCryptoState(vm1, "unlocked")
   cryptoMgr.RemoveKeys(keyIds, True)
   vm1.Reload()
   WithRetry(lambda: VerifyConnectionState(vm1, "invalid"))
   VerifyCryptoState(vm1, "locked")
   VerifyEncrypted(vm1.config, keyId1, providerId1)
   VerifyEncryptedDisks(vm1, keyId2, providerId2)
   vm.Destroy(vm1)

   cryptoMgr.AddKeys([cryptoKey1, cryptoKey2])

   # Second, create the same simple VM again. This time we'll create
   # snapshots and perform power operations.
   configSpec = vmconfig.CreateDefaultSpec(name="%s-nokey" % vmname,
                                           datastoreName=dsName)
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId1, providerId1)
   vmconfig.AddScsiCtlr(configSpec)
   vmconfig.AddScsiDisk(configSpec, datastorename=dsName,
                        policy=DefaultCryptoPolicy(),
                        crypto=CreateCryptoSpecEncrypt(keyId2, providerId2))
   vm1 = vm.CreateFromSpec(configSpec)
   VerifyEncrypted(vm1.config, keyId1, providerId1)
   VerifyEncryptedDisks(vm1, keyId2, providerId2)

   # Power cycle, and add snapshots for a more interesting VM.
   PowerCycle(vm1)
   vm.CreateSnapshot(vm1, "Snap1", None)
   vm.CreateSnapshot(vm1, "Snap2", None)
   PowerCycle(vm1)
   VerifyEncrypted(vm1.config, keyId1, providerId1)
   VerifyEncryptedDisks(vm1, keyId2, providerId2)
   WithRetry(lambda: VerifyConnectionState(vm1, "connected"))
   VerifyCryptoState(vm1, "unlocked")

   # Remove the key, and power-on the VM. Hostd will now detect that
   # the VM is locked, but we should still be able to match the keyId
   cryptoMgr.RemoveKeys(keyIds, True)
   VerifyException(lambda: vm.PowerOn(vm1),
                   Vim.Fault.EncryptionKeyRequired)
   WithRetry(lambda: VerifyConnectionState(vm1, "invalid"))
   VerifyCryptoState(vm1, "locked")
   VerifyEncrypted(vm1.config, keyId1, providerId1)
   VerifyEncryptedDisks(vm1, keyId2, providerId2)

   # Put the first key back on the host, and power-on should still fail.
   cryptoMgr.AddKey(cryptoKey1)
   WithRetry(lambda: VerifyConnectionState(vm1, "connected"))
   # Hostd reloads the VM asynchronously after keys are added. This is
   # good for performance, but bad for scripting. Add a retry loop...
   WithRetry(lambda: VerifyEncrypted(vm1.config, keyId1, providerId1))
   WithRetry(lambda: VerifyEncryptedDisks(vm1, keyId2, providerId2))
   # The connection state does not consider when we have keys for disks.
   WithRetry(lambda: VerifyException(lambda: vm.PowerOn(vm1),
                                     Vim.Fault.GenericVmConfigFault,
                                     msgid="msg.disk.encrypted"))
   VerifyCryptoState(vm1, "unlocked")

   # Put the second key back on the host, and power-on should succeed.
   cryptoMgr.AddKey(cryptoKey2)
   VerifyEncrypted(vm1.config, keyId1, providerId1)
   VerifyEncryptedDisks(vm1, keyId2, providerId2)
   PowerCycle(vm1)
   VerifyCryptoState(vm1, "unlocked")

   # Remove the keys again, and re-register the VM. It should still be in
   # the locked state, and it can still be deleted.
   cryptoMgr.RemoveKeys(keyIds, True)
   vm1.Reload()
   WithRetry(lambda: VerifyConnectionState(vm1, "invalid"))
   VerifyCryptoState(vm1, "locked")
   VerifyEncrypted(vm1.config, keyId1, providerId1)
   VerifyEncryptedDisks(vm1, keyId2, providerId2)

   vmxPath = vm1.GetSummary().GetConfig().GetVmPathName()
   vm1.Unregister()
   folder.Register(vmxPath)
   vm1 = folder.Find("%s-nokey" % vmname)
   WithRetry(lambda: VerifyConnectionState(vm1, "invalid"))
   vm.Destroy(vm1)

def TestInvalidPolicy(si, vm1, keyId, providerId):
   """Verify errors when an policy is provided with a CryotoSpec.

   Some failures below that throw InvalidArgument or GenericVmConfigFault,
   but we should be throwing InvalidDeviceSpec for consistency. It's
   difficult to check for these failures up-front, and they are unlikely
   to happen in real deployments because VC will fill in the CryptoSpec.
   """
   # Confirm that the VM can be encrypted.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncrypted(vm1.config, keyId, providerId)

   # CryptoSpecNoOp with encryption IO filter.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecNoOp()
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vmodl.Fault.InvalidArgument)
   VerifyNotEncryptedDisks(vm1)

   # CryptoSpecNoOp with encryption IO filter, scrubbed.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecNoOp()
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config, scrub=True,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vmodl.Fault.InvalidArgument)
   VerifyNotEncryptedDisks(vm1)

   # CryptoSpecEncrypt with no encryption IO filter.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultEmptyPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.badPolicy")
   VerifyNotEncryptedDisks(vm1)

   # CryptoSpecEncrypt with no encryption IO filter, scrubbed.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config, scrub=True,
                        policy=DefaultEmptyPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.badPolicy")
   VerifyNotEncryptedDisks(vm1)

   # Successfully add not encrypted disk.
   configSpec = Vim.Vm.ConfigSpec()
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config)
   vm.Reconfigure(vm1, configSpec)
   VerifyNotEncryptedDisks(vm1)

   # CryptoSpecEncrypt with no encryption IO filter.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultEmptyPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.badPolicy")
   VerifyNotEncryptedDisks(vm1)

   # CryptoSpecNoOp with encryption IO filter.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   cryptoSpec = CreateCryptoSpecNoOp()
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vmodl.fault.NotSupported,
                   msgid="msg.disk.policyChangeFailure")
   VerifyNotEncryptedDisks(vm1)

   # No CryptoSpec with encryption IO filter.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy())
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vmodl.fault.NotSupported,
                   msgid="msg.disk.policyChangeFailure")
   VerifyNotEncryptedDisks(vm1)

   # Successfully encrypt.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # CryptoSpecDeepRecrypt with no encryption IO filter.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   cryptoSpec = CreateCryptoSpecRecrypt(keyId, providerId)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultEmptyPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.badPolicy")
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # CryptoSpecShallowRecrypt with encryption IO filter is allowed.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   cryptoSpec = CreateCryptoSpecRekey(keyId, providerId)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # CryptoSpecDecrypt with encryption IO filter.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   cryptoSpec = CreateCryptoSpecDecrypt()
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.badPolicy")
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # CryptoSpecDecrypt with no policy specified.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   cryptoSpec = CreateCryptoSpecDecrypt()
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.badPolicy")
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # Delete the added disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   vm.Reconfigure(vm1, configSpec)

   DecryptVM(vm1)

def TestInvalidSpec(si, vm1, keyId, providerId):
   """Verify errors when an invalid spec is provided.
   """
   # Confirm that the an attempt to decrypt,recrypt or rekey an
   # unencrypted VM fails.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecRekey(keyId, providerId)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidVmConfig,
                   msgid="msg.hostd.configSpec.enc.notEncrypted")

   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecRecrypt(keyId, providerId)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidVmConfig,
                   msgid="msg.hostd.configSpec.enc.notEncrypted")

   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecDecrypt()
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidVmConfig,
                   msgid="msg.hostd.configSpec.enc.notEncrypted")

   # Confirm that the VM can be encrypted.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncrypted(vm1.config, keyId, providerId)

   # Encrypting an encrypted VM should fail too.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidVmConfig,
                   msgid="msg.hostd.configSpec.enc.encrypted")

   # We currently only support a single backing in the device spec.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   backingSpec = Vim.Vm.Device.VirtualDeviceSpec.BackingSpec()
   configSpec.deviceChange[0].backing.parent = backingSpec
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec)
   VerifyNotEncryptedDisks(vm1)

   # Encryption only applies to a VirtualDisk device type.
   configSpec = Vim.Vm.ConfigSpec()
   vmconfig.AddFloppy(configSpec, type="image", backingName="foo.txt")
   backingSpec = Vim.Vm.Device.VirtualDeviceSpec.BackingSpec()
   backingSpec.SetCrypto(CreateCryptoSpecEncrypt(keyId, providerId))
   configSpec.deviceChange[0].SetBacking(backingSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.notDisk")
   VerifyNotEncryptedDisks(vm1)

   # Encrypting a new disk requires an 'Encrypt' spec.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecRecrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceOperation)
   VerifyNotEncryptedDisks(vm1)

   # Succesfully add a disk so that we can test invalid ::remove.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # CryptoSpec with remove disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   backingSpec = Vim.Vm.Device.VirtualDeviceSpec.BackingSpec()
   backingSpec.SetCrypto(CreateCryptoSpecDecrypt())
   configSpec.deviceChange[0].SetBacking(backingSpec)
   profile = vmconfig.CreateProfileSpec(DefaultEmptyPolicy())
   configSpec.deviceChange[0].SetProfile(profile)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceOperation)
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # Encrypt an already encrypted disk.
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceOperation,
                   msgid="msg.hostd.deviceSpec.enc.encrypted")
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # Decrypt the disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecDecrypt()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultEmptyPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyNotEncryptedDisks(vm1)

   # Decrypt an already decrypted disk.
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   cryptoSpec = CreateCryptoSpecDecrypt()
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultEmptyPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceOperation,
                   msgid="msg.hostd.deviceSpec.enc.notEncrypted")
   VerifyNotEncryptedDisks(vm1)

   # Shallow recrypt an already decrypted disk.
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   cryptoSpec = CreateCryptoSpecRecrypt(keyId, providerId)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceOperation,
                   msgid="msg.hostd.deviceSpec.enc.notEncrypted")
   VerifyNotEncryptedDisks(vm1)

   # Deep recrypt an already decrypted disk.
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   cryptoSpec = CreateCryptoSpecRecrypt(keyId, providerId)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceOperation,
                   msgid="msg.hostd.deviceSpec.enc.notEncrypted")
   VerifyNotEncryptedDisks(vm1)

   # Delete the added disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   vm.Reconfigure(vm1, configSpec)

   # Decrypt the VM to leave it in the initial configuration.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecDecrypt()
   vm.Reconfigure(vm1, configSpec)
   VerifyNotEncrypted(vm1.config)

def TestInvalidState(si, vm1, keyId, providerId):
   """Verify VM state during encryption operations.

   Most encryption operation can only be performed while the VM is
   powered off today. Rekey is the exception.
   """
   # The VM cannot be encrypted while powered on.
   vm.PowerOn(vm1)
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidPowerState)
   VerifyNotEncrypted(vm1.config)
   vm.PowerOff(vm1)

   # Encrypt the VM for the remaining tests.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncrypted(vm1.config, keyId, providerId)

   # Decrypt and Recrypt are also not allowed while powered on.
   vm.PowerOn(vm1)
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecRecrypt(keyId, providerId)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidPowerState)
   VerifyEncrypted(vm1.config, keyId, providerId)
   configSpec.crypto = CreateCryptoSpecDecrypt()
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidPowerState)
   VerifyEncrypted(vm1.config, keyId, providerId)
   vm.PowerOff(vm1)

   # Decrypt the VM to leave it in the initial configuration.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecDecrypt()
   vm.Reconfigure(vm1, configSpec)
   VerifyNotEncrypted(vm1.config)

def TestScrubbedDisk(si, vm1, keyId, providerId):
   """Verify that a scrubbed disk may be added to the VM.

   Adding a scrubbed disk takes a completely different path in host
   when compared to a non-scrubbed disk. Verify that path.
   """
   encryptSpec = CreateCryptoSpecEncrypt(keyId, providerId)

   # Encrypt the virtual machine.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = encryptSpec
   vm.Reconfigure(vm1, configSpec)
   VerifyEncrypted(vm1.config, keyId, providerId)

   # Add a 'scrubbed' disk to the virtual machine.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config, scrub=True,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedDisks(vm1, keyId, providerId)

   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   if not disk.backing.eagerlyScrub:
      raise Exception("Failed to scrub disk.")

   # Delete the disk. We can't decrypt it yet. (Always added at end?)
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   vm.Reconfigure(vm1, configSpec)

   # Decrypt the VM to leave it in the initial configuration.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecDecrypt()
   vm.Reconfigure(vm1, configSpec)
   VerifyNotEncrypted(vm1.config)

def TestReconfigure(si, vm1, keyId, providerId):
   """Test reconfiguring an existing VM for encryption.
   """
   # Add a disk and power-cycle to make snapshots more interesting.
   configSpec = Vim.Vm.ConfigSpec()
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config)
   vm.Reconfigure(vm1, configSpec)
   PowerCycle(vm1)

   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   oldDiskPath = disk.backing.fileName

   # Encrypt the entire VM.
   EncryptVM(vm1, keyId, providerId)
   PowerCycle(vm1)

   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   newDiskPath = disk.backing.fileName
   if newDiskPath == oldDiskPath:
      raise Exception("Unexpected disk path")
   oldDiskPath = newDiskPath

   # Decrypt the entire VM.
   DecryptVM(vm1)
   PowerCycle(vm1)

   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   newDiskPath = disk.backing.fileName
   if newDiskPath == oldDiskPath:
      raise Exception("Unexpected disk path")

   # Delete the added disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   vm.Reconfigure(vm1, configSpec)

def TestCancelable(si, vm1, keyId, providerId):
   """Verify that encryption operations are cancelable.
   """
   # Add a 4GB thick disk so that encryption operations take some time.
   configSpec = Vim.Vm.ConfigSpec()
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config, thin=False,
                        capacity=(4 * 1024 * 1024))
   vm.Reconfigure(vm1, configSpec)

   # Encrypt the VM and the disk. This would take a while if not for cancel.
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = cryptoSpec
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   task = vm1.Reconfigure(configSpec)

   # Setup property collector in order to track the task cancel state.
   pc = si.content.propertyCollector
   objspec = Vmodl.Query.PropertyCollector.ObjectSpec(obj=task)
   propspec = Vmodl.Query.PropertyCollector.PropertySpec(
      type=Vim.Task, pathSet=[], all=True)
   filterspec = Vmodl.Query.PropertyCollector.FilterSpec()
   filterspec.objectSet = [objspec]
   filterspec.propSet = [propspec]

   # Wait for the task to become cancelable, and issue the cancel.
   filter = pc.CreateFilter(filterspec, True)
   version, state = None, None
   while state not in (Vim.TaskInfo.State.success, Vim.TaskInfo.State.error):
      try:
         if task.info.cancelable:
            # A race may result in an InvalidState or NotSupported.
            try:
               task.Cancel()
            except (Vim.Fault.InvalidState, Vmodl.Fault.NotSupported):
               pass
         update = pc.WaitForUpdates(version)
         state = task.info.state
         version = update.version
      except Vmodl.Fault.ManagedObjectNotFound:
         break
   filter.Destroy()

   # Expect the task to fail with a cancel fault.
   if state != "error":
      raise Exception("Expected encryption operation to fail.")
   if not isinstance(task.info.error, Vmodl.Fault.RequestCanceled):
      raise task.info.error

   # Delete the added disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   vm.Reconfigure(vm1, configSpec)

def TestExtraConfig(si, vm1, keyId, providerId):
   """Verify the extraConfig encryption.bundle and dataFileKey entries.
   """
   # Power-cycle so that we have data files to encrypt (e.g. nvram).
   PowerCycle(vm1)

   assert not InExtraConfig(vm1.config.extraConfig, "encryption.bundle")
   assert not InExtraConfig(vm1.config.extraConfig, "dataFileKey")

   EncryptVM(vm1, keyId, providerId)

   assert     InExtraConfig(vm1.config.extraConfig, "encryption.bundle")
   assert not InExtraConfig(vm1.config.extraConfig, "dataFileKey")

   bundle = GetExtraConfig(vm1.config.extraConfig, "encryption.bundle")
   assert "vmware:key/list/(pair/(fqid/<VMWARE-NULL>/Test" in bundle

   # Setting the extraConfig back will exercise unpacking the
   # encryption.bundle entry.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.extraConfig = vm1.config.extraConfig
   vm.Reconfigure(vm1, configSpec)
   VerifyEncrypted(vm1.config, keyId, providerId)

   assert     InExtraConfig(vm1.config.extraConfig, "encryption.bundle")
   assert not InExtraConfig(vm1.config.extraConfig, "dataFileKey")

   # Power cycle to make sure we haven't corrupted the dataFileKey.
   PowerCycle(vm1)

   # It's not legal to set a 'secret' key explicitly while encrypted.
   dataFileKey = ("type=key:cipher=XTS-AES-256:key=BGm1PkeipPRcUDbSH/"
                  "b6Q++PsQtRVMTX9a+VoIs1iw/22zsZg0paAsgmmeYX1BSJGGOq8"
                  "RaV68gbBuBG79G9/Q%3d%3d")
   extraConfig = vm1.config.extraConfig
   AddExtraConfig(extraConfig, "dataFileKey", dataFileKey)
   configSpec.extraConfig = extraConfig
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vmodl.Fault.InvalidArgument,
                   msg="config.extraConfig[\"dataFileKey\"]")
   VerifyEncrypted(vm1.config, keyId, providerId)

   assert     InExtraConfig(vm1.config.extraConfig, "encryption.bundle")
   assert not InExtraConfig(vm1.config.extraConfig, "dataFileKey")

   # Power cycle to make sure we haven't corrupted the dataFileKey.
   PowerCycle(vm1)

   DecryptVM(vm1)

   assert not InExtraConfig(vm1.config.extraConfig, "encryption.bundle")
   assert not InExtraConfig(vm1.config.extraConfig, "dataFileKey")

   # The encryption.bundle cannot be set when a VM is not encrypted.
   extraConfig = vm1.config.extraConfig
   AddExtraConfig(extraConfig, "encryption.bundle", bundle)
   configSpec.extraConfig = extraConfig
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vmodl.Fault.SystemError,
                   msg="Key required for encryption.bundle.")
   VerifyNotEncrypted(vm1.config)

   assert not InExtraConfig(vm1.config.extraConfig, "encryption.bundle")
   assert not InExtraConfig(vm1.config.extraConfig, "dataFileKey")

   # Power cycle to make sure we haven't corrupted the dataFileKey.
   PowerCycle(vm1)

def TestExtractNvram(si, vm1, keyId, providerId):
   """Verify nvram file extraction requires the encryption.bundle.
   """
   hostSystem = host.GetHostSystem(si)
   llpm = hostSystem.RetrieveInternalConfigManager().llProvisioningManager

   # Encrypt the virtual machine.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncrypted(vm1.config, keyId, providerId)

   # Power-cycle so that we know that we should have an nvram file.
   PowerCycle(vm1)

   # Create a snapshot. We'll be extracting the nvram from here.
   vm.CreateSnapshot(vm1, "Snap1", None)
   snap = vm1.snapshot.currentSnapshot
   fileIdx = vm1.layoutEx.snapshot[0].dataKey
   vmsnPath = vm1.layoutEx.file[fileIdx].name

   # A file name for the extracted nvram. Delete this file on success!
   nvramPath = os.path.splitext(vmsnPath)[0] + ".nvram"

   def ExtractNvramContent(vmsnPath, nvramPath, bundle=None):
      task = llpm.ExtractNvramContent(vmsnPath, nvramPath, bundle)
      WaitForTask(task)

   # Use llpm without the bundle; expect failure.
   VerifyException(lambda: ExtractNvramContent(vmsnPath, nvramPath),
                   Vim.Fault.CannotAccessFile,
                   msg="Unable to access file snapshot")

   # The key to unlock the vmsn is in the encryption.bundle.
   bundle = GetExtraConfig(vm1.config.extraConfig, "encryption.bundle")

   # Use llpm with the bundle; the nvram file will be created.
   ExtractNvramContent(vmsnPath, nvramPath, bundle)

   # Cleanup our extracted file and decrypt the VM.
   hostSystem.datastoreBrowser.DeleteFile(nvramPath)
   vm.RemoveAllSnapshots(vm1)
   DecryptVM(vm1)

def TestSnapshots(si, vm1, keyId, providerId):
   """Verify basic snapshot operation.
   """
   def _verifyErrorEncSnapshots(operation):
      VerifyException(operation, Vim.Fault.InvalidVmConfig,
                      msgid="msg.hostd.configSpec.enc.snapshots")

   def _verifyErrorDiskChain(operation):
      VerifyException(operation, Vim.Fault.InvalidDeviceOperation,
                      msgid="msg.hostd.deviceSpec.enc.diskChain")

   # Add a disk and power-cycle to make snapshots more interesting.
   configSpec = Vim.Vm.ConfigSpec()
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config)
   vm.Reconfigure(vm1, configSpec)
   PowerCycle(vm1)

   # We expect encryption to fail if snapshots are present.
   vm.CreateSnapshot(vm1, "Not-encrypted", None)
   VerifyNotEncrypted(vm1.snapshot.currentSnapshot.config)

   _verifyErrorEncSnapshots(lambda: EncryptVM(vm1, keyId, providerId))
   VerifyNotEncrypted(vm1.config)

   # We also disallow snapshots with only disk snapshots present.
   vm.RemoveAllSnapshots(vm1, consolidate=False)

   _verifyErrorDiskChain(lambda: EncryptVM(vm1, keyId, providerId))
   VerifyNotEncrypted(vm1.config)

   # Consolidate will cleanup all snapshots; encryption should succeed.
   vm.ConsolidateDisks(vm1)
   # Verify that snapshot operations work on an encrypted VM.
   EncryptVM(vm1, keyId, providerId)

   vm.CreateSnapshot(vm1, "Encrypted", None)
   VerifyEncrypted(vm1.snapshot.currentSnapshot.config, keyId, providerId)

   _verifyErrorEncSnapshots(lambda: DecryptVM(vm1))

   # We also disallow snapshots with only disk snapshots present.
   vm.RemoveAllSnapshots(vm1, consolidate=False)
   newKeyId, newProviderId, newCryptoKey = CreateCryptoKeyDefault()

   # Verify disk deep rekey is not allowed.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   recryptSpec = CreateCryptoSpecRecrypt(newKeyId, newProviderId)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy(), crypto=recryptSpec)
   _verifyErrorDiskChain(lambda: vm.Reconfigure(vm1, configSpec))

   # Verify disk decrypt is not allowed.
   _verifyErrorDiskChain(lambda: DecryptVM(vm1))

   # Consolidate will cleanup all snapshots; encryption should succeed.
   vm.ConsolidateDisks(vm1)

   vm.CreateSnapshot(vm1, "Encrypted", None)
   VerifyEncrypted(vm1.snapshot.currentSnapshot.config, keyId, providerId)

   vm.RevertToCurrentSnapshot(vm1)
   numDisks = len(vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk))
   VerifyEncryptedDisks(vm1, keyId, providerId, expect=numDisks)
   vm.RemoveAllSnapshots(vm1)

   DecryptVM(vm1)
   PowerCycle(vm1)

   # Delete the added disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   vm.Reconfigure(vm1, configSpec)

def TestSnapshotsLocked(si, vm1, keyId, providerId):
   """Verify basic snapshot operation when keys are missing.
   """
   # Add a disk and power-cycle to make snapshots more interesting.
   configSpec = Vim.Vm.ConfigSpec()
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config)
   vm.Reconfigure(vm1, configSpec)
   PowerCycle(vm1)

   # Verify that snapshot operations fails after removing keys from the host.
   cryptoMgr = si.RetrieveContent().cryptoManager
   newKeyId, newProviderId, newCryptoKey = CreateCryptoKeyDefault()
   newCryptoKeyId  = CreateCryptoKeyId(newKeyId,  newProviderId)
   addKeyResult = cryptoMgr.AddKeys([newCryptoKey])
   assert len(addKeyResult) == 1
   assert addKeyResult[0].success

   EncryptVM(vm1, newKeyId, newProviderId)
   vm.CreateSnapshot(vm1, "Encrypted", None)

   assert vm1.snapshot != None and len(vm1.rootSnapshot) == 1
   VerifyEncrypted(vm1.snapshot.currentSnapshot.config, newKeyId, newProviderId)

   VerifyCryptoState(vm1, "unlocked")
   removeKeysResult = cryptoMgr.RemoveKeys([newCryptoKeyId], True)
   assert len(removeKeysResult) == 1
   assert     removeKeysResult[0].success

   # The keys are removed, but still cached. After snapshot failure
   # hostd will notice that the VM is now locked.
   WithRetry(lambda: VerifyConnectionState(vm1, "connected"))
   VerifyException(lambda: vm.CreateSnapshot(vm1, "Encrypted", None),
                   Vim.Fault.InvalidVmConfig,
                   msgid="msg.snapshot.vigor.take.error")
   WithRetry(lambda: VerifyConnectionState(vm1, "invalid"))
   VerifyCryptoState(vm1, "locked")
   # No snapshots are published when hostd considers a VM locked.
   assert vm1.snapshot == None and len(vm1.rootSnapshot) == 0

   # All snapshot operations will fail until the VM is unlocked.
   VerifyExceptionLocked(lambda: vm.RevertToCurrentSnapshot(vm1),
                         newKeyId, newProviderId)
   VerifyExceptionLocked(lambda: vm.RemoveAllSnapshots(vm1),
                         newKeyId, newProviderId)
   assert vm1.snapshot == None and len(vm1.rootSnapshot) == 0

   # Add back the keys and reload the VM. It's no longer locked.
   addKeyResult = cryptoMgr.AddKeys([newCryptoKey])
   assert len(addKeyResult) == 1
   assert addKeyResult[0].success

   WithRetry(lambda: VerifyConnectionState(vm1, "connected"))
   WithRetry(lambda: VerifyEncrypted(vm1.snapshot.currentSnapshot.config,
                                     newKeyId, newProviderId))
   # Hostd may be reloading the VM in the background...
   WithRetry(lambda: vm.CreateSnapshot(vm1, "Encrypted", None))
   VerifyCryptoState(vm1, "unlocked")
   vm.RevertToCurrentSnapshot(vm1)
   vm.RemoveAllSnapshots(vm1)

   # Delete the added disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   vm.Reconfigure(vm1, configSpec)

   DecryptVM(vm1)

def TestVmxSandbox(si, vmname, dsName, keep, keyId, providerId):
   """Verify that the VMX sandbox works with the VMcrypt IO filter.

   This test code is largely lifted from vmxSandboxTests.py. It depends
   on setting special config options that are picked up by the VMX.
   """
   # This test depend on some devel-only config options.
   if not _runObjTests:
      return

   def _runTest(vm1, powerOn):
      vmxPath = vm1.GetSummary().GetConfig().GetVmPathName()

      # Add some test config options that will cause the running VMX to
      # add a floppy disk with an illegal path. This will break the VMX
      # sandbox and cause the VMX to power-off soon after power-on.
      configSpec = Vim.Vm.ConfigSpec()
      AddExtraConfig(configSpec.extraConfig,
                     "vmx.test.sandbox.illegalOption", "1")
      AddExtraConfig(configSpec.extraConfig, "vmx.test.sandbox.nthWrite", "4")
      vm.Reconfigure(vm1, configSpec)

      if powerOn:
         vm.PowerOn(vm1)

      success = False
      for i in range(300):
         if vm1.runtime.powerState == Vim.VirtualMachine.PowerState.poweredOff:
            success = True
            break
         # Write to the config file to help induce nthWrite.
         configSpec = Vim.Vm.ConfigSpec()
         AddExtraConfig(configSpec.extraConfig, "foo", "bar-%d" % i)
         try:
            vm.Reconfigure(vm1, configSpec)
         except (Vim.Fault.InvalidState, Vim.Fault.GenericVmConfigFault):
            # Reconfigure may fail while racing with the power-off.
            pass
         time.sleep(1)
      if not success:
         raise Exception("VM unexpectedly still powered on.")

      if not keep:
         vm.Destroy(vm1)

   # Test 1: Create a simple encrypted VM, with one encrypted disk.
   configSpec = vmconfig.CreateDefaultSpec(name=vmname,
                                           datastoreName=dsName)
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   configSpec.crypto = cryptoSpec
   vmconfig.AddScsiCtlr(configSpec)
   vmconfig.AddScsiDisk(configSpec, datastorename=dsName,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm1 = vm.CreateFromSpec(configSpec)

   # Power-cycle because the first power-on will do a lot of config
   # file writes, and we want our test to fail after power-on.
   PowerCycle(vm1)

   _runTest(vm1, True)

   # Test 2: Create an encrypted VM, with no disk. Create an encrypted
   # disk separately and add it to a powered on VM.
   configSpec = vmconfig.CreateDefaultSpec(name=vmname,
                                           datastoreName=dsName)
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   configSpec.crypto = cryptoSpec
   vm1 = vm.CreateFromSpec(configSpec)
   vm.PowerOn(vm1)

   vdiskMgr = si.RetrieveContent().GetVirtualDiskManager()

   try:
      deletePath = None

      diskSpec = CreateVirtualDiskSpec(DefaultCryptoPolicy(), cryptoSpec)
      datastore = vm1.config.datastoreUrl[0].name
      diskName = vm1.name + "/disk.vmdk"
      diskPath = "[" + datastore + "] " + diskName
      deletePath = CreateVirtualDisk(vdiskMgr, diskPath, diskSpec)

      configSpec = Vim.Vm.ConfigSpec()
      vmconfig.AddScsiCtlr(configSpec)
      vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config, fileName=diskName,
                           policy=DefaultCryptoPolicy())
      vm.Reconfigure(vm1, configSpec)
   except Exception as e:
      # When no exception, the disk is deleted with the VM.
      if deletePath:
         task = vdiskMgr.DeleteVirtualDisk(deletePath, None)
         WaitForTask(task)
      raise

   _runTest(vm1, False)

def TestVdiskMgr(si, vm1, keyId, providerId):
   """Verify VirtualDiskManager encryption operations.
   """
   encryptSpec = CreateCryptoSpecEncrypt(keyId, providerId)

   # Encrypt the virtual machine.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = encryptSpec
   vm.Reconfigure(vm1, configSpec)
   VerifyEncrypted(vm1.config, keyId, providerId)

   vdiskMgr = si.RetrieveContent().GetVirtualDiskManager()

   datastore = vm1.config.datastoreUrl[0].name
   diskSpec = Vim.VirtualDiskManager.FileBackedVirtualDiskSpec()
   diskSpec.SetDiskType("thin")
   diskSpec.SetAdapterType("lsiLogic")
   diskSpec.SetCapacityKb(4 * 1024)

   # Always try to cleanup diskPath so that it's not leaked on failure.
   deletePath = None

   try:
      # First try to create a disk with an invalid spec.
      diskName = vm1.name + "/disk.vmdk"
      diskPath = "[" + datastore + "] " + diskName
      diskSpec.SetCrypto(CreateCryptoSpecDecrypt())
      VerifyException(lambda: CreateVirtualDisk(vdiskMgr, diskPath, diskSpec),
                      Vmodl.Fault.InvalidArgument)

      # Second test with a NoOp spec. The disk will not be encrypted.
      diskName = vm1.name + "/disk.vmdk"
      diskPath = "[" + datastore + "] " + diskName
      diskSpec.SetCrypto(CreateCryptoSpecNoOp());
      deletePath = CreateVirtualDisk(vdiskMgr, diskPath, diskSpec)

      # Verify that the disk can be added, and that it's not encrypted.
      configSpec = Vim.Vm.ConfigSpec()
      vmconfig.AddScsiDisk(configSpec, datastorename=datastore,
                           cfgInfo=vm1.config, fileName=diskName)
      vm.Reconfigure(vm1, configSpec)
      VerifyNotEncryptedDisks(vm1)

      # Try to clone the disk to make it encrypted. The operation should
      # fail due to an invalid spec.
      diskName = vm1.name + "/copy.vmdk"
      copyPath = "[" + datastore + "] " + diskName
      diskSpec.SetCrypto(encryptSpec)
      diskSpec.SetProfile(vmconfig.CreateProfileSpec(DefaultCryptoPolicy()))
      deletePath = copyPath
      VerifyException(lambda: CopyVirtualDisk(vdiskMgr, diskPath,
                                              copyPath, diskSpec),
                      Vmodl.Fault.InvalidArgument)

      # Delete the disk.
      disks = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)
      configSpec = Vim.Vm.ConfigSpec()
      fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
      vmconfig.RemoveDeviceFromSpec(configSpec, disks[-1], fileOp)
      vm.Reconfigure(vm1, configSpec)

      # Create a new disk with a proper spec. The disk will be encrypted.
      diskName = vm1.name + "/disk.vmdk"
      diskPath = "[" + datastore + "] " + diskName
      diskSpec.SetCrypto(encryptSpec)
      diskSpec.SetProfile(vmconfig.CreateProfileSpec(DefaultCryptoPolicy()))
      deletePath = CreateVirtualDisk(vdiskMgr, diskPath, diskSpec)

      configSpec = Vim.Vm.ConfigSpec()
      vmconfig.AddScsiDisk(configSpec, datastorename=datastore,
                           cfgInfo=vm1.config, fileName=diskName,
                           policy=DefaultCryptoPolicy())
      vm.Reconfigure(vm1, configSpec)

      # Try to clone the disk to make it decrypted. Disk should remain
      # encrypted. Disks can only encrypted or decrypted using reconfigure.
      diskName = vm1.name + "/copy.vmdk"
      copyPath = "[" + datastore + "] " + diskName
      diskSpec.SetCrypto(None)
      diskSpec.SetProfile(None)
      CopyVirtualDisk(vdiskMgr, diskPath, copyPath, diskSpec)

      configSpec = Vim.Vm.ConfigSpec()
      vmconfig.AddScsiDisk(configSpec, datastorename=datastore,
                           cfgInfo=vm1.config, fileName=diskName,
                           policy=DefaultCryptoPolicy())
      vm.Reconfigure(vm1, configSpec)
      VerifyEncryptedDisks(vm1, keyId, providerId, 2)

      # Delete the disk.
      disks = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)
      configSpec = Vim.Vm.ConfigSpec()
      fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
      vmconfig.RemoveDeviceFromSpec(configSpec, disks[-1], fileOp)
      vmconfig.RemoveDeviceFromSpec(configSpec, disks[-2], fileOp)
      vm.Reconfigure(vm1, configSpec)

      # Decrypt the VM to leave it in the initial configuration.
      configSpec = Vim.Vm.ConfigSpec()
      configSpec.crypto = CreateCryptoSpecDecrypt()
      vm.Reconfigure(vm1, configSpec)
      VerifyNotEncrypted(vm1.config)
   except Exception as e:
      if deletePath:
         try:
            task = vdiskMgr.DeleteVirtualDisk(deletePath, None)
            WaitForTask(task)
         except Vim.Fault.FileNotFound:
            pass
      raise

def TestCryptoManager(si, vm1, keyId, providerId):
   """Verify Crypto Manager Add/Find/Remove operations
   """
   def HasKey(keysList, searchKey):
      for keyResult in keysList:
         if keyResult.keyId == searchKey.keyId and \
            keyResult.providerId.id == searchKey.providerId.id :
               return True;
      return False;

   cryptoMgr = si.RetrieveContent().cryptoManager

   # create a couple of keys
   newKeyId, newProviderId, newCryptoKey = CreateCryptoKeyDefault()
   newKeyId2, newProviderId2, newCryptoKey2 = CreateCryptoKeyDefault()

   newCryptoKeyId  = CreateCryptoKeyId(newKeyId,  newProviderId)
   newCryptoKeyId2 = CreateCryptoKeyId(newKeyId2, newProviderId2)
   newCryptoKeyId3 = CreateCryptoKeyId(newKeyId2, newProviderId)
   newCryptoKeyId4 = CreateCryptoKeyId(newKeyId,  newProviderId2)

   listKeysBefore = cryptoMgr.ListKeys()
   assert not HasKey(listKeysBefore, newCryptoKeyId)

   # Neg.1: try and fail deleting the keys
   allKeys = [newCryptoKeyId, newCryptoKeyId2, newCryptoKeyId3, newCryptoKeyId4]
   removeKeysResult = cryptoMgr.RemoveKeys(allKeys, False)
   assert len(removeKeysResult) == 4
   for removeKeyResult in removeKeysResult:
      assert not removeKeyResult.success
      assert removeKeyResult.reason == 'key.keyId'

   # Pos.1
   addKeyResult = cryptoMgr.AddKeys([newCryptoKey])
   assert len(addKeyResult) == 1
   assert addKeyResult[0].success
   assert addKeyResult[0].keyId.keyId == newKeyId
   assert addKeyResult[0].keyId.providerId.id == newProviderId

   # Pos.2
   listKeysAfterResult = cryptoMgr.ListKeys()
   assert     HasKey(listKeysAfterResult, newCryptoKeyId)
   assert not HasKey(listKeysAfterResult, newCryptoKeyId2)
   assert not HasKey(listKeysAfterResult, newCryptoKeyId3)

   # Neg.2a: try and fail adding again the key
   VerifyException(lambda: cryptoMgr.AddKey(newCryptoKey),
                   Vim.Fault.AlreadyExists)

   # Neg.2b: try and fail adding again the key
   addKeyResult = cryptoMgr.AddKeys([newCryptoKey])
   assert not addKeyResult[0].success
   assert "AlreadyExists" in addKeyResult[0].reason

   listKeysAfterResult = cryptoMgr.ListKeys()
   assert     HasKey(listKeysAfterResult, newCryptoKeyId)
   assert not HasKey(listKeysAfterResult, newCryptoKeyId2)
   assert not HasKey(listKeysAfterResult, newCryptoKeyId3)

   # Pos.3: Remove the key
   removeKeysResult = cryptoMgr.RemoveKeys(
      [newCryptoKeyId, newCryptoKeyId2, newCryptoKeyId3, newCryptoKeyId4],
      False)
   assert len(removeKeysResult) == 4
   assert     removeKeysResult[0].success
   assert not removeKeysResult[1].success
   assert not removeKeysResult[2].success
   assert not removeKeysResult[3].success

   # Neg.3: try and fail deleting the key again
   VerifyException(lambda: cryptoMgr.RemoveKey(newCryptoKeyId, False),
                   Vmodl.Fault.InvalidArgument)

   # Pos.4
   listKeysAfter = cryptoMgr.ListKeys()
   assert not HasKey(listKeysAfter, newCryptoKeyId)
   assert not HasKey(listKeysAfter, newCryptoKeyId2)
   assert not HasKey(listKeysAfter, newCryptoKeyId3)
   assert not HasKey(listKeysAfter, newCryptoKeyId4)

def TestCapabilities(si, vm1, keyId, providerId):
   """Verify that the ESX host reports expected capabilities.
   """
   hs = host.GetHostSystem(si)
   assert not hs.capability.encryptionChangeOnAddRemoveSupported
   if featureStateOf.VMcrypt_OnlineVMEncryption:
      assert hs.capability.encryptionHotOperationSupported
   else:
      assert not hs.capability.encryptionHotOperationSupported
   assert not hs.capability.encryptionWithSnapshotsSupported
   assert not hs.capability.encryptionFaultToleranceSupported
   assert hs.capability.encryptionMemorySaveSupported
   assert not hs.capability.encryptionRDMSupported
   assert not hs.capability.encryptionVFlashSupported
   assert not hs.capability.encryptionCBRCSupported
   assert hs.capability.encryptionHBRSupported

def TestDSBrowser(si, vmname, dsName, keep, keyId, providerId):
   """Verify that the DatastoreBrowser returns encryption information.

   The DatastoreBrowser can be used to search for encrypted VMs and
   disks and also optionally returns the encrypted state of .vmx and
   .vmdk files.
   """
   def CreateVmDiskSearchSpec(diskFilter=None, diskDetails=None):
      query = Vim.Host.DatastoreBrowser.VmDiskQuery()
      if not diskDetails:
         diskDetails = Vim.Host.DatastoreBrowser.VmDiskQuery.Details()
         diskDetails.SetEncryption(True)
      query.SetDetails(diskDetails)
      query.SetFilter(diskFilter)

      fileDetails = Vim.Host.DatastoreBrowser.FileInfo.Details()
      fileDetails.SetFileType(True)

      searchSpec = Vim.Host.DatastoreBrowser.SearchSpec()
      searchSpec.SetQuery([query])
      searchSpec.SetDetails(fileDetails)
      searchSpec.SetMatchPattern(["*.vmdk"]) # For performance?

      return searchSpec

   def CreateVmConfigSearchSpec(vmFilter=None, vmDetails=None):
      query = Vim.Host.DatastoreBrowser.VmConfigQuery()
      if not vmDetails:
         vmDetails = Vim.Host.DatastoreBrowser.VmConfigQuery.Details()
         vmDetails.SetEncryption(True)
      query.SetDetails(vmDetails)
      query.SetFilter(vmFilter)

      fileDetails = Vim.Host.DatastoreBrowser.FileInfo.Details()
      fileDetails.SetFileType(True)

      searchSpec = Vim.Host.DatastoreBrowser.SearchSpec()
      searchSpec.SetQuery([query])
      searchSpec.SetDetails(fileDetails)
      searchSpec.SetMatchPattern(["*.vmx"]) # For performance?

      return searchSpec

   def SearchVM(vm1, searchSpec):
      # Searching an entire datastore is insanely inefficient. A search
      # of all vmdk files took 1 hour on my machine (I have a lot of
      # disks). Always limit tests to searching one folder.
      datastoreBrowser = host.GetHostSystem(si).datastoreBrowser
      task = datastoreBrowser.Search(vm1.config.files.logDirectory, searchSpec)
      WaitForTask(task)
      return task.info.result

   def VerifySearchResults(searchResults, files, expected,
                           keyId=None, providerId=None):
      for item in files:
         found = None
         for result in searchResults.file:
            if result.path == item:
               found = result
               break

         if found and found.encryption:
            if keyId:
               VerifyEncrypted(found.encryption, keyId, providerId)
            else:
               VerifyNotEncrypted(found.encryption)
         else:
            assert not keyId and not providerId

         if expected and not found:
            raise Exception("Failed to file.")
         if found and not expected:
            raise Exception("Found unexpected file.")

   def RunTest(vm1, vmxEncrypted, vmxPlain, vmdkEncrypted, vmdkPlain):
      # Search for any VM. Results include all VMs above.
      searchSpec = CreateVmConfigSearchSpec()
      searchResults = SearchVM(vm1, searchSpec)
      VerifySearchResults(searchResults, vmxEncrypted, True, keyId, providerId)
      VerifySearchResults(searchResults, vmxPlain, True)

      # Search for encrypted VMs. Results include only vmxEncrypted.
      vmFilter = Vim.Host.DatastoreBrowser.VmConfigQuery.Filter()
      vmFilter.SetEncrypted(True)
      searchSpec = CreateVmConfigSearchSpec(vmFilter)
      searchResults = SearchVM(vm1, searchSpec)
      VerifySearchResults(searchResults, vmxEncrypted, True, keyId, providerId)
      VerifySearchResults(searchResults, vmxPlain, False)

      # Search for plaintext VMs. Results include only vmxPlain.
      vmFilter = Vim.Host.DatastoreBrowser.VmConfigQuery.Filter()
      vmFilter.SetEncrypted(False)
      searchSpec = CreateVmConfigSearchSpec(vmFilter)
      searchResults = SearchVM(vm1, searchSpec)
      VerifySearchResults(searchResults, vmxEncrypted, False)
      VerifySearchResults(searchResults, vmxPlain, True)

      # Search for any disks. Results include all disks above.
      searchSpec = CreateVmDiskSearchSpec()
      searchResults = SearchVM(vm1, searchSpec)
      VerifySearchResults(searchResults, vmdkEncrypted, True, keyId, providerId)
      VerifySearchResults(searchResults, vmdkPlain, True)

      # Search for encrypted disks. Results include only vmdkEncrypted.
      diskFilter = Vim.Host.DatastoreBrowser.VmDiskQuery.Filter()
      diskFilter.SetEncrypted(True)
      searchSpec = CreateVmDiskSearchSpec(diskFilter)
      searchResults = SearchVM(vm1, searchSpec)
      VerifySearchResults(searchResults, vmdkEncrypted, True, keyId, providerId)
      VerifySearchResults(searchResults, vmdkPlain, False)

      # Search for plaintext disks. Results include only vmdkPlain.
      diskFilter = Vim.Host.DatastoreBrowser.VmDiskQuery.Filter()
      diskFilter.SetEncrypted(False)
      searchSpec = CreateVmDiskSearchSpec(diskFilter)
      searchResults = SearchVM(vm1, searchSpec)
      VerifySearchResults(searchResults, vmdkEncrypted, False)
      VerifySearchResults(searchResults, vmdkPlain, True)

   # Create a VM that is not encrypted. We will search for this VM.
   vmxEncrypted = []
   vmxPlain = []
   vmdkEncrypted = []
   vmdkPlain = []

   configSpec = vmconfig.CreateDefaultSpec(name=vmname,
                                           datastoreName=dsName)
   vmconfig.AddScsiCtlr(configSpec)
   vmconfig.AddScsiDisk(configSpec, datastorename=dsName)
   vm1 = vm.CreateFromSpec(configSpec)

   vmxPlain.append(os.path.basename(vm1.config.files.vmPathName))
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   vmdkPlain.append(os.path.basename(disk.backing.fileName))

   RunTest(vm1, vmxEncrypted, vmxPlain, vmdkEncrypted, vmdkPlain)

   # Create an encrypted VM; one encrypted disk and one not encrypted
   # disk. We will search for this VM and its disks.
   vmxEncrypted = []
   vmxPlain = []
   vmdkEncrypted = []
   vmdkPlain = []

   configSpec = vmconfig.CreateDefaultSpec(name=vmname,
                                           datastoreName=dsName)
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   configSpec.crypto = cryptoSpec
   vmconfig.AddScsiCtlr(configSpec)
   vmconfig.AddScsiDisk(configSpec, datastorename=dsName)
   vmconfig.AddScsiDisk(configSpec, datastorename=dsName,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm2 = vm.CreateFromSpec(configSpec)

   vmxEncrypted.append(os.path.basename(vm2.config.files.vmPathName))
   disk = vmconfig.CheckDevice(vm2.config, Vim.Vm.Device.VirtualDisk)[0]
   vmdkPlain.append(os.path.basename(disk.backing.fileName))
   disk = vmconfig.CheckDevice(vm2.config, Vim.Vm.Device.VirtualDisk)[1]
   vmdkEncrypted.append(os.path.basename(disk.backing.fileName))

   RunTest(vm2, vmxEncrypted, vmxPlain, vmdkEncrypted, vmdkPlain)

   if not keep:
      vm.Destroy(vm1)
      vm.Destroy(vm2)

def TestDownloadVMXConfig(si, vm1, keyId, providerId):
   """Verify that the DownloadVMXConfig API does not leak secrets.
   """
   # Encrypt the VM so that we have secret .vmx config options.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedVM(vm1, vm1.config, keyId, providerId)

   internalContent = si.RetrieveInternalContent()
   ovhdService = internalContent.GetOverheadService()
   vmxConfig = ovhdService.DownloadVMXConfig(vm1).decode("utf-8")

   for line in vmxConfig.splitlines():
      if ("dataFileKey".lower() in line.lower() and not
          "censored".lower() in line.lower()):
         raise Exception("Found dataFileKey leak: %s" % line)

   # Decrypt the VM to put it back in the original state.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecDecrypt()
   vm.Reconfigure(vm1, configSpec)
   VerifyNotEncryptedVM(vm1, vm1.config)

def TestInitialOverhead(si, vm1, keyId, providerId):
   """Verify that the memory overhead is correct for an encrypted VM.
   """
   numVcpus = 2
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   configSpec.numCPUs = numVcpus
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedVM(vm1, vm1.config, keyId, providerId)
   memReservationEnc = vm1.config.initialOverhead.initialMemoryReservation
   swapReservationEnc = vm1.config.initialOverhead.initialSwapReservation

   # Decrypt the VM to put it back in the original state.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecDecrypt()
   vm.Reconfigure(vm1, configSpec)
   VerifyNotEncryptedVM(vm1, vm1.config)

   memReservation = vm1.config.initialOverhead.initialMemoryReservation
   swapReservation = vm1.config.initialOverhead.initialSwapReservation

   memOvhd = memReservationEnc - memReservation
   swapOvhd = swapReservationEnc - swapReservation

   # We use 4 SG arrays each having 256 page size elements for async writes and
   # numVcpus pages are used for sync writes.
   expectedMemOvhd = (4 * 256 + numVcpus) * 4 * 1024

   if expectedMemOvhd != memOvhd or swapOvhd != 0:
      raise Exception("Unexpected Memory or swap overhead, "
                      "memory overhead(expected: %d, actual: %d), "
                      "swap overhead(expected: %d, actual: %d)."
                      % (expectedMemOvhd, memOvhd, 0, swapOvhd))

def TestShareEncryptedDisk(si, vmname, dsName, keep, keyId, providerId):
   """Verify that the encrypted disks cannot be shared
   """
   # Create a simple encrypted VM, with one encrypted disk.
   configSpec = vmconfig.CreateDefaultSpec(name=vmname,
                                           datastoreName=dsName)
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   configSpec.crypto = cryptoSpec
   vmconfig.AddScsiCtlr(configSpec)
   vmconfig.AddScsiDisk(configSpec, datastorename=dsName, scrub=True,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)

   # Step 1: Try to create an encrypted VM with shared disk/backing

   # Set the disk backing to shared
   configSpec.deviceChange[1].device.backing.sharing = 'sharingMultiWriter'
   VerifyException(lambda: vm.CreateFromSpec(configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.sharedBacking")
   configSpec.deviceChange[1].device.backing.sharing = None

   # Set the disk's controller bus to shared
   configSpec.deviceChange[0].device.sharedBus = 'physicalSharing'
   VerifyException(lambda: vm.CreateFromSpec(configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.sharedBacking")
   configSpec.deviceChange[0].device.sharedBus = 'noSharing'

   # Step 2: Create a VM with encrypted disks and try change the sharing
   vm1 = vm.CreateFromSpec(configSpec)

   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   vmconfig.AddDeviceToSpec(configSpec, disk, operation)
   configSpec.deviceChange[0].device.backing.sharing = 'sharingMultiWriter'

   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.sharedBacking")

   if not keep:
      vm.Destroy(vm1)

def TestEncryptSharedDisk(si, vmname, dsName, keep, keyId, providerId):
   """Verify that the shared disks cannot be encrypted
   """
   # Create a simple VM with shared disk
   configSpec = vmconfig.CreateDefaultSpec(name=vmname,
                                           datastoreName=dsName)
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   configSpec.crypto = cryptoSpec
   # Multi-writer shared disk
   vmconfig.AddScsiCtlr(configSpec)
   vmconfig.AddScsiDisk(configSpec, datastorename=dsName, scrub=True)
   configSpec.deviceChange[1].device.backing.sharing = 'sharingMultiWriter'
   vm1 = vm.CreateFromSpec(configSpec)
   VerifyNotEncryptedDisks(vm1)

   # try to encrypt a shared disk with normal backing, it should fail
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.sharedBacking")
   VerifyNotEncryptedDisks(vm1)

   if not keep:
      vm.Destroy(vm1)

def TestShareEncryptedBacking(si, vmname, dsName, keep, keyId, providerId):
   """ Verify that encrypted disks' backing contoller cannot be shared
   """
   # Create a simple encrypted VM, with no disks.
   configSpec = vmconfig.CreateDefaultSpec(name=vmname,
                                           datastoreName=dsName)
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   configSpec.crypto = cryptoSpec
   vm1 = vm.CreateFromSpec(configSpec)
   VerifyEncryptedVM(vm1, vm1.config, keyId, providerId)

   # Add a shared bus SCSI controller to the VM.
   configSpec = Vim.Vm.ConfigSpec()
   vmconfig.AddScsiCtlr(configSpec)
   configSpec.deviceChange[0].device.sharedBus = 'physicalSharing'
   vm.Reconfigure(vm1, configSpec)

   # Add an encrypted disk to the VM. This will fail.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config, scrub=True,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.sharedBacking")

   if not keep:
      vm.Destroy(vm1)

def TestEncryptSharedBacking(si, vmname, dsName, keep, keyId, providerId):
   """Verify that the disks with shared backings cannot be encrypted
   """
   # Create a simple VM with shared backing
   configSpec = vmconfig.CreateDefaultSpec(name=vmname,
                                           datastoreName=dsName)
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   configSpec.crypto = cryptoSpec
   # disk with shared backing controller
   sharedBus = Vim.Vm.Device.VirtualSCSIController.Sharing.physicalSharing
   vmconfig.AddScsiCtlr(configSpec, sharedBus=sharedBus)
   vmconfig.AddScsiDisk(configSpec, datastorename=dsName)
   vm1 = vm.CreateFromSpec(configSpec)
   VerifyNotEncryptedDisks(vm1)

   # try to encrypt a disk with shared backing, it should fail
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.sharedBacking")
   VerifyNotEncryptedDisks(vm1)

   if not keep:
      vm.Destroy(vm1)

def TestRDM(si, vm1, keyId, providerId):
   """ Verify that RDMs cannot be encrypted.
   """
   # Encrypt the entire VM.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   vm.Reconfigure(vm1, configSpec)

   # Create a configSpec for adding a new encrypted disk.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)

   # Replace the new backing with a bogus RDM.
   rdmBacking = Vim.Vm.Device.VirtualDisk.RawDiskMappingVer1BackingInfo()
   rdmBacking.fileName = "foo.vmdk"
   rdmBacking.deviceName = "/vmfs/devices/disks/naa.foo"
   rdmBacking.compatibilityMode = "virtualMode"
   configSpec.deviceChange[0].device.backing = rdmBacking

   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.deviceSpec.enc.notFile")

   # Restore the VM to the original state
   DecryptVM(vm1)

def TestEncOnlyDisk(si, vm1, keyId, providerId):
   """Verify that encrypting just disk fails.
   """
   # Confirm that the VM is not initially encrypted.
   VerifyNotEncrypted(vm1.config)

   # Add an encrypted disk to the VM.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.configSpec.enc.mismatch")

def TestRemDiskDecVM(si, vm1, keyId, providerId):
   """Test decrypting a VM while removing its encrypted disk.
   """
   # Confirm that the VM is not initially encrypted.
   VerifyNotEncrypted(vm1.config)

   # Confirm that the VM can be encrypted.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedVM(vm1, vm1.config, keyId, providerId)

   # Add an encrypted disk to the VM.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # Decrypting the VM and removing the encrypted disk should succeed.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecDecrypt()
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   vm.Reconfigure(vm1, configSpec)

def TestDecOnlyVM(si, vm1, keyId, providerId):
   """Test decrypting a VM with encrypted disk.
   """
   # Confirm that the VM is not initially encrypted.
   VerifyNotEncrypted(vm1.config)

   # Confirm that the VM can be encrypted.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedVM(vm1, vm1.config, keyId, providerId)

   # Add an encrypted disk to the VM.
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedDisks(vm1, keyId, providerId)

   # Decrypting the VM without decrypting the disk should fail.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecDecrypt()
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidVmConfig,
                   msgid="msg.hostd.configSpec.enc.mismatch")

   # Delete the disk.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
   vm.Reconfigure(vm1, configSpec)

   # Restore the VM to the original state
   DecryptVM(vm1)

def TestExistingDisk(si, vm1, keyId, providerId):
   """Test adding an encrypted disk to an un encrypted VM.
   """
   # Confirm that the VM is not initially encrypted.
   VerifyNotEncrypted(vm1.config)

   deletePath = None

   try:
      # Create and encrypt the disk.
      vdiskMgr = si.RetrieveContent().GetVirtualDiskManager()
      datastore = vm1.config.datastoreUrl[0].name
      diskSpec = Vim.VirtualDiskManager.FileBackedVirtualDiskSpec()
      diskSpec.SetDiskType("thin")
      diskSpec.SetAdapterType("lsiLogic")
      diskSpec.SetCapacityKb(4 * 1024)

      cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
      cryptoSpecRegister = CreateCryptoSpecRegister(keyId, providerId)
      diskName = vm1.name + "/disk.vmdk"
      diskPath = "[" + datastore + "] " + diskName
      diskSpec.SetCrypto(cryptoSpec)
      diskSpec.SetProfile(vmconfig.CreateProfileSpec(DefaultCryptoPolicy()))
      deletePath = CreateVirtualDisk(vdiskMgr, diskPath, diskSpec)

      # Adding encrypted disk to an unencrypted VM should fail.
      configSpec = Vim.Vm.ConfigSpec()
      vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config, fileName=diskName,
                           policy=DefaultCryptoPolicy(),
                           crypto=cryptoSpecRegister)
      VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                      Vim.Fault.InvalidDeviceSpec,
                      msgid="msg.hostd.configSpec.enc.mismatch")

      # Encrypt the VM and try again. Operation succeeds.
      configSpec = Vim.Vm.ConfigSpec()
      configSpec.crypto = cryptoSpec
      vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config, fileName=diskName,
                           policy=DefaultCryptoPolicy(),
                           crypto=cryptoSpecRegister)
      vm.Reconfigure(vm1, configSpec)
      VerifyEncryptedVM(vm1, vm1.config, keyId, providerId)
      VerifyEncryptedDisks(vm1, keyId, providerId)

      # Remove the disk so that we can try again while powered on.
      disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
      configSpec = Vim.Vm.ConfigSpec()
      vmconfig.RemoveDeviceFromSpec(configSpec, disk)
      vm.Reconfigure(vm1, configSpec)
      VerifyNotEncryptedDisks(vm1)

      # Power on the VM to test hot-add of an encrypted disk.
      vm.PowerOn(vm1)

      configSpec = Vim.Vm.ConfigSpec()
      vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config, fileName=diskName,
                           policy=DefaultCryptoPolicy(),
                           crypto=cryptoSpecRegister)
      vm.Reconfigure(vm1, configSpec)
      VerifyEncryptedDisks(vm1, keyId, providerId)

      vm.PowerOff(vm1)

      # Delete the disk.
      disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
      configSpec = Vim.Vm.ConfigSpec()
      fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
      vmconfig.RemoveDeviceFromSpec(configSpec, disk, fileOp)
      vm.Reconfigure(vm1, configSpec)

      # Restore the VM to the original state
      DecryptVM(vm1)
   except Exception as e:
      if deletePath:
         task = vdiskMgr.DeleteVirtualDisk(deletePath, None)
         WaitForTask(task)
      raise

def TestEncDiskDecVM(si, vm1, keyId, providerId):
   """Test disk encryption and VM decryption at the same time.
   """
   # Confirm that the VM is not initially encrypted.
   VerifyNotEncrypted(vm1.config)

   # Confirm that the VM can be encrypted.
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncryptedVM(vm1, vm1.config, keyId, providerId)

   # Add an encrypted disk to the VM and at the same time decrypt the VM
   configSpec = Vim.Vm.ConfigSpec()
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                        policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
   configSpec.crypto = CreateCryptoSpecDecrypt()
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidVmConfig,
                   msgid="msg.hostd.configSpec.enc.mismatch")

   # Add two unencrypted disks.
   configSpec = Vim.Vm.ConfigSpec()
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config)
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config)
   vm.Reconfigure(vm1, configSpec)

   # Encrypt one of the disks and decrypt the VM at same time.
   disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
   configSpec = Vim.Vm.ConfigSpec()
   operation = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
   encSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   vmconfig.AddDeviceToSpec(configSpec, disk, operation,
                            policy=DefaultCryptoPolicy(), crypto=encSpec)
   configSpec.crypto = CreateCryptoSpecDecrypt()
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.InvalidDeviceSpec,
                   msgid="msg.hostd.configSpec.enc.mismatch")

   # Delete the disk.
   disks = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disks[-1], fileOp)
   vmconfig.RemoveDeviceFromSpec(configSpec, disks[-2], fileOp)
   vm.Reconfigure(vm1, configSpec)

   # Restore the VM to the original state
   DecryptVM(vm1)

def TestTicketing(si, vmname, dsName, keep, keyId, providerId):
   """Verify VMcrypt restrictions on hostd ticket operations
   """

   def VerifyTicketPermission(operation, shouldFailNoPerm, testuser):
      result = None
      failedNoPerm = False
      try:
         result = operation()
      except (Vim.Fault.NoPermission):
         failedNoPerm = True

      if shouldFailNoPerm and not failedNoPerm:
         raise Exception("Ticket operation with test user %s should have "
                         "failed with NoPermission, but didn't." % testuser)
      elif not shouldFailNoPerm and failedNoPerm:
         raise Exception("Ticket operation with test user %s should not "
                         "have failed with NoPermission, but did." % testuser)

      return result

   def DeleteTicketTestUser(si, testsi, testuser):
      sic = si.RetrieveContent()
      lam = sic.GetAccountManager()
      testrole = testuser + "_role";

      try:
         if testsi:
            Disconnect(testsi)
         # Disconnect sets the global si to None...
            SetSi(si)
      except:
         pass
      try:
         lam.RemoveUser(testuser)
      except:
         pass
      try:
         roleid = GetRoleId(testrole)
         RemoveRole(roleid, False)
      except:
         pass

   def CreateTicketTestUser(si, testuser, testpword, testprivs):
      DeleteTicketTestUser(si, None, testuser)

      sic = si.RetrieveContent()
      lam = sic.GetAccountManager()
      am = sic.GetAuthorizationManager()
      rf = sic.GetRootFolder()

      aspec = Vim.Host.LocalAccountManager.PosixAccountSpecification()
      aspec.SetId(testuser)
      aspec.SetPassword(testpword)
      aspec.SetDescription("test user for VMcrypt.py")

      lam.CreateUser(aspec)

      testrole = testuser + "_role";
      roleid = CreateRole(testrole, privsToAdd = testprivs)

      perm = Vim.AuthorizationManager.Permission()
      perm.group = False
      perm.principal = testuser
      perm.propagate = True
      perm.roleId = roleid

      am.SetEntityPermissions(rf, [perm])

      testsi = SmartConnect(host=_hostname,
                            user=testuser,
                            pwd=testpword,
                            port=443)
      if not testsi:
         raise Exception("Could not connect to '%s' as '%s'." %
                         (host, testuser))

      # What's with this "SetSi" stuff? connect.py has an "_si" global
      # that is used by a lot of things. It essentially represents the
      # current user session. Here, we want to open multiple user
      # sessions and switch between them on-the-fly. "SetSi" lets us do
      # that. Here, we call it because SmartConnect switched us to the
      # newly created user's session, and we want to switch back to the
      # original root session.

      SetSi(si)
      return testsi

   def TestMKSTicketing(testsi, testuser, vm1, ds, shouldFailNoPerm):
      vm.PowerOn(vm1)

      # XXX We have to wait for hostd to notice the VM is powered-on and
      # set the _mksReady property in the VM. Is there a better way?
      try:
         for i in range(300):
            try:
               VerifyTicketPermission(lambda: vm1.AcquireMksTicket(),
                                      shouldFailNoPerm, testuser)
            except (Vmodl.Fault.SystemError):
               # Failed due to _mksReady not being set, loop...
               time.sleep(1)
      finally:
         vm.PowerOff(vm1)

   def TestNFCTicketing(testsi, testuser, vm1, ds, shouldFailNoPerm):
      deviceKey = None
      for device in vm1.GetConfig().GetHardware().GetDevice():
         if isinstance(device, Vim.Vm.Device.VirtualDisk):
            deviceKey = device.GetKey()
            diskPath = device.backing.fileName
            break
      assert deviceKey

      nfcs = testsi.RetrieveInternalContent().GetNfcService()

      ops = [
         lambda: nfcs.RandomAccessOpen(vm1, deviceKey, None),
         lambda: nfcs.RandomAccessOpenReadonly(vm1, deviceKey, None),
         lambda: nfcs.RandomAccessFileOpen(diskPath, 10, None),
         lambda: nfcs.GetVmFiles(vm1, None),
         lambda: nfcs.PutVmFiles(vm1, None),
         lambda: nfcs.SystemManagement(None),
         lambda: nfcs.FileManagement(ds, None),
         ]

      for op in ops:
         VerifyTicketPermission(op, shouldFailNoPerm, testuser)

      # Test ExportVm separately. We must complete the lease on
      # success or VM destroy fails.

      # See BUG 1738898. For now, this is always expected to fail for
      # encrypted VMs. Therefore commenting out the old test
      #     lease = VerifyTicketPermission(lambda: vm1.ExportVm(),
      #                                    shouldFailNoPerm, testuser)
      #     if lease != None:
      #        lease.HttpNfcLeaseComplete()
      failedNotSupported = False
      try:
         result = vm1.ExportVm()
      except (Vmodl.Fault.NotSupported):
         failedNotSupported = True
      finally:
         if not failedNotSupported:
            raise Exception("This operation should fail with NotSupported for "
                            "encrypted VMs but didn't!")

   testuser1 = "testVMcryptUser1"
   testuser2 = "testVMcryptUser2"
   testpword1 = "a^winner*is#you111!!11"
   testpword2 = "youre%$winner#@!$!111!!"
   nfcprivs = ["VirtualMachine.Provisioning.DiskRandomAccess",
               "VirtualMachine.Provisioning.DiskRandomRead",
               "VirtualMachine.Provisioning.FileRandomAccess",
               "VirtualMachine.Provisioning.GetVmFiles",
               "VirtualMachine.Provisioning.PutVmFiles",
               "Datastore.FileManagement",
               "Host.Config.SystemManagement",
               "VApp.Export"]
   mksprivs = ["VirtualMachine.Interact.ConsoleInteract"]
   defaultprivs = ["System.View",
                   "VirtualMachine.Interact.PowerOn",
                   "VirtualMachine.Interact.PowerOff"]
   cryptoprivs = ["Cryptographer.Access"]
   testprivs1 = defaultprivs + cryptoprivs + nfcprivs + mksprivs
   testprivs2 = defaultprivs + nfcprivs + mksprivs
   testsi1 = None
   testsi2 = None

   try:
      testsi1 = CreateTicketTestUser(si, testuser1, testpword1, testprivs1)
      testsi2 = CreateTicketTestUser(si, testuser2, testpword2, testprivs2)

      configSpec = vmconfig.CreateDefaultSpec(name=vmname,
                                              datastoreName=dsName)
      cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
      configSpec.crypto = cryptoSpec
      vmconfig.AddScsiCtlr(configSpec)
      vmconfig.AddScsiDisk(configSpec, datastorename=dsName,
                           policy=DefaultCryptoPolicy(), crypto=cryptoSpec)
      vm1 = vm.CreateFromSpec(configSpec)
      ds = FindDatastoreObject(dsName, si)
      SetSi(testsi1)

      # "SetSi" actually doesn't effect operations on an existing VM object.
      # We have to lookup the VM again!
      vm1 = folder.Find(vmname)
      TestNFCTicketing(testsi1, testuser1, vm1, ds, False)
      TestMKSTicketing(testsi1, testuser1, vm1, ds, False)
      SetSi(testsi2)
      vm1 = folder.Find(vmname)
      TestNFCTicketing(testsi2, testuser2, vm1, ds, True)
      TestMKSTicketing(testsi2, testuser2, vm1, ds, True)
   finally:
      SetSi(si)
      vm1 = folder.Find(vmname)
      if vm1 and not keep:
         vm.Destroy(vm1)
      DeleteTicketTestUser(si, testsi1, testuser1)
      DeleteTicketTestUser(si, testsi2, testuser2)

def TestAddDisk(si, vmname, dsName, keep, keyId, providerId):
   """Test add disk restrictions.
   """

   # Create an encrypted VM with no disk.
   configSpec = vmconfig.CreateDefaultSpec(name=vmname,
                                           datastoreName=dsName)
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   configSpec.crypto = cryptoSpec
   vmconfig.AddScsiCtlr(configSpec)
   vm1 = vm.CreateFromSpec(configSpec)
   VerifyEncrypted(vm1.config, keyId, providerId)

   # Create two disks, one encrypted and one plain. Don't add them to
   # the VM yet.
   diskSpecEnc = CreateVirtualDiskSpec(DefaultCryptoPolicy(), cryptoSpec)
   diskSpecPlain = CreateVirtualDiskSpec(DefaultEmptyPolicy())

   datastore = vm1.config.datastoreUrl[0].name
   diskNameEnc = vm1.name + "/diskEnc.vmdk"
   diskNamePlain = vm1.name + "/diskPlain.vmdk"
   diskPathEnc = "[" + datastore + "] " + diskNameEnc
   diskPathPlain = "[" + datastore + "] " + diskNamePlain

   deletePathEnc = None
   deletePathPlain = None

   try:
      vdiskMgr = si.RetrieveContent().GetVirtualDiskManager()

      deletePathEnc = CreateVirtualDisk(vdiskMgr, diskPathEnc, diskSpecEnc)
      deletePathPlain = CreateVirtualDisk(vdiskMgr, diskPathPlain,
                                          diskSpecPlain)

      # Add plain disk to the VM with "crypto" policy, should fail
      # since we don't support encrypting a disk during add.
      configSpec = Vim.Vm.ConfigSpec()
      vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                           fileName=diskNamePlain, policy=DefaultCryptoPolicy())
      VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                      Vim.Fault.InvalidDeviceSpec,
                      msgid="msg.hostd.deviceSpec.add.noencrypt")

      # Add plain disk to the VM with "none" policy, should work.
      configSpec = Vim.Vm.ConfigSpec()
      vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                           fileName=diskNamePlain, policy=DefaultEmptyPolicy())
      vm.Reconfigure(vm1, configSpec)

      # Add encrypted disk to the VM with "none" policy, should fail since
      # we don't support decrypting a disk during add.
      #
      # XXX PR 1628418: For now, this is actually a positive test. The
      # disk remains encrypted.
      #
      configSpec = Vim.Vm.ConfigSpec()
      vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                           fileName=diskNameEnc, policy=DefaultEmptyPolicy())
#      VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
#                      Vim.Fault.InvalidDeviceSpec,
#                      msgid="msg.hostd.deviceSpec.add.nodecrypt")
      vm.Reconfigure(vm1, configSpec)
      VerifyEncryptedDisks(vm1, keyId, providerId, 1)

      # Remove the encrypted disk we just added.
      disk = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualDisk)[-1]
      configSpec = Vim.Vm.ConfigSpec()
      vmconfig.RemoveDeviceFromSpec(configSpec, disk)
      vm.Reconfigure(vm1, configSpec)

      # Add encrypted disk to the VM with "crypto" policy, should work.
      configSpec = Vim.Vm.ConfigSpec()
      vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config,
                           fileName=diskNameEnc, policy=DefaultCryptoPolicy())
      vm.Reconfigure(vm1, configSpec)
   except Exception as e:
      # When no exception, the disks are deleted with the VM.
      if not keep:
         if deletePathEnc:
            task = vdiskMgr.DeleteVirtualDisk(deletePathEnc, None)
            WaitForTask(task)
         if deletePathPlain:
            task = vdiskMgr.DeleteVirtualDisk(deletePathPlain, None)
            WaitForTask(task)
      raise

   if not keep:
      vm.Destroy(vm1)

def TestVTPM(si, vm1, keyId, providerId):
   """Verify that VTPM requires VM encryption.
   """
   def AddVTPM(configSpec):
      tpm = Vim.Vm.Device.VirtualTPM()
      tpm.key = 11000   # XXX Is this right?
      op = Vim.Vm.Device.VirtualDeviceSpec.Operation.add
      vmconfig.AddDeviceToSpec(configSpec, tpm, op)

   def RemoveVTPM(vm1, configSpec):
      tpm = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualTPM)
      assert tpm[0]
      configSpec = vmconfig.RemoveDeviceFromSpec(configSpec, tpm[0])

   # Power-cycle so that we have an nvram file to play with
   PowerCycle(vm1)

   # Confirm that the VM is not initially encrypted.
   VerifyNotEncrypted(vm1.config)

   # Add a VTPM while not encrypted -> fail
   configSpec = Vim.Vm.ConfigSpec()
   AddVTPM(configSpec)
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.GenericVmConfigFault,
                   msgid="msg.vtpm.add.notEncrypted")

   # Add a VTPM while encrypted -> pass
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecEncrypt(keyId, providerId)
   AddVTPM(configSpec)
   vm.Reconfigure(vm1, configSpec)
   VerifyEncrypted(vm1.config, keyId, providerId)

   # Decrypt VM while VTPM present -> fail
   configSpec = Vim.Vm.ConfigSpec()
   configSpec.crypto = CreateCryptoSpecDecrypt()
   VerifyException(lambda: vm.Reconfigure(vm1, configSpec),
                   Vim.Fault.GenericVmConfigFault,
                   msgid="msg.vigor.enc.required.vtpm")
   VerifyEncrypted(vm1.config, keyId, providerId)

   # Remove VTPM while decrypting -> pass
   configSpec = Vim.Vm.ConfigSpec()
   RemoveVTPM(vm1, configSpec)
   configSpec.crypto = CreateCryptoSpecDecrypt()
   vm.Reconfigure(vm1, configSpec)
   VerifyNotEncrypted(vm1.config)

def TestMigrateVm(si, vmname, dsName, keep, keyId, providerId):
   """Create an encrypted VM and then make a copy.

   Hostd doesn't implement the Vim clone or relocate APIs, but we still
   want to test those code paths without needing VC. This test creates
   a very simple VM, and then takes a memory snapshot. It then creates a
   second VM with the same encryption bundle as the first VM and the vmsd,
   vmem, vmsn, nvram files copied from the first VM. It verifies that these
   files are recrypted with new keys by verifying that revert to old snapshot
   succeeds.
   """
   def _runTest(vm1):
      # Take memory snapshot
      vm.CreateSnapshot(vm1, "Encrypted", None)
      snap1 = vm1.snapshot.currentSnapshot
      VerifyEncrypted(snap1.config, keyId, providerId)

      # Get the encryption bundle from the first VM.
      bundle = GetExtraConfig(snap1.config.extraConfig, "encryption.bundle")

      # Generate new keyID to use for recrypt and rekey.
      cryptoMgr = si.RetrieveContent().cryptoManager
      newKeyId, newProviderId, cryptoKey = CreateCryptoKeyDefault()
      cryptoMgr.AddKeys([cryptoKey])

      dsPath = GetDatastorePath(si, dsName)
      srcVmDir = os.path.join(dsPath, vmname)
      dstVmName = "%s-recrypt" %vmname
      dstVmDir = os.path.join(dsPath, dstVmName)

      assert not os.path.exists(dstVmDir)
      os.makedirs(dstVmDir)

      # Copy vmem, nvram, vmsd and vmsn files.
      from shutil import copyfile
      vmemFile = "%s-Snapshot1.vmem" %vmname
      copyfile(os.path.join(srcVmDir, vmemFile),
               os.path.join(dstVmDir, vmemFile))

      vmsnFile = "%s-Snapshot1.vmsn" %vmname
      copyfile(os.path.join(srcVmDir, vmsnFile),
               os.path.join(dstVmDir, vmsnFile))

      copyfile(os.path.join(srcVmDir, "%s.nvram" %vmname),
               os.path.join(dstVmDir, "%s.nvram" %dstVmName))

      copyfile(os.path.join(srcVmDir, "%s.vmsd" %vmname),
               os.path.join(dstVmDir, "%s.vmsd" %dstVmName))

      # Create a VM with the first VM encryption state recrypted with new keys.
      configSpec = vmconfig.CreateDefaultSpec(dstVmName,
                                              datastoreName=dsName)
      cryptoSpec = CreateCryptoSpecRecrypt(newKeyId, newProviderId)
      configSpec.crypto = cryptoSpec
      AddExtraConfig(configSpec.extraConfig, "encryption.bundle", bundle)
      vm2 = vm.CreateFromSpec(configSpec)
      VerifyEncrypted(vm2.config, newKeyId, newProviderId)
      snap2 = vm2.snapshot.currentSnapshot
      VerifyEncrypted(snap2.config, newKeyId, newProviderId)
      vm.RevertToCurrentSnapshot(vm2)
      vm.PowerOff(vm2)

      # Power cycle for verification.
      PowerCycle(vm2)

      if not keep:
         vm.Destroy(vm2)

   # Test verification requires local file access - vmsd, vmsn, etc.
   if not IsLocalhostESX():
      return

   # Create a very simple encrypted VM; no disks.
   configSpec = vmconfig.CreateDefaultSpec(name=vmname,
                                           datastoreName=dsName)
   cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
   configSpec.crypto = cryptoSpec
   vm1 = vm.CreateFromSpec(configSpec)
   VerifyEncrypted(vm1.config, keyId, providerId)

   # Power-cycle the VM so that metadata files are created (e.g. nvram).
   PowerCycle(vm1)

   vm.PowerOn(vm1)
   _runTest(vm1)
   vm.PowerOff(vm1)

   if not keep:
      vm.Destroy(vm1)


def TestEncDiskWithFcdSidecar(si, vm1, keyId, providerId):
   """Ensure that FCD metadata sidecar is present after VM encryption
   and decryption.
   """
   def getDiskPath(vm):
      disk = vmconfig.CheckDevice(vm.config, Vim.Vm.Device.VirtualDisk)[-1]
      return os.path.join(
         vm.config.datastoreUrl[0].url,
         vm.name,
         os.path.basename(disk.backing.fileName),
      )
   def ensureFcdSidecarPresent(path):
      enumSidecarsCmd = ["/bin/diskTool", "--sidecar", "enum", path]
      output = subprocess.check_output(enumSidecarsCmd, shell=False)
      assert "key = \\'fcdmdsidecar\\'" in str(output).lower(), output

   configSpec = Vim.Vm.ConfigSpec()
   vmconfig.AddScsiDisk(configSpec, cfgInfo=vm1.config)
   vm.Reconfigure(vm1, configSpec)

   diskPath = getDiskPath(vm1)

   createSidecarCmd = ["/bin/diskTool", "--sidecar",
                       "create,fcdmdsidecar,1m", diskPath]
   subprocess.check_output(createSidecarCmd, shell=False)
   ensureFcdSidecarPresent(diskPath)

   EncryptVM(vm1, keyId, providerId)
   ensureFcdSidecarPresent(getDiskPath(vm1))

   DecryptVM(vm1)
   ensureFcdSidecarPresent(getDiskPath(vm1))


Test = namedtuple('Test', ['fn', 'createsVm', 'quick', 'disabled'])
_tests = [
   #     Function                   Creates VM? Quick? Disabled?
   Test( TestAddDisk,               True,       False, False,    ),
   Test( TestCancelable,            False,      False, False,    ),
   Test( TestCapabilities,          False,      False, False,    ),
   Test( TestCloneVm,               True,       False, False,    ),
   Test( TestCreateVm,              True,       True,  False,    ),
   Test( TestCryptoManager,         False,      False, False,    ),
   Test( TestDSBrowser,             True,       False, False,    ),
   Test( TestDecOnlyVM,             False,      False, False,    ),
   Test( TestDownloadVMXConfig,     False,      False, False,    ),
   Test( TestEncOnlyDisk,           False,      False, False,    ),
   Test( TestEncDiskDecVM,          False,      False, False,    ),
   Test( TestEncDiskWithFcdSidecar, False,      False, False,    ),
   Test( TestExistingDisk,          False,      False, False,    ),
   Test( TestExtraConfig,           False,      False, False,    ),
   Test( TestExtractNvram,          False,      False, False,    ),
   Test( TestInitialOverhead,       False,      False, False,    ),
   Test( TestInvalidPolicy,         False,      False, False,    ),
   Test( TestInvalidSpec,           False,      False, False,    ),
   Test( TestInvalidState,          False,      False, False,    ),
   Test( TestKeyNoProvider,         False,      False, False,    ),
   Test( TestKeyNotFound,           False,      False, False,    ),
   Test( TestMigrateVm,             True,       False, False,    ),
   Test( TestNoKey,                 True,       False, False,    ),
   Test( TestNoOp,                  False,      False, False,    ),
   Test( TestReconfigure,           False,      True,  False,    ),
   Test( TestRekey,                 False,      False, False,    ),
   Test( TestRekeySnapshots,        False,      False, False,    ),
   Test( TestRemDiskDecVM,          False,      False, False,    ),
   Test( TestRDM,                   False,      False, False,    ),
   Test( TestSanity,                False,      True,  False,    ),
   Test( TestScrubbedDisk,          False,      False, False,    ),
   Test( TestShareEncryptedBacking, True,       False, False,    ),
   Test( TestEncryptSharedBacking,  True,       False, False,    ),
   Test( TestShareEncryptedDisk,    True,       False, False,    ),
   Test( TestEncryptSharedDisk,     True,       False, False,    ),
   Test( TestSnapshots,             False,      False, False,    ),
   Test( TestSnapshotsLocked,       False,      False, False,    ),
   Test( TestTicketing,             True,       False, False,    ),
   Test( TestVdiskMgr,              False,      False, False,    ),
   Test( TestVmxSandbox,            True,       False, False,    ),
   Test( TestVTPM,                  False,      False, False,    ),
]

def CleanupVm(vm1):
   try:
      poweredOn = Vim.VirtualMachine.PowerState.poweredOn
      if vm1.runtime.powerState == poweredOn:
         vm.PowerOff(vm1)
      vm.Destroy(vm1)
   except Exception as e:
      Log("Error cleaning up VM: %s" % e)

def CleanupAllVm(vmname):
   Log("Cleaning up all VMs with name %s ..." % vmname)
   oldVms = folder.FindPrefix(vmname)
   for oldVm in oldVms:
      CleanupVm(oldVm)

def TestName(test):
   fnName = test.fn.__name__
   assert fnName[:4] == "Test"
   return fnName[4:]

def RunTest(si, test, vmname, dsName, vm1, keep, keyId, providerId,
            memcheck = False, dump = False):
   Log("  * Testing %s ..." % TestName(test))
   memChecker = MemoryLeakChecker()

   try:
      if not test.createsVm:
         if not vm1:
            vm1 = vm.CreateQuickDummy(vmname, datastoreName=dsName,
                                      scsiCtlrs=1)
         test.fn(si, vm1, keyId, providerId)
         if not keep:
            CleanupVm(vm1)
      else:
         assert not vm1
         test.fn(si, vmname, dsName, keep, keyId, providerId)

      # Check if there is a memory leak in hostd.
      if memcheck and memChecker.HasMemoryLeak("hostd", True):
         Log("Test %s failed." % TestName(test))
         Log("Memory leak in hostd.")
         Log("Memory leak check related files are available at %s."
             % memChecker.GetMemleakCheckDirectory())

         if dump:
            Log(memChecker.GetMemleakCheckOutput())
         return False
   except Exception as e:
      Log("Test %s failed." % TestName(test))
      import traceback
      Log(traceback.format_exc())
      return False
   else:
      return True

def Run(si, test, vmname, dsName, vm1, quick, disabled,
        keep, keyId, providerId, memcheck, dump):
   global _status

   if memcheck:
      Log("hostd memory leak check enabled.")

   for t in _tests:
      # Only run quick tests during a quick run.
      if quick and not t.quick:
         continue
      # Skip tests that are disabled, unless requested.
      if not disabled and t.disabled:
         continue
      # Only run the specified test, or all.
      if test.lower() != "all" and test.lower() != TestName(t).lower():
         continue
      # We have an existing VM; only some tests support that.
      if vm1 and t.createsVm:
         continue
      # OK this is a test that we want to run.
      if not RunTest(si, t, vmname, dsName, vm1, keep, keyId, providerId,
                     memcheck, dump):
         assert _status == "FAIL"
         return

   _status = "PASS"

def TestIncapableHost(si):
   """Verify expected failures on an crypto-incapable host.

   Once a host is prepared, we can't un-prepare it. Because of this, we
   need to run some tests in the context of "Main"; before CryptoManager
   has been configured.
   """
   hs = host.GetHostSystem(si)
   assert hs.runtime.cryptoState == "incapable"
   cryptoMgr = si.RetrieveContent().cryptoManager
   assert not cryptoMgr.enabled

   keyId, providerId, cryptoKey = CreateCryptoKeyDefault()
   VerifyException(lambda: cryptoMgr.AddKey(cryptoKey),
                   Vim.Fault.InvalidState)

   keyId, providerId, cryptoKey = CreateCryptoHostKeyDefault()
   VerifyException(lambda: host.GetHostSystem(si).EnableCrypto(cryptoKey),
                   Vim.Fault.InvalidState)

def TestPreparedHost(si):
   """Verify expected failures on a crypto-prepared host.

   Once a host is prepared, we can't un-prepare it. Because of this, we
   need to run some tests in the context of "Main"; before CryptoManager
   has been configured.
   """
   hs = host.GetHostSystem(si)
   assert hs.runtime.cryptoState == "prepared"
   cryptoMgr = si.RetrieveContent().cryptoManager
   assert not cryptoMgr.enabled

   keyId, providerId, cryptoKey = CreateCryptoKeyDefault(algo="XTS-AES-256")
   VerifyException(lambda: host.GetHostSystem(si).EnableCrypto(cryptoKey),
                   Vmodl.Fault.InvalidArgument, msg="key.algorithm")

   keyId1, providerId1, cryptoKey1 = CreateCryptoKeyDefault()
   Log("Using temporary host key provider '%s' with key ID '%s' : %s" %
       (providerId1, keyId1, cryptoKey1.keyData))
   hs.EnableCrypto(cryptoKey1)

   keyId2, providerId2, cryptoKey2 = CreateCryptoKeyDefault()
   Log("Test changing host key provider '%s' with key ID '%s' : %s" %
       (providerId2, keyId2, cryptoKey2.keyData))
   hs.EnableCrypto(cryptoKey2)

   # Test setting the same host key, when the host is prepared or safe.
   hs.EnableCrypto(cryptoKey2)
   hs.PrepareCrypto()
   hs.EnableCrypto(cryptoKey2)

   # Going back to the prepared state is not required (but supported) PR 1646506
   hs.PrepareCrypto()

def VerifyCryptoKeyId(hs, expectedKeyId):
   observedKeyId = hs.runtime.cryptoKeyId.keyId

   if observedKeyId != expectedKeyId:
      raise ValueError("cryptoKeyId mismatch: observed %s expected %s" %
                       (observedKeyId, expectedKeyId))

def PerformChangeKey(cryptoMgr, key):
   task = cryptoMgr.ChangeKey(key)
   WaitForTask(task)

def TestChangingHostKey(si):
   """Use the CryptoManagerHost interfaces to change the host key"""
   hs = host.GetHostSystem(si)
   assert hs.runtime.cryptoState == "prepared"
   cryptoMgr = si.RetrieveContent().cryptoManager
   assert not cryptoMgr.enabled

   # Cannot return to prepared state
   VerifyException(lambda: cryptoMgr.Prepare(), Vim.Fault.InvalidState)

   # Generate a few test keys
   keyId1, providerId1, cryptoKey1 = CreateCryptoKeyDefault()
   keyId2, providerId2, cryptoKey2 = CreateCryptoKeyDefault()

   # Install the initial host key
   Log("Using temporary host key provider '%s' with key ID '%s' : %s" %
       (providerId1, keyId1, cryptoKey1.keyData))
   cryptoMgr.Enable(cryptoKey1)
   WithRetry(lambda: VerifyCryptoKeyId(hs, keyId1))
   assert cryptoMgr.enabled

   # Installing the initial host key again should be OK (ignored)
   cryptoMgr.Enable(cryptoKey1)
   assert cryptoMgr.enabled

   # Cannot use Enable to install a host key once one has been installed
   VerifyException(lambda: cryptoMgr.Enable(cryptoKey2),
                   Vim.Fault.AlreadyExists)

   # Change to a new host key
   Log("Using temporary host key provider '%s' with key ID '%s' : %s" %
       (providerId2, keyId2, cryptoKey2.keyData))
   PerformChangeKey(cryptoMgr, cryptoKey2)
   VerifyCryptoKeyId(hs, keyId2)
   assert cryptoMgr.enabled

   # Reuse the new host key; this should be OK
   Log("Using temporary host key provider '%s' with key ID '%s' : %s" %
       (providerId2, keyId2, cryptoKey2.keyData))
   PerformChangeKey(cryptoMgr, cryptoKey2)
   VerifyCryptoKeyId(hs, keyId2)
   assert cryptoMgr.enabled

   # Return to the original host key
   Log("Using temporary host key provider '%s' with key ID '%s' : %s" %
       (providerId1, keyId1, cryptoKey1.keyData))
   PerformChangeKey(cryptoMgr, cryptoKey1)
   VerifyCryptoKeyId(hs, keyId1)
   assert cryptoMgr.enabled

def TestDisablePreparedHostCrypto(si):
   hs = host.GetHostSystem(si)
   assert hs.runtime.cryptoState == "incapable"
   cryptoMgr = si.RetrieveContent().cryptoManager
   cryptoMgr.Prepare()

   assert hs.runtime.cryptoState == "prepared"
   cryptoMgr.Disable()
   assert hs.runtime.cryptoState == "incapable"

def TestDisableSafeHostCrypto(si):
   hs = host.GetHostSystem(si)
   assert hs.runtime.cryptoState == "safe"
   cryptoMgr = si.RetrieveContent().cryptoManager

   cryptoMgr.Disable()
   assert hs.runtime.cryptoState == "pendingIncapable"
   assert not cryptoMgr.enabled
   assert os.path.exists("/var/run/vmware/pendingIncapableCrypto")

   keyId3, providerId3, cryptoKey3 = CreateCryptoKeyDefault()
   cryptoMgr.Enable(cryptoKey3)
   assert cryptoMgr.enabled
   assert hs.runtime.cryptoState == "safe"
   assert not os.path.exists("/var/run/vmware/pendingIncapableCrypto")


def Main(args, si, vm1, dsName):
   if vm1:
      vmname = vm1.config.name
   else:
      vmname = args.GetKeyValue("vmname")
      if not vmname:
         vmname = "%sVM.%d" % (_testName, os.getpid())
   test = args.GetKeyValue("test")
   quick = args.GetKeyValue("quick")
   disabled = args.GetKeyValue("disabled")
   keep = args.GetKeyValue("keep")
   memcheck = args.GetKeyValue("memcheck")
   dump = args.GetKeyValue("dump")

   if not memcheck and dump:
      Log("Error passing memcheck parameters.")
      Log("Dumping of ah64 output selected without setting memcheck.")

   cryptoMgr = si.RetrieveContent().cryptoManager

   if not cryptoMgr.enabled:
      hs = host.GetHostSystem(si)

      if hs.runtime.cryptoState == "incapable":
         TestIncapableHost(si)
         TestDisablePreparedHostCrypto(si)
         Log("Prepare host for crypto")
         cryptoMgr.Prepare()
         TestPreparedHost(si)

      TestChangingHostKey(si)

      TestDisableSafeHostCrypto(si)

      # Setting the real host-key. DO NOT change the host-key after this point!
      keyId, providerId, cryptoKey = CreateCryptoHostKeyDefault()
      Log("Using host key with key ID '%s' : %s" % (keyId, cryptoKey.keyData))
      PerformChangeKey(cryptoMgr, cryptoKey)
      VerifyCryptoKeyId(hs, "VMwareInternalHostKeyForTesting")

   if not cryptoMgr.enabled:
      raise Exception("CryptoManager is not enabled.")

   keyId, providerId, cryptoKey = CreateCryptoKeyDefault()
   Log("Using VM key provider '%s' with key ID '%s' : %s" %
       (providerId, keyId, cryptoKey.keyData))
   cryptoMgr.AddKeys([cryptoKey])

   if vm1:
      Log("Using existing VM: %s" % vm1.config.name)
      Log("A subset of tests will be run.")
      keep = True
   else:
      Log("Using VM name '%s', with datastore [%s]." % (vmname, dsName))

   if quick:
      Log("Quick tests only.")
   if disabled:
      Log("Including disabled tests.")

   Log("--- TEST CASES ---")
   Run(si, test, vmname, dsName, vm1, quick, disabled,
       keep, keyId, providerId, memcheck, dump)
   Log("--- TEST CASES ---")
   if not keep:
      CleanupAllVm(vmname)

def ParseArgs():
   supportedArgs = [ (["h:", "host="], "localhost", "ESX Host", "host"),
                     (["u:", "user="], "root", "Username", "user"),
                     (["p:", "pwd="], "", "Password", "pwd"),
                     (["v:", "vm="], None, "Existing VM", "vm"),
                     (["n:", "vmname="], None, "VM Name", "vmname"),
                     (["d:", "datastore="], "datastore1", "Datastore",
                                            "datastore"),
                     (["t:", "test="], "All", "Test Name", "test"),
                   ]
   supportedToggles = [ (["quick"], False, "Quick Test", "quick"),
                        (["disabled"], False, "Include Disabled", "disabled"),
                        (["keep"], False, "Keep VMs", "keep"),
                        (["memcheck"], False, "Check if memory leak in hostd", "memcheck"),
                        (["dump"], False, "Dump ah64 result in the log.", "dump"),
                        (["usage", "help"], False, "Help", "usage")
                      ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage"):
      args.Usage()
      sys.exit(0)
   return args

def Connect(args):
   global _hostname
   _hostname = args.GetKeyValue("host")
   si = SmartConnect(host=_hostname,
                     user=args.GetKeyValue("user"),
                     pwd=args.GetKeyValue("pwd"),
                     port=443)
   if not si:
      Log("Could not connect to '%s'." % _hostname)
      sys.exit(1)
   atexit.register(Disconnect, si)
   Log("Connected to %s (%s)" % (_hostname, si.content.about.fullName))
   return si

def GetVM(args):
   vmname = args.GetKeyValue("vm")
   if vmname:
      if args.GetKeyValue("vmname"):
         Log("Invalid argument 'vmname'.")
         sys.exit(1)
      vm1 = folder.Find(vmname)
      if not vm1:
         Log("Could not find virtual machine, '%s'." % vmname)
         sys.exit(1)
      return vm1
   else:
      # A virtual machine will be created.
      return None

def GetDatastorePath(si, dsName):
   hs = host.GetHostSystem(si)
   datastores = hs.GetDatastore()
   for ds in datastores:
      if (ds.name == dsName or
          ds.info.url.replace("/vmfs/volumes/", "") == dsName):
         return ds.info.url
   Log("Error looking up datastore: %s" % dsName)
   sys.exit(1)

def GetDatastore(args, si):
   hs = host.GetHostSystem(si)
   datastores = hs.GetDatastore()
   dsName = args.GetKeyValue("datastore")
   dsName = dsName.replace("/vmfs/volumes/", "")
   for ds in datastores:
      if (ds.name == dsName or
          ds.info.url.replace("/vmfs/volumes/", "") == dsName):
         return ds.name
   Log("Error looking up datastore: %s" % dsName)
   sys.exit(1)

def CheckBuildType():
   buildType = os.environ.get('VMBLD') or os.environ.get('BLDTYPE')
   if not buildType:
      Log("Unknown ESXi build type. Assuming OBJ.")
      return
   if buildType != 'obj':
      Log("Detected non-OBJ build type. A subset of tests will be run.")
      global _runObjTests
      _runObjTests = False

if __name__ == "__main__":
   Log("%s Host Test" % _testName)
   CheckBuildType()
   args = ParseArgs()
   si = Connect(args)
   vm1 = GetVM(args)
   dsName = GetDatastore(args, si)
   clock = StopWatch()
   Main(args, si, vm1, dsName)
   clock.finish(_testName)
   Log("VM Encryption Tests Completed")
   Log("Test status: %s" % _status)
   if _status == "FAIL":
      sys.exit(1)
