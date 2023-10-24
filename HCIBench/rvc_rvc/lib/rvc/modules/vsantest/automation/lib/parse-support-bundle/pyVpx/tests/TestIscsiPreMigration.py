#!/usr/bin/python
#
# TestIscsiBindings.py -
#
#   Validates iSCSI binding and migration API additions
#
from __future__ import print_function

import sys
from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
from optparse import OptionParser
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm, host
from pyVim import invt
from pyVim import vmconfig
from pyVim import vimutil
from pyVim import arguments
from pyVim.helpers import StopWatch
import time
import atexit
import operator


GLOBAL_STATUS = True
ABORT_ON_FAIL = True

class iScsiAdapter :

   def __init__ (self, si, vmhba):
      """Constructor"""
      self.si        = si;
      self.vmhba     = vmhba;

   def getName(self):
      return self.vmhba;

   def iscsiManager(self) :
      return host.GetHostSystem(self.si).GetConfigManager().iscsiManager;

   def storageSystem(self) :
      return host.GetHostSystem(self.si).GetConfigManager().storageSystem;

   def getAdapter(self) :
      storageSystem = self.storageSystem();
      deviceInfo = storageSystem.storageDeviceInfo
      adapters = deviceInfo.hostBusAdapter;

      for adapter in adapters:
         if adapter.device == self.vmhba:
            return adapter

      msg = self.vmhba + " not found";
      print("WARNING: " + msg)
      raise Exception(msg)


   def addStaticTarget(self, address, port, iqn):
      target = Vim.Host.InternetScsiHba.StaticTarget(
            address=address,
            port=port,
            iScsiName=iqn
            )
      targets = []
      targets.append(target)
      return self.addStaticTargets(targets);

   def addStaticTargets(self, targets):
      try :
         self.storageSystem().AddInternetScsiStaticTargets(self.vmhba, targets)
      except Exception as e:
         return False;

      return True;

   def removeStaticTarget(self, address, port, iqn):
      target = Vim.Host.InternetScsiHba.StaticTarget(
                  address=address,
                  port=port,
                  iScsiName=iqn
                  )

      targets = []
      targets.append(target)

      return self.removeStaticTargets(targets);

   def removeStaticTargets(self, targets):
      try :
         self.storageSystem().RemoveInternetScsiStaticTargets(self.vmhba, targets)
      except Exception as e:
         print("WARNING: removeStaticTargets:: %s" % e)
         return False;

      return True;

   def helperRemoveAllStaticTargets(self):
      adapter = self.getAdapter();

      targets = adapter.configuredStaticTarget;
      if len(targets) > 0:
         return self.removeStaticTargets(targets);

      return True;

   def rescan(self):
      try :
         self.storageSystem().RescanHba(self.vmhba);
      except Exception as e:
         print("WARNING: rescan %s" % e)
         return False;
      return True;

   def addVnic(self, vnic):
      #return self.iscsiManager().AddVnic(self.vmhba, vnic)
      return self.iscsiManager().BindVnic(self.vmhba, vnic)

   def removeVnic(self, vnic, force):
      #return self.iscsiManager().RemoveVnic(self.vmhba, vnic, force)
      return self.iscsiManager().UnbindVnic(self.vmhba, vnic, force)

   def removeAllVnics(self):
      nics = self.queryBoundVnics()
      for nic in nics:
         self.removeVnic(nic.vnicDevice, True);

   def queryBoundVnics(self) :
      return  self.iscsiManager().QueryBoundVnics(self.vmhba)


##############################################################
#
#
#
def UTIL_HasFault(status, fault ):
   for reason in status.reason:
      if reason.faultMessage[0].key == fault:
         return True
   return False

###################################################################################
#
def TEST_CheckDependency(si, nicList, allowed, reason, depExpected) :
   failReason = "";
   flat = ""
   for nic in nicList:
      if flat == "" :
         flat = nic;
      else:
         flat = flat + "," + nic;

   print("  TESTCASE: CheckDependancy(%s)" % flat)

   iscsiManager = host.GetHostSystem(si).GetConfigManager().iscsiManager;

   depActual = [];

   failed = False
   try :
      checkInfo = iscsiManager.QueryMigrationDependencies(nicList);
      if checkInfo.migrationAllowed != allowed:
         if allowed:
            failReason="Expected MigrationAllowed=True,  Actual=False";
         else:
            failReason="Expected MigrationAllowed=False, Actual=True";
         failed = True;

      #if checkInfo.migrationAllowed == False:
      #   if checkInfo.disallowReason != reason:
      #      print("reason %s" % checkInfo.disallowReason)
      #      failed = True

      for dep in checkInfo.dependency:
         actual = dep.vmhbaName + "," + dep.pnicDevice + "," + dep.vnicDevice
         depActual.append(actual);

      #
      # Check to see our lists match
      #
      for actual in depActual[:]:
         for expected in depExpected[:]:
            if expected == actual:
               depActual.remove(actual)
               depExpected.remove(expected)

      if len(depActual) != 0:
         print("Actual: " + str(len(depActual)))
         failed = True;

      if len(depExpected) != 0:
         print("Expected: " + str(len(depExpected)))
         for dep in depExpected:
            print("DEP: %s" % dep)

         failed = True;


   except Exception as e:
      failReason = "EXCEPTION:" + e
      failed = True;

   if failed:
      GLOBAL_STATUS = False;
      print("    --- FAIL --- (%s)" % failReason)
      if ABORT_ON_FAIL:
         exit(0);
      return False
   else:
      print("    --- PASS ---")
      return True





def TEST_CheckBoundNicStatus(si, iscsi, status):
   failReason = "";
   print("  TESTCASE: TestCheckBoundNicStatus (vmhba="+ iscsi.getName() + " expected=" + status + ")")
   failed = False;

   iscsiManager = iscsi.iscsiManager();


   """ POSITIVE TEST 1 - Get validate vmhba's bound vmknic """
   try:
      vmknics = iscsiManager.QueryBoundVnics(iscsi.getName())
      for vmknic in vmknics:
         if vmknic.pathStatus != status:
            print("   ", iscsi.getName(), "->", vmknic.vnicDevice, "S:", vmknic.pathStatus)
            failed = True;
   except Exception as e:
      failReason = "EXCEPTION: " +  e
      failed = True;

   if failed:
      print("    --- FAIL --- (%s)" % failReason)
      GLOBAL_STATUS = False;
      if ABORT_ON_FAIL:
         exit(0);
      return False
   else:
      print("    --- PASS ---")
      return True

def TEST_PnicStatus(si, pnic, expected):
   failReason = "";
   print("  TESTCASE: TestPnicStatus (pnic="+ pnic + " expected=" + expected + ")")
   failed = False;

   mgr = host.GetHostSystem(si).GetConfigManager().iscsiManager;

   try:
      status = mgr.QueryPnicStatus(pnic)

      if expected != "":
         if UTIL_HasFault(status, expected) != True:
            failReason = "expected",expected,"NOT FOUND in fault list",
            failed = True;
      else:
         if status.reason :
            failReason = "expected success, got failure=", status.reason.faultMessage[0].key
            failed = True;

   except Exception as e :
      failReason = "EXCEPTION: " +  e
      failed = True;


   if failed:
      print("    --- FAIL --- (%s)" % failReason)
      GLOBAL_STATUS = False;
      if ABORT_ON_FAIL:
         exit(0);
      return False
   else:
      print("    --- PASS ---")
      return True

#
# Basic verification of getting bound vmknics for a vmhba
#   - Test: GetBoundVmknics with valid vmhba
#   - Test: GetBoundVmknics with invalid vmhba
#
def TestCheckBoundNicStatusUnused(si, iscsi):
    TEST_CheckBoundNicStatus(si, iscsi, "NotUsed");



def TEST_ClearConfig(iscsiList):
   for iscsi in iscsiList:
      iscsi.helperRemoveAllStaticTargets();
      iscsi.rescan();

   for iscsi in iscsiList:
      iscsi.rescan();
      iscsi.removeAllVnics();



def TEST_CheckPnicDependency(si, pnicList, allowed, depList, faultList):
   failed = False;
   mgr = host.GetHostSystem(si).GetConfigManager().iscsiManager;

   try :
      dep = mgr.QueryMigrationDependencies(pnicList);
   except Exception as e:
      print("    EXCEPTION: %s" % e)
      failed = True;

   #### DEBUG PRINT START #####
   if dep.migrationAllowed :
      print("Allowed: TRUE")
   else :
      print("Allowed: FALSE")

   for entity in dep.dependency:
      print("ENTIY: %s %s %s"
            % (entity.pnicName, entity.vmhbaName, entity.vnicName))

   #for fault in dep.disallowReason.reason:
   #      print("FAULT:", end='')


   #### DEBUG PRINT END #####

   if dep.migrationAllowed != allowed:
      print("Expected: %s, Actual: %s"
            % (str(allowed), str(dep.migrationAllowed)))
      failed = True;


   if failed:
      print("    --- FAIL ---")
      return False
   else:
      print("    --- PASS ---")
      return True



def VALIDATE_PathStatus(config, si, iscsiList):
   LUNZ = False;
   exec open(config).read()

   TEST_ClearConfig(iscsiList);

   ## Prep our hbas
   bcm1    = iscsiList[0];
   bcm2    = iscsiList[1];
   swiscsi = iscsiList[2];

   if OPT_QLA_VMHBA != "" :
      qla = iScsiAdapter(si, OPT_QLA_VMHBA);
      qla.getAdapter();
      iscsiList.append(qla);
      TEST_ClearConfig(iscsiList);
      iscsiList.remove(qla);

   # Test Config #1:
   #  No active sessions, all vmknics bound properly
   #   * Migration should be allowed
   #   * pnic interdependancy should bee seen
   #   * Bound Nic status should be unused
   print("CONFIG: No Active Sessionn (BCM1,BCM2,SWISCSI)")
   TEST_PnicStatus(si, OPT_BCM_PNIC_1, "");
   TEST_PnicStatus(si, OPT_BCM_PNIC_2, "");

   bcm1.addVnic(OPT_BCM_VNIC_1);
   bcm2.addVnic(OPT_BCM_VNIC_2);

   TEST_CheckBoundNicStatus(si, bcm1, "notUsed");
   TEST_CheckBoundNicStatus(si, bcm2, "notUsed");
   TEST_CheckBoundNicStatus(si, swiscsi, "notUsed");
   TEST_PnicStatus(si, OPT_BCM_PNIC_1, "com.vmware.vim.iscsi.error.pnicInUse");
   TEST_PnicStatus(si, OPT_BCM_PNIC_2, "com.vmware.vim.iscsi.error.pnicInUse");
   TEST_PnicStatus(si, OPT_UNUSED_PNIC, "");

   nicList = [OPT_UNUSED_PNIC]
   depList = []
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_INVALID_PNIC]
   depList = []
   TEST_CheckDependency(si, nicList , True, "Unset", depList);


   nicList = [OPT_BCM_PNIC_1]
   depList = [OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_BCM_PNIC_2]
   depList = [OPT_BCM_VMHBA_2 + ","+OPT_BCM_PNIC_2+","+OPT_BCM_VNIC_2];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   swiscsi.addVnic(OPT_BCM_VNIC_1);
   nicList = [OPT_BCM_PNIC_1]
   depList = [OPT_SW_VMHBA +","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1,
               OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   swiscsi.addVnic(OPT_BCM_VNIC_2);
   nicList = [OPT_BCM_PNIC_1,OPT_BCM_PNIC_2]
   depList = [OPT_SW_VMHBA +","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1,
               OPT_SW_VMHBA +","+OPT_BCM_PNIC_2+","+OPT_BCM_VNIC_2,
               OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1,
               OPT_BCM_VMHBA_2 + ","+OPT_BCM_PNIC_2+","+OPT_BCM_VNIC_2];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_BCM_PNIC_1]
   depList = [OPT_SW_VMHBA +","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1,
               OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   TEST_CheckBoundNicStatus(si, bcm1, "notUsed");
   TEST_CheckBoundNicStatus(si, bcm2, "notUsed");

   ##################################################################
   # Test Config #2:
   #  * Active Sessions on bcm port #1
   #  * Migration of bcm_nic_1 should NOT be allowed
   #
   print("CONFIG: Active Session (BCM1), No Sessions (BCM2,SW)")
   TEST_ClearConfig(iscsiList);
   bcm1.addVnic(OPT_BCM_VNIC_1);
   bcm2.addVnic(OPT_BCM_VNIC_2);


   bcm1.addStaticTarget(OPT_ACTIVE_TARGET_IP, 3260, OPT_ACTIVE_TARGET_IQN);
   bcm1.rescan();
   TEST_CheckBoundNicStatus(si, bcm1, "lastActive");
   TEST_CheckBoundNicStatus(si, bcm2, "notUsed");

   nicList = [OPT_UNUSED_PNIC]
   depList = []
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_INVALID_PNIC]
   depList = []
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   ###
   # Migration of BCM_PNIC_1 should not be allowed.. active sessions
   #
   nicList = [OPT_BCM_PNIC_1]
   depList = [OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1];
   TEST_CheckDependency(si, nicList , False, "Unset", depList);

   ###
   # Migration of BCM_PNIC_1 should not be allowed.. active sessions
   #
   nicList = [OPT_BCM_PNIC_1,OPT_BCM_PNIC_2]
   depList = [OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1 ,
             OPT_BCM_VMHBA_2 + ","+OPT_BCM_PNIC_2+","+OPT_BCM_VNIC_2];
   TEST_CheckDependency(si, nicList , False, "Unset", depList);


   ###
   # Migration of BCM_PNIC_2 SHOULD be allowed.. active sessions on PNIC_1
   #
   nicList = [OPT_BCM_PNIC_2]
   depList = [OPT_BCM_VMHBA_2 + ","+OPT_BCM_PNIC_2+","+OPT_BCM_VNIC_2];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);


   ##################################################################
   # Test Config #3  ( Add paths on BCM2)
   #  Entry Expectaion: Previous test case configured BCM1..
   #
   #  Result:
   #    * Active Sessions on bcm port 1 & 2
   #    * No migrations allowed
   #
   print("CONFIG: Active Session (BCM1,BCM2), No Sessions/No Bindings (SW)")
   bcm2.addStaticTarget(OPT_ACTIVE_TARGET_IP, 3260, OPT_ACTIVE_TARGET_IQN);
   bcm2.rescan();
   TEST_CheckBoundNicStatus(si, bcm1, "active");
   TEST_CheckBoundNicStatus(si, bcm2, "active");

   nicList = [OPT_UNUSED_PNIC]
   depList = []
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_INVALID_PNIC]
   depList = []
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_BCM_PNIC_1]
   depList = [OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_BCM_PNIC_2]
   depList = [OPT_BCM_VMHBA_2 + ","+OPT_BCM_PNIC_2+","+OPT_BCM_VNIC_2];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_BCM_PNIC_1,OPT_BCM_PNIC_2]
   depList = [OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1 ,
              OPT_BCM_VMHBA_2 + ","+OPT_BCM_PNIC_2+","+OPT_BCM_VNIC_2];
   TEST_CheckDependency(si, nicList , False, "Unset", depList);


   ##################################################################
   # Test Config #4
   #   Dead Path on BCM2
   #print("CONFIG: Active Session (BCM1,BCM2), No Sessions/No Bindings (SW)")
   print("CONFIG: Active Session (BCM1), Dead Path (BCM2), No Sessions/No Bindings (SW)")
   bcm2.removeStaticTarget(OPT_ACTIVE_TARGET_IP, 3260, OPT_ACTIVE_TARGET_IQN);
   time.sleep(5);
   TEST_CheckBoundNicStatus(si, bcm1, "lastActive")

   nicList = [OPT_UNUSED_PNIC]
   depList = []
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_INVALID_PNIC]
   depList = []
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_BCM_PNIC_1]
   depList = [OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1];
   TEST_CheckDependency(si, nicList , False, "Unset", depList);

   nicList = [OPT_BCM_PNIC_2]
   depList = [OPT_BCM_VMHBA_2 + ","+OPT_BCM_PNIC_2+","+OPT_BCM_VNIC_2];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_BCM_PNIC_1,OPT_BCM_PNIC_2]
   depList = [OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1 ,
              OPT_BCM_VMHBA_2 + ","+OPT_BCM_PNIC_2+","+OPT_BCM_VNIC_2];
   TEST_CheckDependency(si, nicList , False, "Unset", depList);

   ##TEST_CheckBoundNicStatus(si, bcm2, "lastActive")

   ##################################################################
   # Test Config #5:
   #   Standby Sessions on bcm port 1
   #   Active Sessions on bcm port 2
   print("CONFIG: Standby Path (BCM1), Active Path (BCM2), No Sessions/No Bindings (SW)")
   TEST_ClearConfig(iscsiList);
   bcm1.addVnic(OPT_BCM_VNIC_1);
   bcm2.addVnic(OPT_BCM_VNIC_2);

   bcm2.addStaticTarget(OPT_ACTIVE_TARGET_IP, 3260, OPT_ACTIVE_TARGET_IQN);
   bcm1.addStaticTarget(OPT_STANDBY_TARGET_IP, 3260, OPT_STANDBY_TARGET_IQN);
   bcm2.rescan();
   time.sleep(5);
   bcm1.rescan();
   time.sleep(5);

   TEST_CheckBoundNicStatus(si, bcm1, "standBy")
   TEST_CheckBoundNicStatus(si, bcm2, "active");


   nicList = [OPT_UNUSED_PNIC]
   depList = []
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_INVALID_PNIC]
   depList = []
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_BCM_PNIC_1]
   depList = [OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_BCM_PNIC_2]
   depList = [OPT_BCM_VMHBA_2 + ","+OPT_BCM_PNIC_2+","+OPT_BCM_VNIC_2];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_BCM_PNIC_1,OPT_BCM_PNIC_2]
   depList = [OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1 ,
              OPT_BCM_VMHBA_2 + ","+OPT_BCM_PNIC_2+","+OPT_BCM_VNIC_2];
   TEST_CheckDependency(si, nicList , False, "Unset", depList);

   ## Workaround: remove standby first
   bcm1.removeStaticTarget(OPT_STANDBY_TARGET_IP, 3260, OPT_STANDBY_TARGET_IQN);
   bcm1.rescan();
   TEST_ClearConfig(iscsiList);

   ##################################################################
   # Test Config #6:
   #   Active Sessions on bcm port 1
   #   Standby Sessions on bcm port 2
   print("CONFIG: Active Path (BCM1), Standby Path (BCM2), No Sessions/No Bindings (SW)")
   TEST_ClearConfig(iscsiList);
   bcm1.addVnic(OPT_BCM_VNIC_1);
   bcm2.addVnic(OPT_BCM_VNIC_2);

   bcm1.addStaticTarget(OPT_ACTIVE_TARGET_IP, 3260, OPT_ACTIVE_TARGET_IQN);
   bcm2.addStaticTarget(OPT_STANDBY_TARGET_IP, 3260, OPT_STANDBY_TARGET_IQN);
   bcm1.rescan();
   bcm2.rescan();
   TEST_CheckBoundNicStatus(si, bcm1, "active")
   TEST_CheckBoundNicStatus(si, bcm2, "standBy")

   ## Workaround: remove standby first
   bcm2.removeStaticTarget(OPT_STANDBY_TARGET_IP, 3260, OPT_STANDBY_TARGET_IQN);
   bcm2.rescan();
   TEST_ClearConfig(iscsiList);

   ##################################################################
   # Test Config #7:
   #  Check partial binding mesh:
   #
   print("CONFIG: No Paths SW=BMC2")
   bcm1.addVnic(OPT_BCM_VNIC_1);
   bcm2.addVnic(OPT_BCM_VNIC_2);
   swiscsi.addVnic(OPT_BCM_VNIC_2);

   nicList = [OPT_BCM_PNIC_1]
   depList = [OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1 ];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   nicList = [OPT_BCM_PNIC_2]
   depList = [OPT_BCM_VMHBA_2 + ","+OPT_BCM_PNIC_2 + "," +OPT_BCM_VNIC_2,
              OPT_SW_VMHBA    + ","+OPT_BCM_PNIC_2 + "," +OPT_BCM_VNIC_2 ];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);


   nicList = [OPT_BCM_PNIC_1,OPT_BCM_PNIC_2]
   depList = [OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1+","+OPT_BCM_VNIC_1 ,
              OPT_BCM_VMHBA_2 + ","+OPT_BCM_PNIC_2+","+OPT_BCM_VNIC_2,
              OPT_SW_VMHBA + ","+OPT_BCM_PNIC_2+","+OPT_BCM_VNIC_2];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);
   TEST_ClearConfig(iscsiList);
   ##################################################################
   # Test Config #7:
   #  Check full binding mesh
   #
   print("CONFIG: No Paths SW=BMC2, SW=BCM1")
   bcm1.addVnic(OPT_BCM_VNIC_1);
   bcm2.addVnic(OPT_BCM_VNIC_2);
   swiscsi.addVnic(OPT_BCM_VNIC_1);
   swiscsi.addVnic(OPT_BCM_VNIC_2);

   nicList = [OPT_BCM_PNIC_1,OPT_BCM_PNIC_2]
   depList = [OPT_BCM_VMHBA_1 + ","+OPT_BCM_PNIC_1 + "," + OPT_BCM_VNIC_1,
              OPT_BCM_VMHBA_2 + ","+OPT_BCM_PNIC_2 + "," + OPT_BCM_VNIC_2,
              OPT_SW_VMHBA    + ","+OPT_BCM_PNIC_1 + "," + OPT_BCM_VNIC_1,
              OPT_SW_VMHBA    + ","+OPT_BCM_PNIC_2 + "," + OPT_BCM_VNIC_2];
   TEST_CheckDependency(si, nicList , True, "Unset", depList);

   #############################
   # Check to see if we have a QLogic card present, if so run it's
   #  tests as well
   if OPT_QLA_VMHBA != "" :
      print(" ------------ ADDENDUM ------------")
      qla = iScsiAdapter(si, OPT_QLA_VMHBA);
      qla.getAdapter();
      iscsiList.append(qla);

      ####
      # Test Config QLA.1
      #
      print("CONFIG: BCM1=Active, QLA=Active")
      TEST_ClearConfig(iscsiList);
      bcm1.addVnic(OPT_BCM_VNIC_1);
      bcm1.addStaticTarget(OPT_ACTIVE_TARGET_IP, 3260, OPT_ACTIVE_TARGET_IQN);
      qla.addStaticTarget(OPT_ACTIVE_TARGET_IP, 3260, OPT_ACTIVE_TARGET_IQN);
      bcm1.rescan();
      qla.rescan();

      TEST_CheckBoundNicStatus(si, bcm1, "active");
      nicList = [OPT_BCM_PNIC_1]
      depList = [OPT_BCM_VMHBA_1 + "," + OPT_BCM_PNIC_1 + "," +OPT_BCM_VNIC_1];
      TEST_CheckDependency(si, nicList , True, "Unset", depList);

      ####
      # Test Config QLA.2
      #
      print("CONFIG: BCM1=Active, QLA=DEAD")
      qla.removeStaticTarget(OPT_ACTIVE_TARGET_IP, 3260, OPT_ACTIVE_TARGET_IQN);
      time.sleep(5)
      TEST_CheckBoundNicStatus(si, bcm1, "lastActive");
      nicList = [OPT_BCM_PNIC_1]
      depList = [OPT_BCM_VMHBA_1 + "," + OPT_BCM_PNIC_1 + "," +OPT_BCM_VNIC_1];
      TEST_CheckDependency(si, nicList , False, "Unset", depList);

      ####
      # Test Config QLA.3
      #
      TEST_ClearConfig(iscsiList);
      print("CONFIG: BCM1=Standby, QLA=Active")
      bcm1.addVnic(OPT_BCM_VNIC_1);
      qla.addStaticTarget(OPT_ACTIVE_TARGET_IP, 3260, OPT_ACTIVE_TARGET_IQN);
      qla.rescan();
      bcm1.addStaticTarget(OPT_STANDBY_TARGET_IP, 3260, OPT_STANDBY_TARGET_IQN);
      bcm1.rescan();

      TEST_CheckBoundNicStatus(si, bcm1, "standBy");
      nicList = [OPT_BCM_PNIC_1]
      depList = [OPT_BCM_VMHBA_1 + "," + OPT_BCM_PNIC_1 + "," + OPT_BCM_VNIC_1];
      TEST_CheckDependency(si, nicList , True, "Unset", depList);

      TEST_ClearConfig(iscsiList);
      iscsiList.remove(qla);
   else :
      print("Skipped QLogic Test cases. QLA=%s" % OPT_QLA_VMHBA)


   ##################################
   # Unbound NIC tests.
   #


   #
   #   ALL DONE HERE.
   #
   ######################################################################
def VALIDATE_BindUnbind(config, si, iscsiList):
   LUNZ = False;
   exec open(config).read()

   TEST_ClearConfig(iscsiList);

   ## Prep our hbas
   bcm1    = iscsiList[0];
   bcm2    = iscsiList[1];
   swiscsi = iscsiList[2];

   if OPT_QLA_VMHBA != "" :
      qla = iScsiAdapter(si, OPT_QLA_VMHBA);
      qla.getAdapter();
      iscsiList.append(qla);
      TEST_ClearConfig(iscsiList);
      iscsiList.remove(qla);

   # Test Config #1:
   #  No active sessions, all vmknics bound properly
   #   * Migration should be allowed
   #   * pnic interdependancy should bee seen
   #   * Bound Nic status should be unused
   print("CONFIG: No Active Sessionn (BCM1,BCM2,SWISCSI)")
   TEST_PnicStatus(si, OPT_BCM_PNIC_1, "");
   TEST_PnicStatus(si, OPT_BCM_PNIC_2, "");

   bcm1.addVnic(OPT_BCM_VNIC_1);
   bcm2.addVnic(OPT_BCM_VNIC_2);

   TEST_ClearConfig(iscsiList);


def VALIDATE_QueryBoundNics(config, si, iscsiList):
   LUNZ = False;
   exec open(config).read()

   TEST_ClearConfig(iscsiList);

   ## Prep our hbas
   bcm1    = iscsiList[0];
   bcm2    = iscsiList[1];
   swiscsi = iscsiList[2];

   bcm1.addVnic(OPT_BCM_VNIC_1);
   bcm2.addVnic(OPT_BCM_VNIC_2);

   loop = 0;
   while loop < 500 :
      for iscsi in iscsiList:
         iscsi.rescan();
         iscsi.queryBoundVnics();
         loop=loop+1;
         print("LOOP: %s" % loop)


def VALIDATE_ValidateLeak(config, si, iscsiList):
   ns = host.GetHostSystem(si).GetConfigManager().networkSystem;

   loop = 0;
   while True:
      hint = ns.QueryNetworkHint();
      loop=loop+1;
      print("LOOP: %s" % loop)

#
# Cleanup
#
def cleanup(si):
   """
   XXX: No cleanup at this time...
   """

#
# Generic get_options handling
#
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
    parser.add_option("-d", "--adapter",
                      help="Storage adapter list ex. vmhba#,vmhba#")

    parser.add_option("-c", "--config",
                      help="Configuration file filled in with Host options")

    (options, _) = parser.parse_args()

    return options

#
# Test does the following.
#   - Basic verification of bound vmknics
#   - Basic verification of candidate vmknics
#   - Binding and unbinding of vmknics
#   - Migration Dependency Checks
#   - Nic Status Checks
#
def main():
   """ Get and validate options """
   options = get_options()

   exec open(options.config).read()
   #execfile(options.config);

   vmhbaList = OPT_VMHBA_LIST;

   if (len(vmhbaList) < 3):
      print("FAIL: Atleast 3 adapters must be specified. (2 broadcom+1 swiscsi")
      return -1

   """ Connect to vmodl """
   si = SmartConnect(host=OPT_ESX_HOST,
                     user=OPT_ESX_USER,
                     pwd=OPT_ESX_PASSWORD)
   atexit.register(Disconnect, si)

   iscsiList = [];
   try:
      for hba in OPT_VMHBA_LIST:
         obj = iScsiAdapter(si, hba);
         # check to see if it's valid
         obj.getAdapter();
         iscsiList.append(obj);
   except Exception as e:
      print("EXCEPTION: %s" % e)
      cleanup(si)
      return -1

   """ Start tests """
   try:
      #loop = 0;
      #while True:
      #   VALIDATE_BindUnbind(options.config, si, iscsiList)
      #   loop=loop+1;
      #   print("LOOP: %s" % loop)
      #VALIDATE_QueryBoundNics(options.config, si, iscsiList);
      #VALIDATE_ValidateLeak(options.config, si, iscsiList);
      VALIDATE_PathStatus(options.config, si, iscsiList)

      print("============================================")
      if GLOBAL_STATUS:
         print("RESULT: PASS")
      else:
         print("RESULT: FAILED")

   except Exception as e:
      cleanup(si)
      print(e)
      return -1

   cleanup(si)
   print("DONE.")
   return 0

# Start program
if __name__ == "__main__":
    sys.exit(main())
