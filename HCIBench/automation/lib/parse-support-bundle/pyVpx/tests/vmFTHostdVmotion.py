#!/usr/bin/python

import os
import sys
import time
import getopt
import traceback
from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim.helpers import Log
from pyVim import vm
from pyVim import host
from pyVim import invt
from pyVim import connect
from pyVim import arguments
from pyVim import folder

from vmFTUtils import *
status = "PASS"
FTType = vim.VirtualMachine.FaultToleranceType
ftLoggingNicType = vim.host.VirtualNicManager.NicType.faultToleranceLogging
vmotionNicType = vim.host.VirtualNicManager.NicType.vmotion

def main():
   supportedArgs = [ (["P:", "primary host="], "localhost", "Primary host name", "primaryHost"),
                     (["S:", "secondary host="], "localhost", "Secondary host name", "secondaryHost"),
                     (["d:", "shared datastore name="], "storage1", "shared datastore name", "dsName"),
                     (["k:", "keep="], "0", "Keep configs", "keep"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd"),
                     (["v:", "vmname="], "vmFT", "Name of the virtual machine", "vmname"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter"),
                     (["t:", "FT type="], "up", "Type of fault tolerance [up|smp]", "ftType"), ]
   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Process command line
   vmname = args.GetKeyValue("vmname")
   numiter = int(args.GetKeyValue("iter"))
   keep = int(args.GetKeyValue("keep"))
   dsName = args.GetKeyValue("dsName")
   primaryHost = args.GetKeyValue("primaryHost")
   secondaryHost = args.GetKeyValue("secondaryHost")
   ftType = args.GetKeyValue("ftType")

   numCPU = 2 if ftType == "smp" else 1
   memSize = 64

   for i in range(numiter):
       primaryVm = None
       primarySi = None
       secondarySi = None
       try:
           # Connect to primary host
           primarySi = SmartConnect(host=primaryHost,
                               user=args.GetKeyValue("user"),
                                    pwd=args.GetKeyValue("pwd"))
	   Log("Connected to Primary host")

           # Cleanup from previous runs
           try:
              CleanupVm(vmname)
           except vim.fault.InvalidOperationOnSecondaryVm:
              pass

	   # Connect to secondary host
           secondarySi = SmartConnect(host=secondaryHost,
                                 user=args.GetKeyValue("user"),
                                      pwd=args.GetKeyValue("pwd"))
	   Log("Connected to Secondary host")

           for si in [primarySi, secondarySi]:
              if len(FindNicType(si, ftLoggingNicType)) == 0:
                 SelectVnic(si, "vmk0", ftLoggingNicType)
              if len(FindNicType(si, vmotionNicType)) == 0:
                 SelectVnic(si, "vmk0", vmotionNicType)

	   ftMgrDst = host.GetFaultToleranceMgr(secondarySi)

	   # Cleanup from previous runs
           CleanupVm(vmname)
           CleanupVm(vmname, True)

           connect.SetSi(primarySi)
           CleanupDir(dsName, vmname)
           if ftType == "smp":
              CleanupDir(dsName, "%s_shared" % vmname)


	   # Create new VM
           Log("Creating primary VM " + vmname)
           primaryVm = vm.CreateQuickDummy(vmname,
                                           guest="winNetEnterpriseGuest",
                                           numScsiDisks=2,
                                           scrubDisks=True,
                                           memory=memSize,
                                           datastoreName=dsName)
           primaryUuid = primaryVm.GetConfig().GetInstanceUuid()
           primaryCfgPath = primaryVm.GetConfig().GetFiles().GetVmPathName()
           primaryDir = primaryCfgPath[:primaryCfgPath.rfind("/")]

           ftMetadataDir = GetSharedPath(primarySi, primaryVm)

           Log("Using VM : " + primaryVm.GetName() + " with instanceUuid " + primaryUuid)

           ftMetadataDir = GetSharedPath(primarySi, primaryVm)
           cSpec = vim.vm.ConfigSpec()
           if ftType != "smp":
              # Enable record/replay for the primaryVm
              # See PR 200254
              flags = vim.vm.FlagInfo(recordReplayEnabled=True)
              cSpec.SetFlags(flags)
              task = primaryVm.Reconfigure(cSpec)
              WaitForTask(task)
              Log("Enabled record/replay for Primary VM.")
              CheckFTState(primaryVm,
                           vim.VirtualMachine.FaultToleranceState.notConfigured)
           else:
              cSpec.files = vim.vm.FileInfo(ftMetadataDirectory=ftMetadataDir)
              cSpec.numCPUs = numCPU
              task = primaryVm.Reconfigure(cSpec)
              WaitForTask(task)

           # Create secondary VM
	   connect.SetSi(secondarySi)
	   Log("Creating secondary VM " + vmname)
           secondaryVm = vm.CreateQuickSecondary(vmname, primaryVm,
                                                 ftType=ftType,
                                                 scrubDisks=True,
                                                 numScsiDisks=2,
                                                 datastoreName=dsName,
                                                 ftMetadataDir=ftMetadataDir)
           if secondaryVm == None:
               raise "Secondary VM creation failed"
           secondaryUuid = secondaryVm.GetConfig().GetInstanceUuid()
           secondaryCfgPath = secondaryVm.GetConfig().GetFiles().GetVmPathName()
           Log("Created secondary VM " + secondaryVm.GetName())
           Log("Secondry VM: instanceUuid " + secondaryUuid)
           Log("Secondary cfg path: " + secondaryCfgPath)

	   ##  Configure some additional config variables needed for FT
	   ##  This should eventually be done automatically at FT Vmotion time
	   Log("Setting up extra config settings for the primary VM...")

	   cSpec = vim.Vm.ConfigSpec()
           extraCfgs = []
           if ftType == "smp": # some of these options are temporary
              cSpec.flags = vim.vm.FlagInfo(faultToleranceType=FTType.checkpointing)
              AddExtraConfig(extraCfgs, "ftcpt.maxDiskBufferPages", "0")
              AddExtraConfig(extraCfgs, "sched.mem.pshare.enable", "FALSE")
              AddExtraConfig(extraCfgs, "sched.mem.fullreservation", "TRUE")
              AddExtraConfig(extraCfgs, "monitor_control.disable_mmu_largepages", "TRUE")
              AddExtraConfig(extraCfgs, "sched.mem.min", memSize)
              AddExtraConfig(extraCfgs, "migration.dataTimeout", "2000")
              cSpec.files = vim.vm.FileInfo(ftMetadataDirectory=ftMetadataDir)
           else:
              cSpec.flags = vim.vm.FlagInfo(faultToleranceType=FTType.recordReplay)
              AddExtraConfig(extraCfgs, "replay.allowBTOnly", "TRUE")

	   cSpec.SetExtraConfig(extraCfgs)
           WaitForTask(primaryVm.Reconfigure(cSpec))

           # Register secondary VM
           Log("Register secondary VM with the primary")
           ftMgr = host.GetFaultToleranceMgr(primarySi)
           connect.SetSi(primarySi)
           task = ftMgr.RegisterSecondary(primaryVm, secondaryUuid,
                                          secondaryCfgPath)
           WaitForTask(task)
           Log("Secondary VM registered successfully")

           # Verify FT role & state
           CheckFTRole(primaryVm, 1)
           CheckFTState(primaryVm,
                        vim.VirtualMachine.FaultToleranceState.enabled)

	   Log("FT configured successfully.")

	   # PowerOn FT VM
	   Log("Powering on Primary VM")
           vm.PowerOn(primaryVm)
           if ftType == "smp": # some of these options are temporary
              task = primaryVm.CreateSnapshot("snap-early",
                                              "before secondary starts",
                                              memory=False, quiesce=True)
              WaitForTask(task)

	   # Perform the FT VMotion
           Log("Calling StartSecondary on remote host...")
           primaryThumbprint = GetHostThumbprint(primaryHost)
           secondaryThumbprint = GetHostThumbprint(secondaryHost)
           Log("Primary thumbprint: %s" % primaryThumbprint)
           Log("Secondary thumbprint: %s" % secondaryThumbprint)

           secondaryHostSystem = secondarySi.content.rootFolder.childEntity[0].hostFolder.childEntity[0].host[0]
           sslThumbprintInfo = vim.host.SslThumbprintInfo(ownerTag='hostd-test', principal='vpxuser')
           sslThumbprintInfo.sslThumbprints = [primaryThumbprint]
           secondaryHostSystem.UpdateSslThumbprintInfo(sslThumbprintInfo, "add")

           sslThumbprintInfo.sslThumbprints = [secondaryThumbprint]
           primaryHostSystem = primarySi.content.rootFolder.childEntity[0].hostFolder.childEntity[0].host[0]
           primaryHostSystem.UpdateSslThumbprintInfo(sslThumbprintInfo, "add")

           task = ftMgr.StartSecondaryOnRemoteHost(primaryVm, secondaryCfgPath,
                                            secondaryHost, 80, secondaryThumbprint)
           WaitForTask(task)
	   Log("Start secondary done.")

           if ftType == "smp":
              # Verify snapshot is gone
              if primaryVm.snapshot is not None:
                 raise Exception("Snapshot still exists on primary")

              task = primaryVm.CreateSnapshot("snap", "without memory snapshot",
                                              memory=False, quiesce=True)
              WaitForTask(task)

              if not primaryVm.snapshot or not primaryVm.snapshot.currentSnapshot:
                 raise Exception("Snapshot was not created")
              else:
                 Log("Snapshot %s exists as expected" % primaryVm.snapshot.currentSnapshot)

           # Retrieve reference to new secondary VM
           connect.SetSi(secondarySi)
           secondaryVm = folder.FindCfg(secondaryCfgPath)
           connect.SetSi(primarySi)

           # FT state check
           CheckFTState(primaryVm,
                        vim.VirtualMachine.FaultToleranceState.running)
           CheckFTState(secondaryVm,
                        vim.VirtualMachine.FaultToleranceState.running)

	   Log("Start secondary done.")

           # allows some time for FT to run and checkpoint before failing
           # over. This seems more necessary on nested VM environments
           # than physical
           time.sleep(20)

           Log("Failing over to the secondary.")
           WaitForTask(ftMgr.MakePrimary(primaryVm, secondaryUuid))
           WaitForPowerState(primaryVm, primarySi, vim.VirtualMachine.PowerState.poweredOff)
           Log("Verified primary power state is off.")
           WaitForFTState(secondaryVm, FTState.needSecondary)

           Log("Starting secondary.")
           task = ftMgrDst.StartSecondaryOnRemoteHost(secondaryVm, primaryCfgPath,
                                                      primaryHost, 80, primaryThumbprint)
           WaitForTask(task)

           # Verify snapshot is gone
           if primaryVm.snapshot is not None:
              raise Exception("Snapshot still exists on old primary")

           Log("Failing over to the old-primary.")
           WaitForTask(ftMgrDst.MakePrimary(secondaryVm, secondaryUuid))
           WaitForPowerState(secondaryVm, secondarySi, vim.VirtualMachine.PowerState.poweredOff)
           Log("Verified primary power state is off.")
           WaitForFTState(primaryVm, FTState.needSecondary)

           task = ftMgr.StartSecondaryOnRemoteHost(primaryVm, secondaryCfgPath,
                                            secondaryHost, 80, secondaryThumbprint)
           WaitForTask(task)

	   # PowerOff FT VMs
	   Log("Power off Primary VM")
	   vm.PowerOff(primaryVm)
	   connect.SetSi(secondarySi)
	   for i in range(10):
	      if secondaryVm.GetRuntime().GetPowerState() == vim.VirtualMachine.PowerState.poweredOn:
	         time.sleep(1)
	   if secondaryVm.GetRuntime().GetPowerState() == vim.VirtualMachine.PowerState.poweredOn:
	      raise Exception("Secondary VM is still powered on!")
	   Log("Verified secondary power state.")

	   Log("Unregistering secondary VM " + vmname)
	   ftMgrDst.Unregister(secondaryVm)

	   # Cleanup
	   if not keep:
	      connect.SetSi(primarySi)
	      CleanupVm(vmname)
	      CleanupDir(dsName, vmname)
	      if ftType == "smp":
	         CleanupDir(dsName, "%s_shared" % vmname)

	      connect.SetSi(secondarySi)
	      CleanupVm(vmname, True)
       except Exception as e:
           Log("Caught exception : %s" % e)
           stackTrace = " ".join(traceback.format_exception(
                                 sys.exc_info()[0],
                                 sys.exc_info()[1],
                                 sys.exc_info()[2]))
           Log(stackTrace)
           global status
           status = "FAIL"
           Disconnect(primarySi)
           Disconnect(secondarySi)
           return

       Disconnect(primarySi)
       Disconnect(secondarySi)

# Start program
if __name__ == "__main__":
    main()
    Log("Test status: " + status)
    Log("FT Tests completed")
    if status != "PASS":
        sys.exit(1)
