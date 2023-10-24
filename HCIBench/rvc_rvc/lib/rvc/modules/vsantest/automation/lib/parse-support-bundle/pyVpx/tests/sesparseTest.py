#!/usr/bin/python

from __future__ import print_function

import sys
import datetime
from pyVmomi import Vim, Vmodl
from pyVmomi import VmomiSupport
from pyVmomi.VmomiSupport import newestVersions
from vimsupport import VimSession, CreateSession
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import arguments
from pyVim import vm, folder, invt, vimutil
from pyVim.helpers import Log,StopWatch
from pyVim import vmconfig
import atexit
import random

TWOGB_IN_MB = (1<<10) * 2

def VerifySetup(si):
   dataCenter = si.RetrieveContent().GetRootFolder().GetChildEntity()[0]
   hostFolder = dataCenter.hostFolder
   host = hostFolder.childEntity[0]
   hostSystem = hostFolder.childEntity[0].host[0]
   return host, hostSystem, dataCenter

def VmTest(spec, dc, host,resPool, remove=True):
   print("vm resoure pool is " + str(resPool))
   thisVm = vm.CreateFromSpec(spec, dc.GetName(), host, resPool)
   if remove:
      vm.Destroy(thisVm)
   else:
      return thisVm

def CreateVmSpec(vmName, dsName, backing, diskSize, vmVersion='vmx-09'):
   return vm.CreateQuickDummySpec(vmname=vmName,
                                  numScsiDisks=1,
                                  diskSizeInMB=diskSize,
                                  datastoreName=dsName,
                                  backingType=backing,
                                  thin=True,
                                  vmxVersion=vmVersion)

def MigrateVm(session, vm, cloneVmName, expSuccess=True, cspec=None, rspec=None):
   if cspec:
      folder = vm.parent
      t = vm.Clone(folder, cloneVmName, cspec)
   else:
      t = vm.Relocate(rspec)

   ret = False
   try:
      result = session.WaitForTask(t)
      if result == Vim.TaskInfo.State.success:
         ret = True
   except Vmodl.MethodFault as failure:
      Log("Vm operation failed, fault = " + str(failure. __class__.__name__))

   if expSuccess != ret:
      Log("Test failed, expect " + str(expSuccess) + " got " + str(ret))
      return False

   return True

def GetCloneSpec(host, vm1, datastore):
   disks = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualDisk)
   location = Vim.Vm.RelocateSpec()

   snapshot = vm1.GetSnapshot().GetCurrentSnapshot()

   location.SetHost(host)
   location.SetDatastore(datastore)
   location.SetPool(host.parent.resourcePool)
   location.SetDiskMoveType("createNewChildDiskBacking")

   diskLocators = []
   diskLoc = Vim.Vm.RelocateSpec.DiskLocator()
   flatThickEager = Vim.vm.Device.VirtualDisk.FlatVer2BackingInfo()
   #flatThickEager.SetDeltaDiskFormat("seSparseFormat")
   diskLoc.SetDiskBackingInfo(flatThickEager)
   diskLoc.diskId = disks[0].GetKey()
   diskLoc.SetDatastore(datastore)
   diskLocators.append(diskLoc)
   location.SetDisk(diskLocators)

   cspec = Vim.Vm.CloneSpec()
   cspec.SetLocation(location)
   cspec.SetTemplate(False)
   cspec.SetPowerOn(False)
   cspec.SetSnapshot(snapshot)
   return cspec

def CreateLinkedClone(hostSystem, host, vm1, datastore, session):
   cloneSpec = GetCloneSpec(hostSystem, vm1,datastore)
   val = MigrateVm(session, vm1,
                   vm1.GetName() +
                   "LinkedClone", cspec=cloneSpec)
   return val

def CreateDeltaVm(vm1, host, hostSystem, datastore, dc):
   snapshot = vm1.GetSnapshot().GetCurrentSnapshot()

   disks = vmconfig.CheckDevice(snapshot.GetConfig(), Vim.Vm.Device.VirtualDisk)
   parentDisk = disks[0].GetBacking().GetFileName()
   #spec=CreateVmSpec(vm1.GetName() +"-clone", datastore.GetName(), 'flat', TWOGB_IN_MB)
   spec=CreateVmSpec(vm1.GetName() +"-clone", datastore.GetName(), 'flat', 500)
   childDiskBacking = spec.GetDeviceChange()[1].GetDevice().GetBacking()
   parentBacking = Vim.Vm.Device.VirtualDisk.FlatVer2BackingInfo()
   parentBacking.SetFileName(parentDisk)

   #childDiskBacking.SetDeltaDiskFormat('seSparseFormat')

   childDiskBacking.SetParent(parentBacking)
   snapshotVm=VmTest(spec, dc, hostSystem, host.GetResourcePool(), remove = False)
   print(snapshotVm.GetName() + " delta vm created.")

def CreateMainVm(host, hostSystem, datastore, dc, vmName, vmVersion='vmx-09'):
   spec = CreateVmSpec(vmName, datastore.GetName(), 'flat',  TWOGB_IN_MB,
                       vmVersion)
   vm1 = VmTest(spec, dc, hostSystem, host.GetResourcePool(),remove = False)
   vm.CreateSnapshot(vm1, "S1", "snap shot 1 of vm1", False, False)
   print(vm1.GetName() + " created.")
   return vm1

# This test create a dummy vm (vm1), create a linked clone vm on vm1
# with hardware version < 9 in a vmfs 6 datastore. The test will fail
# for vmfs 5, since hardware version < 9 is not supported
def hwVersionTest(host, hostSystem, ds, dc, session):
    # create main vm with hwversion 08
    vm1 = CreateMainVm(host, hostSystem, ds , dc, "MainVM", "vmx-09")
    # this linked clone operation should not fail in vmfs 6 datastore
    # since it supports sesparse format for hardware version below 6
    CreateLinkedClone(hostSystem, host, vm1, ds, session)
    #CreateDeltaVm(vm1, host, hostSystem, ds, dc)
    vm1.Destroy(vm1)

def main():
    # connect to vc, host
   vc = "10.161.250.162"
   user1 = "administrator@vsphere.local"
   pwd1 = "Admin!23"
   si= Connect(host=vc,
               user=user1,
               pwd=pwd1,
               version=newestVersions.GetName('vim'))
   print("Connected to VC: " + vc)
   host, hostSystem, dc = VerifySetup(si)
   vimInternalNs = newestVersions.GetInternalNamespace('vim')
   session = CreateSession(vc, '443', user1, pwd1, vimInternalNs)
   # ds0 should be a vmfs 6 datastore
   ds0 = session.GetDatastore(host, "ds0")

   #hwversion test
   hwVersionTest(host, hostSystem, ds0, dc, session)

if __name__ == "__main__":
   main()
