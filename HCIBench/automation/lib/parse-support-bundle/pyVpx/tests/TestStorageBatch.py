from __future__ import print_function

import sys
import time
import copy
from pyVmomi import Vim, VmomiSupport, Vmodl
from pyVmomi.VmomiSupport import newestVersions
from pyVim import host, connect
from pyVim.connect import Connect, Disconnect
from pyVim import arguments
from pyVim.task import WaitForTask
import os, time
import random
import atexit

storageSystem = None
datastoreSystem = None

totalLuns = 120
totalVmfs = 120
totalNas = 120

def GetLuns():
   # filter non-disk and local disk
   disks = [disk for disk in storageSystem.storageDeviceInfo.scsiLun
           if disk.deviceType == "disk" and not disk.canonicalName.startswith("mpx")]
   # filter disks used by vmfs volume
   vmfs = GetVmfsVolume()
   for mnt in vmfs:
      fullName = "/vmfs/devices/disks/" + mnt.volume.extent[0].diskName
      diskNames = [disk.deviceName for disk in disks]
      try:
         disks.pop(diskNames.index(fullName))
      except ValueError:
         continue;
   return disks

def ModifyLuns(luns, enable):
   #print("modify lun state to " + str(enable))
   #print("Luns " + str([lun.uuid for lun in luns]))
   bt = time.time()
   lunUuid = [lun.uuid for lun in luns]
   if enable:
      task = storageSystem.AttachScsiLunEx(lunUuid)
   else:
      task = storageSystem.DetachScsiLunEx(lunUuid)
   WaitForTask(task)
   #print("ModifyLuns results " + str(task.info.result))
   op = ("disable", "enable")
   print(op[enable] + " " + str(len(luns)) + " luns in " + str(time.time() - bt) + " sec")
   return task.info.result

def VerifyLuns(rlts, state, fault=False):
   if len(rlts) == 0:
      raise Exception("Nothing to verify")
   # state is "ok" "off"
   luns = GetLuns()
   for rlt in rlts:
      for lun in luns:
         if lun.uuid == rlt.key:
            if lun.operationalState[0] != state:
               raise Exception("VerifyLuns.MismatchState lun=" + rlt.key
                               + ", hasState=" + lun.operationalState[0]
                               + ", expectState=" + state)
            if fault and not rlt.fault:
               raise Exception("VerifyLuns.ExceptFault lun=" + rlt.key)
            if not fault and rlt.fault:
               raise Exception("VerifyLuns.ExceptNoFault lun=" + rlt.key)
            break
      else:
         raise Exception("VerifyLuns.NotFound lun=" + rlt.key)

def GetNasDatastore(otherType=False):
   return [ds for ds in datastoreSystem.datastore
           if isinstance(ds.info, Vim.Host.NasDatastoreInfo) != otherType]

def GetVmfsVolume():
   return [mnt for mnt in storageSystem.fileSystemVolumeInfo.mountInfo
           if isinstance(mnt.volume, Vim.Host.VmfsVolume)]
           #and mnt.volume.local == False]

def VerifyVmfs(rlts, mounted, fault=False):
   if len(rlts) == 0:
      raise Exception("Nothing to verify")
   vmfs = GetVmfsVolume()
   for rlt in rlts:
      for mnt in vmfs:
         if mnt.volume.uuid == rlt.key:
            if fault and not rlt.fault:
               raise Exception("VerifyVmfs.ExceptFault vmfs=" + rlt.key)
            if not fault and rlt.fault:
               raise Exception("VerifyVmfs.ExceptNoFault vmfs=" + rlt.key + str(rlt.fault))
            if mnt.mountInfo.mounted != mounted:
               raise Exception("VerifyVmfs.MismatchMounteState vmfs=" + rlt.key
                         + ", hasState=" + str(mnt.mountInfo.mounted)
                         + ", expectState=", str(mounted))
            break
      else:
         raise Exception("verifyVmfs.NotFound vmfs=" + rlt.key)

def ModifyVmfs(vmfs, mount):
   if mount:
      bt = time.time()
      task = storageSystem.MountVmfsVolumeEx([mnt.volume.uuid for mnt in vmfs])
      WaitForTask(task)
      print("Mount" + " " + str(len(vmfs)) + " volumes in " + str(time.time() - bt) + " sec")
      return task.info.result
   else:
      bt = time.time()
      task = storageSystem.UnmountVmfsVolumeEx([mnt.volume.uuid for mnt in vmfs])
      WaitForTask(task)
      print("Unmount" + " " + str(len(vmfs)) + " volumes in " + str(time.time() - bt) + " sec")
      return task.info.result

def VerifyNasDatastore(rlts, present, fault=False, spec=False):
   nas = GetNasDatastore()
   for rlt in rlts:
      if spec:
         name = rlt.localPath
         found = rlt.localPath in [ds.name for ds in nas]
      else:
         name = str(rlt.key)
         found = rlt.key in nas
         if not fault and rlt.fault:
            raise Exception("VerifyNasDatastore.ExceptNoFault datastore="
                            + name)
      if present != found:
         raise Exception("VerifyNasDatastore.Mismatch state datastore="
                         + name)
def GetNasSpec(nasDs):
   nasSpec = []
   for ds in nasDs:
      spec = Vim.Host.NasVolume.Specification()
      spec.remoteHost = ds.info.nas.remoteHost
      spec.remotePath = ds.info.nas.remotePath
      spec.localPath = ds.info.name
      spec.accessMode = "readWrite"
      nasSpec.append(spec)
   return nasSpec

def ModifyNasDatastore(nasDs, add):
   if not add:
      bt = time.time()
      task = datastoreSystem.RemoveDatastoreEx(nasDs)
      WaitForTask(task)
      print("remove " + str(len(nasDs)) + " NAS datastores in " + str(time.time() - bt) + " sec")
      return task.info.result
   else:
      for spec in nasDs:
         datastoreSystem.CreateNasDatastore(spec)
      return None

def LunVerify():
   luns = GetLuns()
   if len(luns) < totalLuns:
      raise Exception("LunVerify: No luns detected")
   ModifyLuns(luns, True)

def LunSimpleTest():
   luns = GetLuns()
   rlts = ModifyLuns(luns[0:totalLuns], False)
   VerifyLuns(rlts, "off")
   print("SimpleTest.DetachLun: passed")
   rlts = ModifyLuns(luns[0:totalLuns], True)
   VerifyLuns(rlts, "ok")
   print("SimpleTest.AttachLun: passed")

def LunNegativeTest():
   '''
   test with duplicated id.
   Expected behavor: first operation the device succeeds,
   all subsequent operations on same device fails
   '''
   luns = GetLuns()
   badLuns = [luns[0], luns[0], luns[0]]
   ModifyLuns(badLuns[0:1], True)
   rlts = ModifyLuns(badLuns, False)
   VerifyLuns(rlts[0:1], "off")
   VerifyLuns(rlts[1:], "off", True)
   ModifyLuns(badLuns[0:1], True)
   print("NegativeTest.DupLun: passed")
   '''
   test with empty luns
   '''
   try:
      ModifyLuns(luns[0:0], True)
      raise Exception("Lun operation must has at least one lun")
   except TypeError:
      print("NegativeTest.NoArgLun: passed")

def VmfsVerify():
   vmfs = GetVmfsVolume()
   if len(vmfs) < totalVmfs:
      print("tottalVmfs=%s" % totalVmfs)
      print("Found vmfs=%s" % len(vmfs))
      raise Exception("VmfsVerify: No vmfs detected")
   mountVmfs = [mnt for mnt in vmfs if mnt.mountInfo.mounted == False]
   if len(mountVmfs) > 0:
      ModifyVmfs(mountVmfs, True)

def VmfsSimpleTest():
   vmfs = GetVmfsVolume()
   rlts = ModifyVmfs(vmfs[0:totalVmfs], False)
   VerifyVmfs(rlts, False)
   print("SimpleTest.UnmountVmfs: passed")
   rlts = ModifyVmfs(vmfs[0:totalVmfs], True)
   VerifyVmfs(rlts, True)
   print("SimpleTest.mountVmfs: passed")


def VmfsNegativeTest():
   '''
   test with duplicated id.
   Expected behavor: first operation the device succeeds,
   all subsequent operations on same device fails
   '''
   vmfs = GetVmfsVolume()
   badVmfs = [vmfs[0], vmfs[0], vmfs[0]]
   rlts = ModifyVmfs(badVmfs, False)
   VerifyVmfs(rlts[0:1], False, False)
   VerifyVmfs(rlts[1:], False, True)
   ModifyVmfs(badVmfs[0:1], True)
   print("NegativeTest.DupVmfs: passed")
   '''
   test with empty luns
   '''
   try:
      ModifyVmfs(vmfs[0:0], False)
      raise Exception("Vmfs operation must has at least one lun")
   except TypeError:
      print("NegativeTest.NoArgVmfs: passed")

def NasVerify():
   if len(GetNasDatastore()) < totalNas:
      raise Exception("NASVerify: No NAS detected")

def NasSimpleTest():
   nas = GetNasDatastore()[0:totalNas]
   nasSpec = GetNasSpec(nas)
   rlts = ModifyNasDatastore(nas, False)
   VerifyNasDatastore(rlts, False)
   print("SimpleTest.RemoveNasDatastore: passed")
   ModifyNasDatastore(nasSpec, True)
   VerifyNasDatastore(nasSpec, True, spec=True)
   print("SimpleTest.CreateNasDatastore: passed")

def NasNegativeTest():
   nas = GetNasDatastore()
   badNas = [nas[0], nas[0], nas[0]]
   badSpec = GetNasSpec(badNas)
   rlts = ModifyNasDatastore(badNas, False)
   VerifyNasDatastore(rlts[0:1], False)
   VerifyNasDatastore(rlts[1:], False, True)
   ModifyNasDatastore(badSpec[0:1], True)
   VerifyNasDatastore(badSpec[0:1], True, spec=True)
   print("NegativeTest.DupNas: passed")

   try:
      ModifyNasDatastore(nas[0:0], False)
      raise Exception("Nas operation must has at least one datastore")
   except TypeError:
      print("NegativeTest.NoArgNas: passed")

   nonNas = GetNasDatastore(True)
   try:
      ModifyNasDatastore(nonNas[0:1], False)
      raise Exception("Nas operation does not support other type of datastore")
   except Vmodl.MethodFault:
      print("NegativeTest.OtherDstype: passed")


def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                    (["u:", "user="], "root", "User name", "user"),
                    (["p:", "pwd="], "", "password", "pwd"),
                    (("t:", "test="), "lun", "test lun, vmfs, or nas", "test")
                    ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage") ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   si = Connect(host=args.GetKeyValue("host"),
                user=args.GetKeyValue("user"),
                pwd=args.GetKeyValue("pwd"),
                version=newestVersions.GetName('vim'))

   atexit.register(Disconnect, si)
   global datastoreSystem
   datastoreSystem = host.GetHostConfigManager(si).GetDatastoreSystem()
   global storageSystem
   storageSystem = host.GetHostConfigManager(si).GetStorageSystem()
   test = args.GetKeyValue("test")
   if test == "lun":
      LunVerify()
      LunSimpleTest()
      LunNegativeTest()
   elif test == "vmfs":
      VmfsVerify()
      VmfsSimpleTest()
      VmfsNegativeTest()
   elif test == "nas":
      NasVerify()
      NasSimpleTest()
      NasNegativeTest()
   else:
      raise Exception("Unsupported test = " + test)

if __name__ == "__main__":
   main()
