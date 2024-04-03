#!/usr/bin/python

"""
Copyright 2010-2017,2021 VMware, Inc.  All rights reserved. -- VMware Confidential

A set of simple tests to exercise support for FT VMs.
"""
from __future__ import print_function

import ssl
import sys
import os
import time
import getopt
import traceback
from pyVmomi import vim, vmodl, VmomiSupport
from pyVim.connect import SmartConnect, Disconnect, GetSi
from pyVim.task import WaitForTask
from pyVim.helpers import Log
from pyVim import vm
from pyVim import vmconfig
from pyVim import host
from pyVim import connect
from pyVim import arguments
from pyVim import folder

import ft
from vmFTUtils import *

status = "PASS"
checkRRState = True
ftType = "smp"
FTState = vim.VirtualMachine.FaultToleranceState
PowerState = vim.VirtualMachine.PowerState
ftLoggingNicType = vim.host.VirtualNicManager.NicType.faultToleranceLogging
vmotionNicType = vim.host.VirtualNicManager.NicType.vmotion

ftvmotion = vim.Host.VMotionManager.VMotionType.fault_tolerance
ftsubtype = vim.Host.FaultToleranceManager.FaultToleranceType.fault_tolerance_using_recordreplay

def IsTestEsx():
    """
    Returns True iff the current invocation is running under test-esx.
    """

    return 'TESTESX_VOLUME' in os.environ

def LogForTestEsx(msg):
    """
    Print a Log message that also gets echoed by test-esx.

    By default test-esx saves stdout, but discards it if the test
    passes.  This Log function forces the message to get echoed (in
    case the message is important), even if the test passes.

    This is useful for reporting important conditions that might not
    result in test failure to the test-esx user.
    """

    Log(msg)
    if IsTestEsx():
        print('TESTESX-ALWAYS: %s' % msg)

def GetDatastore(si, name):
    """
    Returns the non-UUID datastore name for the supplied name.

    The supplied name is a string that specifies the datastore.  It is
    either a UUID or non-UUID name.  This function will do the
    conversion from UUID to non-UUID name if necessary, as well as
    validate that the datastore actually exists.
    """

    hs = host.GetHostSystem(si)
    datastores = hs.GetDatastore()
    name = name.replace('/vmfs/volumes/', '')
    for ds in datastores:
        if ds.name == name or \
                ds.info.url.replace('/vmfs/volumes/', '') == name:
            return ds.name
    raise Exception('Error looking up datastore: %s' % name)

def SummarizeHost(si, name):
    """
    Log some information about a host.
    """

    s = host.GetHostSystem(si)
    Log('%(host)s: %(threads)dx %(desc)s, %(hz).1f GHz %(mem).1f GB' % {
            'host':    name,
            'threads': s.summary.hardware.numCpuThreads,
            'desc':    s.summary.hardware.cpuModel,
            'hz':      s.summary.hardware.cpuMhz / 1000.0,
            'mem':     1.0 * s.summary.hardware.memorySize / (1 << 30),
            })

def CleanDirs(si, dsName, vmName, ftType):
    """
    Remove directories created by test.
    """
    prevSi = connect.GetSi()
    connect.SetSi(si)
    Log('Cleaning up %s on %s' % (vmName, dsName))
    CleanupDir(dsName, vmName)
    if ftType == "smp":
        CleanupDir(dsName, "%s_shared" % vmName)
    connect.SetSi(prevSi)

def ReportFiles(path):
    """
    Report VM files sitting in the given directory.

    Only useful when running under test-esx.
    """

    def Blacklisted(name):
        blacklist = '.vmdk .vswp .nvram .hlog .lck'.split()
        for j in blacklist:
            if j in name:
                return True
        return False

    try:
        for i in os.listdir(path):
            try:
                i = os.path.join(path, i)
                if not os.path.isfile(i) or Blacklisted(i):
                    continue
                print('#BUGREPORT:LOGFILE:%d# %s' % (os.getppid(), i))
            except OSError: pass
    except Exception: pass

def TestMakePrimary(ftMgr, ftUuid, primarySi, primaryVm,
                    secondarySi, secondaryVm):
    saveSi = connect.GetSi()
    connect.SetSi(primarySi)
    Log("Failing over to the secondary.")
    ft.MakePrimary(ftMgr, primaryVm, ftUuid)
    WaitForPowerState(primaryVm, primarySi, PowerState.poweredOff)
    Log("Verified primary power state is off.")

    connect.SetSi(secondarySi)
    WaitForFTState(secondaryVm, FTState.needSecondary)
    CheckNeedSecondaryReason(secondaryVm, "userAction")

    # A user-invoked failover (MakePrimary) has just happened.  The old
    # primary VM should have assumed the secondary FT role and be in the
    # powered-off state.  However, because of a race between the FT metadata
    # file update from the host secondarySi and the offline Vigor read of
    # the same shared FT metadata file on the host primarySi during the
    # failover, the host primarySi may see that the old primary VM still
    # has the primary FT role and never correct that even after the FT
    # metadata file is updated by the host secondarySi.  This can fail
    # subsequent operations such as CleanupVm [PR 1844401].  To work around
    # this, we force a reload of the old primary VM on the host primarySi.
    #
    connect.SetSi(primarySi)
    primaryVm.Reload()
    CheckFTRole(primaryVm, 2)
    connect.SetSi(saveSi)

def QuickTest(dsName=None,
              primarySi=None,
              secondarySi=None,
              primaryName=None,
              secondaryName=None,
              scrubDisks=False):
    """
    Perform a quick FT test.
    """

    # Create primary VM
    connect.SetSi(primarySi)
    primaryVm = None
    Log("Creating primary VM %s" % primaryName)
    # Short delay to avoid colliding with a cleanup.
    time.sleep(5)
    primaryVm = vm.CreateQuickDummy(primaryName,
                                    guest="winXPProGuest",
                                    memory=4,
                                    cdrom=0,
                                    numScsiDisks=1,
                                    scrubDisks=scrubDisks,
                                    datastoreName=dsName)
    ftMetadataDir = GetSharedPath(primarySi, primaryVm)
    if ftType == "smp" and primaryVm.config.hardware.numCPU == 1:
        LogOp(vm.Reconfigure, primaryVm, vim.vm.ConfigSpec(numCPUs=2))

    primaryUuid = primaryVm.GetConfig().GetInstanceUuid()
    primaryCfgPath = primaryVm.GetConfig().GetFiles().GetVmPathName()
    primaryDir = primaryCfgPath[:primaryCfgPath.rfind("/")]
    Log("Using VM : %s with instanceUuid %s" % (primaryVm.GetName(), primaryUuid))
    CheckFTState(primaryVm, FTState.notConfigured)

    # Create secondary VM
    connect.SetSi(secondarySi)
    Log("Creating secondary VM %s" % secondaryName)
    secondaryVm = vm.CreateQuickSecondary(secondaryName,
                                          primaryVm,
                                          datastoreName=dsName,
                                          numScsiDisks=1,
                                          scrubDisks=scrubDisks,
                                          ftType=ftType,
                                          ftMetadataDir=ftMetadataDir)

    if secondaryVm == None:
        raise Exception("Secondary VM creation failed")

    secondaryUuid = secondaryVm.GetConfig().GetInstanceUuid()
    secondaryCfgPath = secondaryVm.GetConfig().GetFiles().GetVmPathName()
    Log("Created secondary VM %s" % secondaryVm.GetName())
    Log("Secondary VM: instanceUuid %s" % secondaryUuid)
    Log("Secondary cfg path: %s" % secondaryCfgPath)

    ReloadSecondary(secondarySi, secondaryVm)
    CheckFTState(secondaryVm, FTState.disabled, False)

    if ftType == "smp":
        # SMP-FT supports hot start
        Log("Powering on Primary VM.")
        vm.PowerOn(primaryVm)

    ##  Configure some additional config variables needed for FT
    ##  This should eventually be done automatically at FT Vmotion time
    Log("Setting up extra config settings for the primary VM...")
    connect.SetSi(primarySi)
    extraCfgs = []
    cSpec = vim.Vm.ConfigSpec()
    if ftType == "smp": # some of these options are temporary
        AddExtraConfig(extraCfgs, "ftcpt.maxDiskBufferPages", "0")
        AddExtraConfig(extraCfgs, "sched.mem.pshare.enable", "FALSE")
        AddExtraConfig(extraCfgs, "sched.mem.fullreservation", "TRUE")
        AddExtraConfig(extraCfgs, "monitor_control.disable_mmu_largepages", "TRUE")
        AddExtraConfig(extraCfgs, "migration.dataTimeout", "2000")
        cSpec.flags = vim.vm.FlagInfo(faultToleranceType=FTType.checkpointing)
        cSpec.files = vim.vm.FileInfo()
        cSpec.files.ftMetadataDirectory = ftMetadataDir
    else:
        cSpec.flags = vim.vm.FlagInfo(recordReplayEnabled=True)
        AddExtraConfig(extraCfgs, "replay.allowBTOnly", "TRUE")
        AddExtraConfig(extraCfgs, "replay.allowFT", "TRUE")
    if primaryName != secondaryName:
        AddExtraConfig(extraCfgs, "ft.allowUniqueName", "TRUE")

    cSpec.SetExtraConfig(extraCfgs)
    Log("Reconfiguring Primary VM.");
    LogOp(vm.Reconfigure, primaryVm, cSpec)

    # Register secondary VM
    Log("Register secondary VM with the powered off primary")
    ftMgr = host.GetFaultToleranceMgr(primarySi)
    ft.RegisterSecondary(ftMgr, primaryVm, secondaryUuid, secondaryCfgPath)
    Log("Secondary VM registered successfully")

    # Verify FT role & state
    CheckFTRole(primaryVm, 1)
    if ftType == "smp":
       CheckFTState(primaryVm, FTState.needSecondary)
    else:
       CheckFTState(primaryVm, FTState.enabled)
    CheckNeedSecondaryReason(primaryVm, None)

    # Reload and check FT state of secondary VM
    ReloadSecondary(secondarySi, secondaryVm)
    CheckFTRole(secondaryVm, 2)
    CheckFTState(secondaryVm, FTState.enabled, False)
    Log("FT configured successfully.")

    # PowerOn FT VM
    if ftType != "smp":
        Log("Powering on Primary VM")
        vm.PowerOn(primaryVm)

    # Perform the FT VMotion
    Log("Migrating state from primary to secondary VM.")
    vm.Migrate(primaryVm, primarySi, secondarySi, secondaryCfgPath, True,
               ftvmotion, ftType=ftsubtype, destVm=secondaryVm)
    WaitForFTState(primaryVm, FTState.running)
    WaitForFTState(secondaryVm, FTState.running)

    TestMakePrimary(ftMgr, secondaryUuid, primarySi, primaryVm,
                    secondarySi, secondaryVm)

    vm.PowerOff(secondaryVm)
    WaitForPowerState(secondaryVm, secondarySi, PowerState.poweredOff)
    CheckNeedSecondaryReason(secondaryVm, None)
    connect.SetSi(secondarySi)
    CleanupVm(secondaryName, True)
    connect.SetSi(primarySi)
    CleanupVm(primaryName)
    CleanDirs(primarySi, dsName, primaryName, ftType)

def TestFTDisableEnable(ftMgr, primaryVm, secondaryVm, primarySi, secondarySi):
    global ftType
    connect.SetSi(secondarySi)
    secondaryUuid = secondaryVm.GetConfig().GetInstanceUuid()
    connect.SetSi(primarySi)
    primaryPowerState = primaryVm.GetRuntime().GetPowerState()

    # Disable Secondary VM
    connect.SetSi(primarySi)
    Log("Disabling secondary VM")
    ft.DisableSecondary(ftMgr, primaryVm, secondaryUuid)
    Log("Secondary VM disabled successfully")
    for i in range(5):
       if primaryVm.GetRuntime().GetFaultToleranceState() == FTState.running:
          time.sleep(1)
    CheckFTState(primaryVm, FTState.disabled)
    if primaryPowerState == PowerState.poweredOn:
       WaitForPowerState(secondaryVm, secondarySi, PowerState.poweredOff)

    CheckNeedSecondaryReason(primaryVm, None)
    ReloadSecondary(secondarySi, secondaryVm)
    CheckFTState(secondaryVm, FTState.disabled, False)

    # Negative test: test disable on secondary VM again
    try:
       ft.DisableSecondary(ftMgr, primaryVm, secondaryUuid)
    except vim.Fault.SecondaryVmAlreadyDisabled as e:
       Log("Caught SecondaryAlreadyDisabled exception as expected")
    else:
       raise Exception("Did not hit exception disabling secondary")

    # Validate disk add/edit/remove are not allowed
    if ftType == "smp":
       spec = vmconfig.AddScsiCtlr(vim.vm.ConfigSpec())
       spec = vmconfig.AddDisk(spec)
       try:
          LogOp(vm.Reconfigure, primaryVm, spec)
       except:
          Log("Exception raised during disk add as expected")
       else:
          raise Exception("Disk add allowed")

       disk = vmconfig.CheckDevice(primaryVm.GetConfig(),
                                   vim.vm.device.VirtualDisk)[-1]
       spec = vim.vm.ConfigSpec(deviceChange=[
          vim.vm.device.VirtualDeviceSpec(device=disk, operation="edit")
                                             ])
       try:
          LogOp(vm.Reconfigure, primaryVm, spec)
       except:
          Log("Exception raised during disk edit as expected")
       else:
          raise Exception("Disk edit allowed")

       spec.deviceChange[0].operation="remove"
       try:
          LogOp(vm.Reconfigure, primaryVm, spec)
       except:
          Log("Exception raised during disk remove as expected")
       else:
          raise Exception("Disk remove allowed")

    # Enable Secondary VM
    Log("Enabling secondary VM")
    ft.EnableSecondary(ftMgr, primaryVm, secondaryUuid)
    Log("Secondary VM enabled successfully")
    ftState = FTState.enabled
    if primaryPowerState == PowerState.poweredOn:
       ftState = FTState.needSecondary
    CheckFTState(primaryVm, ftState)
    CheckNeedSecondaryReason(primaryVm, None)
    ReloadSecondary(secondarySi, secondaryVm)
    CheckFTState(secondaryVm, FTState.enabled, False)
    # Negative test: test enable on secondary VM again
    try:
       ft.EnableSecondary(ftMgr, primaryVm, secondaryUuid)
    except vim.Fault.SecondaryVmAlreadyEnabled as e:
       Log("Caught SecondaryAlreadyEnabled exception as expected")
    else:
       raise Exception("Did not hit exception enabling secondary")

def QueryFTCompatibility(si, primaryVm, forLegacyFt):
   numTests = 15
   successTests = 0
   faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)
   if faults is None or len(faults) == 0:
      successTests += 1
   else:
      Log("Unexpected Fault generated %s" % faults)

   # Test nestedHV
   spec = vim.vm.ConfigSpec(nestedHVEnabled=True)
   LogOp(vm.Reconfigure, primaryVm, spec)
   faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)
   if faults is not None and len(faults) > 0 and \
      isinstance(faults[0], vim.fault.InvalidVmConfig):
      successTests += 1
      Log("Fault %s raised as expected" % faults[0])
      spec.nestedHVEnabled = False
      LogOp(vm.Reconfigure, primaryVm, spec)
   else:
      Log("Unexpected faults: %s" % faults)

   # Test numCPU limit
   numCPUs = 9
   oldCPUs = primaryVm.config.hardware.numCPU
   LogOp(vm.Reconfigure, primaryVm, vim.vm.ConfigSpec(numCPUs=numCPUs))
   faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)
   if faults is not None and \
      isinstance(faults[0], vim.fault.NumVirtualCpusIncompatible):
      successTests += 1
      Log("Fault %s raised as expected" % faults)
   else:
      Log("Fault not thrown when setting numCPU > allowed: %s" % faults)
   LogOp(vm.Reconfigure, primaryVm, vim.vm.ConfigSpec(numCPUs=oldCPUs))

   # Test memoryMB limit
   newMemoryMB = 1024 * 129
   oldMemoryMB = primaryVm.config.hardware.memoryMB
   LogOp(vm.Reconfigure, primaryVm, vim.vm.ConfigSpec(memoryMB=newMemoryMB))
   faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)
   if faults is not None and len(faults) > 0 and \
      isinstance(faults[0], vim.fault.MemorySizeNotSupported):
      successTests += 1
      Log("Fault %s raised as expected" % faults[0])
   else:
      Log("Fault not thrown when setting memoryMB > allowed")

   LogOp(vm.Reconfigure, primaryVm, vim.vm.ConfigSpec(memoryMB=oldMemoryMB))

   # Test controllers for ftcpt
   specDevice = [(vmconfig.AddScsiCtlr(vim.vm.ConfigSpec(), ctlrType="buslogic"),
                  vim.vm.device.VirtualBusLogicController,
                  True),
                 (vmconfig.AddUSBCtlr(vim.vm.ConfigSpec()),
                  vim.vm.device.VirtualUSBController,
                  forLegacyFt),
                ]
   for addSpec, device, posTest in specDevice:
      LogOp(vm.Reconfigure, primaryVm, addSpec)
      faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)
      if not posTest:
         if faults is not None and len(faults) > 0 and \
            isinstance(faults[0], vim.fault.DeviceControllerNotSupported):
            successTests += 1
            Log("Fault %s raised as expected" % faults[0])
         else:
            Log("Fault not thrown when using %s device" % device)
      else:
         if faults is not None and len(faults) > 0:
            Log("Fault thrown when not expected for %s controller" % device)
         else:
            successTests += 1
            Log("%s Controller added as expected" % device)
      ctlrs = vmconfig.CheckDevice(primaryVm.GetConfig(), device)
      spec = vmconfig.RemoveDeviceFromSpec(vim.vm.ConfigSpec(), ctlrs[-1])
      LogOp(vm.Reconfigure, primaryVm, spec)

   # Test non-persistent disk
   spec = vmconfig.AddScsiCtlr(vim.vm.ConfigSpec())
   spec = vmconfig.AddDisk(spec,
      diskmode=vim.vm.device.VirtualDiskOption.DiskMode.nonpersistent)
   LogOp(vm.Reconfigure, primaryVm, spec)
   faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)
   if faults is not None and len(faults) > 0 and \
      isinstance(faults[0], vim.fault.VirtualDiskModeNotSupported):
      successTests += 1
      Log("Fault %s raised as expected" % faults[0])
   else:
      Log("Fault not thrown when using non persistent disk")
   ctlrs = vmconfig.CheckDevice(primaryVm.GetConfig(), vim.vm.device.VirtualSCSIController)
   disks = vmconfig.CheckDevice(primaryVm.GetConfig(), vim.vm.device.VirtualDisk)
   fileOp = vim.vm.device.VirtualDeviceSpec.FileOperation.destroy
   spec = vmconfig.RemoveDeviceFromSpec(vim.vm.ConfigSpec(), disks[-1], fileOp)
   spec = vmconfig.RemoveDeviceFromSpec(spec, ctlrs[-1])
   LogOp(vm.Reconfigure, primaryVm, spec)

   # Test independent-persistent disk
   spec = vmconfig.AddScsiCtlr(vim.vm.ConfigSpec())
   spec = vmconfig.AddDisk(spec,
      diskmode=vim.vm.device.VirtualDiskOption.DiskMode.independent_persistent)
   LogOp(vm.Reconfigure, primaryVm, spec)
   faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)

   if forLegacyFt:
      if faults is not None and len(faults) > 0 and \
         isinstance(faults[0], vim.fault.VirtualDiskModeNotSupported):
         successTests += 1
         Log("Fault %s raised as expected" % faults[0])
      else:
         Log("Fault not thrown when using persistent disk %s" % device)
   else:
      if faults is not None and len(faults) > 0:
         Log("Fault thrown when not expected for %s disk: %s" % (device, faults))
      else:
         successTests += 1
         Log("%s Device added for checkpointing as expected" % device)

   ctlrs = vmconfig.CheckDevice(primaryVm.GetConfig(), vim.vm.device.VirtualSCSIController)
   disks = vmconfig.CheckDevice(primaryVm.GetConfig(), vim.vm.device.VirtualDisk)
   fileOp = vim.vm.device.VirtualDeviceSpec.FileOperation.destroy
   spec = vmconfig.RemoveDeviceFromSpec(vim.vm.ConfigSpec(), disks[-1], fileOp)
   spec = vmconfig.RemoveDeviceFromSpec(spec, ctlrs[-1])
   LogOp(vm.Reconfigure, primaryVm, spec)

   # Test seSparse disk
   spec = vmconfig.AddScsiCtlr(vim.vm.ConfigSpec())
   spec = vmconfig.AddDisk(spec, backingType="seSparse")
   LogOp(vm.Reconfigure, primaryVm, spec)
   faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)
   if faults is not None and len(faults) > 0 and \
      isinstance(faults[0], vim.fault.DeviceBackingNotSupported):
      successTests += 1
      Log("Fault %s raised as expected" % faults[0])
   else:
      Log("Fault not thrown when adding SESparse")
   ctlrs = vmconfig.CheckDevice(primaryVm.GetConfig(), vim.vm.device.VirtualSCSIController)
   disks = vmconfig.CheckDevice(primaryVm.GetConfig(), vim.vm.device.VirtualDisk)
   fileOp = vim.vm.device.VirtualDeviceSpec.FileOperation.destroy
   spec = vmconfig.RemoveDeviceFromSpec(vim.vm.ConfigSpec(), disks[-1], fileOp)
   spec = vmconfig.RemoveDeviceFromSpec(spec, ctlrs[-1])
   LogOp(vm.Reconfigure, primaryVm, spec)

   # Test NPIV
   if not forLegacyFt:
      spec = vim.vm.ConfigSpec(npivWorldWideNameOp="generate",
                               npivDesiredNodeWwns=2,
                               npivDesiredPortWwns=3)
      LogOp(vm.Reconfigure, primaryVm, spec)
      faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)
      if faults is not None and len(faults) > 0 and \
         isinstance(faults[0], vim.fault.InvalidVmConfig):
         successTests += 1
         Log("NPIV Fault %s raised as expected" % faults[0])
      else:
         Log("Fault not thrown when setting NPIV")
      spec = vim.vm.ConfigSpec(npivWorldWideNameOp="remove")
      LogOp(vm.Reconfigure, primaryVm, spec)
   else:
      successTests += 1

   # Test snapshot
   if not forLegacyFt:
      LogOp(vm.CreateSnapshot, primaryVm, 'queryft', '', False, False)
      faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)
      if faults is not None and len(faults) > 0 and \
         isinstance(faults[0], vim.fault.VmFaultToleranceConfigIssue):
         successTests += 1
         Log("Snapshot Fault %s raised as expected" % faults[0])
      else:
         Log("Fault not thrown for existing Snapshot")

      LogOp(vm.RemoveAllSnapshots, primaryVm)
   else:
      successTests += 1

   # Test ide disks
   spec = vmconfig.AddIdeDisk(vim.vm.ConfigSpec())
   LogOp(vm.Reconfigure, primaryVm, spec)

   faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)
   if not forLegacyFt:
      if faults is not None and len(faults) > 0 and \
         isinstance(faults[0], vim.fault.DeviceControllerNotSupported):
         successTests += 1
         Log("Fault %s raised as expected" % faults[0])
      else:
         Log("Fault not thrown when using %s device" % device)
   else:
      if faults is not None and len(faults) > 0:
         Log("Fault thrown when not expected for %s controller" % device)
      else:
         successTests += 1
         Log("%s Controller added for recordReplay as expected" % device)
   disks = vmconfig.CheckDevice(primaryVm.GetConfig(), vim.vm.device.VirtualDisk, {'controllerKey': 200})
   spec = vmconfig.RemoveDeviceFromSpec(vim.vm.ConfigSpec(), disks[0])
   LogOp(vm.Reconfigure, primaryVm, spec)

   # Can't test template as markAsTemplate is not supported via
   # hostd

   # Test multi-writer
   disk = vmconfig.CheckDevice(primaryVm.GetConfig(), vim.vm.device.VirtualDisk)[-1]
   spec = vim.vm.ConfigSpec(deviceChange=[vim.vm.device.VirtualDeviceSpec(device=disk, operation="edit")])
   disk.backing.sharing = vim.vm.device.VirtualDisk.Sharing.sharingMultiWriter
   LogOp(vm.Reconfigure, primaryVm, spec)

   faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)
   if not forLegacyFt:
      if faults is not None and len(faults) > 0 and \
         isinstance(faults[0], vim.fault.MultiWriterNotSupported):
         successTests += 1
         Log("Fault %s raised as expected" % faults[0])
      else:
         Log("Fault not thrown when using %s disk" % disk)
   else:
      if faults is not None and len(faults) > 0:
         Log("Fault thrown when not expected for %s disk" % disk)
      else:
         successTests += 1
         Log("%s multi-writer set for recordReplay as expected" % disk)

   disk.backing.sharing = vim.vm.device.VirtualDisk.Sharing.sharingNone
   LogOp(vm.Reconfigure, primaryVm, spec)

   # Test cbrc
   disk = vmconfig.CheckDevice(primaryVm.GetConfig(), vim.vm.device.VirtualDisk)[-1]

   # Enable digest on the disk
   devSpec = vim.cbrc.DeviceSpec(vm=primaryVm, deviceKey=disk.key)
   cbrcManager = si.RetrieveInternalContent().cbrcManager
   WaitForTask(LogOp(cbrcManager.ConfigureDigest, [devSpec], True))

   # Then enable it on the VM
   spec = vim.vm.ConfigSpec(deviceChange=[vim.vm.device.VirtualDeviceSpec(device=disk, operation="edit")])
   spec.deviceChange[0].device.backing.digestEnabled = True

   LogOp(vm.Reconfigure, primaryVm, spec)

   faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)
   if not forLegacyFt:
      if faults is not None and len(faults) > 0 and \
         isinstance(faults[0], vim.fault.DigestNotSupported):
         successTests += 1
         Log("Fault %s raised as expected" % faults[0])
      else:
         Log("Fault (%s) not thrown when using %s disk" % (faults, disk))
   else:
      if faults is not None and len(faults) > 0:
         Log("Fault (%s) thrown when not expected for %s disk" % (faults, disk))
      else:
         successTests += 1
         Log("%s CBRC set for recordReplay as expected" % disk)

   # Disable digest on the VM, then disk
   spec.deviceChange[0].device.backing.digestEnabled = False
   LogOp(vm.Reconfigure, primaryVm, spec)
   WaitForTask(LogOp(cbrcManager.ConfigureDigest, [devSpec], False))

   spec = vmconfig.AddSataCtlr(vim.vm.ConfigSpec())
   spec = vmconfig.AddSataDisk(spec)
   LogOp(vm.Reconfigure, primaryVm, spec)

   faults = ft.QueryFaultToleranceCompatibility(primaryVm, forLegacyFt)
   if forLegacyFt:
      if faults is not None and len(faults) > 0 and \
         isinstance(faults[0], vim.fault.DeviceNotSupported):
         successTests += 1
         Log("Fault %s raised as expected" % faults[0])
      else:
         Log("Fault (%s) not thrown when using %s disk" % (faults, disk))
   else:
      if faults is not None and len(faults) > 0:
         Log("Fault (%s) thrown when not expected for %s disk" % (faults, disk))
      else:
         successTests += 1

   ctlr = vmconfig.CheckDevice(primaryVm.GetConfig(),
                               vim.vm.device.VirtualSATAController)[0]
   disks = vmconfig.CheckDevice(primaryVm.GetConfig(),
                                vim.vm.device.VirtualDisk,
                                {'controllerKey': ctlr.key})
   spec = vmconfig.RemoveDeviceFromSpec(vim.vm.ConfigSpec(), ctlr)
   spec = vmconfig.RemoveDeviceFromSpec(spec, disks[0])
   LogOp(vm.Reconfigure, primaryVm, spec)


   if successTests != numTests:
      raise Exception("QueryFTCompatibility tests failed")

def NestedHV(primaryVm):
   spec = vim.vm.ConfigSpec(nestedHVEnabled=False)
   try:
      LogOp(vm.Reconfigure, primaryVm, spec)
   except Exception as e:
      raise Exception("Exception raised while disabling nestedHV: %s" % e)

   spec.SetNestedHVEnabled(True)
   try:
      LogOp(vm.Reconfigure, primaryVm, spec)
   except vim.fault.VmConfigIncompatibleForFaultTolerance as e:
      Log("Nested HV reconfig failed as expected")
   else:
      raise Exception("Did not hit exception enabling nested HV")

def TestMonitorType(primaryVm):
   flags = vim.vm.FlagInfo(monitorType="stats")
   spec = vim.vm.ConfigSpec(flags=flags)
   try:
      LogOp(vm.Reconfigure, primaryVm, spec)
   except vim.fault.VmConfigIncompatibleForFaultTolerance as e:
      Log("Monitor type threw fault as expected : %s" % e)
   else:
      raise Exception("Did not hit exception when changing monitorType")

def VirtualE1000e(primaryVm, supported):
   spec = vmconfig.AddNic(vim.vm.ConfigSpec(), nicType = "e1000e")
   try:
      LogOp(vm.Reconfigure, primaryVm, spec)
   except vim.fault.VmConfigIncompatibleForFaultTolerance as e:
      if supported:
         Log("Adding e1000e device failed as expected")
      else:
         raise Exception("Hit exception adding e1000e device")
   else:
      if supported:
         raise Exception("Did not hit exception adding e1000e device")
      else:
         Log("Added e1000e successfully")

def VirtualNic(primaryVm):
   spec = vmconfig.AddNic(vim.vm.ConfigSpec(), nicType = "e1000")
   LogOp(vm.Reconfigure, primaryVm, spec)

   nic = vmconfig.CheckDevice(primaryVm.GetConfig(),
                              vim.vm.device.VirtualEthernetCard)
   vm.PowerOn(primaryVm)

   # try to edit nic
   try:
      spec = vim.vm.ConfigSpec(
         deviceChange=[vim.vm.device.VirtualDeviceSpec(
            device=nic[0],
            operation=vim.vm.device.VirtualDeviceSpec.Operation.edit)]
      )
      LogOp(vm.Reconfigure, primaryVm, spec)
   except vim.fault.VmConfigIncompatibleForFaultTolerance:
      Log("Hot-edit of nic failed as expected")
   else:
      raise Exception("Hot-edit of nic was allowed")
   finally:
      LogOp(vm.PowerOff, primaryVm)
      spec = vmconfig.RemoveDeviceFromSpec(vim.vm.ConfigSpec(), nic[-1])
      LogOp(vm.Reconfigure, primaryVm, spec)

def TestAddDisk(primaryVm):
   spec = vim.vm.ConfigSpec()
   spec = vmconfig.AddScsiCtlr(spec)
   spec = vmconfig.AddDisk(spec)
   try:
      LogOp(vm.Reconfigure, primaryVm, spec)
   except vim.fault.VmConfigIncompatibleForFaultTolerance as e:
      Log("Adding disk to FT VM failed as expected")
   else:
      raise Exception("Did not hit exception adding disk to SMP FT VM")

def CheckCdrom(testVm, isoFilePath):
   """
   Check whether "testVm" has a CDROM device backed by "isoFilePath".
   """
   devices = vmconfig.CheckDevice(testVm.config,
                                  vim.vm.Device.VirtualCdrom,
                                  {'backing.fileName': isoFilePath})
   if len(devices) != 1:
      raise Exception('Failed to find cdrom backed with %s!' % isoFilePath)

def AddCdrom(primaryVm):
   """
   Add an iso file backed CDROM device to the given VM.
   """
   isofile='[] /usr/lib/vmware/isoimages/linux.iso'
   Log("Adding CDROM")
   cspec = vim.vm.ConfigSpec()
   vmconfig.AddCdrom(cspec, isoFilePath=isofile)
   try:
      LogOp(vm.Reconfigure, primaryVm, cspec)
   except:
      raise
   CheckCdrom(primaryVm, isofile)

def TestReconfigCdromBacking(primaryVm, primarySi, secondaryVm, secondarySi):
   """
   Reconfigure the CDROM backing file and verify the CDROM reconfiguration
   is preserved after FT failovers.
   """
   isofile='[] /usr/lib/vmware/isoimages/windows.iso'
   Log("Testing reconfig CDROM backing")
   connect.SetSi(primarySi)
   cdrom = vmconfig.CheckDevice(primaryVm.config,
                                vim.vm.Device.VirtualCdrom)[0]
   cspec = vim.vm.ConfigSpec()
   backing = vim.vm.Device.VirtualCdrom.IsoBackingInfo(fileName=isofile)
   cdrom.backing = backing
   vmconfig.AddDeviceToSpec(cspec, cdrom,
                            vim.vm.Device.VirtualDeviceSpec.Operation.edit)
   LogOp(vm.Reconfigure, primaryVm, cspec)
   CheckCdrom(primaryVm, isofile)

   # Allow some time for the cdrom reconfig to be replicated to secondary.
   time.sleep(1)

   primaryCfgPath = primaryVm.config.files.vmPathName
   secondaryCfgPath = secondaryVm.config.files.vmPathName
   ftMgr = host.GetFaultToleranceMgr(primarySi)
   ftMgr2 = host.GetFaultToleranceMgr(secondarySi)
   secondaryUuid = secondaryVm.GetConfig().GetInstanceUuid()

   TestMakePrimary(ftMgr, secondaryUuid, primarySi, primaryVm,
                   secondarySi, secondaryVm)

   connect.SetSi(secondarySi)
   CheckCdrom(secondaryVm, isofile)

   RestartFT(secondaryVm, primaryVm, secondarySi, primarySi, primaryCfgPath)

   Log("Failing over again to restore the original primary.")
   TestMakePrimary(ftMgr2, secondaryUuid, secondarySi, secondaryVm,
                   primarySi, primaryVm)

   connect.SetSi(primarySi)
   CheckCdrom(primaryVm, isofile)
   RestartFT(primaryVm, secondaryVm, primarySi, secondarySi, secondaryCfgPath)

def RestartFT(primaryVm, secondaryVm, primarySi, secondarySi, secondaryCfgPath):
   # Sanity checks. primary should be in needSecondary, secondary should be
   # enabled.
   CheckFTRole(primaryVm, 1)
   CheckFTState(primaryVm, FTState.needSecondary)
   ReloadSecondary(secondarySi, secondaryVm)
   CheckFTRole(secondaryVm, 2)
   CheckFTState(secondaryVm, FTState.enabled, False)

   # Perform VMotion to resume FT protection
   Log("Doing FT VMotion to re-enable FT")
   saveSi = connect.GetSi()
   connect.SetSi(primarySi)
   LogOp(vm.Migrate, primaryVm, primarySi, secondarySi, secondaryCfgPath, True,
         ftvmotion, ftType=ftsubtype, destVm=secondaryVm)
   WaitForFTState(primaryVm, FTState.running)
   WaitForFTState(secondaryVm, FTState.running)
   connect.SetSi(saveSi)

def RoundtripVmotion(theVm, vmName, srcSi, dstSi, cfgPath):
   saveSi = connect.GetSi()
   connect.SetSi(srcSi)
   Log("Doing 1st VMotion of VM")
   LogOp(vm.Migrate, theVm, srcSi, dstSi, cfgPath, False)
   time.sleep(5)
   connect.SetSi(dstSi)
   theVm = folder.Find(vmName)
   if theVm == None:
      raise Exception("No VM with name %s found!" % vmName)
   Log("Doing 2nd VMotion of VM")
   LogOp(vm.Migrate, theVm, dstSi, srcSi, cfgPath, False)
   time.sleep(1)
   connect.SetSi(saveSi)

def TestSnapshots(primaryVm, primarySi, secondaryVm, secondarySi):
   # Take snapshot with memory, catch fault
   oldDisks = vmconfig.CheckDevice(primaryVm.GetConfig(), vim.vm.Device.VirtualDisk)

   try:
      LogOp(vm.CreateSnapshot, primaryVm, "snap1", "invalid memory snapshot",
            memory=True, quiesce=True)
   except vmodl.fault.NotSupported as e:
      Log("Caught exception during CreateSnapshot as expected")
   else:
      raise Exception("Snapshot with memory allowed")

   # Take snapshot w/o memory, verify snapshot
   snapshot = LogOp(vm.CreateSnapshot, primaryVm, "snap2",
                    "without memory snapshot", memory=False, quiesce=True)
   if primaryVm.snapshot is None:
      raise Exception("VM has no snapshot exposed")
   if len(primaryVm.rootSnapshot) < 1:
      raise Exception("VM has no rootSnapshot exposed")
   if snapshot._GetMoId() != primaryVm.snapshot.currentSnapshot._GetMoId():
      raise Exception("Current snapshot is not correct")

   # Remove snapshot
   LogOp(vm.RemoveSnapshot, snapshot, True, True)

   newDisks = vmconfig.CheckDevice(primaryVm.GetConfig(), vim.vm.Device.VirtualDisk)

   for i in range(len(oldDisks)):
      if oldDisks[i].backing.fileName != newDisks[i].backing.fileName:
         raise Exception("Disk filename differs after snapshot old: %s != new: %s" %
                         (oldDisks[i].backing.fileName, newDisks[i].backing.fileName))

   # Take snapshot, verify, remove all snapshots, verify
   snapshot = LogOp(vm.CreateSnapshot, primaryVm, "snap3",
                    "without memory, remove all", memory=False, quiesce=True)
   if snapshot._GetMoId() != primaryVm.snapshot.currentSnapshot._GetMoId():
      raise Exception("Current snapshot is not correct (2nd)")

   LogOp(vm.RemoveAllSnapshots, primaryVm, True)
   if primaryVm.snapshot is not None and \
      primaryVm.snapshot.currentSnapshot is not None:
      raise Exception("Snapshot remains after being removed")

   try:
      connect.SetSi(secondarySi)
      LogOp(vm.CreateSnapshot, secondaryVm, "snap4",
            "invalid secondary snapshot", memory=False, quiesce=True)
   except vim.fault.InvalidOperationOnSecondaryVm as e:
      Log("Caught exception during CreateSnapshot on secondary as expected")
   else:
      raise Exception("Snapshot on Secondary allowed")

   connect.SetSi(primarySi)
   # Take snapshot, failover, delete snapshot on (new secondary, primaryVm)
   snapshot = LogOp(vm.CreateSnapshot, primaryVm, "snap5",
                    "old primary snapshot", memory=False, quiesce=True)

   primaryCfgPath = primaryVm.config.files.vmPathName
   secondaryCfgPath = secondaryVm.config.files.vmPathName
   ftMgr = host.GetFaultToleranceMgr(primarySi)
   ftMgr2 = host.GetFaultToleranceMgr(secondarySi)
   secondaryUuid = secondaryVm.GetConfig().GetInstanceUuid()

   TestMakePrimary(ftMgr, secondaryUuid, primarySi, primaryVm,
                   secondarySi, secondaryVm)

   LogOp(vm.RemoveSnapshot, snapshot, True)

   RestartFT(secondaryVm, primaryVm, secondarySi, primarySi,
             primaryCfgPath)

   # The VM seems to take a bit of time to really get going
   time.sleep(10)

   Log("Failing over again to restore the original primary.")
   TestMakePrimary(ftMgr2, secondaryUuid, secondarySi, secondaryVm,
                   primarySi, primaryVm)

   RestartFT(primaryVm, secondaryVm, primarySi, secondarySi,
             secondaryCfgPath)

   if primaryVm.snapshot is not None and \
      primaryVm.snapshot.currentSnapshot is not None:
      raise Exception("Snapshot remains after being removed")

def ConnectToHost(host, options):
    sslContext = None
    if options.GetKeyValue('nosslcheck') or \
       host in ['localhost', '127.0.0.1', '::1']:
       sslContext = ssl._create_unverified_context()
    return SmartConnect(host=host,
                        user=options.GetKeyValue('user'),
                        pwd=options.GetKeyValue('pwd'),
                        sslContext=sslContext)

def main():
   global status
   supportedArgs = [ (["P:", "primary host="], "localhost", "Primary host name", "primaryHost"),
                     (["S:", "secondary host="], "localhost", "Secondary host name", "secondaryHost"),
                     (["T:", "tertiary host="], "", "Third host name for VMotion test", "tertiaryHost"),
                     (["d:", "shared datastore name="], "storage1", "shared datastore name", "dsName"),
                     (["secondaryDatastore="], "", "Secondary datastore name", "secondaryDatastore"),
                     (["k:", "keep="], "0", "Keep configs", "keep"),
                     (["l:", "leaveRunning="], False, "Leave FT VMs running", "leaveRunning"),
                     (["L:", "leaveRegistered="], False, "Leave FT VMs configured but not powered on", "leaveRegistered"),
                     (["e:", "useExisting="], False, "Use existing VM", "useExistingVm"),
                     (["r:", "check RecordReplay state="], True, "Validate Record/Replay states", "checkRRState"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd"),
                     (["v:", "VM name="], "vmFT", "Name of the virtual machine", "vmname"),
                     (["t:", "FT type="], "smp", "Type of fault tolerance [smp]", "ftType"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter"),
                     (["primaryFtNic="], "vmk0", "Primary ft logging nic", "primaryFtNic"),
                     (["secondaryFtNic="], "vmk0", "Secondary ft logging nic", "secondaryFtNic"),
                     (["tertiaryFtNic="], "vmk0", "Tertiary ft logging nic", "tertiaryFtNic"),
                     (["primaryVmotionNic="], "vmk0", "Primary vmotion nic", "primaryVmotionNic"),
                     (["secondaryVmotionNic="], "vmk0", "Secondary vmotion nic", "secondaryVmotionNic"),
                     (["tertiaryVmotionNic="], "vmk0", "Tertiary vmotion nic", "tertiaryVmotionNic"),
                   ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage"),
                        (['quick'], False, 'Do a quick-n-dirty test, instead of the default longer one', 'quick'),
                        (['M', 'mandatoryTest'], False, 'Mandatory test and '
                         'fail on unsupported host hardware', 'mandatoryTest'),
                        (['no-check-certificate'], False,
                         'Dsiable SSL certificate verification if the server '
                         'is a remote ESX host or a vCenter server',
                         'nosslcheck')
                      ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Process command line
   primaryName = args.GetKeyValue("vmname")
   numiter = int(args.GetKeyValue("iter"))
   keep = int(args.GetKeyValue("keep"))
   leaveRegistered = bool(args.GetKeyValue("leaveRegistered"))
   leaveRunning = bool(args.GetKeyValue("leaveRunning"))
   useExistingVm = bool(args.GetKeyValue("useExistingVm"))
   global checkRRState
   checkRRState = bool(args.GetKeyValue("checkRRState"))
   global ftType
   ftType = args.GetKeyValue("ftType")
   global ftsubtype
   if ftType == "smp":
      checkRRState = False # no RR
      ftsubtype = vim.Host.FaultToleranceManager.FaultToleranceType.fault_tolerance_using_checkpoints
   dsName = args.GetKeyValue("dsName")
   primaryHost = args.GetKeyValue("primaryHost")
   secondaryHost = args.GetKeyValue("secondaryHost")
   tertiaryHost = args.GetKeyValue("tertiaryHost")
   if primaryHost == secondaryHost:
      secondaryName = "_" + primaryName
   else:
      secondaryName = primaryName
   orphanedSecondaryName = primaryName + "_orphaned"

   # Only run the negative migration test if secondary host is localhost and
   # that either VMBLD or BLDTYPE is set to obj/opt.  This is conservative but
   # is true for CAT runs.
   testMigFail = False
   if secondaryHost == 'localhost':
      bldType = os.environ.get('VMBLD', '') or os.environ.get('BLDTYPE', '')
      testMigFail = bldType and bldType in ['obj', 'opt']

   for i in range(numiter):
       primaryVm = None
       primarySi = None
       secondarySi = None
       tertiarySi = None
       try:
           # Connect to tertiary host, if provided.
           if tertiaryHost != "":
              tertiarySi = ConnectToHost(tertiaryHost, args)
              Log("Connected to VMotion test host, VMotion will be tested")
              CleanupVm(primaryName)
              CleanupVm(secondaryName)
              if len(FindNicType(tertiarySi, ftLoggingNicType)) == 0:
                 SelectVnic(tertiarySi, args.GetKeyValue("tertiaryFtNic"), ftLoggingNicType)
              if len(FindNicType(tertiarySi, vmotionNicType)) == 0:
                 SelectVnic(tertiarySi, args.GetKeyValue("tertiaryVmotionNic"), vmotionNicType)

           primarySi = ConnectToHost(primaryHost, args)
           Log("Connected to Primary host")

           if len(FindNicType(primarySi, ftLoggingNicType)) == 0:
              SelectVnic(primarySi, args.GetKeyValue("primaryFtNic"), ftLoggingNicType)
           if len(FindNicType(primarySi, vmotionNicType)) == 0:
              SelectVnic(primarySi, args.GetKeyValue("primaryVmotionNic"), vmotionNicType)

           dsName = GetDatastore(primarySi, dsName)
           Log('Using datastore: %s' % dsName)
           SummarizeHost(primarySi, primaryHost)

           # Cleanup from previous runs
           if not useExistingVm:
               CleanupVm(primaryName)
               CleanDirs(primarySi, dsName, primaryName, ftType)

           secondarySi = ConnectToHost(secondaryHost, args)
           Log("Connected to Secondary host")

           secondaryDatastore = args.GetKeyValue("secondaryDatastore")
           if secondaryDatastore == "":
              secondaryDatastore = dsName
           else:
              secondaryDatastore = GetDatastore(secondarySi, secondaryDatastore)

           if len(FindNicType(secondarySi, ftLoggingNicType)) == 0:
              SelectVnic(secondarySi, args.GetKeyValue("secondaryFtNic"), ftLoggingNicType)
           if len(FindNicType(secondarySi, vmotionNicType)) == 0:
              SelectVnic(secondarySi, args.GetKeyValue("secondaryVmotionNic"), vmotionNicType)

           # Cleanup from previous runs
           connect.SetSi(secondarySi)
           CleanupVm(secondaryName, True)
           CleanDirs(secondarySi, secondaryDatastore, secondaryName, ftType)

           CleanupVm(orphanedSecondaryName, True)
           CleanDirs(secondarySi, secondaryDatastore, orphanedSecondaryName, ftType)
           connect.SetSi(primarySi)

           if ftType != 'smp':
              Log('Testing R/R FT: UP FT')
           else:
              Log('Testing ftcpt: SMP FT')
              quitTest = False
              for mysi in primarySi, secondarySi, tertiarySi:
                 if mysi == None:
                    continue
                 hostSystem = host.GetHostSystem(mysi)
                 if hostSystem.capability.smpFtSupported == False:
                    quitTest = True
                    msg = "Skipping test: host %s doesn't have Intel EPT or AMD RVI" % \
                        hostSystem.name
                    LogForTestEsx(msg)
              if quitTest:
                 # By default, and as a courtesy, we'll pass the invocation
                 # rather than error out.  The idea being: if this test is
                 # run in the context of some automation (for example,
                 # test-esx), it is somewhat obnoxious to fail the test run
                 # just because the ESX box is on HW earlier than Nehalem or
                 # Barcelona.  However, if the test is mandatory, we will
                 # fail on unsupported host hardware.  This can catch
                 # problems in detecting supported hosts (e.g., PR 987017).
                 if args.GetKeyValue('mandatoryTest'):
                    raise Exception('Missing Intel EPT or AMD RVI support on host')
                 else:
                    return

           # Scrub disks is true for both up-ft and smp-ft to test
           # multi-writer flag.
           scrubDisks = True

           if args.GetKeyValue('quick'):
               QuickTest(dsName=dsName,
                         primarySi=primarySi,
                         secondarySi=secondarySi,
                         primaryName=primaryName,
                         secondaryName=secondaryName,
                         scrubDisks=scrubDisks)
               continue

           # Create new VM
           connect.SetSi(primarySi)
           primaryVm = None
           if useExistingVm:
               primaryVm = folder.Find(primaryName)
               if primaryVm == None:
                   raise Exception("No primary VM with name %s found!" % primaryName)
               Log("Using primary VM %s" % primaryName)
           else:
               Log("Creating primary VM %s" % primaryName)
               # Short delay to avoid colliding with a cleanup.
               time.sleep(5)
               primaryVm = LogOp(vm.CreateQuickDummy,
                                 primaryName,
                                 guest="winXPProGuest",
                                 memory=4,
                                 cdrom=0,
                                 numScsiDisks=1,
                                 scrubDisks=scrubDisks,
                                 datastoreName=dsName)
               AddCdrom(primaryVm);
           # query FT test
           forLegacyFt = False if ftType == "smp" else True

           Log("Testing QueryFaultToleranceCompatibility: forLegacyFt = %s"
               % forLegacyFt)
           QueryFTCompatibility(primarySi, primaryVm, forLegacyFt)

           ftMetadataDir = GetSharedPath(primarySi, primaryVm)

           if ftType == "smp" and primaryVm.config.hardware.numCPU == 1:
              LogOp(vm.Reconfigure, primaryVm, vim.vm.ConfigSpec(numCPUs=2))

           # Get details about primary VM
           primaryUuid = primaryVm.GetConfig().GetInstanceUuid()
           primaryCfgPath = primaryVm.GetConfig().GetFiles().GetVmPathName()
           primaryDir = primaryCfgPath[:primaryCfgPath.rfind("/")]
           Log("Using VM : %s with instanceUuid %s" % (primaryVm.GetName(), primaryUuid))
           CheckFTState(primaryVm, FTState.notConfigured)

           # Create secondary VM
           connect.SetSi(secondarySi)
           Log("Creating secondary VM %s" % secondaryName)
           secondaryVm = LogOp(vm.CreateQuickSecondary,
                               secondaryName,
                               primaryVm,
                               datastoreName=secondaryDatastore,
                               numScsiDisks=1,
                               scrubDisks=scrubDisks,
                               ftType=ftType,
                               ftMetadataDir=ftMetadataDir)

           if secondaryVm == None:
               raise Exception("Secondary VM creation failed")

           Log("Creating orphaned secondary VM %s" % orphanedSecondaryName)
           orphanedVm = LogOp(vm.CreateQuickSecondary,
                              orphanedSecondaryName,
                              primaryVm,
                              datastoreName=secondaryDatastore,
                              numScsiDisks=1,
                              scrubDisks=scrubDisks,
                              ftType=ftType,
                              ftMetadataDir=ftMetadataDir)
           if orphanedVm == None:
               raise Exception("Orphaned secondary VM creation failed")

           secondaryUuid = secondaryVm.GetConfig().GetInstanceUuid()
           secondaryCfgPath = secondaryVm.GetConfig().GetFiles().GetVmPathName()
           Log("Created secondary VM %s" % secondaryVm.GetName())
           Log("Secondary VM: instanceUuid %s" % secondaryUuid)
           Log("Secondary cfg path: %s" % secondaryCfgPath)

           ReloadSecondary(secondarySi, secondaryVm)
           CheckFTState(secondaryVm, FTState.disabled, False)

           if ftType == "smp":
              # SMP-FT supports hot start
              Log("Powering on Primary VM.")
              LogOp(vm.PowerOn, primaryVm)

           ##  Configure some additional config variables needed for FT
           ##  This should eventually be done automatically at FT Vmotion time
           Log("Setting up extra config settings for the primary VM...")
           connect.SetSi(primarySi)
           extraCfgs = []
           cSpec = vim.Vm.ConfigSpec()
           if ftType == "smp": # some of these options are temporary
              AddExtraConfig(extraCfgs, "ftcpt.maxDiskBufferPages", "0")
              AddExtraConfig(extraCfgs, "sched.mem.pshare.enable", "FALSE")
              AddExtraConfig(extraCfgs, "sched.mem.fullreservation", "TRUE")
              AddExtraConfig(extraCfgs, "monitor_control.disable_mmu_largepages", "TRUE")
              AddExtraConfig(extraCfgs, "migration.dataTimeout", "2000")
              cSpec.flags = vim.vm.FlagInfo(faultToleranceType=FTType.checkpointing)
              cSpec.files = vim.vm.FileInfo()
              cSpec.files.ftMetadataDirectory = ftMetadataDir
           else:
              cSpec.flags = vim.vm.FlagInfo(recordReplayEnabled=True)
              AddExtraConfig(extraCfgs, "replay.allowBTOnly", "TRUE")
              AddExtraConfig(extraCfgs, "replay.allowFT", "TRUE")
           if primaryName != secondaryName:
              AddExtraConfig(extraCfgs, "ft.allowUniqueName", "TRUE")

           cSpec.SetExtraConfig(extraCfgs)
           Log("Reconfiguring Primary VM.");
           LogOp(vm.Reconfigure, primaryVm, cSpec)

           # Register secondary VM
           Log("Register secondary VM with the powered off primary")
           ftMgr = host.GetFaultToleranceMgr(primarySi)
           ft.RegisterSecondary(ftMgr, primaryVm, secondaryUuid,
                                secondaryCfgPath)
           Log("Secondary VM registered successfully")

           Log("Verifying orphaned secondary is still a secondary")
           ReloadSecondary(secondarySi, orphanedVm)
           CheckFTRole(orphanedVm, 2)
           if not orphanedVm.config.ftInfo.orphaned:
              raise Exception("Expected VM to be orphaned")
           ReloadSecondary(secondarySi, secondaryVm)
           CheckFTRole(secondaryVm, 2)
           if secondaryVm.config.ftInfo.orphaned:
              raise Exception("Secondary VM not expected to be orphaned")

           # Negative test: try to register secondary again
           Log("Attempt to re-register secondary VM")
           try:
              ftMgr = host.GetFaultToleranceMgr(primarySi)
              ft.RegisterSecondary(ftMgr, primaryVm, secondaryUuid,
                                   secondaryCfgPath)
           except:
              Log("Received exception as expected")
           else:
              raise Exception("Duplicate secondary register succeeded")

           # Verify FT role & state
           CheckFTRole(primaryVm, 1)
           if ftType == "smp":
              CheckFTState(primaryVm, FTState.needSecondary)
           else:
              CheckFTState(primaryVm, FTState.enabled)
           CheckNeedSecondaryReason(primaryVm, None)


           try:
              if ftType == "smp":
                 LogOp(vm.Reconfigure, primaryVm, vim.vm.ConfigSpec(numCPUs=1))
              else:
                 LogOp(vm.Reconfigure, primaryVm, vim.vm.ConfigSpec(numCPUs=2))
           except vim.fault.VmConfigIncompatibleForFaultTolerance as e:
              pass # exception thrown as expected
           else:
              raise Exception("Failed to raise an exception when setting " +
                              "invalid number of vCPUs")

           # Reload and check FT state of secondary VM
           ReloadSecondary(secondarySi, secondaryVm)
           CheckFTRole(secondaryVm, 2)
           CheckFTState(secondaryVm, FTState.enabled, False)
           Log("FT configured successfully.")

           Log("Deleting orphaned secondary.")
           connect.SetSi(secondarySi)
           CleanupVm(orphanedVm, True)
           connect.SetSi(primarySi)

           if ftType == "smp":
              Log("Enabling FT while enabled.");
              SetFtCpt(primaryVm, True)

           if leaveRegistered:
              Log("VMs are configured for FT but not powered on.")
              Disconnect(primarySi)
              Disconnect(secondarySi)
              return

           # PowerOn FT VM
           if ftType != "smp":
              Log("Powering on Primary VM")
              LogOp(vm.PowerOn, primaryVm)

           if leaveRunning:
              Log("Migrating state from primary to secondary VM.")
              LogOp(vm.Migrate, primaryVm, primarySi, secondarySi,
                    secondaryCfgPath, True, ftvmotion, ftType=ftsubtype,
                    destVm=secondaryVm)
              WaitForFTState(primaryVm, FTState.running)
              WaitForFTState(secondaryVm, FTState.running)
              Log("VMs are running with FT protection.")
              Disconnect(primarySi)
              Disconnect(secondarySi)
              return

           # hot vmx*3 is not supported for FT
           TestMonitorType(primaryVm)

           Log("Unregister secondary VM with the powered on primary")
           ft.UnregisterSecondary(ftMgr, primaryVm, secondaryUuid)
           Log("Secondary VM unregistered successfully")
           CheckFTState(primaryVm, FTState.notConfigured)
           CheckNeedSecondaryReason(primaryVm, None)
           ReloadSecondary(secondarySi, secondaryVm)
           CheckFTState(secondaryVm, FTState.disabled, False)

           # Negative tests: test ops after unregistering secondary
           Log("Attempting to disable an unregistered secondary")
           try:
              ft.DisableSecondary(ftMgr, primaryVm, secondaryUuid)
           except vim.Fault.SecondaryVmAlreadyDisabled as e:
              Log("Caught SecondaryVmAlreadyDisabled exception as expected")
           else:
              raise Exception("Did not get SecondaryVmAlreadyDisabled exception")
           Log("Attempting to enable an unregistered secondary")
           try:
              ft.EnableSecondary(ftMgr, primaryVm, secondaryUuid)
           except:
              Log("Caught exception as expected")
           else:
              raise Exception("Did not get an exception")

           Log("Register secondary VM with the powered on primary")
           connect.SetSi(primarySi)
           ftMgr = host.GetFaultToleranceMgr(primarySi)
           ft.RegisterSecondary(ftMgr, primaryVm, secondaryUuid,
                                secondaryCfgPath)
           Log("Secondary VM re-registered successfully")

           # Verify FT role & state
           CheckFTRole(primaryVm, 1)
           CheckFTState(primaryVm, FTState.needSecondary)
           CheckNeedSecondaryReason(primaryVm, None)

           # Reload and check FT state of secondary VM
           ReloadSecondary(secondarySi, secondaryVm)
           CheckFTRole(secondaryVm, 2)
           CheckFTState(secondaryVm, FTState.enabled, False)
           Log("FT reconfigured successfully.")

           if testMigFail:
              # Perform a FT VMotion that will fail
              option = vim.Option.OptionValue(key='poweron.forceFail',
                                              value='FTCpt')
              cspec = vim.Vm.ConfigSpec(extraConfig=[option])
              Log("Reconfiguring VM for negative migration test.");
              LogOp(vm.Reconfigure, primaryVm, cspec)
              try:
                 vm.Migrate(primaryVm, primarySi, secondarySi, secondaryCfgPath,
                            True, ftvmotion, ftType=ftsubtype,
                            destVm=secondaryVm)
              except:
                 Log("FT migration failed as expected")
              WaitForFTState(primaryVm, FTState.needSecondary, 90)
              option = vim.Option.OptionValue(key='poweron.forceFail', value='')
              cspec = vim.Vm.ConfigSpec(extraConfig=[option])
              Log("Reverting previous reconfigure so next migration will succeed.")
              LogOp(vm.Reconfigure, primaryVm, cspec)

           # Perform the FT VMotion
           Log("Migrating state from primary to secondary VM.")
           vm.Migrate(primaryVm, primarySi, secondarySi,
                      secondaryCfgPath, True, ftvmotion, ftType=ftsubtype, destVm=secondaryVm)
           WaitForFTState(primaryVm, FTState.running)
           WaitForFTState(secondaryVm, FTState.running)

           # Run snapshot tests
           if ftType == "smp":
              TestSnapshots(primaryVm, primarySi, secondaryVm, secondarySi)

           Log("Unregister secondary VM while it is running")
           ft.UnregisterSecondary(ftMgr, primaryVm, secondaryUuid)
           Log("Secondary VM unregistered successfully")
           CheckFTState(primaryVm, FTState.notConfigured)
           CheckNeedSecondaryReason(primaryVm, None)
           WaitForPowerState(secondaryVm, secondarySi, PowerState.poweredOff)
           ReloadSecondary(secondarySi, secondaryVm)
           CheckFTState(secondaryVm, FTState.disabled, False)

           if ftType == "smp":
              hostSystem = host.GetHostSystem(primarySi)

              # Turn off FT
              onOverhead = primaryVm.GetConfig().initialOverhead.initialMemoryReservation
              Log("Memory Overhead: %d" % onOverhead)
              Log("Disabling FT.");
              SetFtCpt(primaryVm, False)
              offOverhead = primaryVm.GetConfig().initialOverhead.initialMemoryReservation
              Log("Memory Overhead: %d" % offOverhead)

              Log("Enabling FT.");
              SetFtCpt(primaryVm, True)
              onOverhead2 = primaryVm.GetConfig().initialOverhead.initialMemoryReservation
              Log("Memory Overhead: %d" % onOverhead2)
              if offOverhead > onOverhead or offOverhead > onOverhead2:
                 raise Exception("Unexpected memory overhead")

           Log("Deleting and re-creating secondary")
           connect.SetSi(secondarySi)
           CleanupVm(secondaryVm)
           time.sleep(5)
           secondaryVm = vm.CreateQuickSecondary(secondaryName, primaryVm,
                                                 datastoreName=secondaryDatastore,
                                                 numScsiDisks=1,
                                                 scrubDisks=scrubDisks,
                                                 ftType=ftType,
                                                 ftMetadataDir=ftMetadataDir)
           if secondaryVm == None:
               raise Exception("Secondary VM creation failed")
           secondaryUuid = secondaryVm.GetConfig().GetInstanceUuid()
           secondaryCfgPath = secondaryVm.GetConfig().GetFiles().GetVmPathName()

           # Call GetSharedPath to create metadata dir before register secondary
           _ftMetadataDir = GetSharedPath(primarySi, primaryVm)
           if _ftMetadataDir != ftMetadataDir:
               raise Exception("Created metadata directory at wrong path: %s" %
                               _ftMetadataDir)

           Log("Re-register secondary VM with the powered on primary")
           #connect.SetSi(primarySi)
           ftMgr = host.GetFaultToleranceMgr(primarySi)
           ft.RegisterSecondary(ftMgr, primaryVm, secondaryUuid,
                                secondaryCfgPath)
           Log("Secondary VM reregistered successfully")

           # Verify FT role & state
           CheckFTRole(primaryVm, 1)
           CheckFTState(primaryVm, FTState.needSecondary)
           CheckNeedSecondaryReason(primaryVm, None)

           # Reload and check FT state of secondary VM
           ReloadSecondary(secondarySi, secondaryVm)
           CheckFTRole(secondaryVm, 2)
           CheckFTState(secondaryVm, FTState.enabled, False)
           Log("FT reconfigured successfully.")

           Log("Testing disable/enable with a powered on primary.")
           TestFTDisableEnable(ftMgr, primaryVm, secondaryVm,
                               primarySi, secondarySi)

           RestartFT(primaryVm, secondaryVm, primarySi, secondarySi,
             secondaryCfgPath)

           TestReconfigCdromBacking(primaryVm, primarySi, secondaryVm,
                                    secondarySi)

           Log("Mounting tools installer.")
           try:
              primaryVm.MountToolsInstaller()
           except:
              Log("Mounting tools installer failed, continuing anyway...")
           Log("Testing a generic reconfigure on the primary.")
           LogOp(vm.Reconfigure, primaryVm, vim.vm.ConfigSpec())

           Log("Killing the secondary.")
           ft.TerminateFaultTolerantVM(ftMgr, primaryVm, secondaryUuid)
           WaitForPowerState(secondaryVm, secondarySi, PowerState.poweredOff)
           Log("Verified secondary power state is off.")

           WaitForFTState(primaryVm, FTState.needSecondary)
           CheckNeedSecondaryReason(primaryVm, "userAction")
           RestartFT(primaryVm, secondaryVm, primarySi, secondarySi,
                     secondaryCfgPath)

           if ftType == "smp":
              Log("Killing the secondary.")
              LogOp(secondaryVm.Terminate)
              WaitForPowerState(secondaryVm, secondarySi,
                                PowerState.poweredOff)
              Log("Verified secondary power state is off.")

              WaitForFTState(primaryVm, FTState.needSecondary)
              CheckNeedSecondaryReason(primaryVm, "lostConnection")
              RestartFT(primaryVm, secondaryVm, primarySi, secondarySi,
                        secondaryCfgPath)

           TestMakePrimary(ftMgr, secondaryUuid, primarySi, primaryVm,
                           secondarySi, secondaryVm)

           RestartFT(secondaryVm, primaryVm, secondarySi, primarySi,
                     primaryCfgPath)

           Log("Unmounting tools installer after failover and restart.")
           connect.SetSi(secondarySi)
           try:
              secondaryVm.UnmountToolsInstaller()
           except:
              pass

           Log("Failing over again to restore the original primary.")
           ftMgr2 = host.GetFaultToleranceMgr(secondarySi)
           TestMakePrimary(ftMgr2, secondaryUuid, secondarySi, secondaryVm,
                           primarySi, primaryVm)

           RestartFT(primaryVm, secondaryVm, primarySi, secondarySi,
                     secondaryCfgPath)

           # Test VMotion of primary and secondary, if a third host is given
           if tertiarySi != None:
              Log("Testing primary VMotion")
              RoundtripVmotion(primaryVm, primaryName, primarySi, tertiarySi,
                               primaryCfgPath)
              primaryVm = folder.FindCfg(primaryCfgPath)
              if primaryVm == None:
                 raise Exception("No primary VM at %s found!" % primaryCfgPath)
              Log("Testing secondary VMotion")
              connect.SetSi(secondarySi)
              RoundtripVmotion(secondaryVm, secondaryName, secondarySi,
                               tertiarySi, secondaryCfgPath)
              secondaryVm = folder.FindCfg(secondaryCfgPath)
              if secondaryVm == None:
                 raise Exception("No secondary VM at %s found!" %
                                 secondaryCfgPath)
           else:
              Log("Skipping VMotion test, no -T option specified")

           # Test disabling and enabling FT
           # This kills the secondary as an intentional side-effect
           # so we need to restart it
           TestFTDisableEnable(ftMgr, primaryVm, secondaryVm,
                               primarySi, secondarySi)
           RestartFT(primaryVm, secondaryVm, primarySi, secondarySi,
                     secondaryCfgPath)

           # PowerOff FT VMs. Both should power off.
           Log("Power off Primary VM")
           vm.PowerOff(primaryVm)
           WaitForPowerState(primaryVm, primarySi, PowerState.poweredOff)
           WaitForPowerState(secondaryVm, secondarySi, PowerState.poweredOff)
           CheckNeedSecondaryReason(primaryVm, None)

           CheckFTState(primaryVm, FTState.enabled)
           CheckFTState(secondaryVm, FTState.enabled, isPrimary=False)

           # nested HV reconfigure needs to happen when VM is powered off
           Log("Testing nested HV configure")
           NestedHV(primaryVm)

           # e1000e is not supported for R/R
           Log("Testing virtual e1000e device add")
           VirtualE1000e(primaryVm, ftType != "smp")

           # Test edit of virtual nic
           Log("Testing virtual nic editing")
           VirtualNic(primaryVm)

           # add disk not supported for SMP-FT VM
           if ftType == "smp":
              TestAddDisk(primaryVm)

           # Test disabling and enabling FT, this time with the VM powered off
           TestFTDisableEnable(ftMgr, primaryVm, secondaryVm,
                               primarySi, secondarySi)

           # Unregister secondary VM
           Log("Unregister secondary VM with the primary")
           ft.UnregisterSecondary(ftMgr, primaryVm, secondaryUuid)
           Log("Secondary VM unregistered successfully")
           CheckFTState(primaryVm, FTState.notConfigured)
           ReloadSecondary(secondarySi, secondaryVm)
           CheckFTState(secondaryVm, FTState.disabled, False)

           # Cleanup
           if not keep:
              if not useExistingVm:
                 CleanupVm(primaryVm)
              connect.SetSi(secondarySi)
              CleanupVm(secondaryVm, True)
       except Exception as e:
           Log("Caught exception : %s" % e)
           stackTrace = " ".join(traceback.format_exception(
                                 sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2]))
           Log(stackTrace)
           status = "FAIL"
           Disconnect(primarySi)
           Disconnect(secondarySi)
           if IsTestEsx():
               ReportFiles('/vmfs/volumes/%s/%s' % (dsName, primaryName))
           return
       if status == "PASS" and IsTestEsx() and 'test-esx-vmFT' in primaryName:
           CleanDirs(primarySi, dsName, primaryName, ftType)
       Disconnect(primarySi)
       Disconnect(secondarySi)

# Start program
if __name__ == "__main__":
    main()
    Log("Test status: %s" % status)
    Log("FT Tests completed")
    if status != "PASS":
        sys.exit(1)
