## @file ft.py
## @brief Fault Tolerance Operations

__author__ = "VMware, Inc"

from pyVim import task, vimutil
from vmFTUtils import LogSelfOp
## Make Primary commit suicide, so secondary becomes primary
# @param ftMgr [in] Fault Tolerance Manager
# @param vm [in] Primary VM
# @param secondaryUuid [in] instanceUuid of the secondary
def MakePrimary(ftMgr, vm, secondaryUuid):
   with LogSelfOp():
      return vimutil.InvokeAndTrackWithTask(ftMgr.MakePrimary, vm, secondaryUuid)

## Query the Fault Tolerance compatibility of the VM returning faults for
## anything not compatible
# @param vm [in] Virtual machine to query
# @param forLegacyFt [in] Whether to query against recordReplay FT or
#                         checkpoint FT
def QueryFaultToleranceCompatibility(vm, forLegacyFt):
   with LogSelfOp():
      return vm.QueryFaultToleranceCompatibilityEx(forLegacyFt)

## Register a secondary to the primary VM, updating the shared.vmft file
# @param ftMgr [in] Fault Tolerance Manager
# @param vm [in] Primary VM
# @param secondaryUuid [in] instanceUuid of the secondary
# @param secondaryCfgPath [in] dsPath to the secondary VM
def RegisterSecondary(ftMgr, vm, secondaryUuid, secondaryCfgPath):
   with LogSelfOp():
      return vimutil.InvokeAndTrackWithTask(ftMgr.RegisterSecondary, vm,
                                            secondaryUuid, secondaryCfgPath)

## Unregister a secondary from the primary VM
# @param ftMgr [in] Fault Tolerance Manager
# @param vm [in] Primary VM
# @param secondaryUuid [in] instanceUuid of the secondary
def UnregisterSecondary(ftMgr, vm, secondaryUuid):
   with LogSelfOp():
      return vimutil.InvokeAndTrackWithTask(ftMgr.UnregisterSecondary, vm,
                                            secondaryUuid)

## Disable a secondary VM
# @param ftMgr [in] Fault Tolerance Manager
# @param vm [in] Primary VM
# @param secondaryUuid [in] instanceUuid of the secondary
def DisableSecondary(ftMgr, vm, secondaryUuid):
   with LogSelfOp():
      return vimutil.InvokeAndTrackWithTask(ftMgr.DisableSecondary, vm,
                                            secondaryUuid)

## Enable the secondary VM that was disabled
# @param ftMgr [in] Fault Tolerance Manager
# @param vm [in] Primary VM
# @param secondaryUuid [in] instanceUuid of the secondary
def EnableSecondary(ftMgr, vm, secondaryUuid):
   with LogSelfOp():
      return vimutil.InvokeAndTrackWithTask(ftMgr.EnableSecondary, vm,
                                            secondaryUuid)

## Ask the vmx to terminate the fault tolerant VM
# @param ftMgr [in] Fault Tolerance Manager
# @param vm [in] Primary VM
# @param instanceUuid [in] instanceUuid of the VM to terminate
def TerminateFaultTolerantVM(ftMgr, vm, instanceUuid):
   with LogSelfOp():
      return vimutil.InvokeAndTrackWithTask(ftMgr.TerminateFaultTolerantVM, vm,
                                            instanceUuid)

