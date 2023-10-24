## @file vm.py
## @brief Virtual Machine Management Operations
##
## Detailed description (for Doxygen goes here)
"""
Virtual Machine Management Operations

Detailed description (for [e]pydoc goes here)
"""

__author__ = "VMware, Inc"

import traceback
from pyVmomi import Vim, Vmodl
from .task import WaitForTask
from .folder import Find
from .invt import *
from . import vimutil
from . import vmconfig
from six.moves import range


## @param vm [in] Power on a VM
def PowerOn(vm):
    vimutil.InvokeAndTrack(vm.PowerOn, None)


## @param vm [in] Power off a VM
def PowerOff(vm):
    vimutil.InvokeAndTrack(vm.PowerOff)


## @param vm [in] suspend a VM
def Suspend(vm):
    vimutil.InvokeAndTrack(vm.Suspend)


## @param vm [in] suspend a VM to memory
def SuspendToMemory(vm):
    vimutil.InvokeAndTrack(vm.SuspendToMemory)


## @param vm [in] reset guest OS in a VM
def Reset(vm):
    vimutil.InvokeAndTrack(vm.Reset)


## Create a screenshot for a VM or snapshot
# @param obj [in] VM or screenshot
# @param w [in/opt] Screenshot width
# @param h [in/opt] Screenshot height
# @param x0 [in/opt] Left edge of crop rectangle
# @param y0 [in/opt] Top edge of crop rectangle
# @param x1 [in/opt] Right edge of crop rectangle
# @param y1 [in/opt] Bottom edge of crop rectangle
def GetScreenshot(obj, w=None, h=None, x0=None, y0=None, x1=None, y1=None):
    from urllib2 import URLError, HTTPError
    path = '/screen?id=%s' % (obj._moId)
    opts = [('w', w), ('h', h), ('x0', x0), ('y0', y0), ('x1', x1), ('y1', y1)]
    for (key, val) in [(k, v) for (k, v) in opts if v is not None]:
        path += '&%s=%s' % (key, val)
    try:
        return connect.OpenPathWithStub(path, obj._stub)
    except HTTPError as e:
        # Try to convert HTTP status into corresponding VIM fault
        if e.code == 404:
            # Not found
            raise Vim.Fault.NotFound()
        elif e.code == 409 and isinstance(obj, Vim.VirtualMachine):
            # Conflict: virtual machine is powered off
            raise Vim.Fault.InvalidState()
        elif e.code == 409 and isinstance(obj, Vim.Vm.Snapshot):
            # Conflict: snapshot doesn't have a screenshot
            raise Vim.Fault.InvalidState()
        else:
            from six.moves.BaseHTTPServer import BaseHTTPRequestHandler
            _, msg = BaseHTTPRequestHandler.responses[e.code]
            raise Vmodl.Fault.SystemError(reason=msg)
    except URLError as e:
        _, msg = e.reason
        raise Vmodl.Fault.SystemError(reason=msg)


## @param vm [in] snapshot state of OS in a VM
# @param name [in] name of snapshot
# @param memory [in] default to ture, capture memory state
# @param quiesce [in] default to true
def CreateSnapshot(vm, name, desc, memory=True, quiesce=True):
    return vimutil.InvokeAndTrackWithTask(vm.CreateSnapshot, name, desc,
                                          memory, quiesce).info.result


## @param snap [in] Snapshot to be reverted
def RevertSnapshot(snap):
    vimutil.InvokeAndTrack(snap.Revert)


## @param vm   [in] start a recording on a VM
#  @param name [in] name of the recording
#  @param desc [in] description of the recording
def StartRecording(vm, name, desc):
    vimutil.InvokeAndTrack(vm.StartRecording, name, desc)


## @param vm  [in] stops a recording on a VM
def StopRecording(vm):
    vimutil.InvokeAndTrack(vm.StopRecording)


## @param vm  [in] starts a replay session on a VM
## @snapshot  [in] snapshot associated with the replay
def StartReplaying(vm, snapshot):
    vimutil.InvokeAndTrack(vm.StartReplaying, snapshot)


## @param vm  [in] stops a replay session on a VM
def StopReplaying(vm):
    vimutil.InvokeAndTrack(vm.StopReplaying)


# Reverts to the current snapshot of the VM"""
## @param vm [in] vm to revert state
def RevertToCurrentSnapshot(vm, suppressPowerOn=None):
    vimutil.InvokeAndTrack(vm.RevertToCurrentSnapshot, None, suppressPowerOn)


## @param vm [in] Removes all snapshots for this VM
def RemoveAllSnapshots(vm, consolidate=True):
    vimutil.InvokeAndTrack(vm.RemoveAllSnapshots, consolidate)


## @param snap [in] Snapshot to be removed
## @param removeChildren [in|opt] Remove children if any.
def RemoveSnapshot(snap, removeChildren=True, consolidate=True):
    vimutil.InvokeAndTrack(snap.Remove, removeChildren, consolidate)


## @param vm [in] vm to consolidate
def ConsolidateDisks(vm):
    vimutil.InvokeAndTrack(vm.ConsolidateDisks)


## @param vm  [in] VM to reconfigure
## @param cspec [in] config spec to be applied
def Reconfigure(vm1, cspec):
    vimutil.InvokeAndTrack(vm1.Reconfigure, cspec)


## @param vm  [in] VM to relocate
## @param rspec [in] relocate spec to be used
def Relocate(vm1, rspec):
    vimutil.InvokeAndTrack(vm1.Relocate, rspec)


## @param vm [in] Deletes the VM with the given name
def Delete(name, powerOffVm=False):
    vm = Find(name)
    if vm == None:
        return

    if powerOffVm and vm.GetRuntime().GetPowerState() == \
           Vim.VirtualMachine.PowerState.poweredOn:
        PowerOff(vm)
    Destroy(vm)


## @param [in] Destroys the given VM
def Destroy(vm):
    vimutil.InvokeAndTrack(vm.Destroy)


## @param [in] Create a screenshot for the given VM
def CreateScreenshot(vm):
    vimutil.InvokeAndTrack(vm.CreateScreenshot)


## VMotion the VM through Hostd
# @param vm [in] The VM to be migrated
# @param srcSi [in] ServiceInstance corresponding to the source host
# @param dstSi [in] ServiceInstance corresponding to the dst host
# @param dstPath [in] The config file path of the destination VM.
# @param unsharedSwap [in] VMotion parameter for sharing the swap file
# @param vmotionType [in] The type of VMotion requested
# @param encrypt [in] Whether to use encryption for this VMotion
# @param destDs [in] Destination datatore required for storage vmotions
##
def Migrate(vm,
            srcSi,
            dstSi,
            dstPath=None,
            unsharedSwap=False,
            vmotionType=Vim.Host.VMotionManager.VMotionType.vmotion,
            destDs=None,
            ftType=None,
            destVm=None):
    from . import vmotion
    vmotion.Migrate(vm, srcSi, dstSi, dstPath, unsharedSwap, vmotionType,
                    destDs, ftType, destVm)


## Create a rudimentary secondaray virtual machine
# @param vmname [in] name of vm
# @param primaryVm [in] vm of the primary
# @param role [in] FT role of this secondary VM
# @param resPool [in] Resource pool to create this VM under
# @param host [in] Host object the VM will be on
# @param ftType [in] Type of FT to use (up/smp)
# @param numScsiDisks [in] Number of disks primary VM has (for smp-ft only)
# @param scrubDisks [in] Whether to scrub the disks or not
# @param ftMetadataDir [in] Path to the metadata directory (for SMP-FT)
def CreateQuickSecondary(vmname,
                         primaryVm,
                         role=2,
                         resPool=None,
                         host=None,
                         ftType="up",
                         datastoreName=None,
                         numScsiDisks=0,
                         scrubDisks=True,
                         ftMetadataDir=None):
    config = CreateQuickDummySpec(vmname,
                                  guest="winXPProGuest",
                                  numScsiDisks=numScsiDisks,
                                  scrubDisks=scrubDisks,
                                  memory=primaryVm.config.hardware.memoryMB,
                                  datastoreName=datastoreName)
    primaryName = primaryVm.GetName()
    primaryUuid = primaryVm.GetConfig().GetInstanceUuid()
    primaryCfgPath = primaryVm.GetConfig().GetFiles().GetVmPathName()
    primaryDir = primaryCfgPath[:primaryCfgPath.rfind("/")]
    config.numCPUs = primaryVm.GetConfig().GetHardware().GetNumCPU()

    # Setup Fault Tolerance Info
    ftInfo = Vim.Vm.FaultToleranceConfigInfo()
    ftInfo.SetRole(role)
    ftInfo.SetInstanceUuids([primaryUuid])
    ftInfo.SetConfigPaths([primaryCfgPath])
    config.SetFtInfo(ftInfo)

    # Setup the directory in which the secondary VM must reside
    vmFiles = config.GetFiles()
    if ftType == "smp":
        secondaryName = vmname if vmname != primaryName else "_%s" % vmname
        vmFiles.SetVmPathName("[%s] %s/%s.vmx" %
                              (datastoreName, vmname, secondaryName))
    else:
        vmFiles.SetVmPathName(primaryDir)

    if ftMetadataDir is not None:
        vmFiles.SetFtMetadataDirectory(ftMetadataDir)
    config.SetFiles(vmFiles)
    config.SetFlags(vim.vm.FlagInfo())
    # Set some extraConfig options for FT

    # Set the record/replay enabled flag
    if ftType == "up":
        config.extraConfig.append(
            Vim.Option.OptionValue(key="replay.allowBTOnly", value="TRUE"))
        config.flags.faultToleranceType = vim.VirtualMachine.FaultToleranceType.recordReplay
    else:
        config.flags.faultToleranceType = vim.VirtualMachine.FaultToleranceType.checkpointing
        config.extraConfig.append(
            Vim.Option.OptionValue(key="sched.mem.pshare.enable",
                                   value="FALSE"))
        config.extraConfig.append(
            Vim.Option.OptionValue(
                key="monitor_control.disable_mmu_largepages", value="TRUE"))
        config.extraConfig.append(
            Vim.Option.OptionValue(key="sched.mem.min",
                                   value=primaryVm.config.hardware.memoryMB))

    if resPool == None:
        resPool = GetResourcePool()

    vmFolder = GetVmFolder()
    task = vmFolder.CreateVm(config, resPool, host)
    WaitForTask(task)
    return task.info.result


## Create a rudimentary virtual machine. Great for fast action
# create/deletes.
# @param config [in] configSpec, probably from CreateQuickDummySpec
def CreateFromSpec(config,
                   dc=None,
                   host=None,
                   resPool=None,
                   vmFolder=None,
                   si=None):
    if resPool == None:
        resPool = GetResourcePool(dc, si)

    if vmFolder == None:
        vmFolder = GetVmFolder(dc, si)

    task = vmFolder.CreateVm(config, resPool, host)
    WaitForTask(task=task, si=si)
    vm = task.info.result
    return vm


## Create a rudimentary virtual machine. Great for fast action
# create/deletes.
# @param vmname [in] name of vm
# @param disk [in] disk to use
# @param nic [in] network interface to use
# @param cdrom [in] cdrom to use
def CreateQuickDummy(vmname, numScsiDisks = 0, numIdeDisks = 0, \
                     nic = 0, cdrom = 0, host = None, memory = 128, \
                     resPool = None, envBrowser = None, diskSizeInMB = 4, \
                     networkName = None, datastoreName = None,
                     videoRamSize = -1, vmxVersion = None, guest = "dosGuest",
                     scsiCtlrs = 0, scrubDisks = False, cfgOption = None,
                     cfgTarget = None, backingType = "flat", thin = False,
                     dc=None, vmFolder = None, policy = None,
                     vmFolderName = None, si = None):
    config = CreateQuickDummySpec(vmname,
                                  numScsiDisks,
                                  numIdeDisks,
                                  nic,
                                  cdrom,
                                  envBrowser,
                                  diskSizeInMB,
                                  memory,
                                  networkName,
                                  datastoreName,
                                  videoRamSize,
                                  vmxVersion,
                                  guest,
                                  scsiCtlrs,
                                  scrubDisks,
                                  cfgOption,
                                  cfgTarget,
                                  backingType,
                                  thin=thin,
                                  dc=dc,
                                  policy=policy,
                                  vmFolderName=vmFolderName,
                                  si=si)
    return CreateFromSpec(config,
                          dc=dc,
                          host=host,
                          resPool=resPool,
                          vmFolder=vmFolder,
                          si=si)


def CreateQuickDummySpec(vmname,
                         numScsiDisks=0,
                         numIdeDisks=0,
                         nic=0,
                         cdrom=0,
                         envBrowser=None,
                         diskSizeInMB=4,
                         memory=128,
                         networkName=None,
                         datastoreName=None,
                         videoRamSize=-1,
                         vmxVersion=None,
                         guest="dosGuest",
                         scsiCtlrs=0,
                         scrubDisks=False,
                         cfgOption=None,
                         cfgTarget=None,
                         backingType="flat",
                         thin=False,
                         ctlrType="lsilogic",
                         dc=None,
                         policy=None,
                         vmFolderName=None,
                         si=None):

    if envBrowser == None:
        envBrowser = GetEnv(dc, si)

    if not cfgOption:
        cfgOption = envBrowser.QueryConfigOption(None, None)

    if not cfgTarget:
        cfgTarget = envBrowser.QueryConfigTarget(None)

    if datastoreName == None:
        # Pick the first datastore and create a spec based on it.
        dsList = cfgTarget.GetDatastore()
        if not dsList:
            raise Exception("No datastore available to create VM.")
        dsname = None
        for ds in dsList:
            if ds.GetDatastore().GetAccessible():
                dsname = ds.GetDatastore().GetName()
                break
        if dsname == None:
            raise Exception("No available datastore")
    else:
        dsname = datastoreName
    config = vmconfig.CreateDefaultSpec(name=vmname,
                                        datastoreName=dsname,
                                        memory=memory,
                                        guest=guest,
                                        policy=policy,
                                        vmFolderName=vmFolderName)
    if vmxVersion != None:
        config.SetVersion(vmxVersion)
    currentKey = -1
    deviceChange = []
    config.SetDeviceChange(deviceChange)

    # Add scsi controller
    numDiskPerScsiCtlr = 15
    numCtlr = (numScsiDisks + numDiskPerScsiCtlr - 1) // numDiskPerScsiCtlr
    if numCtlr == 0:
        numCtlr = scsiCtlrs

    for c in range(numCtlr):
        config = vmconfig.AddScsiCtlr(config,
                                      cfgOption,
                                      cfgTarget,
                                      ctlrType=ctlrType)

    # Add scsi disk
    for d in range(numScsiDisks):
        config = vmconfig.AddScsiDisk(config, cfgOption, cfgTarget, \
        capacity=(diskSizeInMB * 1024), datastorename = dsname,
        scrub = scrubDisks, backingType = backingType, thin = thin, policy=policy)

    # Add ide disk
    for d in range(numIdeDisks):
        config = vmconfig.AddIdeDisk(config, cfgOption, cfgTarget, \
        capacity=(diskSizeInMB * 1024), datastorename = dsname,
               backingType = backingType, policy = policy)

    # Add nic
    for d in range(nic):
        config = vmconfig.AddNic(config,
                                 cfgOption,
                                 cfgTarget,
                                 devName=networkName)

    # Add cdrom
    for d in range(cdrom):
        config = vmconfig.AddCdrom(config, cfgOption, cfgTarget)

    # Add video card
    if videoRamSize != -1:
        config = vmconfig.AddVideoCard(config, cfgOption, cfgTarget,
                                       videoRamSize)

    return config


## Power off all vms specified. Raise an exception if a vm is still
# powered on at the end
# @param vmList [in] list of VM to power down
def PowerOffAllVms(vmList):
    for vmIter in vmList:
        if (vmIter.GetRuntime().GetPowerState() !=
                vmIter.PowerState.POWEREDOFF):
            try:
                PowerOff(vmIter)
            except:
                traceback.print_exc()
                # still not powered off?
            if (vmIter.GetRuntime().GetPowerState() !=
                    vmIter.PowerState.POWEREDOFF):
                # give up
                raise Exception("Unable to initialize all VMs to" +
                                "power off state (problem with " +
                                vmIter.GetName() + ")")


## Create a vm of specified name or return an existing vm of same name
# @param name [in] vm name to generate or find
# @param disk [in] to use if vm not found
def CreateOrReturnExisting(name, disk=0):
    vmnew = Find(name)
    if vmnew == None:
        vmnew = CreateQuickDummy(name, disk)
    return vmnew


def RemoveDevice(vm1, device, fileop=None):
    # Helper to do the removal of a single device.
    cspec = Vim.Vm.ConfigSpec()
    cspec = vmconfig.RemoveDeviceFromSpec(cspec, device, fileop)
    task = vm1.Reconfigure(cspec)
    WaitForTask(task)


## Provides managed operations against a single Virtual Machine
class VM:
    ## @param moRef [in] VM retrieved from host
    # @param propC [in] property collector instance to use
    # @param config [in] configuration of this VM
    # config is result of moRef->GetConfig()
    def __init__(self, moRef, propC, resPool, config=None):
        if moRef is None:
            raise Exception("moRef must be specified")
        self._mo = moRef
        self._pc = propC
        if config is None:
            config = self._mo.GetConfig()
        if config is not None:
            self._vmname = config.GetName()
            self._vmuuid = config.GetUuid()
            self._vmxFile = config.GetFiles().GetVmPathName()
        else:
            self._vmname = "amnesiac"
            self._vmxFile = "unknown"
        self._pool = resPool
        self._template = False
        self._host = None

    ## @return user oriented version
    def __str__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, self._vmxFile,
                               self._vmname)

    ## @return programmer oriented version
    def __repr__(self):
        return "'%s(%s)'" % (self.__class__.__name__, self._vmname)

    def __del__(self):
        self._mo = None
        self._vmname = None
        self._pc = None

    ## Return configuration of this VM
    def GetConfig(self):
        return self._mo.GetConfig()

    ## Power on a VM
    # @pre VM is not powered on
    # @post VM is powered on
    def PowerOn(self):
        rqt = vimutil.Request(self._pc, self._mo.PowerOn, None)
        rqt.Invoke()

    ## Power off a VM
    # @pre VM is powered on
    # @post VM is powered off
    def PowerOff(self):
        rqt = vimutil.Request(self._pc, self._mo.PowerOff)
        rqt.Invoke()

    ## Suspend a VM
    # @pre VM is powered on
    # @post VM is suspended
    def Suspend(self):
        rqt = vimutil.Request(self._pc, self._mo.Suspend)
        rqt.Invoke()

    ## Reset a VM
    # @pre VM is powered on
    # @post VM is rebooted
    def Reset(self):
        rqt = vimutil.Request(self._pc, self._mo.Reset)
        rqt.Invoke()

    ## Save state of a VM to disk
    # @pre VM is powered on, Snaphost is enabled
    # @post A snapshot is saved to disk
    def CreateSnapshot(self, name, desc, memory=True, quiesce=True):
        rqt = vimutil.Request(self._pc, self._mo.CreateSnapshot, name, desc,
                              memory, quiesce)
        rqt.Invoke()

    ## reconfigure number of vpus for this vm
    # @pre VM is powered off
    def SetVpu(self, vpus):
        if self.IsRunning():
            raise Exception("VM Must be powered off state to reconfigure VPUs")
        cspec = Vim.Vm.ConfigSpec()
        cspec.version = "6"
        cspec.numCPUs = vpus
        rqt = vimutil.Request(self._pc, self._mo.Reconfigure, cspec)
        rqt.Invoke()

    ## Restore VM to most current saved state
    # @pre VM is powered on, Snapshot is enabled
    # @post VM is running current snapshot
    def RevertToCurrentSnapshot(self):
        rqt = vimutil.Request(self._pc, self._mo.RevertToCurrentSnapshot, None)
        rqt.Invoke()

    ## Release all storage used to save VM state
    # @pre VM is running
    # @post This VM's snapshot files are removed
    def RemoveAllSnapshots(self):
        rqt = vimutil.Request(self._pc, self._mo.RemoveAllSnapshots)
        rqt.Invoke()

    ## Start a recording session on the VM
    # @pre VM is powered on, Record/replay flag is enabled
    # @post a recording session is initiated
    def StartRecording(self, name, desc):
        rqt = vimutil.Request(self._pc, self._mo.StartRecording, name, desc)
        rqt.Invoke()

    ## Stops an recording session on the VM
    # @pre VM is powered on and has an active recording session
    # @post a recording session is stopped
    def StopRecording(self):
        rqt = vimutil.Request(self._pc, self._mo.StopRecording)
        rqt.Invoke()

    ## Start a replaying session on the VM
    # @pre Record/replay flag is enabled and the VM has
    #      at least one replayable snapshot
    # @post a replaying session is initiated
    def StartReplaying(self, snapshot):
        rqt = vimutil.Request(self._pc, self._mo.StartReplaying, snapshot)
        rqt.Invoke()

    ## Stops a replaying session on the VM
    # @pre VM is powered on and has an active replaying session
    # @post a replaying session is stopped
    def StopReplaying(self):
        rqt = vimutil.Request(self._pc, self._mo.StopReplaying)
        rqt.Invoke()

    ## @pre VM is not running,
    # @post cached guest info is cleared
    def ResetGuestInformation(self):
        rqt = vimutil.Request(self._pc, self._mo.ResetGuestInformation)
        rqt.Invoke()

    ## @pre VM is running and has tools installed
    # @post Guest OS initiates shutdown procedure
    def ShutdownGuest(self):
        rqt = vimutil.Request(self._pc, self._mo.ShutdownGuest)
        rqt.Invoke()

    ## @pre VM is running and has tools installed
    # @post Guest OS initiates reboot procedure
    def RebootGuest(self):
        rqt = vimutil.Request(self._pc, self._mo.RebootGuest)
        rqt.Invoke()

    ## @pre VM is running and has tools installed
    # @post Guest OS initiates standby procedure
    def StandbyGuest(self):
        rqt = vimutil.Request(self._pc, self._mo.StandbyGuest)
        rqt.Invoke()

    ##
    ## @pre VM is running and has tools installed, using TCP to connect to VM
    ## @post Returns one-time credential VirtualMachine.MksTicket
    ##
    def AcquireMksTicket(self):
        rqt = vimutil.Request(self._pc, self._mo.AcquireMksTicket)
        rqt.Invoke()

    ##
    ## @pre VM is running and has tools installed, using TCP to connect to VM
    ## @post Returns one-time credential VirtualMachine.Ticket
    ##
    def AcquireTicket(self, ticketType):
        rqt = vimutil.Request(self._pc, self._mo.AcquireTicket, ticketType)
        rqt.Invoke()

    ##
    ## @param width Screen width in pixels
    ## @param height Screen height in pixels
    ## @pre VM is running and has tools installed
    ## @post VM console changed to new width and height
    ##
    def SetScreenResolution(self, width, height):
        rqt = vimutil.Request(self._pc, self._mo.SetScreenResolution, width,
                              height)
        rqt.Invoke()

    ##
    ## @param spec is of type Vim.Vm.Customization.Specification
    ## @pre VM is running and has tools installed
    ## @post Guest OS initiates standby procedure
    ##
    def Customize(self, spec):
        rqt = vimutil.Request(self._pc, self._mo.Customize, spec)
        rqt.Invoke()

    ##
    ## @param spec is of type Vim.Vm.Customization.Specification
    ## @pre preconfigured CDROM to this VM is not already mounted
    ## @post preconfigured CDROM added to VM
    ##
    def CheckCustomizationSpec(self, spec):
        rqt = vimutil.Request(self._pc, self._mo.CheckCustomizationSpec, spec)
        rqt.Invoke()

    ##
    ## Change VM settings
    ##
    ## @param cfgspec [in] is type Vim.Vm.ConfigSpec
    ## @pre VM is running and has tools installed
    ## @post Guest OS initiates standby procedure
    ##
    def Reconfigure(self, cfgspec):
        rqt = vimutil.Request(self._pc, self._mo.Reconfigure, cfgspec)
        rqt.Invoke()

    ##
    ## Answer outstanding question from VM
    ##
    ## @param qid is question id
    ## @param choice is anwser to qid
    ## @pre VM is asking a question
    ## @post VM question is answered
    ##
    def Answer(self, qid, choice):
        rqt = vimutil.Request(self._pc, self._mo.Answer, qid, choice)
        rqt.Invoke()

    ##
    ## Mount VM Tools onto guest OS cdrom drive
    ##
    ## @pre preconfigured CDROM to this VM is not already mounted
    ## @post preconfigured CDROM added to VM
    ##
    def MountToolsInstaller(self):
        rqt = vimutil.Request(self._pc, self._mo.MountToolsInstaller)
        rqt.Invoke()

    ##
    ## Unmount VM Tools from guest OS cdrom drive
    ## @pre preconfigured CDROM is already mounted
    ## @post preconfigured CDROM removed from VM
    ##
    def UnmountToolsInstaller(self):
        rqt = vimutil.Request(self._pc, self._mo.UnmountToolsInstaller)
        rqt.Invoke()

    ## Bring tools in Guest OS up to current VM version
    #  @post tools software install initiated
    def UpgradeTools(self, opts=None):
        rqt = vimutil.Request(self._pc, self._mo.UpgradeTools, opts)
        rqt.Invoke()

    ## Change VM to template type
    #  @post This VM changed to template (can't be powered on)
    def MarkAsTemplate(self):
        rqt = vimutil.Request(self._pc, self._mo.MarkAsTemplate)
        rqt.Invoke()

    ## Change VM to normal type
    #  @post This VM is changed to plain virtual machine
    def MarkAsVirtualMachine(self):
        rqt = vimutil.Request(self._pc, self._mo.MarkAsTemplate)
        rqt.Invoke()

    ## @param version [in] ??
    # @post Revise this VM's devices to comply with the host's current version
    def UpgradeVirtualHardware(self, version=None):
        rqt = vimutil.Request(self._pc, self._mo.UpgradeVirtualHardware, None)
        rqt.Invoke()

    ## Make a copy of this VM
    # @param folder [in]
    # @param name [in]
    # @param spec [in]
    def Clone(self, folder, name, spec):
        rqt = vimutil.Request(self._pc, self._mo.Clone, folder, name, spec)
        rqt.Invoke()

    ## Move this VM
    # @param pool [in]
    # @param host [in]
    # @param priority [in]
    # @param state [in]
    def Migrate(self, pool=None, host=None, priority=1, state=None):
        priority = 'lowPriority'
        ## @todo use Vim.VirtualMachine.MovePriority.lowPriority
        rqt = vimutil.Request(self._pc, self._mo.Migrate, pool, host, priority,
                              state)
        rqt.Invoke()

    ## @param spec [in]
    #
    def Relocate(self, spec):
        rqt = vimutil.Request(self._pc, self._mo.Relocate, spec)
        rqt.Invoke()

    ## Unregister a VM from hostd inventory
    # @post VM state is removed from hostd
    #       (stats, resource pool, alarms, permissions)
    def Unregister(self):
        rqt = vimutil.Request(self._pc, self._mo.Unregister)
        rqt.Invoke()

    ## @todo describe what is done here
    #
    def Destroy(self):
        rqt = vimutil.Request(self._pc, self._mo.Destroy, None)
        rqt.Invoke()

    ## @post no internal state change
    # @return true if vm is in suspended state else false
    def IsSuspended(self):
        rt = self._mo.GetRuntime()
        ps = rt.GetPowerState()
        # @todo how to use the generated constant?
        if ps is not None and ps == 'suspended':
            question = rt.GetQuestion()
            if question is None:
                return True
        return False

    ## @post no internal state change
    # @return true if vm is powered up (and not waiting for questions)
    #         else false
    def IsRunning(self):
        rt = self._mo.GetRuntime()
        ps = rt.GetPowerState()
        ## @todo how to use the generated constant?
        if ps is not None and ps == 'poweredOn':
            question = rt.GetQuestion()
            if question is None:
                return True
        return False

    ## Check if VM is powered off w/o any outstanding question
    # @return true if vm is powered off else False
    # @post no internal state change
    def IsPoweredOff(self):
        rt = self._mo.GetRuntime()
        ps = rt.GetPowerState()
        ## @todo how to use the generated constant?
        if ps is not None and ps == 'poweredOff':
            question = rt.GetQuestion()
            if question is None:
                return True
        return False

    ## @post no internal state change
    # @return True if VM is waiting for answer to a question else False
    def IsWaitingForAnswer(self):
        rt = self._mo.GetRuntime()
        question = rt.GetQuestion()
        if question is not None:
            return False
        return True

    ## Get state of VMware tools installed in guest OS
    # @return True if tools are running else False
    def IsVMToolsRunning(self):
        if "green" == self._mo.GetGuestHeartbeatStatus():
            return True
        else:
            return False

    ## Return state of this VM
    # @return a string that provides the current name, uuid,
    # powerstate, and any question vm is asking of operator.
    # If no question, then add connection state
    def ReportState(self):
        rt = self._mo.GetRuntime()
        rpt = "VM: %s(%s) is %s" % (self._vmname, self._vmuuid,
                                    rt.GetPowerState())
        question = rt.GetQuestion()
        if question is not None:
            rpt += " VM halted pending answer to: %s" % (question.GetText())
        else:
            rpt += " connection state: " + rt.GetConnectionState()
        return rpt
