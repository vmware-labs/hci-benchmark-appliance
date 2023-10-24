#!/usr/bin/python

###  @file vmVCP.py
###
###      Tests to exercise VM component protection for FT VMs
###
### @todo: Need to consolidate this test suite with vmFT.py
###
###


import sys
import time
import getopt
from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim.helpers import Log
from pyVim import vm
from pyVim import host
from pyVim import invt
from pyVim import connect
from pyVim import arguments
from pyVim import folder

status = "PASS"

## Cleanup VMs with the given name on a host.
def CleanupVm(vmname, useLlpm = False):
    Log("Cleaning up VMs with name " + vmname)
    oldVms = folder.FindPrefix(vmname)
    for oldVm in oldVms:
	if oldVm.GetRuntime().GetPowerState() == \
	   Vim.VirtualMachine.PowerState.poweredOn:
		vm.PowerOff(oldVm)
        Log("Destroying VM")
        if useLlpm == True:
             vmConfig = oldVm.GetConfig()
             hw = vmConfig.GetHardware()
             hw.SetDevice([])
             vmConfig.SetHardware(hw)
             llpm = invt.GetLLPM()
             llpm.DeleteVm(vmConfig)
        else:
            vm.Destroy(oldVm)


## Helper routine to add extra config entries to a VM.
def AddExtraConfig(extraCfgs, key, value):
   opt = Vim.Option.OptionValue()
   opt.SetKey(key)
   opt.SetValue(value)
   extraCfgs.append(opt)


## Validate FT state of the VM
def CheckFTState(vm, state, si = None, isPrimary = True):
   prevSi = None
   if si != None:
      prevSi = connect.GetSi()
      connect.SetSi(si)
   ftState = vm.GetRuntime().GetFaultToleranceState()
   if ftState != state:
      raise Exception(
      "Runtime FT state " + str(ftState) + " not set to " + str(state))
   Log("Verified runtime fault tolerance state as " + str(state))


## Test component health information exchange between FT peers
def TestComponentHealthInfo(ftMgr1, ftMgr2,
                            vm1, vm2,
                            health):
    ftMgr1.SetLocalVMComponentHealth(vm1, health)
    health2 = ftMgr2.GetPeerVMComponentHealth(vm2)
    if health.isStorageHealthy != health2.isStorageHealthy or \
       health.isNetworkHealthy != health2.isNetworkHealthy:
        Log("Got peer health information : " + str(health2))
        raise Exception("Peer health information does not match")


def WaitForPowerState(vm, si, powerState, nsec = 20):
   saveSi = connect.GetSi()
   connect.SetSi(si)
   for i in range(nsec):
      if vm.GetRuntime().GetPowerState() != powerState:
         time.sleep(1)
   if vm.GetRuntime().GetPowerState() != powerState:
      raise Exception("VM did not transition to expected power state!")
   connect.SetSi(saveSi)


## main
def main():
   supportedArgs = [ (["P:", "primary host="], "localhost", "Primary host name", "primaryHost"),
                     (["S:", "secondary host="], "localhost", "Secondary host name", "secondaryHost"),
                     (["T:", "tertiary host="], "", "Third host name for VMotion test", "tertiaryHost"),
                     (["d:", "shared datastore name="], "storage1", "shared datastore name", "dsName"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["e:", "useExisting="], False, "Use existing VM", "useExistingVm"),
                     (["v:", "VM name="], "vmFT", "Name of the virtual machine", "vmname"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)


   # Process command line
   primaryName = args.GetKeyValue("vmname")
   numiter = int(args.GetKeyValue("iter"))
   dsName = args.GetKeyValue("dsName")
   primaryHost = args.GetKeyValue("primaryHost")
   secondaryHost = args.GetKeyValue("secondaryHost")
   tertiaryHost = args.GetKeyValue("tertiaryHost")
   useExisting = bool(args.GetKeyValue("useExistingVm"))
   if primaryHost == secondaryHost:
      secondaryName = "_" + primaryName
   else:
      secondaryName = primaryName

   for i in range(numiter):
       primaryVm = None
       primarySi = None
       secondarySi = None
       tertiarySi = None
       try:
           # Connect to tertiary host, if provided.
           if tertiaryHost != "":
	      tertiarySi = SmartConnect(host=tertiaryHost,
				        user=args.GetKeyValue("user"),
				        pwd=args.GetKeyValue("pwd"))
	      Log("Connected to VMotion test host, VMotion will be tested")
              if not useExisting:
	         CleanupVm(primaryName)
	         CleanupVm(secondaryName, True)

           # Connect to primary host
           primarySi = SmartConnect(host=primaryHost,
                                    user=args.GetKeyValue("user"),
                                    pwd=args.GetKeyValue("pwd"))
	   Log("Connected to Primary host")

           # Cleanup from previous runs
           if not useExisting:
               CleanupVm(primaryName)
               CleanupVm(secondaryName, True)

	   # Connect to secondary host
           secondarySi = SmartConnect(host=secondaryHost,
                                      user=args.GetKeyValue("user"),
                                      pwd=args.GetKeyValue("pwd"))
	   Log("Connected to Secondary host")

	   # Cleanup from previous runs
           if not useExisting:
               CleanupVm(primaryName)
               CleanupVm(secondaryName, True)

	   # Create new VM
	   connect.SetSi(primarySi)
           primaryVm = None
           if useExisting:
               primaryVm = folder.Find(primaryName)
               if primaryVm == None:
                   raise Exception("No primary VM with name " + primaryName + " found!")
               Log("Using primary VM " + primaryName)
           else:
               Log("Creating primary VM " + primaryName)
               primaryVm = vm.CreateQuickDummy(primaryName,
                                               guest = "winXPProGuest",
                                               cdrom = 1,
                                               numScsiDisks = 1,
                                               scrubDisks = True,
                                               datastoreName = dsName)

           # Get details about primary VM
           primaryUuid = primaryVm.GetConfig().GetInstanceUuid()
           primaryCfgPath = primaryVm.GetConfig().GetFiles().GetVmPathName()
           primaryDir = primaryCfgPath[:primaryCfgPath.rfind("/")]
           Log("Using VM : " + primaryVm.GetName() + " with instanceUuid " + primaryUuid)
           if useExisting:
               ftState = Vim.VirtualMachine.FaultToleranceState.running
           else:
               ftState = Vim.VirtualMachine.FaultToleranceState.notConfigured
           CheckFTState(primaryVm, ftState)


           # Create secondary VM
	   connect.SetSi(secondarySi)
           if useExisting:
               secondaryVm = folder.Find(secondaryName)
               if secondaryVm == None:
                   raise Exception("No secondary VM with name " + secondaryName + " found!")
               Log("Using secondary VM " + secondaryName)
           else:
               Log("Creating secondary VM " + secondaryName)
               secondaryVm = vm.CreateQuickSecondary(secondaryName, primaryUuid,
                                                     primaryCfgPath, primaryDir)
               if secondaryVm == None:
                   raise "Secondary VM creation failed"
               Log("Created secondary VM " + secondaryVm.GetName())

           secondaryUuid = secondaryVm.GetConfig().GetInstanceUuid()
           secondaryCfgPath = secondaryVm.GetConfig().GetFiles().GetVmPathName()
           Log("Secondry VM: instanceUuid " + secondaryUuid)
           Log("Secondary cfg path: " + secondaryCfgPath)
           primaryFTMgr = host.GetFaultToleranceMgr(primarySi)

           if not useExisting:
               ##  Configure some additional config variables needed for FT
	       ##  This should eventually be done automatically at FT Vmotion time
               Log("Setting up extra config settings for the primary VM...")
               connect.SetSi(primarySi)
               extraCfgs = primaryVm.GetConfig().GetExtraConfig()
               AddExtraConfig(extraCfgs, "replay.allowBTOnly", "TRUE")
               AddExtraConfig(extraCfgs, "replay.allowFT", "TRUE")
               if primaryName != secondaryName:
                   AddExtraConfig(extraCfgs, "ft.allowUniqueName", "TRUE")
               cSpec = Vim.Vm.ConfigSpec()
               cSpec.SetExtraConfig(extraCfgs)
               task = primaryVm.Reconfigure(cSpec)
               WaitForTask(task)

               # Register secondary VM
               Log("Register secondary VM with the powered off primary")
               task = primaryFTMgr.RegisterSecondary(primaryVm, secondaryUuid,
                                                     secondaryCfgPath)
               WaitForTask(task)
               Log("Secondary VM registered successfully")

               # Verify FT state
               CheckFTState(primaryVm,
                            Vim.VirtualMachine.FaultToleranceState.enabled)
               Log("FT configured successfully.")

               # PowerOn FT VM
               Log("Powering on Primary VM")
               vm.PowerOn(primaryVm)

               # Perform FT VMotion to setup protection
               Log("Migrating state from primary to secondary VM.")
               vm.Migrate(primaryVm, primarySi, secondarySi,
                          secondaryCfgPath, True,
                          Vim.Host.VMotionManager.VMotionType.fault_tolerance)
               CheckFTState(primaryVm,
                            Vim.VirtualMachine.FaultToleranceState.running)
               CheckFTState(secondaryVm,
                            Vim.VirtualMachine.FaultToleranceState.running,
                            secondarySi, False)
               Log("VMs are running with FT protection.")

           # Test VM component health exchanges
           secondaryFTMgr = host.GetFaultToleranceMgr(secondarySi)
           health = Vim.Host.FaultToleranceManager.ComponentHealthInfo()
           health.SetIsStorageHealthy(True)
           health.SetIsNetworkHealthy(True)

           Log("Testing VM health exchange from primary to secondary: all healthy")
           TestComponentHealthInfo(primaryFTMgr, secondaryFTMgr,
                                   primaryVm, secondaryVm,
                                   health)

           Log("Testing VM health exchange from primary to secondary: storage unhealthy")
           health.SetIsStorageHealthy(False)
           TestComponentHealthInfo(primaryFTMgr, secondaryFTMgr,
                                   primaryVm, secondaryVm,
                                   health)

           Log("Testing VM health exchange from secondary to primary: network unhealthy")
           health.SetIsStorageHealthy(True)
           health.SetIsNetworkHealthy(False)
           TestComponentHealthInfo(secondaryFTMgr, primaryFTMgr,
                                   secondaryVm, primaryVm,
                                   health)
           # Making peer go live
           Log("Making FT primary go live from secondary")
           secondaryFTMgr.GoLivePeerVM(secondaryVm)
           time.sleep(5)
           CheckFTState(primaryVm,
                        Vim.VirtualMachine.FaultToleranceState.needSecondary,
                        primarySi)
	   WaitForPowerState(secondaryVm, secondarySi,
			     Vim.VirtualMachine.PowerState.poweredOff)

	   # Set local VM storage and network health
	   Log("Setting primary VM as unhealthy")
           health.SetIsStorageHealthy(False)
           health.SetIsNetworkHealthy(False)
           primaryFTMgr.SetLocalVMComponentHealth(primaryVm, health)

	   # Restart secondary VM. It should still show storage unhealthy
	   Log("Restarting secondary VM.")
           vm.Migrate(primaryVm, primarySi, secondarySi,
                      secondaryCfgPath, True,
                      Vim.Host.VMotionManager.VMotionType.fault_tolerance)
           CheckFTState(primaryVm,
                        Vim.VirtualMachine.FaultToleranceState.running)
           CheckFTState(secondaryVm,
                        Vim.VirtualMachine.FaultToleranceState.running,
                        secondarySi, False)
           Log("VMs are running with FT protection.")

	   # Verify health has propagated to the new secondary
           health2 = secondaryFTMgr.GetPeerVMComponentHealth(secondaryVm)
	   if health.isStorageHealthy != health2.isStorageHealthy or \
	      health.isNetworkHealthy != health2.isNetworkHealthy:
              Log("Got peer health information : " + str(health2))
              raise Exception("Peer health information does not match")

	   # Test VMotion of primary and secondary, if a third host is given
	   if tertiarySi != None:
	      # Mark secondary as unhealthy
              health.SetIsStorageHealthy(True)
              health.SetIsNetworkHealthy(False)
              secondaryFTMgr.SetLocalVMComponentHealth(secondaryVm, health)

	      Log("VMotion primary to tertiary host")
              vm.Migrate(primaryVm, primarySi, tertiarySi,
			 primaryCfgPath, False)
              primaryFTMgr = host.GetFaultToleranceMgr(tertiarySi)
              connect.SetSi(tertiarySi)
              primaryVm = folder.Find(primaryName)
              CheckFTState(primaryVm,
			   Vim.VirtualMachine.FaultToleranceState.running,
			   tertiarySi)
              CheckFTState(secondaryVm,
			   Vim.VirtualMachine.FaultToleranceState.running,
			   secondarySi, False)

	      # Verify secondary health has propagated to primary on new host
              health2 = primaryFTMgr.GetPeerVMComponentHealth(primaryVm)
	      if health.isStorageHealthy != health2.isStorageHealthy or \
	         health.isNetworkHealthy != health2.isNetworkHealthy:
                 Log("Got peer health information : " + str(health2))
                 raise Exception("Peer health information does not match")

	      # Mark primary as unhealthy
              health.SetIsStorageHealthy(False)
              health.SetIsNetworkHealthy(True)
              primaryFTMgr.SetLocalVMComponentHealth(primaryVm, health)

	      Log("VMotion secondary to tertiary host")
              vm.Migrate(secondaryVm, secondarySi, tertiarySi,
			 secondaryCfgPath, False)
              secondaryFTMgr = host.GetFaultToleranceMgr(tertiarySi)
              connect.SetSi(tertiarySi)
              secondaryVm = folder.Find(secondaryName)
              CheckFTState(primaryVm,
			   Vim.VirtualMachine.FaultToleranceState.running,
			   tertiarySi)
              CheckFTState(secondaryVm,
			   Vim.VirtualMachine.FaultToleranceState.running,
			   tertiarySi, False)

	      # Verify primary health has propagated to secondary on new host
              health2 = secondaryFTMgr.GetPeerVMComponentHealth(secondaryVm)
	      if health.isStorageHealthy != health2.isStorageHealthy or \
	         health.isNetworkHealthy != health2.isNetworkHealthy:
                 Log("Got peer health information : " + str(health2))
                 raise Exception("Peer health information does not match")

              Log("Power off Primary VM")
	      connect.SetSi(tertiarySi)
	      vm.PowerOff(primaryVm)
	      WaitForPowerState(primaryVm, tertiarySi,
				Vim.VirtualMachine.PowerState.poweredOff)
	      WaitForPowerState(secondaryVm, primarySi,
				Vim.VirtualMachine.PowerState.poweredOff)
	      if not useExisting:
                 Log("Cleaning up VMs")
                 CleanupVm(primaryName)
                 CleanupVm(secondaryName, True)
           else:
	      # Skipped VMotion test
              Log("Power off Primary VM")
	      connect.SetSi(primarySi)
	      vm.PowerOff(primaryVm)
	      WaitForPowerState(primaryVm, primarySi,
			   	Vim.VirtualMachine.PowerState.poweredOff)
	      WaitForPowerState(secondaryVm, secondarySi,
			   	Vim.VirtualMachine.PowerState.poweredOff)
	      if not useExisting:
                 Log("Cleaning up VMs")
                 CleanupVm(primaryName)
                 connect.SetSi(secondarySi)
                 CleanupVm(secondaryName, True)

       except Exception as e:
           Log("Caught exception : " + str(e))
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
    Log("VCP Tests completed")
