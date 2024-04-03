#!/usr/bin/env python

import os
import sys
import time
import subprocess
from pyVmomi import vim, VmomiSupport
from pyVim.task import WaitForTask
from pyVim.helpers import Log
from pyVim import vm
from pyVim import host
from pyVim import invt
from pyVim import folder
from pyVim import connect

FTState = vim.VirtualMachine.FaultToleranceState
PowerState = vim.VirtualMachine.PowerState
FTType = vim.VirtualMachine.FaultToleranceType

def DescribeVm(vm):
   return vm.GetConfig().GetFiles().GetVmPathName()

def WaitForPowerState(vm, si, powerState, nsec=40):
   with LogSelfOp() as logOp:
      saveSi = connect.GetSi()
      connect.SetSi(si)
      for i in range(nsec):
         if vm.GetRuntime().GetPowerState() != powerState:
            time.sleep(1)
      if vm.GetRuntime().GetPowerState() != powerState:
         raise Exception("%s: VM did not transition to expected power state!" % \
                             DescribeVm(vm))
      connect.SetSi(saveSi)

def GetHostThumbprint(hostname):
   cmd = 'openssl s_client -connect %s:443 </dev/null 2>&1 |' % hostname + \
         'openssl x509 -noout -fingerprint|cut -d"=" -f 2'
   p = subprocess.Popen([cmd], shell=True, stdout=subprocess.PIPE)
   p.wait()
   stdout = p.stdout.read()
   return stdout.strip()

## Cleanup VMs with the given name on a host.
def CleanupVm(vmname, useLlpm = False):
   with LogSelfOp() as logOp:
      if isinstance(vmname, vim.VirtualMachine):
         Log("Cleaning up VMs with name %s" % vmname.name)
         oldVms = [vmname]
      else:
         Log("Cleaning up VMs with name %s" % vmname)
         oldVms = folder.FindPrefix(vmname)
      for oldVm in oldVms:
         if oldVm.GetRuntime().GetPowerState() == PowerState.poweredOn:
            vm.PowerOff(oldVm)
         ftInfo = oldVm.config.ftInfo
         if ftInfo and ftInfo.role == 1:
            # If the VM is a primary, unregister all secondaries
            # before deleting the VM.
            ftMgr = host.GetFaultToleranceMgr(connect.GetSi())
            WaitForTask(ftMgr.UnregisterSecondary(oldVm, None))
         Log("Destroying VM")
         if useLlpm == True:
            vmConfig = oldVm.GetConfig()
            hw = vmConfig.GetHardware()
            if vmConfig.flags.faultToleranceType and \
               vmConfig.flags.faultToleranceType == "recordReplay":
               hw.SetDevice([])
            vmConfig.SetHardware(hw)
            llpm = invt.GetLLPM()
            llpm.DeleteVm(vmConfig)
         else:
            vm.Destroy(oldVm)

def CleanupDir(datastoreName, folderName):
   with LogSelfOp() as logOp:
      si = connect.GetSi()
      fileMgr = si.content.fileManager
      try:
         WaitForTask(fileMgr.Delete(datastorePath="[%s] %s" %
                                    (datastoreName, folderName),
                                    fileType=vim.FileManager.FileType.File))
      except vim.fault.FileNotFound as e:
         pass
      except Exception as e:
         Log("Error cleaning up %s: %s" % (folderName, e))

## Reload the secondary VM, to update stale info
def ReloadSecondary(si, vm1):
   with LogSelfOp() as logOp:
      curSi = connect.GetSi()
      connect.SetSi(si)
      vmname = vm1.GetConfig().GetName()
      Log("Reloading secondary VM")
      vm1.Reload()
      vm2 = folder.Find(vmname)
      if vm2 == None:
         raise Exception("Reload caused the VM to go invalid")
      connect.SetSi(curSi)


## Validate FT state and record/replay state of the VM
def CheckFTState(vm, state, isPrimary=True, checkRRState=False):
   with LogSelfOp() as logOp:
      expRRState = None
      if isPrimary:
         expRRState = vim.VirtualMachine.RecordReplayState.recording
      else:
         expRRState = vim.VirtualMachine.RecordReplayState.replaying

      ftState = vm.GetRuntime().GetFaultToleranceState()
      rrState = vm.GetRuntime().GetRecordReplayState()
      if ftState != state:
         raise Exception("%s: Runtime FT state %s not set to %s" % \
                             (DescribeVm(vm), ftState, state))
      Log("Verified runtime fault tolerance state as %s" % state)

      if not checkRRState:
         return

      # Check record/replay state
      if ftState == FTState.running:
         if rrState != expRRState:
            raise Exception("Runtime recordReplay state %s not set to %s" % \
                            (rrState, expRRState))
      elif rrState != vim.VirtualMachine.RecordReplayState.inactive:
         raise Exception("Runtime recordReplay state %s not set to inactive" % rrState)
      Log("Verified runtime record/replay state as %s" % rrState)

## Validate FT role of a VM against an expected value.
def CheckFTRole(vm, role):
   with LogSelfOp() as logOp:
      ftInfo = vm.GetConfig().GetFtInfo()
      if ftInfo == None:
         raise Exception("No FT info configured for this VM")
      if ftInfo.GetRole() != role:
         raise Exception("FT role of VM does not match " + str(role))

## Helper routine to add extra config entries to a VM.
def AddExtraConfig(extraCfgs, key, value):
   opt = vim.Option.OptionValue()
   opt.SetKey(key)
   opt.SetValue(value)
   extraCfgs.append(opt)

## Retrieve the file name associated with a datastore path.
def GetFileName(dsPath):
    relPath = dsPath.split()[1]
    cfgPath = relPath.split("/")[1]
    return cfgPath

def GetSharedPath(si, vm):
   workingDir = vm.config.files.suspendDirectory
   workingDir += "_shared"

   fileMgr = si.content.fileManager
   try:
      fileMgr.MakeDirectory(name=workingDir)
   except vim.fault.FileAlreadyExists:
      pass

   return workingDir

def SetFtCpt(vm, val):
   with LogSelfOp() as logOp:
      flags = vim.vm.FlagInfo(faultToleranceType=FTType.checkpointing if val else FTType.unset)
      WaitForTask(vm.Reconfigure(vim.Vm.ConfigSpec(flags=flags)))

def WaitForFTState(vm, desiredFtState, nsec=20):
   with LogSelfOp() as logOp:
      for i in range(nsec):
         ftState = vm.GetRuntime().GetFaultToleranceState()
         if ftState != desiredFtState:
            time.sleep(1)
      ftState = vm.GetRuntime().GetFaultToleranceState()
      if ftState != desiredFtState:
         raise Exception("%s: VM did not transition to expected FT state current %s != desired %s!" % \
                         (DescribeVm(vm), ftState, desiredFtState))

def CheckNeedSecondaryReason(theVm, reason):
   with LogSelfOp() as logOp:
      theReason = theVm.GetRuntime().GetNeedSecondaryReason()
      if theReason != reason:
         raise Exception("%s: Unexpected need secondary reason: %s" % \
                          (DescribeVm(theVm), theReason))
      if reason:
         Log("Verified needSecondaryReason %s" % reason)
      else:
         Log("Verified needSecondaryReason unset")

def FindNicType(si, nicType):
   nics = []
   for netConfig in host.GetHostVirtualNicManager(si).info.netConfig:
      if netConfig.nicType == nicType:
         for selectedVnic in netConfig.selectedVnic:
            nics.append(selectedVnic)
   return nics

def SelectVnic(si, vnic, nicType):
   with LogSelfOp() as logOp:
      host.GetHostVirtualNicManager(si).SelectVnic(nicType, vnic)

opCount = 0

def GenId():
   global opCount
   opCount += 1
   return '%d%d' % (time.time() * 1e9, opCount)

def GenOpId(name):
   return 'vmFTOp-%s-%s' % (name, GenId())

def LogOp(op, *args, **kwargs):
   with LogSelfOp(op.__name__) as logOp:
      return op(*args, **kwargs)

class LogSelfOp():
   def __init__(self, name=None):
      self.name = name
      if self.name is None:
         self.name = sys._getframe(1).f_code.co_name

   def __enter__(self, name=None):
      opID = GenOpId(self.name)
      reqCtx = VmomiSupport.GetRequestContext()
      reqCtx['operationID'] = opID
      Log("%s opID=%s" % (self.name, opID))

   def __exit__(self, *args):
      reqCtx = VmomiSupport.GetRequestContext()
      reqCtx['operationID'] = ""
