#!/usr/bin/python

#
# Basic tests for Vim::Vm::Guest::WindowsRegistryManager
#
# These require the latest tools on a Windows VM
#

from pyVmomi import Vim, Vmodl
from pyVim.helpers import Log
from guestOpsUtils import *

def testSetup():
   Log("Setup for Registry Operations")

   # --- HKEY_CURRENT_USER\TEST_KEY\ABC_1 ---
   keyPath = "HKEY_CURRENT_USER\TEST_KEY\ABC_1"
   keyName = regDef.RegistryKeyName(registryPath=keyPath,
                                    wowBitness="WOWNative")

   Log("Cleaning up key: %s" % keyPath)
   try:
      result = regMgr.DeleteRegistryKeyInGuest(virtualMachine, guestAuth,
                                               keyName, True)
   except Vim.Fault.GuestRegistryKeyInvalid as e:
      pass

   Log("Creating key: %s" % keyPath)
   result = regMgr.CreateRegistryKeyInGuest(virtualMachine, guestAuth,
                                            keyName, True)

   # --- HKEY_CURRENT_USER\TEST_KEY\ABC_1 ---
   keyPath = "HKEY_CURRENT_USER\TEST_KEY\ABC_2"
   keyName = regDef.RegistryKeyName(registryPath=keyPath,
                                    wowBitness="WOWNative")

   Log("Cleaning up key %s" % keyPath)
   try:
      result = regMgr.DeleteRegistryKeyInGuest(virtualMachine, guestAuth,
                                               keyName, True)
   except Vim.Fault.GuestRegistryKeyInvalid as e:
      pass

   Log("Creating key: %s" % keyPath)
   result = regMgr.CreateRegistryKeyInGuest(virtualMachine, guestAuth,
                                            keyName, True)

   # --- HKEY_CURRENT_USER\TEST_KEY\XYZ_1 ---
   keyPath = "HKEY_CURRENT_USER\TEST_KEY\XYZ_1"
   keyName = regDef.RegistryKeyName(registryPath=keyPath,
                                    wowBitness="WOWNative")

   Log("Cleaning up key %s" % keyPath)
   try:
      result = regMgr.DeleteRegistryKeyInGuest(virtualMachine, guestAuth,
                                               keyName, True)
   except Vim.Fault.GuestRegistryKeyInvalid as e:
      pass

   Log("Creating key: %s" % keyPath)
   result = regMgr.CreateRegistryKeyInGuest(virtualMachine, guestAuth,
                                            keyName, True)

   # --- HKEY_CURRENT_USER\TEST_KEY\XYZ_2 ---
   keyPath = "HKEY_CURRENT_USER\TEST_KEY\XYZ_2"
   keyName = regDef.RegistryKeyName(registryPath=keyPath,
                                    wowBitness="WOWNative")

   Log("Cleaning up key %s" % keyPath)
   try:
      result = regMgr.DeleteRegistryKeyInGuest(virtualMachine, guestAuth,
                                               keyName, True)
   except Vim.Fault.GuestRegistryKeyInvalid as e:
      pass

   Log("Creating key: %s" % keyPath)
   result = regMgr.CreateRegistryKeyInGuest(virtualMachine, guestAuth,
                                            keyName, True)

   # --- Create ABC_1 sub-keys ---
   keyPath = "HKEY_CURRENT_USER\TEST_KEY\ABC_1"
   keyName = regDef.RegistryKeyName(registryPath=keyPath,
                                    wowBitness="WOWNative")

   Log("Creating values under key: %s" % keyPath)

   try:
      Log("Creating val: def_1 (dword)")
      valueName = regDef.RegistryValueName(keyName=keyName, name="def_1")
      valueData = regDef.RegistryValueDword(value=101)
      value = regDef.RegistryValue(name=valueName, data=valueData)
      result = regMgr.SetRegistryValueInGuest(virtualMachine, guestAuth, value)

      Log("Creating val: def_2 (string)")
      valueName = regDef.RegistryValueName(keyName=keyName, name="def_2")
      valueData = regDef.RegistryValueString(value="testVal")
      value = regDef.RegistryValue(name=valueName, data=valueData)
      result = regMgr.SetRegistryValueInGuest(virtualMachine, guestAuth, value)

      Log("Creating val: ghi_1 (dword)")
      valueName = regDef.RegistryValueName(keyName=keyName, name="ghi_1")
      valueData = regDef.RegistryValueDword(value=101)
      value = regDef.RegistryValue(name=valueName, data=valueData)
      result = regMgr.SetRegistryValueInGuest(virtualMachine, guestAuth, value)

      Log("Creating val: ghi_2 (string)")
      valueName = regDef.RegistryValueName(keyName=keyName, name="ghi_2")
      valueData = regDef.RegistryValueString(value="testVal")
      value = regDef.RegistryValue(name=valueName, data=valueData)
      result = regMgr.SetRegistryValueInGuest(virtualMachine, guestAuth, value)
   except Exception:
      raise

   # --- Create XYZ_1 sub-keys ---
   keyPath = "HKEY_CURRENT_USER\TEST_KEY\XYZ_1"
   Log("Creating subkeys under key: %s" % keyPath)

   try:
      Log("Creating key: HKEY_CURRENT_USER\TEST_KEY\XYZ_1\SUBKEY_1")
      keyName = regDef.RegistryKeyName(registryPath="HKEY_CURRENT_USER\TEST_KEY\XYZ_1\SUBKEY_1", wowBitness="WOWNative")
      result = regMgr.CreateRegistryKeyInGuest(virtualMachine, guestAuth, keyName, True)
   except Vim.Fault.GuestRegistryKeyAlreadyExists as e:
      Log("Setup successful. Expected GuestRegistryKeyAlreadyExists fault is thrown.")

   try:
      Log("Creating key: HKEY_CURRENT_USER\TEST_KEY\XYZ_1\SUBKEY_2")
      keyName = regDef.RegistryKeyName(registryPath="HKEY_CURRENT_USER\TEST_KEY\XYZ_1\SUBKEY_2", wowBitness="WOWNative")
      result = regMgr.CreateRegistryKeyInGuest(virtualMachine, guestAuth, keyName, True)
   except Vim.Fault.GuestRegistryKeyAlreadyExists as e:
      Log("Setup successful. Expected GuestRegistryKeyAlreadyExists fault is thrown.")


def testListKeys():
   Log("Testing ListRegistryKeysInGuest")
   keyName = regDef.RegistryKeyName(registryPath="HKEY_CURRENT_USER\TEST_KEY", wowBitness="WOWNative")
   keyNameBad = regDef.RegistryKeyName(registryPath="HKEY_CURRENT_USER\TEST_KEY_BAD", wowBitness="WOWNative")

   try:
      Log("ListRegistryKeysInGuest - 0")
      result = regMgr.ListRegistryKeysInGuest(virtualMachine, guestAuthBad, keyNameBad, False)
      Log("Test case failed.")
   except Vim.Fault.InvalidGuestLogin as e:
      Log("Testcase passed. Expected InvalidGuestLogin fault is thrown.")

   try:
      Log("ListRegistryKeysInGuest - 1")
      result = regMgr.ListRegistryKeysInGuest(virtualMachine, guestAuth, keyNameBad, False)
      Log("Test case failed.")
   except Vim.Fault.GuestRegistryKeyInvalid as e:
      Log("Testcase passed. Expected GuestRegistryKeyInvalid fault is thrown.")

   Log("ListRegistryKeysInGuest - 2")
   result = regMgr.ListRegistryKeysInGuest(virtualMachine, guestAuth, keyName, False)
   numResults = len(result)
   if numResults >= 4:
      Log("Test case passed with at least 4 keys as expected")
   else:
      Log("Test case failed. Expected 4 keys. Got %s" % numResults)
      raise AssertionError("Test case failed. Expected 4 keys. Got %s" % numResults)

   Log("ListRegistryKeysInGuest - 3")
   result = regMgr.ListRegistryKeysInGuest(virtualMachine, guestAuth, keyName, True)
   numResults = len(result)
   if numResults >= 6:
      Log("Test case passed with at least 6 keys as expected")
   else:
      Log("Test case failed. Expected 6 keys. Got %s" % numResults)
      raise AssertionError("Test case failed. Expected 6 keys. Got %s" % numResults)

   Log("ListRegistryKeysInGuest - 4")
   result = regMgr.ListRegistryKeysInGuest(virtualMachine, guestAuth, keyName, False, "ABC")
   numResults = len(result)
   if numResults == 2:
      Log("Test case passed with 2 keys as expected")
   else:
      Log("Test case failed. Expected 2 keys. Got %s" % numResults)
      raise AssertionError("Test case failed. Expected 2 keys. Got %s" % numResults)


def testListValues():
   Log("Testing ListRegistryValuesInGuest")
   keyName = regDef.RegistryKeyName(registryPath="HKEY_CURRENT_USER\TEST_KEY\ABC_1", wowBitness="WOWNative")
   keyNameBad = regDef.RegistryKeyName(registryPath="HKEY_CURRENT_USER\TEST_KEY_BAD", wowBitness="WOWNative")

   try:
      Log("ListRegistryValuesInGuest - 0")
      result = regMgr.ListRegistryValuesInGuest(virtualMachine, guestAuthBad, keyNameBad, False)
      Log("Test case failed.")
   except Vim.Fault.InvalidGuestLogin as e:
      Log("Testcase passed. Expected InvalidGuestLogin fault is thrown.")

   try:
      Log("ListRegistryValuesInGuest - 1")
      result = regMgr.ListRegistryValuesInGuest(virtualMachine, guestAuth, keyNameBad, False)
      Log("Test case failed.")
   except Vim.Fault.GuestRegistryKeyInvalid as e:
      Log("Testcase passed. Expected GuestRegistryKeyInvalid fault is thrown.")

   try:
      Log("ListRegistryValuesInGuest - 2")
      result = regMgr.ListRegistryValuesInGuest(virtualMachine, guestAuth, keyName, False)
      numResults = len(result)
      if numResults == 4:
         Log("Test case passed with 4 values as expected")
      else:
         Log("Test case failed. Expected 4 values. Got %s" % numResults)
         raise AssertionError("Test case failed. Expected 4 values. Got %s" % numResults)
   except Exception:
      raise

   try:
      Log("ListRegistryValuesInGuest - 3")
      result = regMgr.ListRegistryValuesInGuest(virtualMachine, guestAuth, keyName, False, "def")
      numResults = len(result)
      if numResults == 2:
         Log("Test case passed with 2 values as expected")
      else:
         Log("Test case failed. Expected 2 values. Got %s" % numResults)
         raise AssertionError("Test case failed. Expected 2 values. Got %s" % numResults)
   except Exception:
      raise


def testCreateKey():
   Log("Testing CreateRegistryKeyInGuest")
   keyPathBase = "HKEY_CURRENT_USER\TEST_KEY"
   keyPathNew = keyPathBase + "\NEW_TEST_KEY1"
   keyNameBase = regDef.RegistryKeyName(registryPath=keyPathBase, wowBitness="WOWNative")
   keyNameNew = regDef.RegistryKeyName(registryPath=keyPathNew, wowBitness="WOWNative")

   try:
      Log("CreateRegistryKeyInGuest - 0")
      result = regMgr.CreateRegistryKeyInGuest(virtualMachine, guestAuthBad, keyNameNew, True)
      Log("Test case failed.")
   except Vim.Fault.InvalidGuestLogin as e:
      Log("Testcase passed. Expected InvalidGuestLogin fault is thrown.")

   try:
      Log("CreateRegistryKeyInGuest - 1")
      result = regMgr.CreateRegistryKeyInGuest(virtualMachine, guestAuth, keyNameNew, True)
      Log("Test case passed.")
   except Vim.Fault.GuestRegistryKeyAlreadyExists as e:
      Log("Testcase passed. Expected GuestRegistryKeyAlreadyExists fault is thrown.")

   try:
      Log("CreateRegistryKeyInGuest - 2")
      result = regMgr.CreateRegistryKeyInGuest(virtualMachine, guestAuth, keyNameNew, True)
      Log("Test case failed.")
   except Vim.Fault.GuestRegistryKeyAlreadyExists as e:
      Log("Testcase passed. Expected GuestRegistryKeyAlreadyExists fault is thrown.")

   try:
      Log("CreateRegistryKeyInGuest - Verify")
      result = regMgr.ListRegistryKeysInGuest(virtualMachine, guestAuth, keyNameBase, False)
      numResults = len(result)
      Log("Found %s results" % numResults)
      found = False
      for keys in result:
         if keys.key.keyName.registryPath == keyPathNew:
            Log("Verification passed. Found newly created key %s" % keyPathNew)
            found = True
            break
      if not found:
         Log("Verification failed. Did not find newly created key %s" % keyPathNew)
         raise AssertionError("Did not find newly created key %s" % keyPathNew)
   except Exception:
      Log("Caught error in verification of create registry key")


def testSetValue():
   Log("Testing SetRegistryValueInGuest")
   valueDataDword = regDef.RegistryValueDword(value=202)
   valueDataString = regDef.RegistryValueString(value="testVal")
   keyNameGood = regDef.RegistryKeyName(registryPath="HKEY_CURRENT_USER\TEST_KEY\ABC_1", wowBitness="WOWNative")
   valueName = regDef.RegistryValueName(keyName=keyNameGood, name="new_val")
   valueDword = regDef.RegistryValue(name=valueName, data=valueDataDword)
   valueString = regDef.RegistryValue(name=valueName, data=valueDataString)
   keyNameBad = regDef.RegistryKeyName(registryPath="HKEY_CURRENT_USER\TEST_KEY_BAD", wowBitness="WOWNative")
   valueNameBad = regDef.RegistryValueName(keyName=keyNameBad, name="new_val")
   valueBad = regDef.RegistryValue(name=valueNameBad, data=valueDataDword)

   try:
      Log("SetRegistryValueInGuest - 0")
      result = regMgr.SetRegistryValueInGuest(virtualMachine, guestAuthBad,
                                              valueBad)
      Log("Test case failed.")
   except Vim.Fault.InvalidGuestLogin as e:
      Log("Testcase passed. Expected InvalidGuestLogin fault is thrown.")

   try:
      Log("SetRegistryValueInGuest - 1")
      result = regMgr.SetRegistryValueInGuest(virtualMachine, guestAuth,
                                              valueBad)
   except Vim.Fault.GuestRegistryKeyInvalid as e:
      Log("Testcase passed. Expected GuestRegistryKeyInvalid fault is thrown.")
   else:
      Log("Test case failed.")

   Log("SetRegistryValueInGuest - 2")
   result = regMgr.SetRegistryValueInGuest(virtualMachine, guestAuth,
                                           valueDword)
   Log("Test case passed.")

   Log("SetRegistryValueInGuest - Verify 1")
   result = regMgr.ListRegistryValuesInGuest(virtualMachine, guestAuth,
                                             keyNameGood, False)
   Log("result %s" % result)
   numResults = len(result)
   Log("Found %s results" % numResults)
   found = False
   for vals in result:
      if vals.name.name == "new_val" and vals.data.value == 202:
         Log("Verification passed. Found newly created value 'new_val' with dword data=202")
         found = True
         break
   if not found:
      Log("Verification failed. Did not find newly created value 'new_val' with dword data=202")
      raise AssertionError("Verification failed. Did not find newly created value 'new_val' with dword data=202")

   Log("SetRegistryValueInGuest - 3")
   result = regMgr.SetRegistryValueInGuest(virtualMachine, guestAuth,
                                           valueString)
   Log("Test case passed.")

   Log("SetRegistryValueInGuest - Verify 2")
   result = regMgr.ListRegistryValuesInGuest(virtualMachine, guestAuth,
                                             keyNameGood, False)
   numResults = len(result)
   Log("Found %s results" % numResults)
   found = False
   for vals in result:
      if vals.name.name == "new_val" and vals.data.value == "testVal":
         Log("Verification passed. Found newly created value 'new_val' with string data=\"testVal\"")
         found = True
         break
   if not found:
      Log("Verification failed. Did not find newly created value 'new_val' with string data=\"testVal\"")
      raise AssertionError("Verification failed. Did not find newly created value 'new_val' with string data=\"testVal\"")


def testDeleteValue():
   Log("Testing DeleteRegistryValueInGuest")
   keyNameGood = regDef.RegistryKeyName(registryPath="HKEY_CURRENT_USER\TEST_KEY\ABC_1", wowBitness="WOWNative")
   keyNameBad = regDef.RegistryKeyName(registryPath="HKEY_CURRENT_USER\TEST_KEY_BAD", wowBitness="WOWNative")
   valueName = regDef.RegistryValueName(keyName=keyNameGood, name="new_val")
   valueNameBadKey = regDef.RegistryValueName(keyName=keyNameBad, name="new_val")
   valueNameBadValue = regDef.RegistryValueName(keyName=keyNameGood, name="bad_val")

   try:
      Log("DeleteRegistryValueInGuest - 0")
      result = regMgr.DeleteRegistryValueInGuest(virtualMachine, guestAuthBad, valueNameBadKey)
   except Vim.Fault.InvalidGuestLogin as e:
      Log("Testcase passed. Expected InvalidGuestLogin fault is thrown.")
   else:
      Log("Test case failed.")

   try:
      Log("DeleteRegistryValueInGuest - 1")
      result = regMgr.DeleteRegistryValueInGuest(virtualMachine, guestAuth, valueNameBadKey)
   except Vim.Fault.GuestRegistryKeyInvalid as e:
      Log("Testcase passed. Expected GuestRegistryKeyInvalid fault is thrown.")
   else:
      Log("Test case failed.")

   try:
      Log("DeleteRegistryValueInGuest - 2")
      result = regMgr.DeleteRegistryValueInGuest(virtualMachine, guestAuth, valueNameBadValue)
   except Vim.Fault.GuestRegistryValueNotFound as e:
      Log("Testcase passed. Expected GuestRegistryValueNotFound fault is thrown.")
   else:
      Log("Test case failed.")

   Log("DeleteRegistryValueInGuest - 3")
   result = regMgr.DeleteRegistryValueInGuest(virtualMachine, guestAuth, valueName)
   Log("Test case passed.")

   Log("DeleteRegistryValueInGuest - Verify")
   result = regMgr.ListRegistryValuesInGuest(virtualMachine, guestAuth, keyNameGood, False)
   numResults = len(result)
   Log("Found %s results" % numResults)
   for vals in result:
      if vals.name.name == "new_val" and vals.data.value == "testVal":
         Log("Verification failed. Found deleted value 'new_val' with string data=2\"testVal\"")
         raise AssertionError("Verification failed. Found deleted value 'new_val' with string data=2\"testVal\"")
   Log("Verification passed. Did not find deleted value 'new_val' with string data=\"testVal\"")


def testDeleteKey():
   Log("Testing DeleteRegistryKeyInGuest")
   keyPathBase = "HKEY_CURRENT_USER"
   keyPathNew = keyPathBase + "\TEST_KEY"
   keyNameBase = regDef.RegistryKeyName(registryPath=keyPathBase, wowBitness="WOWNative")
   keyNameNew = regDef.RegistryKeyName(registryPath=keyPathNew, wowBitness="WOWNative")

   try:
      Log("DeleteRegistryKeyInGuest - 0")
      result = regMgr.DeleteRegistryKeyInGuest(virtualMachine, guestAuthBad, keyNameNew, False)
   except Vim.Fault.InvalidGuestLogin as e:
      Log("Testcase passed. Expected InvalidGuestLogin fault is thrown.")
   else:
      Log("Test case failed.")

   try:
      Log("DeleteRegistryKeyInGuest - 1")
      result = regMgr.DeleteRegistryKeyInGuest(virtualMachine, guestAuth, keyNameNew, False)
   except Vim.Fault.GuestRegistryKeyHasSubkeys as e:
      Log("Testcase passed. Expected GuestRegistryKeyHasSubkeys fault is thrown.")
   else:
      Log("Test case failed.")

   Log("DeleteRegistryKeyInGuest - 2")
   result = regMgr.DeleteRegistryKeyInGuest(virtualMachine, guestAuth, keyNameNew, True)
   Log("Test case passed.")

   try:
      Log("DeleteRegistryKeyInGuest - 3")
      result = regMgr.DeleteRegistryKeyInGuest(virtualMachine, guestAuth, keyNameNew, False)
   except Vim.Fault.GuestRegistryKeyInvalid as e:
      Log("Testcase passed. Expected GuestRegistryKeyInvalid fault is thrown.")
   else:
      Log("Test case failed.")

   try:
      Log("DeleteRegistryKeyInGuest - verify")
      result = regMgr.ListRegistryKeysInGuest(virtualMachine, guestAuth, keyNameBase, False)
      numResults = len(result)
      Log("Found %s results" % numResults)
      for keys in result:
         if keys.key.keyName.registryPath == keyPathNew:
            Log("Found deleted key %s" % keyPathNew)
            raise AssertionError("Found deleted key %s" % keyPathNew)
   except Exception:
      Log("Caught error in verification of delete registry key")
   else:
      Log("Verification passed. Did not find deleted key %s" % keyPathNew)


def testCreateKeyVolatile():
   Log("Testing CreateRegistryKeyInGuest - Volatile")
   keyPathBase = "HKEY_CURRENT_USER\Software"
   keyPathVolatile = keyPathBase + "\KEY_VOLATILE"
   keyPathNonVolatile = keyPathBase + "\KEY_NON_VOLATILE"
   keyPathNonVolatileBadChild = keyPathVolatile + "\KEY_NON_VOLATILE"
   keyPathNonVolatileGoodChild = keyPathNonVolatile + "\KEY_NON_VOLATILE"
   keyNameBase = regDef.RegistryKeyName(registryPath=keyPathBase, wowBitness="WOWNative")
   keyNameVolatile = regDef.RegistryKeyName(registryPath=keyPathVolatile, wowBitness="WOWNative")
   keyNameNonVolatile = regDef.RegistryKeyName(registryPath=keyPathNonVolatile, wowBitness="WOWNative")
   keyNameNonVolatileBadChild = regDef.RegistryKeyName(registryPath=keyPathNonVolatileBadChild, wowBitness="WOWNative")
   keyNameNonVolatileGoodChild = regDef.RegistryKeyName(registryPath=keyPathNonVolatileGoodChild, wowBitness="WOWNative")

   try:
      Log("Creating Volatile Key %s" % keyPathVolatile)
      result = regMgr.CreateRegistryKeyInGuest(virtualMachine, guestAuth, keyNameVolatile, True)
   except Vim.Fault.GuestRegistryKeyAlreadyExists as e:
      Log("Testcase passed. Expected GuestRegistryKeyAlreadyExists fault is thrown.")

   try:
      Log("Creating NonVolatile Key %s" % keyPathNonVolatile)
      result = regMgr.CreateRegistryKeyInGuest(virtualMachine, guestAuth, keyNameNonVolatile, False)
   except Vim.Fault.GuestRegistryKeyAlreadyExists as e:
      Log("Testcase passed. Expected GuestRegistryKeyAlreadyExists fault is thrown.")

   try:
      Log("Creating NonVolatile Bad Subkey %s" % keyPathNonVolatileBadChild)
      result = regMgr.CreateRegistryKeyInGuest(virtualMachine, guestAuth, keyNameNonVolatileBadChild, False)
   except Vim.Fault.GuestRegistryKeyParentVolatile as e:
      Log("Testcase passed. Expected GuestRegistryKeyParentVolatile fault is thrown.")

   try:
      Log("Creating NonVolatile Good Subkey %s" % keyPathNonVolatileGoodChild)
      result = regMgr.CreateRegistryKeyInGuest(virtualMachine, guestAuth, keyNameNonVolatileGoodChild, False)
   except Vim.Fault.GuestRegistryKeyAlreadyExists as e:
      Log("Testcase passed. Expected GuestRegistryKeyAlreadyExists fault is thrown.")

   try:
      Log("CreateRegistryKeyInGuest-Volatile - Verify Pre-Restart")
      result = regMgr.ListRegistryKeysInGuest(virtualMachine, guestAuth, keyNameBase, False)
      numResults = len(result)
      Log("Found %s results" % numResults)
      foundVolatile = False
      foundNonVolatile = False
      for keys in result:
         if keys.key.keyName.registryPath == keyPathVolatile:
            Log("Found Volatile key %s" % keyPathVolatile)
            foundVolatile = True
         if keys.key.keyName.registryPath == keyPathNonVolatile:
            Log("Found NonVolatile key %s" % keyPathNonVolatile)
            foundNonVolatile = True
      if not foundVolatile:
         Log("Verification failed. Did not find newly created Volatile key %s" % keyPathVolatile)
         raise AssertionError("Verification failed. Did not find newly created Volatile key %s" % keyPathVolatile)
      if not foundNonVolatile:
         Log("Verification failed. Did not find newly created NonVolatile key %s" % keyPathNonVolatile)
         raise AssertionError("Verification failed. Did not find newly created NonVolatile key %s" % keyPathNonVolatile)
   except Exception:
      raise

   # Re-start the VM and wait for tools to start
   powerOffVM(virtualMachine)
   powerOnVM(virtualMachine)
   waitForTools(virtualMachine)

   try:
      Log("CreateRegistryKeyInGuest-Volatile - Verify Post-Restart")
      result = regMgr.ListRegistryKeysInGuest(virtualMachine, guestAuth, keyNameBase, False)
      numResults = len(result)
      Log("Found %s results" % numResults)
      foundVolatile = False
      foundNonVolatile = False
      for keys in result:
         if keys.key.keyName.registryPath == keyPathVolatile:
            Log("Found Volatile key %s" % keyPathVolatile)
            foundVolatile = True
         if keys.key.keyName.registryPath == keyPathNonVolatile:
            Log("Found NonVolatile key %s" % keyPathNonVolatile)
            foundNonVolatile = True
      if foundVolatile:
         Log("Verification failed. Found previously created Volatile key %s" % keyPathVolatile)
         raise AssertionError("Verification failed. Found previously created Volatile key %s" % keyPathVolatile)
      if not foundNonVolatile:
         Log("Auto Verification failed. Did not find previously created NonVolatile key %s" % keyPathNonVolatile)
         Log("Please check the VM manually.")
   except Exception:
      raise

   try:
      Log("CreateRegistryKeyInGuest-Volatile - Cleanup")
      result = regMgr.DeleteRegistryKeyInGuest(virtualMachine, guestAuth, keyNameNonVolatile, True)
   except Exception:
      Log("Failed to find and delete non-volatile key %s" % keyPathNonVolatile)
   else:
      Log("Cleanup passed.")


def main():
   # Process command line
   options = get_options()

   global svcInst
   global virtualMachine
   global guestAdminAuth
   global guestAuth
   global guestAuthBad
   [svcInst, virtualMachine, guestAdminAuth,
    guestAuth, guestAuthBad] = init(options.host, options.user, options.password,
                                    options.vmname, options.vmxpath, options.guestuser,
                                    options.guestpassword, options.guestrootuser,
                                    options.guestrootpassword)

   # get the processManager object
   global procMgr
   procMgr = svcInst.content.guestOperationsManager.processManager

   # get the registryManager object
   global regMgr
   regMgr = svcInst.content.guestOperationsManager.guestWindowsRegistryManager
   global regDef
   regDef = Vim.Vm.Guest.WindowsRegistryManager

   testNotReady(procMgr, virtualMachine, guestAuth)
   waitForTools(virtualMachine)

   testSetup()

   testListKeys()
   testListValues()
   testCreateKey()
   testSetValue()
   testDeleteValue()
   testDeleteKey()

   # IMPORTANT: This test powers the VM on and off
   # Since the setup will be gone, keep this at end.
   testCreateKeyVolatile()

# Start program
if __name__ == "__main__":
   main()
   Log("winRegMgr tests completed")
