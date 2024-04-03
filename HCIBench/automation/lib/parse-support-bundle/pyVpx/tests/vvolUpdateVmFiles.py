#!/usr/bin/env python

#
# Example -
#  $VMTREE/vim/py/py.sh  $VMTREE/vim/py/tests/vvolUpdateVmFiles.py -h "10.20.104.153" -u "root" -p "ca\$hc0w" -d "coke"
#


import sys
import random

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

def getObjMapping(vmName, desc):
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

   global dstVmxId
   dstVmxId = []

   vmMap = {}
   for f1 in vmRef.layoutEx.file:
      if f1.type == "config":
         lastIdx = f1.name.rfind(".")

         lastIdx1 = f1.name.rfind("/")
         uuid = f1.name[f1.name.rfind("rfc4122.") : lastIdx1]

      elif f1.backingObjectId:
         lastIdx = f1.name.rfind(".")
         uuid = f1.backingObjectId

      else:
         continue

      fname = vmName + f1.name[lastIdx:]
      vmMap[fname] = uuid
      Log("\n   adding %s - %s\n" % (fname, uuid))

      if fname.find(".vmx") != -1:
         dstVmxId.append(uuid)

   # Unregister VM to assume only vvol objects exists
   vm.PowerOff(vmRef)
   vmRef.Unregister()

   return vmMap

def cleanup():
   try:
      for vm1 in vmRefs:
         vm.PowerOff(vm1)
         vm.Destroy(vm1)
   except Exception:
      pass

def checkTaskResult(task):
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

def runTest(numPair = 1, sameVmName = False):
   try:
      failoverPair = []

      vmName = ("vm-%s" % random.randint(1,1000))

      for i in range(numPair):
         if not sameVmName:
            vmName = ("vm-%s" % random.randint(1,1000))

         Log("\nCreating VM pair #%d, vm %s\n" % (i+1, vmName))

         srcMap = getObjMapping(vmName, "Source")

         global dstMap
         dstMap = getObjMapping(vmName, "Target")

         pair = Vim.Datastore.VVolContainerFailoverPair()
         pair.srcContainer = vvolId
         pair.tgtContainer = vvolId

         pair.vvolMapping = []
         for key in srcMap.keys():
            oneMapping = Vim.KeyValue()
            oneMapping.key = srcMap[key]
            oneMapping.value = dstMap[key]
            pair.vvolMapping.append(oneMapping)

      failoverPair.append(pair)
      Log("\nGenerating failoverPair = %s\n" % failoverPair)

      Log("\nCalling updateVVolVirtualMachineFiles\n")
      task = InvokeAndTrackWithTask(vvolDs.UpdateVVolVirtualMachineFiles, failoverPair)
      checkTaskResult(task)

   except Exception as e:
      cleanup()
      raise e

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


