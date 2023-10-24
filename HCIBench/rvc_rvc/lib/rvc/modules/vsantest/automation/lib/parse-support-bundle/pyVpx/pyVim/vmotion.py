## @file vmotion.py
## @brief VMotion operations
##
## Detailed description (for Doxygen goes here)
"""
VMotion operations

Detailed description (for [e]pydoc goes here)
"""

import os
from pyVmomi import Vim
from pyVmomi import Vmodl
from pyVmomi import vmodl
from pyVim.task import WaitForTask
from pyVim.helpers import Log
from pyVim import path
from . import host
import time
from .invt import *
from six import PY3

if PY3:
    long = int

gSupportedVmotionTypes = ['vmotion', 'fault_tolerance', 'disks_only']


##
# Returns list of VMotion types supported by this module\
##
def GetSupportedVMotionTypes():
    return gSupportedVmotionTypes


##
# Given a datastore name, looks up the corresponding datastore URL
#
# @param si       [in] Service instance to use
# @param dsName   [in] datastore name to lookup
##
def GetDsUrl(si, dsName):
    if dsName == None:
        raise Exception("No target datastore specified for storage VMotion!")
    dsList = host.GetHostSystem(si).datastore
    dsUrl = [ds.info.url for ds in dsList if ds.name == dsName]
    if not dsUrl:
        raise Exception("Target datastore %s doesn't exist" % dsName)
    return dsUrl[0]


##
# Given a target directory name and a source disk file path, generate the
# target file path.
#
# @param targetDir       [in] Target directory name
# @param diskFilePath    [in] disk file path from the backing information
##
def GetTargetFileName(targetDir, diskFilePath):
    diskName = diskFilePath[diskFilePath.rfind('/') + 1:]
    return targetDir + '/' + diskName


##
# Create disk specs needed for storage & disk only vmotions
#
# @param  vm1          [in] VM instance to migrate
# @param  targetVmDir  [in] Target directory to copy disks into
#
##
def CreateDiskSpecs(vm1, targetVmDir):
    if vm1.config == None:
        raise Exception("No config information found for VM")

    diskSpecs = []
    ctlrMap = dict([
        (dev.key, dev) for dev in vm1.config.hardware.device
        if issubclass(dev.__class__, Vim.Vm.Device.VirtualController)
    ])

    for dev in vm1.config.hardware.device:
        if issubclass(dev.__class__, Vim.Vm.Device.VirtualDisk) and \
           issubclass(dev.backing.__class__, Vim.Vm.Device.VirtualDevice.FileBackingInfo):
            spec = Vim.Host.VMotionManager.ReparentSpec()
            spec.SetUnitNumber(dev.unitNumber)
            #spec.SetDiskBackingInfo(dev.backing)
            spec.SetFilename(
                GetTargetFileName(path.DsPathToFsPath(targetVmDir),
                                  dev.backing.fileName))
            if dev.backing.parent:
                spec.SetParentFilename(
                    path.DsPathToFsPath(dev.backing.parent.fileName))
            ctlr = ctlrMap[dev.controllerKey]
            spec.SetBusNumber(ctlr.busNumber)
            spec.SetControllerType(ctlr.__class__)
            diskSpecs.append(spec)
    if len(diskSpecs) == 0:
        Log("Devices: %s" % vm1.config.hardware.device)
    return diskSpecs


##
## Helper routine that retrieves the local config file path of a VM
##
## @param vm1 [in] The VM whose config file path is to be retrieved
## @param dsPath [in] If specified, this datastore path overrides the VM's cfg file path
## @param dsUrl [in] If specified, this datastore url overrides the VM's cfg file path
##
def GetLocalCfgPath(vm1, dsPath=None, dsUrl=None):
    if dsPath == None:
        dsPath = vm1.config.files.vmPathName
    dsName = dsPath[dsPath.index("[") + 1:dsPath.rindex("]")]
    if dsName == "":
        return dsPath[dsPath.index("/"):]
    if dsUrl == None:
        datastore = [ds for ds in vm1.datastore if ds.name == dsName][0]
        dsUrl = datastore.GetInfo().GetUrl()
    relVmPath = dsPath[dsPath.rindex("]") + 2:]
    return dsUrl + "/" + relVmPath


## VMotion the VM through Hostd
#
# @param srcVm [in] The VM to be migrated
# @param srcSi [in] ServiceInstance corresponding to the source host
# @param dstSi [in] ServiceInstance corresponding to the dst host
# @param dstPath [in] The config file path of the destination VM.
# @param unsharedSwap [in] VMotion parameter for sharing the swap file
# @param vmotionType [in] The type of VMotion requested
# @param encrypt [in] Whether to use encryption for this VMotion
# @param destDs [in] Destination datatore required for storage vmotions
##
def Migrate(srcVm,
            srcSi,
            dstSi,
            dstPath=None,
            unsharedSwap=False,
            vmotionType=Vim.Host.VMotionManager.VMotionType.vmotion,
            destDs=None,
            ftType=None,
            destVm=None):
    fileMgr = srcSi.content.fileManager
    dirCreated = False
    VMotionType = Vim.Host.VMotionManager.VMotionType
    if srcVm.GetRuntime().GetPowerState(
    ) != Vim.VirtualMachine.PowerState.poweredOn:
        raise Exception("VM not powered on. Cannot VMotion.")

    if vmotionType not in gSupportedVmotionTypes:
        raise Exception("Unsupported VMotion type '%s'" % vmotionType)

    # Create the VMotion spec
    spec = Vim.Host.VMotionManager.Spec()
    migrationId = long(time.time())
    if dstPath == None:
        dstPath = srcVm.GetConfig().GetFiles().GetVmPathName()

    dsUrl = None
    srcVmotionIp = host.GetVMotionIP(srcSi)
    Log("Getting source VMotion IP " + srcVmotionIp)
    spec.SetSrcIp(srcVmotionIp)
    dstVmotionIp = host.GetVMotionIP(dstSi)
    Log("Getting destination VMotion IP " + dstVmotionIp)
    spec.SetDstIp(dstVmotionIp)
    spec.SetType(vmotionType)
    if ftType:
        spec.SetFaultToleranceType(ftType)

    spec.dstVmDirPath, spec.dstVmFileName = os.path.split(dstPath)
    spec.srcVmPathName = srcVm.GetConfig().GetFiles().GetVmPathName()

    # Specify FT logging nic information for FT VMs
    if srcVm.GetRuntime().GetFaultToleranceState(
    ) != Vim.VirtualMachine.FaultToleranceState.notConfigured:
        srcLoggingIp = host.GetLoggingIP(srcSi)
        Log("Getting source Logging IP " + srcLoggingIp)
        spec.SetSrcLoggingIp(srcLoggingIp)
        dstLoggingIp = host.GetLoggingIP(dstSi)
        Log("Getting destination Logging IP " + dstLoggingIp)
        spec.SetDstLoggingIp(dstLoggingIp)

    # Generate disk specs for disk migrations
    if vmotionType == VMotionType.disks_only:
        dsUrl = GetDsUrl(srcSi, destDs)
        targetVmDir = dsUrl + '/' + srcVm.name
        Log("Creating target VM directory %s" % targetVmDir)
        try:
            fileMgr.MakeDirectory("[] " + targetVmDir)
            dirCreated = True
        except Vim.Fault.FileAlreadyExists as e:
            Log("File already exists")
        Log("Creating disk relocation specs")
        spec.SetDiskLocations(CreateDiskSpecs(srcVm, targetVmDir))
    elif vmotionType == VMotionType.fault_tolerance and \
         spec.GetFaultToleranceType() == "fault_tolerance_using_checkpoints":
        if not destDs:
            targetVmDir = destVm.config.files.suspendDirectory
            for url in destVm.config.datastoreUrl:
                targetVmDir.replace("[%s] " % url.name, url.url)
        else:
            dsUrl = GetDsUrl(dstSi, destDs)
            targetVmDir = dsUrl + '/' + destVm.name
        Log("Creating disk relocation specs for %s" % targetVmDir)
        spec.SetDiskLocations(CreateDiskSpecs(destVm, targetVmDir))

    Log("Getting source UUID")
    spec.SetSrcUuid(host.GetHostUuid(srcSi))
    Log("Getting destination UUID")
    spec.SetDstUuid(host.GetHostUuid(dstSi))

    spec.SetPriority(Vim.VirtualMachine.MovePriority.defaultPriority)
    spec.SetUnsharedSwap(unsharedSwap)
    spec.SetMigrationId(migrationId)

    srcMgr = host.GetVmotionManager(srcSi)
    dstMgr = host.GetVmotionManager(dstSi)

    try:
        # Prepare the VMotion operation
        Log("Preparing source")
        connect.SetSi(srcSi)
        print(spec)
        prepareSrcTask = srcMgr.PrepareSourceEx(spec, srcVm)
        WaitForTask(prepareSrcTask)

        if vmotionType != VMotionType.disks_only:
            Log("Preparing destination")
            connect.SetSi(dstSi)
            resPool = host.GetRootResourcePool(dstSi)
            prepareDstTask = dstMgr.PrepareDestinationEx(spec, resPool)
            WaitForTask(prepareDstTask)

        # Initiate the VMotion operation
        if vmotionType != VMotionType.disks_only:
            if destVm is not None:
                localPath = GetLocalCfgPath(destVm, dstPath, dsUrl)
            else:
                localPath = GetLocalCfgPath(srcVm, dstPath, dsUrl)
            Log("Initiating destination with path " + localPath)
            dstState = dstMgr.InitiateDestination(migrationId, localPath)
            dstId = dstState.GetDstId()
            dstTask = dstState.GetDstTask()
        else:
            dstId = 0
        Log("Initiating source")
        connect.SetSi(srcSi)
        srcTask = srcMgr.InitiateSourceEx(migrationId, dstId)

        Log("Waiting for completion")
        try:
            if vmotionType != VMotionType.disks_only:
                WaitForTask(dstTask, si=dstSi)
            WaitForTask(srcTask, si=srcSi)
        except Vmodl.Fault.ManagedObjectNotFound as e:
            Log("Task no longer present.")
        Log("VMotion succeeded.")
    # InitiateSourceEx/Destination throw InvalidArgument
    # when a vmotion starts with an already used migrationID
    # that means if we call CompleteSource/CompleteDestination
    # we will cancel the first vmotion with that id
    except vmodl.fault.InvalidArgument as e:
        if dirCreated:
            try:
                Log("Cleaning up directory")
                fileMgr.deleteFile("[] " + targetVmDir)
            except Exception as e:
                Log("Caught exception %s while deletion directory" % e)
        Log("VMotion failed. Got exception " + str(e))
        raise
    except Exception as e:
        # Complete the VMotion operation
        Log("Completing source")
        srcMgr.CompleteSource(migrationId)
        if vmotionType != VMotionType.disks_only:
            Log("Completing destination")
            dstMgr.CompleteDestination(migrationId)

        if dirCreated:
            try:
                Log("Cleaning up directory")
                fileMgr.deleteFile("[] " + targetVmDir)
            except Exception as e:
                Log("Caught exception %s while deletion directory" % e)
        Log("VMotion failed. Got exception " + str(e))
        raise

    # Complete the VMotion operation
    Log("Completing source")
    srcMgr.CompleteSource(migrationId)
    if vmotionType != VMotionType.disks_only:
        Log("Completing destination")
        dstMgr.CompleteDestination(migrationId)
