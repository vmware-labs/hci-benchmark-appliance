#!/usr/bin/python

#
# Unit test for 2TB+ virtual disk support

from __future__ import print_function

import sys
import datetime
from pyVmomi import Vim, Vmodl
from pyVmomi import VmomiSupport
from pyVmomi.VmomiSupport import newestVersions
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import arguments
from pyVim import vm, folder, invt, vimutil
from pyVim.helpers import Log,StopWatch
from pyVim import vmconfig
import atexit

TWOTB_IN_MB = (1 << 20) * 2 + 2000
TWOGB_IN_MB = (1<<10) * 2
destResPool = None

# expected setup
# one cluster with one 6.0 host and one 5.x host
# both host connected to a two TB + datastore
def VerifySetup(si):
   newHost = None
   oldHost = None
   datastore2TB = None
   dataCenter = si.RetrieveContent().GetRootFolder().GetChildEntity()[0]
   # find 2TB+ datastore
   for datastore in dataCenter.datastore:
      summary = datastore.summary
      if (summary.capacity > (1<<40) * 2 and  summary.type == "VMFS"):
         datastore2TB = datastore
         print("2TB datastore found " + " :" + datastore2TB.GetName())
         break

   if datastore2TB == None:
      raise Exception("cannot find 2TB+ datastore is setup")

   hostFolder = dataCenter.hostFolder
   for hostSystem in hostFolder.childEntity[0].host:
      #hostSystem = host.host[0]
      for datastore in hostSystem.datastore:
         if datastore == datastore2TB:
            break
      else:
         continue
      if hostSystem.config.product.version[0] >= "6":
         newHost = hostSystem
         print("Esx 6.0 + found")
         #print hostSystem.config.product
      else:
         oldHost = hostSystem
         print("Esx 5.0 found")
         #print hostSystem.config.product
   if not (newHost and oldHost and datastore2TB):
      raise AssertionError("cannot find required host")

   srcHost = hostFolder.childEntity[1].host[0]
   for datastore in srcHost.datastore:
      if datastore == datastore2TB:
         print("Source Esx 6.0 found")
         break
   else:
      raise AssertionError("cannot find required host")

   return dataCenter, datastore2TB, newHost, srcHost


def CreateVmSpec(vmName, dsName, backing, diskSize, vmVersion):
   return vm.CreateQuickDummySpec(vmname=vmName,
                                  numScsiDisks=1,
                                  diskSizeInMB=diskSize,
                                  datastoreName=dsName,
                                  backingType=backing,
                                  thin=True,
                                  vmxVersion=vmVersion)

def VmTest(spec, dc, host, remove=True):
   if (not host):
      resPool = destResPool
   else:
      resPool = host.GetParent().GetResourcePool()
   print("vm resoure pool is " + str(resPool))
   thisVm = vm.CreateFromSpec(spec, dc.GetName(), host, resPool)
   if remove:
      vm.Destroy(thisVm)
   else:
      return thisVm

def BaseTest(dc, dsName, host, backingType, vmx, diskSize, positive, test):
   msg = test + "positive =" + str(positive) + '; ' + \
      "backing=" + backingType + '; ' + \
      "vmx version=" + str(vmx) +'; ' + \
      'diskSize=' + str(diskSize) +'; ' + 'result='

   try:
      spec=CreateVmSpec(backingType+"Vm", dsName, backingType, diskSize, vmx)
      VmTest(spec, dc, host)
   except Vmodl.MethodFault as e:
      if not positive:
         print(msg + 'SUCCESS')
         print(e)
      else:
         print(msg + "FAILURE")
         raise
   except Exception:
         print(msg + "FAILURE")
         raise
   else:
      if positive:
         print(msg + 'SUCCESS')
      else:
         print(msg + "FAILURE, negative test through")
         raise AssertionError(msg + "FAILURE, negative test through")

def DeltaTest(dc, dsName, host, backingType,
              deltaDiskFormat, diskSize, vmx, positive, test):
   msg = test + "positive =" + str(positive) + '; ' + \
      "backing=" + backingType + '; ' + \
      "delta=" + str(deltaDiskFormat) + '; ' + \
      "vmx version=" + str(vmx) +'; ' + \
      'diskSize=' + str(diskSize) +'; ' + 'result='

   vm1 = None
   snapshotVm = None
   try:
      spec=CreateVmSpec(backingType+"Vm", dsName, backingType, diskSize, vmx)
      vm1=VmTest(spec, dc, host, remove=False)
      vm.CreateSnapshot(vm1, "S1", "snap shot of vm1", False, False)
      snapshot = vm1.GetSnapshot().GetCurrentSnapshot()
      disks = vmconfig.CheckDevice(snapshot.GetConfig(), \
                                   Vim.Vm.Device.VirtualDisk)
      if len(disks) != 1:
         print(snapshot.GetConfig())
         raise AssertionError("Did not find correct number of snapshot")

      parentDisk = disks[0].GetBacking().GetFileName()
      spec=CreateVmSpec(backingType+"Vm-Clone", dsName, backingType, diskSize, vmx)
      childDiskBacking = spec.GetDeviceChange()[1].GetDevice().GetBacking()
      #print(childDiskBacking)
      if backingType == 'flat':
         parentBacking = Vim.Vm.Device.VirtualDisk.FlatVer2BackingInfo()
      if backingType == 'seSparse':
         parentBacking = Vim.Vm.Device.VirtualDisk.SeSparseBackingInfo()
      parentBacking.SetFileName(parentDisk)
      childDiskBacking.SetParent(parentBacking)
      childDiskBacking.SetDeltaDiskFormat(deltaDiskFormat)
      #print(spec)
      snapshotVm=VmTest(spec, dc, host, remove = False)
   except Vmodl.MethodFault as e:
      if not positive:
         print(msg + 'SUCCESS')
         print(e)
      else:
         print(msg + "FAILURE")
         raise
   except Exception:
         print(msg + "FAILURE")
         raise
   else:
      if positive:
         print(msg + 'SUCCESS')
      else:
         print(msg + "FAILURE, negative test through")
         raise AssertionError(msg + "FAILURE, negative test through")
   finally:
      if vm1:
         vm.Destroy(vm1)
      if snapshotVm:
         vm.Destroy(snapshotVm)

def RelocateTest(srcHost, dc, dsName, host, backingType,
              deltaDiskFormat, diskSize, vmx, positive, test):
   msg = test + "positive =" + str(positive) + '; ' + \
      "backing=" + backingType + '; ' + \
      "delta=" + str(deltaDiskFormat) + '; ' + \
      "vmx version=" + str(vmx) +'; ' + \
      'diskSize=' + str(diskSize) +'; ' + 'result='
   try:
      spec=CreateVmSpec(backingType+"Vm", dsName, backingType, diskSize, vmx)
      vm1=VmTest(spec, dc, srcHost, remove=False)
      vm.PowerOn(vm1)
      if (not host):
         resPool = destResPool
      else:
         resPool = host.GetParent().GetResourcePool()
      print("Vm migrate dest resoure pool is " + str(resPool))
      vimutil.InvokeAndTrack(vm1.Migrate, resPool, host, "defaultPriority")
      if str(vm1.GetResourcePool()) != str(resPool):
         raise AssertionError(msg + "FAILURE, wrong place " + str(vm1.GetResourcePool()) +
                              "Expected " + str(resPool))
      '''
      relocSpec = Vim.Vm.RelocateSpec()
      relocSpec.SetPool(resPool)
      relocSpec.SetHost(host)
      vimutil.InvokeAndTrack(vm1.Relocate, relocSpec)
      '''
   except Vmodl.MethodFault as e:
      if not positive:
         print(msg + 'SUCCESS')
         print(e)
      else:
         print(msg + "FAILURE")
         raise
   except Exception:
         print(msg + "FAILURE")
         raise
   else:
      if positive:
         print(msg + 'SUCCESS')
      else:
         print(msg + "FAILURE, negative test through")
         raise AssertionError(msg + "FAILURE, negative test through")
   finally:
      if vm1:
         vm.Destroy(vm1)


def main():
   # Process command line
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd")
                    ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage") ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   si= Connect(host=args.GetKeyValue("host"),
                user=args.GetKeyValue("user"),
                pwd=args.GetKeyValue("pwd"),
                version=newestVersions.GetName('vim'))
   dc, ds, host, srcHost = VerifySetup(si)
   global destResPool
   destResPool = host.GetParent().GetResourcePool()
   test = 'postive flat 2TB+ test: '
   BaseTest(dc, ds.GetName(), None, 'flat', None, TWOTB_IN_MB, True, test)
   test = 'postive sesparse 2TB+ test: '
   BaseTest(dc, ds.GetName(), None, 'seSparse', None, TWOTB_IN_MB, True, test)
   test = 'postive flat 2TB+ vm version test: '
   BaseTest(dc, ds.GetName(), None, 'flat', 'vmx-08', TWOTB_IN_MB, True, test)
   test = 'postive sesparse 2TB+ vm version test: '
   BaseTest(dc, ds.GetName(), None, 'seSparse', 'vmx-08', TWOTB_IN_MB, True, test)
   test = 'postive flat < 2TB test: '
   BaseTest(dc, ds.GetName(), host, 'flat', None, TWOGB_IN_MB, True, test)
   test = 'postive sesparse < 2TB test: '
   BaseTest(dc, ds.GetName(), host, 'seSparse', None, TWOGB_IN_MB, True, test)
   test = 'positive flat < 2TB, vm version test: '
   BaseTest(dc, ds.GetName(), host, 'flat',  'vmx-08', TWOGB_IN_MB, True, test)
   test = 'Negative sesparse < 2TB, vm version test: '
   BaseTest(dc, ds.GetName(), host, 'seSparse',  'vmx-08', TWOGB_IN_MB, False, test)

   test = 'positive delta flat 2TB+ test: '
   DeltaTest(dc, ds.GetName(), None, 'flat', None, TWOTB_IN_MB, None, True, test)
   test = 'positive delta sesparse 2TB+ test: '
   DeltaTest(dc, ds.GetName(), None, 'seSparse', None, TWOTB_IN_MB, None, True, test)
   test = 'positive delta flat 2TB+ vm version test: '
   DeltaTest(dc, ds.GetName(), None, 'flat', None, TWOTB_IN_MB, 'vmx-08', True, test)
   test = 'positive delta sesparse 2TB+ vm version test: '
   DeltaTest(dc, ds.GetName(), None, 'seSparse', None, TWOTB_IN_MB, 'vmx-08', True, test)
   test = 'negative delta flat 2TB+ redolog test: '
   DeltaTest(dc, ds.GetName(), None, 'flat', 'redoLogFormat' , TWOTB_IN_MB, None, False, test)
   test = 'positive delta flat < 2TB test: '
   DeltaTest(dc, ds.GetName(), host, 'flat', None, TWOGB_IN_MB, None, True, test)
   test = 'positive delta sesparse < 2TB test: '
   DeltaTest(dc, ds.GetName(), host, 'seSparse', None, TWOGB_IN_MB, None, True, test)
   test = 'positive delta flat < 2TB vm version test: '
   DeltaTest(dc, ds.GetName(), host, 'flat', None, TWOGB_IN_MB, 'vmx-08', True, test)
   test = 'negative delta sesparse < 2TB test: '
   DeltaTest(dc, ds.GetName(), host, 'seSparse', 'seSparseFormat', TWOGB_IN_MB, 'vmx-08', False, test)
   test = 'negative delta sesparse < 2TB test 2: '
   DeltaTest(dc, ds.GetName(), host, 'flat', 'seSparseFormat', TWOGB_IN_MB, 'vmx-08', False, test)
   test = 'postive relocate 2TB+ test: '
   RelocateTest(srcHost, dc, ds.GetName(), host, 'flat', None, TWOTB_IN_MB, None, True, test)

if __name__ == "__main__":
   main()
