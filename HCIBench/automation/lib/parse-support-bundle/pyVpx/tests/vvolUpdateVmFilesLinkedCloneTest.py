#!/usr/bin/env python

#
# Example -
#    $VMTREE/vim/py/py.sh  $VMTREE/vim/py/tests/vvolUpdateVmFiles.py \
#       -h "10.20.104.153" -u "administrator@vsphere.local" -p 'Admin!23' \
#       -d "coke"
#
# Note that this test makes a linked clone, so the IP needs to be a VC.  This
# should be run from the ESX host, and the VVol datastore should be configured
# in both VC and ESX and accessible.
#
# Note that it is also expected / assumed that there is a VMFS datastore with
# adequate space available and called 'datastore1' to back up the pre-fixup
# files for comparison.
#
# This test simulates a failover of a VM and two linked clones.  Specifically,
# it does the following steps:
#
# - Create vm-xxx (xxx a random number)
# - Snapshot vm-xxx
# - Create two linked clones from the snapshot, vm-lc1-xxx and vm-lc2-xxx
# - Unregister all of the above
# - Repeat to to generate a fresh set of VVols for the failover target.  The
#   new VMs will have the same names, but the config VVols will be vm-xxx_1,
#   vm-lc1-xxx_1 and vm-lc2-xxx_1.
# - Create config VVols called vm-xxx-tgt, vm-lc1-xxx-tgt and vm-lc2-xxx-tgt
#   and copy the descriptor files from the first set to these.  These are the
#   simulated failover targets.
# - Create a failover map containing vm-xxx and vm-lc1-xxx as the source and
#   mapping to the VVolIds from the *_1 (second set), except that the config
#   VVol Id for *_1 is replaced by the -tgt version.
# - Run UpdateVVolVirtualMachineFiles on this set.
#
# Note that for this operation, the -tgt directory is the failover target,
# so only these should be impacted by the descriptor fix-up.  In particular,
# the original source and the _1 version are BOTH exogenous to this call and
# should NOT be modified at all.
#
# - Create a failover map containing vm-xxx and vm-lc2-xxx as the source and
#   mapping to the VVolIds from the *_1 (second set), except that the config
#   VVol Id for *_1 is replaced by the -tgt version.
# - Run UpdateVVolVirtualMachineFiles on this set.
#
# Note that this runs the parent VM through a second time.  This is necessary
# for the fix-up code to properly check the linked clone paths and parent IDs.
# Since that means the parent VM will be fixed up twice, it is necessary for
# this code to be idempotent.
#
# The code does not internally verify the correctness of the final descriptors.
# This would be a great addition for a future version, but for now that will
# need to be done manually after this test runs.
#


import re
import os
import sys
import glob
import random
import shutil

import pyVmomi
from pyVim.task import WaitForTask
from pyVmomi import Vim, Vmodl, VmomiSupport, SoapStubAdapter
from pyVmomi import Vmodl
from pyVim.connect import SmartConnect, Disconnect
from pyVim.helpers import Log,StopWatch
from pyVim.vimutil import InvokeAndTrackWithTask, InvokeAndTrack
from pyVim.vm import CreateQuickDummy
from pyVim import vm
from pyVim import vmconfig
from pyVim import arguments
from pyVim import host
import time
import atexit

supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                  (["u:", "user="], "root", "User name", "user"),
                  (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                  (["d:", "vvolDsName="], "vvolDs", "Vvol Datastore Name", "dsName")]

supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage") ]

args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
if args.GetKeyValue("usage") == True:
   args.Usage()
   sys.exit(0)

# Connect
si = SmartConnect(host=args.GetKeyValue("host"),
                  user=args.GetKeyValue("user"),
                  pwd=args.GetKeyValue("pwd"))
atexit.register(Disconnect, si)

def GetDatastore(si, dsName):
    hs = host.GetHostSystem(si)
    datastores = hs.GetDatastore()
    for ds in datastores:
        if ds.name == dsName:
           return ds
    raise Exception("Error looking up datastore: %s" % dsName)

def DsNsMgrMkdir(ds, name):
   dsnsmgr = si.content.datastoreNamespaceManager
   return dsnsmgr.CreateDirectory(ds, displayName = name)

def FindSnapshot(vmRef, snapname):
   if vmRef != None and vmRef.snapshot != None:
      snapshotList = list(vmRef.snapshot.rootSnapshotList)
      for snaptree in snapshotList:
         if snaptree.name == snapname:
            return snaptree.snapshot
         elif snaptree.childSnapshotList != None:
            snapshotList.extend(snaptree.childSnapshotList)

   return None

def CreateLinkedClone(vmRef, lcName, ssName):
   diskMoveType = Vim.VirtualMachineRelocateDiskMoveOptions.createNewChildDiskBacking

   snap = FindSnapshot(vmRef, ssName)

   if snap == None:
      raise Exception('Failed to find snapshot')

   profiles = []
   vmPolicy = Vim.VirtualMachineDefinedProfileSpec()
   vmPolicy.profileId =  ""
   vmPolicy.profileData = Vim.VirtualMachineProfileRawData(
      extensionKey = "com.vmware.vim.sps",
      objectData = None
   )
   profiles.append(vmPolicy)

   specList = []
   disks = [d for d in vmRef.config.hardware.device
            if isinstance(d, Vim.VirtualDisk)]
   for disk in disks:
      backing = None
      spec = Vim.VirtualMachineRelocateSpecDiskLocator(
         diskMoveType = diskMoveType,
         datastore = disk.backing.datastore,
         diskId = disk.key,
         profile = profiles,
         diskBackingInfo = backing,
      )
      specList.append(spec)

   spec = Vim.VirtualMachineCloneSpec(
      location = Vim.VirtualMachineRelocateSpec(
         diskMoveType = diskMoveType,
         profile = profiles,
         disk = None,
      ),
      powerOn = False,
      template = False,
      config = None,
      snapshot = snap,
   )

   task = vmRef.CloneVM_Task(folder=vmRef.parent,
                             name=lcName,
                             spec=spec)
   result = WaitForTask(task, si=si)

   if result == "error":
      raise task.info.error
   else:
      return task.info.result

def addObjMappingForVm(vmName, vmRef, vmMap, configId = None):
   for f1 in vmRef.layoutEx.file:
      lastIdx = f1.name.rfind("/")
      if f1.type == "config":
         if configId is not None:
            uuid = configId
         else:
            uuid = f1.name[f1.name.rfind("rfc4122.") : lastIdx]

      elif f1.backingObjectId:
         uuid = f1.backingObjectId

      else:
         continue

      fname = f1.name[lastIdx+1:]

      # swap files have a random number in them, so we need to eliminate it to
      # match up src and dest.
      if f1.type == 'swap':
         fname = re.sub('-[0-9a-fA-F]*\.', '.', fname)

      vmMap[fname] = uuid
      Log("\n   adding %s - %s\n" % (fname, uuid))

      if fname.find(".vmx") != -1:
         dstVmxId.append(uuid)


def getObjMapping(vmName, desc, target = False):
   Log("\nCreating VM object ID map on %s\n" % (desc))
   vmRef = CreateQuickDummy(vmName, datastoreName=vvolDsName, \
                            vmxVersion="vmx-13")

   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddScsiCtlr(cspec, cfgInfo = vmRef.config)
   capacityKB = 5 * 1024
   vmconfig.AddScsiDisk(cspec, cfgInfo = vmRef.config,
                        capacity = capacityKB,
                        datastorename = vvolDsName,
                        thin = True, scrub = False)
   InvokeAndTrack(vmRef.Reconfigure, cspec)

   vmRefs.append(vmRef)

   vm.PowerOn(vmRef)

   ssName = ("ss-%s" % random.randint(1,1000))
   vm.CreateSnapshot(vmRef, ssName, "snaphost",  memory=True, quiesce=False)

   lc1Name = vmName.replace('-', '-lc1-')
   lc1Ref = CreateLinkedClone(vmRef, lc1Name, ssName)

   lc2Name = vmName.replace('-', '-lc2-')
   lc2Ref = CreateLinkedClone(vmRef, lc2Name, ssName)

   global dstVmxId
   dstVmxId = []

   vmConfigId = None
   lc1ConfigId = None
   lc2ConfigId = None
   if target:
      tgtName = vmName + '-tgt'
      tgtPath = DsNsMgrMkdir(vvolDs, tgtName)
      vmConfigId = tgtPath[tgtPath.rfind('/')+1:]

      lc1TgtName = lc1Name + '-tgt'
      lc1TgtPath = DsNsMgrMkdir(vvolDs, lc1TgtName)
      lc1ConfigId = lc1TgtPath[lc1TgtPath.rfind('/')+1:]

      lc2TgtName = lc2Name + '-tgt'
      lc2TgtPath = DsNsMgrMkdir(vvolDs, lc2TgtName)
      lc2ConfigId = lc2TgtPath[lc2TgtPath.rfind('/')+1:]

   vmMap1 = {}
   addObjMappingForVm(vmName, vmRef, vmMap1, vmConfigId)
   addObjMappingForVm(lc1Name, lc1Ref, vmMap1, lc1ConfigId)

   vmMap2 = {}
   addObjMappingForVm(vmName, vmRef, vmMap2, vmConfigId)
   addObjMappingForVm(lc2Name, lc2Ref, vmMap2, lc2ConfigId)

   # Unregister VM to assume only vvol objects exists
   vm.PowerOff(vmRef)
   vmRef.Unregister()
   lc1Ref.Unregister()
   lc2Ref.Unregister()

   # returns the vmMap and a list of VMs created
   return [vmMap1, vmMap2], [vmName, lc1Name, lc2Name]

def cleanup():
   try:
      for vm1 in vmRefs:
         vm.PowerOff(vm1)
         vm.Destroy(vm1)
   except Exception:
      pass

def checkTaskResult(task, dstMap):
   try:
      WaitForTask(task)

      time.sleep(5)
      result = task.info.result;
      # Had better verify detail result by host mob
      # task result contains empty array although host mob
      # shows correct result.
      Log("\n   Task result: %s " % (result))

      if not result:
         raise Exception("Test failed. No result returned")

      succeededVmCfgFile = result.succeededVmConfigFile
      failedVmCfgFile = result.failedVmConfigFile

      if succeededVmCfgFile:
         for item in succeededVmCfgFile:
            if item.value.find(".vmx") == -1:
               raise Exception("Invalid success path = %s" % item.value)

            # item.value is a DS path like [DS] namespace/filename
            # We just want the filename.
            basename = item.value.split('/')[-1]
            if dstMap[basename] != item.key:
               raise Exception("Invalid success pair uuid = %s, path = %s" \
                                % (item.key, item.value))

      if failedVmCfgFile:
         for item in failedVmCfgFile:
            if not (item.tgtCfgId in dstVmxId):
               raise Exception("Invalid failed uuid = %s" % item.tgtCfgId)

      Log("Test succeeded as expected")
   except Vmodl.MethodFault as failure:
      raise Exception("Test failed. Task failed with %s, expected to succeed" \
                       % (failure. __class__.__name__))

def runTest():
   try:
      vmName = ("vm-%s" % random.randint(1,1000))

      Log("\nCreating VM pair -- vm %s\n" % (vmName))

      srcMaps, srcVms = getObjMapping(vmName, "Source")

      dstMaps, dstVms = getObjMapping(vmName, "Target", True)

      # src mapping of vmName.vmx is the true source VM
      # tgt mapping of vmName.vmx is the faked failover VM
      # We need to copy files into the fake VM
      for name in srcVms:
         if (name +  '.vmx' in srcMaps[0]):
            srcPath = os.path.join('/vmfs/volumes', vvolDsName,
                                   srcMaps[0][name + '.vmx'])
            tgtPath = os.path.join('/vmfs/volumes', vvolDsName,
                                   dstMaps[0][name + '.vmx'])
         else:
            srcPath = os.path.join('/vmfs/volumes', vvolDsName,
                                   srcMaps[1][name + '.vmx'])
            tgtPath = os.path.join('/vmfs/volumes', vvolDsName,
                                   dstMaps[1][name + '.vmx'])

         for fn in glob.glob(os.path.join(srcPath, '*.*')):
            shutil.copy(fn, tgtPath)
         for fn in glob.glob(os.path.join(srcPath, '.rfc*')):
            shutil.copy(fn, tgtPath)
         Log('VM {0} duplicated to failover target: {1}'.format(name, tgtPath))

      # Make a copy to compare after the failover
      Log('Removing previous backup...')
      shutil.rmtree(os.path.join('/vmfs/volumes/datastore1', vvolDsName),
                    ignore_errors = True)
      Log('Backing up datastore...')
      shutil.copytree(os.path.join('/vmfs/volumes', vvolDsName),
                      os.path.join('/vmfs/volumes/datastore1', vvolDsName),
                      ignore = shutil.ignore_patterns('*.vmsn', 'rfc4122.*'))

      for idx in xrange(len(srcMaps)):
         pair = Vim.Datastore.VVolContainerFailoverPair()
         pair.srcContainer = vvolId
         pair.tgtContainer = vvolId

         pair.vvolMapping = []
         for key in srcMaps[idx].keys():
            oneMapping = Vim.KeyValue()
            oneMapping.key = srcMaps[idx][key]
            oneMapping.value = dstMaps[idx][key]
            pair.vvolMapping.append(oneMapping)

         Log("\nGenerating failoverPair = %s\n" % pair)
         Log("\nCalling updateVVolVirtualMachineFiles\n")
         task = InvokeAndTrackWithTask(vvolDs.UpdateVVolVirtualMachineFiles,
                                       [pair])
         checkTaskResult(task, dstMaps[idx])

   except Exception:
      cleanup()
      raise

# Main
def main():
   global vvolDsName
   vvolDsName = args.GetKeyValue("dsName")

   global vvolDs
   vvolDs = GetDatastore(si, vvolDsName)

   global vvolId
   vvolId = vvolDs.info.vvolDS.scId

   if not isinstance(vvolDs.info, Vim.Host.VvolDatastoreInfo):
      raise Exception("Datastore must be vvol datastore: %s" % \
                      (vvolDsName))

   global vmRefs
   vmRefs = []

   runTest()

   Log("Tests passed")

# Start program
if __name__ == "__main__":
    main()


