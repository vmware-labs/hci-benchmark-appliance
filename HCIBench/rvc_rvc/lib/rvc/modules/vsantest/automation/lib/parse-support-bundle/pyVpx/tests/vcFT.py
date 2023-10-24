#!/usr/bin/python

import sys
import time
import socket
import getopt
import traceback
import re
import random
from pyVmomi import vim, vmodl
from pyVmomi.VmomiSupport import newestVersions
from pyVim import connect, task, vm, arguments, folder, vimutil
from pyVim.helpers import Log

status = "PASS"
checkRRState = True

FTState = vim.VirtualMachine.FaultToleranceState
PowerState = vim.VirtualMachine.PowerState
ftLoggingNicType = vim.host.VirtualNicManager.NicType.faultToleranceLogging
vmotionNicType = vim.host.VirtualNicManager.NicType.vmotion

ftvmotion = vim.Host.VMotionManager.VMotionType.fault_tolerance
ACTION_LIST = ["disable",
               "off",
               "makePrimary",
               "terminateSecondary",
               "migratePrimary",
               "migrateSecondary",
#              "terminate",
              ]
REV_ACTION = {"disable":"enable",
              "off":"on",
              "enable":"disable",
              "on":"off",
              "makePrimary":None,
              "terminateSecondary":None,
              "migratePrimary":None,
              "migrateSecondary":None,
#              "terminate":None,
             }

def CreateOrUseDC(si, name):
   try:
      return si.content.rootFolder.CreateDatacenter(name)
   except vim.fault.DuplicateName as e:
      return e.object
   return None

def CreateOrUseCluster(dc, name):
   try:
      dasConfig = vim.cluster.DasConfigInfo(enabled=True,
                                            hostMonitoring=vim.cluster.DasConfigInfo.ServiceState.enabled,
                                            admissionControlPolicy=vim.cluster.FailoverLevelAdmissionControlPolicy(failoverLevel=1),
#                                            admissionControlEnabled=True)
                                            admissionControlEnabled=False)
#      drsConfig = vim.cluster.DrsConfigInfo(enabled=True,
      drsConfig = vim.cluster.DrsConfigInfo(enabled=False,
                                            defaultVmBehavior=vim.cluster.DrsConfigInfo.DrsBehavior.fullyAutomated)
      spec = vim.cluster.ConfigSpecEx(dasConfig=dasConfig,
                                      drsConfig=drsConfig)

      return dc.hostFolder.CreateClusterEx(name, spec)
   except vim.fault.DuplicateName as e:
      return e.object
   return None

def AddHostToCluster(si, cluster, host):
   thumbprint = None
   for password in ['', 'ca$hc0w']:
      try:
         spec = vim.host.ConnectSpec(force=True,
                                     hostName=host,
                                     userName='root',
                                     password=password,
                                     sslThumbprint=thumbprint)
         addTask = cluster.AddHost(spec, True)
         task.WaitForTask(addTask)
         return addTask.info.result
      except vim.fault.AlreadyConnected as e:
         return GetHostByName(si, e.name)
      except vim.fault.SSLVerifyFault as e:
         spec.sslThumbprint = thumbprint = e.thumbprint
         addTask = cluster.AddHost(spec, True)
         try:
            task.WaitForTask(addTask)
         except vim.fault.InvalidLogin as e:
            pass
         else:
            return addTask.info.result
      except vim.fault.InvalidLogin as e:
         pass
   return None

def GetHostList(folder):
   hostList = []
   for file in folder.childEntity:
      fileType = "%s" % file
      if fileType.find('vim.Folder') != -1:
         hostList += GetHostList(file)
      elif fileType.find('vim.Datacenter') != -1:
         hostList += GetHostList(file.hostFolder)
      elif fileType.find('vim.ClusterComputeResource') != -1:
         hostList += file.host
      elif fileType.find('vim.ComputeResource') != -1:
         hostList += file.host
   return hostList

def FindDS(host, dsName):
   for ds in host.datastore:
      if ds.info.name == dsName:
         return ds
   return None

def MountNas(host, localPath, remotePath, accessMode = "readWrite"):
   m = re.match(r"^(.*?):(.*)$", remotePath)
   if m:
      remoteHost = m.string[m.start(1):m.end(1)]
      remotePath = m.string[m.start(2):m.end(2)]

      spec = vim.host.NasVolume.Specification(accessMode=accessMode,
                                              localPath=localPath,
                                              remoteHost=remoteHost,
                                              remotePath=remotePath)
      datastoreSystem = host.configManager.datastoreSystem
      return datastoreSystem.CreateNasDatastore(spec)

   Log("remotePath %s did not contain serverName:path format" % remotePath)
   return None

def GetHostByName(si, hostname):
   for host in GetHostList(si.content.rootFolder):
      # sometimes the user doesn't put the hostname in correctly
      # and the lookup fails. Not all cases can be addressed, but
      # try striping everything after the '.' and see if we get
      # a valid name.
      splithost = host.name.split(".")[0]
      if host.name == hostname or \
         LookupHost(host.name) == LookupHost(hostname) or \
         LookupHost(splithost) == LookupHost(hostname):
         return host
   return None

def LookupHost(hostname):
   try:
      addr = socket.getaddrinfo(hostname, None)
   except:
      return None
   return addr[1][4][0]

def FindNicType(si, hostSystem, nicType):
   nics = []
   for netConfig in hostSystem.configManager.virtualNicManager.info.netConfig:
      if netConfig.nicType == nicType:
         for selectedVnic in netConfig.selectedVnic:
            nics.append(selectedVnic)
   return nics

def SelectVnic(si, hostSystem, vnic, nicType):
   hostSystem.configManager.virtualNicManager.SelectVnic(nicType, vnic)

## Cleanup VMs with the given name on a host.
def CleanupVm(vmname):
   si = connect.GetSi()
   Log("Cleaning up VMs with name " + vmname)
   oldVms = folder.FindPrefix(vmname)
   for oldVm in oldVms:
      try:
         if oldVm is None or oldVm.config is None or oldVm.config.ftInfo is None:
            continue
         if oldVm.config.ftInfo.role != 1:
            continue
         if oldVm.GetRuntime().GetPowerState() == \
            vim.VirtualMachine.PowerState.poweredOn:
            vm.PowerOff(oldVm)
         ftInfo = oldVm.config.ftInfo
         Log("Destroying VM")
         vmConfig = oldVm.GetConfig()
         hw = vmConfig.GetHardware()
         hw.SetDevice([])
         vmConfig.SetHardware(hw)
         vm.Destroy(oldVm)
      except vmodl.fault.ManagedObjectNotFound as e:
         pass

## Helper routine to add extra config entries to a VM.
def AddExtraConfig(extraCfgs, key, value):
   opt = vim.Option.OptionValue()
   opt.SetKey(key)
   opt.SetValue(value)
   extraCfgs.append(opt)

## Validate FT state and record/replay state of the VM
def CheckFTState(vm, state, si = None, isPrimary = True):
   expRRState = None
   if isPrimary:
      expRRState = vim.VirtualMachine.RecordReplayState.recording
   else:
      expRRState = vim.VirtualMachine.RecordReplayState.replaying
   ftState = vm.GetRuntime().GetFaultToleranceState()
   rrState = vm.GetRuntime().GetRecordReplayState()
   if ftState != state:
      raise Exception("Runtime FT state %s not set to %s" % (ftState, state))
   Log("Verified runtime fault tolerance state as " + str(state))

   if not checkRRState:
      return

   # Check record/replay state
   if ftState == FTState.running:
      if rrState != expRRState:
         raise Exception("Runtime recordReplay state %s not set to %s" %
                         (rrState, expRRState))
   elif rrState != vim.VirtualMachine.RecordReplayState.inactive:
      raise Exception("Runtime recordReplay state %s not set to inactive" %
                         rrState)
   Log("Verified runtime record/replay state as %s" % rrState)


## Validate FT role of a VM against an expected value.
def CheckFTRole(vm, role, si = None):
    ftInfo = vm.GetConfig().GetFtInfo()
    if ftInfo == None:
        raise Exception("No FT info configured for this VM")
    if ftInfo.GetRole() != role:
        raise Exception("FT role of VM does not match " + str(role))
    Log("Verified FT role of VM")

## Retrieve the file name associated with a datastore path.
def GetFileName(dsPath):
    relPath = dsPath.split()[1]
    cfgPath = relPath.split("/")[1]
    return cfgPath

def WaitForNotPowerState(vm, si, powerState, nsec = 20):
   for i in range(nsec):
      if vm.GetRuntime().GetPowerState() != powerState:
         return
      time.sleep(1)
   raise Exception("VM did not transition to expected power state!")

def WaitForPowerState(vm, si, powerState, nsec = 20):
   for i in range(nsec):
      if vm.GetRuntime().GetPowerState() == powerState:
         return
      time.sleep(1)
   raise Exception("VM did not transition to expected power state!")

def WaitForFTState(vm, state, nsec = 120):
   for i in range(nsec):
      ftState = vm.GetRuntime().GetFaultToleranceState()
      if ftState == state:
         return
      time.sleep(1)
   raise Exception("Runtime FT state %s not set to %s" % (ftState, state))

def WaitForFTRole(vm, role, nsec = 120):
   for i in range(nsec):
      ftInfo = vm.GetConfig().GetFtInfo()
      if ftInfo and ftInfo.GetRole() == role:
         return
      time.sleep(1)
   raise Exception("FT role of VM does not match %s" % role)

def WaitForDasProtection(vm, status, nsec = 120):
   for i in range(nsec):
      dasVmProtection = vm.GetRuntime().GetDasVmProtection()
      if dasVmProtection != None:
         dasProtection = dasVmProtection.GetDasProtected()
         if dasProtection == status:
            return
      time.sleep(1)
   raise Exception("VM is not protected")

def RetryTask(op, *args, **kw):
   while True:
      try:
         t = vimutil.InvokeAndTrackWithTask(op, *args, **kw)
         return t
      except vim.fault.FailToLockFaultToleranceVMs as e:
         Log("VC locking fault thrown")
      time.sleep(5)

def HandleActions(action, revAction=None):
   try:
      HandleAction(action)
   except vim.fault.FailToLockFaultToleranceVMs as e:
      Log("VC locking fault thrown")
   else:
      if revAction:
         while True:
            try:
               HandleAction(revAction)
               break
            except vim.fault.FailToLockFaultToleranceVMs as e:
               Log("VC locking fault thrown on reverse action")

def WaitForRunning():
   global si
   global primaryVm
   global secondaryVm
   WaitForFTRole(primaryVm, 1)
   WaitForFTRole(secondaryVm, 2)
   Log("Waiting For Secondary to power on")
   WaitForPowerState(secondaryVm, si, 'poweredOn', nsec = 300)
   Log("Waiting For Primary to be in running state")
   WaitForFTState(primaryVm, FTState.running)
   Log("Waiting For Secondary to be in running state")
   WaitForFTState(secondaryVm, FTState.running)
   Log("Waiting for dasVmProtection")
   WaitForDasProtection(primaryVm, True)

def HandleAction(action):
   global si
   global primaryVm
   global secondaryVm

   if action == "enable":
      Log("*** EnableSecondary ***")
      task.WaitForTask(primaryVm.EnableSecondary(secondaryVm))
      WaitForPowerState(primaryVm, si, 'poweredOn', nsec = 120)
      WaitForPowerState(secondaryVm, si, 'poweredOn', nsec = 120)
      WaitForFTState(secondaryVm, FTState.running)
      WaitForFTState(primaryVm, FTState.running)
      WaitForDasProtection(primaryVm, True)
   elif action == "disable":
      Log("*** DisableSecondary ***")
      task.WaitForTask(primaryVm.DisableSecondary(secondaryVm))
      WaitForPowerState(primaryVm, si, 'poweredOn', nsec = 120)
      WaitForPowerState(secondaryVm, si, 'poweredOff', nsec = 120)
      WaitForFTState(secondaryVm, FTState.disabled)
      WaitForFTState(primaryVm, FTState.disabled)
   elif action == "on":
      Log("*** TurnOn ***")
      vmTask = primaryVm.CreateSecondary()
      task.WaitForTask(vmTask)
      secondaryVm = vmTask.info.result.vm
      if vmTask.info.result.powerOnAttempted:
         WaitForPowerState(primaryVm, si, 'poweredOn', nsec = 120)
         WaitForPowerState(secondaryVm, si, 'poweredOn', nsec = 120)
         WaitForFTState(secondaryVm, FTState.running)
         WaitForFTState(primaryVm, FTState.running)
   elif action == "off":
      Log("*** TurnOff ***")
      task.WaitForTask(primaryVm.TurnOffFaultTolerance())
      WaitForFTState(primaryVm, FTState.notConfigured)
   elif action == "makePrimary" or action =="terminate":
      if action == "makePrimary":
         Log("*** MakePrimary ***")
         task.WaitForTask(primaryVm.MakePrimary(secondaryVm))
         WaitForRunning()
      else:
         Log("*** TerminateVM ***")
         task.WaitForTask(primaryVm.Terminate())
      Log("Waiting for secondary to go down")
      WaitForNotPowerState(secondaryVm, si, 'poweredOn', nsec = 120)
      Log("Waiting for secondary to come up")
      WaitForPowerState(secondaryVm, si, 'poweredOn', nsec = 900)

   elif action == "terminateSecondary":
      Log("*** TerminateSecondary ***")
      task.WaitForTask(primaryVm.TerminateFaultTolerantVM(secondaryVm))

      Log("Waiting for secondary to go down")
      WaitForNotPowerState(secondaryVm, si, 'poweredOn', nsec = 120)
      Log("Waiting for secondary to come up")
      WaitForPowerState(secondaryVm, si, 'poweredOn', nsec = 900)

      WaitForRunning()
   elif action == "migratePrimary":
      Log("*** Migrate Primary ***")
      task.WaitForTask(primaryVm.Migrate(priority=vim.VirtualMachine.MovePriority.highPriority))
   elif action == "migrateSecondary":
      Log("*** Migrate Secondary ***")
      task.WaitForTask(secondaryVm.Migrate(priority=vim.VirtualMachine.MovePriority.highPriority))
   else:
      Log("Unknown action: '%s'" % action)

def main():
   supportedArgs = [ (["H:", "hosts="], "", "List of hosts (comma separated)", "hosts"),
                     (["D:", "dcName="], "Datacenter", "datacenter name", "dcName"),
                     (["d:", "dsName="], "storage1", "shared datastore name", "dsName"),
                     (["dsMount="], "", "server:path of datastore to mount", "dsMount"),
                     (["k:", "keep="], "0", "Keep configs", "keep"),
                     (["l:", "leaveRunning="], False, "Leave FT VMs running", "leaveRunning"),
                     (["L:", "leaveRegistered="], False, "Leave FT VMs configured but not powered on", "leaveRegistered"),
                     (["e:", "useExistingVm="], False, "Use existing VM", "useExistingVm"),
                     (["r:", "checkRRState="], "True", "Validate Record/Replay states", "checkRRState"),
                     (["V:", "vc="], "", "VC Server name", "vc"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "vmware", "Password", "pwd"),
                     (["v:", "vmname="], "vmFT", "Name of the virtual machine", "vmname") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage")]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Process command line
   primaryName = args.GetKeyValue("vmname")
   keep = int(args.GetKeyValue("keep"))
   vc = args.GetKeyValue("vc")
   leaveRegistered = bool(args.GetKeyValue("leaveRegistered"))
   leaveRunning = bool(args.GetKeyValue("leaveRunning"))
   useExistingVm = bool(args.GetKeyValue("useExistingVm"))
   global checkRRState
   checkRRState = eval(args.GetKeyValue("checkRRState"))
   dsName = args.GetKeyValue("dsName")
   dsMount = args.GetKeyValue("dsMount")
   dcName = args.GetKeyValue("dcName")
   hostList = args.GetKeyValue("hosts")
   hosts = re.split('\s*,\s*', hostList)
   hostSystems = []

   # Connect to VC server
   global si
   Log("Connecting to %s" % vc)
   si = connect.Connect(host=vc,
                user=args.GetKeyValue("user"),
                pwd=args.GetKeyValue("pwd"),
                version=newestVersions.GetName('vim'))
   if si is None:
      raise Exception("Failed to connect to VC")
   connect.SetSi(si)
   Log("Connected to VC Server")

   dc = CreateOrUseDC(si, dcName)
   cluster = CreateOrUseCluster(dc, "HA")

   for host in hosts:
      hostSystem = GetHostByName(si, host)
      if hostSystem is not None and hostSystem.runtime.connectionState != "connected":
         task.WaitForTask(hostSystem.Destroy())
         hostSystem = None
      if hostSystem == None:
         Log("Failed to find %s" % host)
         hostSystem = AddHostToCluster(si, cluster, host)
      hostSystems.append(hostSystem)
      if len(FindNicType(si, hostSystem, ftLoggingNicType)) == 0:
         SelectVnic(si, hostSystem, "vmk0", ftLoggingNicType)
      if len(FindNicType(si, hostSystem, vmotionNicType)) == 0:
         SelectVnic(si, hostSystem, "vmk0", vmotionNicType)
      ds = FindDS(hostSystem, dsName)
      if ds is None and dsMount:
         MountNas(hostSystem, dsName, dsMount, accessMode = "readWrite")

   secondaryName = primaryName
   orphanedSecondaryName = primaryName + "_orphaned"

   global primaryVm
   global secondaryVm

   primaryVm = None
   si = None
   try:
      CleanupVm(primaryName)

      # Create new VM
      primaryVm = None
      if useExistingVm:
          primaryVm = folder.Find(primaryName)
          if primaryVm == None:
              raise Exception("No primary VM with name " + primaryName + " found!")
          Log("Using primary VM " + primaryName)
      else:
          Log("Creating primary VM " + primaryName)
          # Short delay to avoid colliding with a cleanup.
          time.sleep(5)
          primaryVm = vm.CreateQuickDummy(primaryName,
                                          guest="winXPProGuest",
                                          cdrom=0,
                                          numScsiDisks=2,
                                          scrubDisks=False,
                                          datastoreName=dsName,
                                          vmxVersion="vmx-09",
                                          dc=dcName)
          spec = vim.vm.ConfigSpec(numCPUs=2)
          task.WaitForTask(primaryVm.Reconfigure(spec))

      # Get details about primary VM
      primaryUuid = primaryVm.GetConfig().GetInstanceUuid()
      primaryCfgPath = primaryVm.GetConfig().GetFiles().GetVmPathName()
      primaryDir = primaryCfgPath[:primaryCfgPath.rfind("/")]
      Log("Using VM : " + primaryVm.GetName() + " with instanceUuid " + primaryUuid)
      CheckFTState(primaryVm, FTState.notConfigured)

      # Create secondary VM
      Log("Creating secondary VM " + secondaryName)
      HandleAction("on")

      if secondaryVm == None:
          raise "Secondary VM creation failed"

      ##  Configure some additional config variables needed for FT
      ##  This should eventually be done automatically at FT Vmotion time
      Log("Setting up extra config settings for the primary VM...")
      extraCfgs = primaryVm.GetConfig().GetExtraConfig()
#      AddExtraConfig(extraCfgs, "replay.allowBTOnly", "TRUE")
#      AddExtraConfig(extraCfgs, "replay.allowFT", "TRUE")
      cSpec = vim.Vm.ConfigSpec()
      cSpec.SetExtraConfig(extraCfgs)
      task.WaitForTask(primaryVm.Reconfigure(cSpec))

      Log("FT configured successfully.")

      # Test snapshot
      #SnapshotTests(primaryVm)

      Log("PowerOn")
      task.WaitForTask(primaryVm.PowerOn())

      WaitForRunning()
      time.sleep(5)

      # We are now in a good known state, start random testing
      while True:
         action = random.choice(ACTION_LIST)
         revAction = REV_ACTION[action]
         HandleActions(action, revAction)

   except Exception as e:
      Log("Caught exception : " + str(e))
      traceback.print_exc()
      global status
      status = "FAIL"
   finally:
      connect.Disconnect(si)

def SnapshotTests(vm):
   t = RetryTask(vm.CreateSnapshot, 'poweredOffSnapshot', memory=False, quiesce=True)

   Log("Snapshot %s was taken" % t.info.result.config.name)
   RetryTask(vm.PowerOn)

   WaitForRunning()

   if vm.snapshot is not None and vm.snapshot.rootSnapshotList is not None:
      raise Exception("Snapshot %s exists" % vm.snapshot.rootSnapshotList[0].name)

   RetryTask(vm.CreateSnapshot, 'poweredOnSnapshot', memory=False, quiesce=True)

   HandleAction('makePrimary')
   HandleAction('makePrimary')

   if vm.snapshot is not None and vm.snapshot.rootSnapshotList is not None:
      raise Exception("Snapshot %s exists" % vm.snapshot.rootSnapshotList[0].name)

   RetryTask(vm.PowerOff)

# Start program
if __name__ == "__main__":
    main()
    Log("Test status: " + status)
    Log("FT Tests completed")

