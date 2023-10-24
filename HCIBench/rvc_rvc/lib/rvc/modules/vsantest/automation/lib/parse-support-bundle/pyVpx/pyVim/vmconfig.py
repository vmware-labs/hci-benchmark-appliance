#############################################################
# Copyright (c) 2005-2022 VMware, Inc.  All rights reserved.
# -- VMware Confidential
#############################################################

## @file vmconfig.py
## @brief Virtual Machine Configuration Operations
##
## Detailed description (for Doxygen goes here)
"""
Virtual Machine Configuration Operations

Detailed description (for [e]pydoc goes here)
"""

from pyVmomi import Vim, Vmodl
from .invt import *
import six
from six import PY3
from six.moves import range

if PY3:
    long = int


def GetFreeKey(cspec):
    """ Get a free key for a new device in the spec """
    minkey = -1
    deviceChange = cspec.GetDeviceChange()
    if deviceChange == None:
        return minkey
    for devSpec in deviceChange:
        if minkey >= devSpec.GetDevice().GetKey():
            minkey = devSpec.GetDevice().GetKey() - 1
    return minkey


def GetCnxInfo(conInfo):
    """ Function guarantees a connection info that is sufficiently populated """
    if conInfo == None:
        conInfo = Vim.Vm.Device.VirtualDevice.ConnectInfo()
        conInfo.SetAllowGuestControl(True)
        conInfo.SetConnected(False)
        conInfo.SetStartConnected(False)
    return conInfo


def GetCfgOption(cfgOption):
    if cfgOption == None:
        envBrowser = GetEnv()
        cfgOption = envBrowser.QueryConfigOption(None, None)
    return cfgOption


def GetCfgTarget(cfgTarget):
    if cfgTarget == None:
        envBrowser = GetEnv()
        cfgTarget = envBrowser.QueryConfigTarget(None)
    return cfgTarget


def GetDeviceOptions(devType, cfgOption=None):
    foundOptions = []
    if cfgOption == None:
        cfgOption = GetCfgOption()
    for opt in cfgOption.GetHardwareOptions().GetVirtualDeviceOption():
        if isinstance(opt, devType):
            foundOptions.append(opt)
    return foundOptions


def FindDatastoreWithSpace(cfgTarget, capacity):
    """ Find a datastore with specified amount of space """
    datastores = cfgTarget.GetDatastore()
    for datastore in datastores:
        if datastore.GetDatastore().GetAccessible() == True and \
           datastore.GetDatastore().GetFreeSpace() > capacity:
            return datastore
    raise Exception("Failed to find a datastore with sufficient space")


def GetDeviceName(devName, deviceFn):
    """ Get the first device if used didnt pick one already """
    if devName == None:
        if len(deviceFn()) > 0:
            devName = deviceFn()[0].GetName()
        else:
            raise Exception("No device available on the host to add")
    return devName


def GetControllers(cfgOption, controllerType, cfgInfo=None, cspec=None):
    """ Get all controllers of specified type """
    ctlrs = []
    for device in cfgOption.GetDefaultDevice():
        if isinstance(device, controllerType):
            ctlrs.append(device)
    if cfgInfo != None:
        for device in cfgInfo.GetHardware().GetDevice():
            if isinstance(device, controllerType):
                ctlrs.append(device)
    if cspec != None:
        for device in GetDeviceListFromSpec(cspec):
            if isinstance(device, controllerType):
                ctlrs.append(device)
    return ctlrs


def GetDeviceListFromSpec(cspec):
    """ Get an array of devices that is currently present in the config spec """
    devices = []
    deviceChange = cspec.GetDeviceChange()
    if deviceChange == None:
        return devices
    for devSpec in deviceChange:
        if devSpec.GetOperation() != \
                Vim.Vm.Device.VirtualDeviceSpec.Operation.remove:
            devices.append(devSpec.GetDevice())
    return devices


def GetFreeSlot(cspec, cfgInfo, cfgOption, ctlr):
    """ Get a free slot that is available on this controller """
    usedUnitNumbers = []
    devices = GetDeviceListFromSpec(cspec)
    if cfgInfo != None:
        devices.extend(cfgInfo.GetHardware().GetDevice())
    for device in devices:
        if device.GetControllerKey() == ctlr.GetKey():
            usedUnitNumbers.append(device.GetUnitNumber())
    # Find the lowest unused number. This might exceed max allowed devices.
    # In case device is scsi ctlr, drop the one special number
    slot = 0
    maxDevices = -1
    if isinstance(ctlr, Vim.Vm.Device.VirtualSCSIController):
        for opt in cfgOption.GetHardwareOptions().GetVirtualDeviceOption():
            if isinstance(opt, Vim.Vm.Device.VirtualSCSIControllerOption):
                # VirtualControllerOption.devices.max doesn't include the slot
                # used by scsi controller itself
                maxDevices = opt.GetDevices().GetMax() + 1
                usedUnitNumbers.append(opt.GetScsiCtlrUnitNumber())
                break
    elif isinstance(ctlr, Vim.Vm.Device.VirtualIDEController):
        for opt in cfgOption.GetHardwareOptions().GetVirtualDeviceOption():
            if isinstance(opt, Vim.Vm.Device.VirtualIDEControllerOption):
                maxDevices = opt.GetDevices().GetMax()
    elif isinstance(ctlr, Vim.Vm.Device.VirtualPCIController):
        for opt in cfgOption.GetHardwareOptions().GetVirtualDeviceOption():
            if isinstance(opt, Vim.Vm.Device.VirtualPCIControllerOption):
                maxDevices = opt.GetDevices().GetMax()
    elif isinstance(ctlr, Vim.Vm.Device.VirtualSATAController):
        for opt in cfgOption.GetHardwareOptions().GetVirtualDeviceOption():
            if isinstance(opt, Vim.Vm.Device.VirtualSATAControllerOption):
                maxDevices = opt.GetDevices().GetMax()

    # the controller cannot support more devices! pr 406265
    if len(usedUnitNumbers) >= maxDevices:
        return -1

    # grab an available slot
    # it would be nice if the return value was used in AddDisk()
    usedUnitNumbers.sort()
    for i in usedUnitNumbers:
        if slot < i:
            break
        elif slot == i:
            slot = slot + 1

    return slot


# In future this should be the correct function to use when getting the free
# slot for a disk. For the moment it will not replace GetFreeSlot completely as
# some of the callers to AddDisk do not specify the config of the vm. In such a
# case the new implementation would fail with vim.fault.InvalidDeviceSpec as
# GetFreeDiskUnitNumber would return an already taken unit number.
def GetFreeDiskUnitNumber(cspec, cfgInfo, cfgOption, ctlr, unitNumber):
    """ Get a free disk unit number on a given controller """
    # If the unitNumber is set to a free slot, it will be assigned to the disk.
    # In case the unitNumber is not free, the request will fail.
    # When the unitNumber is unset and there are no more free slots on the
    # controller, the request will fail. Otherwise the next free slot will be
    # assigned.

    ctlrKey = ctlr.GetKey()
    deviceList = GetDeviceListFromSpec(cspec)
    if cfgInfo != None:
        deviceList.extend(cfgInfo.GetHardware().GetDevice())
    usedUnitNumbers = []
    diskNumbers = 0

    for device in deviceList:
        if device.GetKey() == ctlrKey and \
           (isinstance(device, Vim.Vm.Device.VirtualSCSIControllerOption) or \
            isinstance(device, Vim.Vm.Device.ParaVirtualSCSIController)):
            if ctlr.GetScsiCtlrUnitNumber():
                devUnitNumber = ctlr.GetScsiCtlrUnitNumber()
            else:
                continue
        else:
            if device.GetControllerKey() == ctlrKey:
                devUnitNumber = device.GetUnitNumber()

                if isinstance(device, Vim.Vm.Device.VirtualDisk):
                    diskNumbers = diskNumbers + 1
            else:
                continue

        # This unit number is already taken
        if unitNumber and unitNumber == devUnitNumber:
            raise Vmodl.Fault.InvalidArgument

        usedUnitNumbers.append(devUnitNumber)

    # If the unit number is unset, try to find a free slot on the controller
    if not unitNumber or unitNumber == -1:
        # The controller already has the maximum number of disks
        if diskNumbers >= GetControllerMaxDisks(cfgOption, ctlr):
            raise Vim.Fault.InvalidController
        else:
            unitNumber = 0

            if usedUnitNumbers:
                usedUnitNumbers.sort()

                lastIndex = len(usedUnitNumbers) - 1
                if lastIndex == usedUnitNumbers[lastIndex]:
                    return lastIndex + 1

                while unitNumber == usedUnitNumbers[unitNumber]:
                    unitNumber = unitNumber + 1

    return unitNumber


def GetControllerMaxDisks(cfgOption, ctlr):
    """ Get the max disks supported by a the given controller """
    maxDisks = 0
    if isinstance(ctlr, Vim.Vm.Device.ParaVirtualSCSIController):
        for opt in cfgOption.GetHardwareOptions().GetVirtualDeviceOption():
            if isinstance(opt, Vim.Vm.Device.ParaVirtualSCSIControllerOption):
                maxDisks = opt.GetNumSCSIDisks().GetMax()
                break
    elif isinstance(ctlr, Vim.Vm.Device.VirtualSCSIController):
        for opt in cfgOption.GetHardwareOptions().GetVirtualDeviceOption():
            if isinstance(opt, Vim.Vm.Device.VirtualSCSIControllerOption):
                maxDisks = opt.GetNumSCSIDisks().GetMax()
                break
    elif isinstance(ctlr, Vim.Vm.Device.VirtualIDEController):
        for opt in cfgOption.GetHardwareOptions().GetVirtualDeviceOption():
            if isinstance(opt, Vim.Vm.Device.VirtualIDEControllerOption):
                maxDisks = opt.GetDevices().GetMax()
                break
    elif isinstance(ctlr, Vim.Vm.Device.VirtualPCIController):
        for opt in cfgOption.GetHardwareOptions().GetVirtualDeviceOption():
            if isinstance(opt, Vim.Vm.Device.VirtualPCIControllerOption):
                maxDisks = opt.GetDevices().GetMax()
                break
    elif isinstance(ctlr, Vim.Vm.Device.VirtualSATAController):
        for opt in cfgOption.GetHardwareOptions().GetVirtualDeviceOption():
            if isinstance(opt, Vim.Vm.Device.VirtualSATAControllerOption):
                maxDisks = opt.GetDevices().GetMax()
                break

    return maxDisks


def GetFreeBusNumber(cfgOption, ctlrType, cfgInfo, cspec):
    ctlrs = GetControllers(cfgOption, ctlrType, cfgInfo, cspec)
    usedBusNumbers = []
    for dev in ctlrs:
        usedBusNumbers.append(dev.GetBusNumber())
    slot = 0
    for i in sorted(usedBusNumbers):
        if slot < i:
            break
        elif slot == i:
            slot = slot + 1
    return slot


def CreateProfileSpec(policy):
    profileSpec = []
    #
    # Even though the correct signature is to expect a profile,
    # to accommodate earlier workarounds that bypassed SPBM, accept
    # strings with raw profile data.
    #
    if isinstance(policy, Vim.Vm.ProfileSpec):
        profileSpec.append(policy)
    else:  # isinstance(policy, string):
        pspec = Vim.Vm.DefinedProfileSpec()
        pspec.SetProfileId('')
        rawData = Vim.Vm.ProfileRawData()
        rawData.SetExtensionKey("com.vmware.vim.sps")
        rawData.SetObjectData(policy)
        pspec.SetProfileData(rawData)
        profileSpec.append(pspec)

    return profileSpec

def CreateDefaultSpec(name = "Dummy VM", memory = 128, guest = "otherGuest", \
                      annotation = "Quick Dummy", cpus = 1, \
                      datastoreName = None, policy = None, \
                      vmFolderName = None):
    cspec = Vim.Vm.ConfigSpec()
    cspec.SetAnnotation(annotation)
    cspec.SetMemoryMB(long(memory))
    cspec.SetGuestId(guest)
    cspec.SetName(name)
    cspec.SetNumCPUs(cpus)
    files = Vim.Vm.FileInfo()
    if (datastoreName == None):
        raise Exception("Invalid datastore")
    vmPathNameStr = "[" + datastoreName + "]"
    if vmFolderName != None:
        vmPathNameStr += " " + vmFolderName
    files.SetVmPathName(vmPathNameStr)
    cspec.SetFiles(files)

    if policy != None:
        profileSpec = CreateProfileSpec(policy)
        cspec.SetVmProfile(profileSpec)

    return cspec


def AddDeviceToSpec(cspec,
                    device,
                    op=None,
                    fileop=None,
                    policy=None,
                    crypto=None,
                    changeMode=None):
    """ Add a device to the given spec """
    devSpec = Vim.Vm.Device.VirtualDeviceSpec()
    if op != None:
        devSpec.SetOperation(op)
    if fileop != None:
        devSpec.SetFileOperation(fileop)
    devSpec.SetDevice(device)

    if policy != None:
        profileSpec = CreateProfileSpec(policy)
        devSpec.SetProfile(profileSpec)

    if crypto != None:
        backingSpec = Vim.Vm.Device.VirtualDeviceSpec.BackingSpec()
        backingSpec.SetCrypto(crypto)
        devSpec.SetBacking(backingSpec)

    if changeMode != None:
        devSpec.SetChangeMode(changeMode)

    if cspec.GetDeviceChange() == None:
        cspec.SetDeviceChange([])
    deviceChange = cspec.GetDeviceChange()
    deviceChange.append(devSpec)
    cspec.SetDeviceChange(deviceChange)
    return cspec


def RemoveDeviceFromSpec(cspec, device, fileop=None):
    """ Remove the specified device from the vm """
    devSpec = Vim.Vm.Device.VirtualDeviceSpec()
    devSpec.SetDevice(device)
    devSpec.SetOperation(Vim.Vm.Device.VirtualDeviceSpec.Operation.remove)
    if fileop != None:
        devSpec.SetFileOperation(fileop)

    if cspec.GetDeviceChange() == None:
        cspec.SetDeviceChange([])
    deviceChange = cspec.GetDeviceChange()
    deviceChange.append(devSpec)
    cspec.SetDeviceChange(deviceChange)
    return cspec


def GetNic(type):
    if type == "pcnet":
        return Vim.Vm.Device.VirtualPCNet32()
    elif type == "e1000":
        return Vim.Vm.Device.VirtualE1000()
    elif type == "vmxnet":
        return Vim.Vm.Device.VirtualVmxnet()
    elif type == "vmxnet3":
        return Vim.Vm.Device.VirtualVmxnet3()
    elif type == "e1000e":
        return Vim.Vm.Device.VirtualE1000e()
    elif type == "vrdma":
        return Vim.Vm.Device.VirtualVmxnet3Vrdma()
    else:
        raise Exception("Invalid nic type " + type + " specified!")

def AddOpaqueNetwork(cspec, cfgOption = None, \
                     startConnected = True, \
                     opaqueNetworkId = None, \
                     opaqueNetworkType = None, \
                     type = "vmxnet3", mac = None, \
                     conInfo = None, unitNumber = -1, wakeOnLan = False, \
                     externalId = None, \
                     cfgInfo = None):

    back = Vim.Vm.Device.VirtualEthernetCard.OpaqueNetworkBackingInfo()
    back.SetOpaqueNetworkId(opaqueNetworkId)
    back.SetOpaqueNetworkType(opaqueNetworkType)
    nic = GetNic(type)
    nic.SetWakeOnLanEnabled(wakeOnLan)
    nic.SetBacking(back)
    if externalId != None:
        nic.SetExternalId(externalId)

    conInfo = Vim.Vm.Device.VirtualDevice.ConnectInfo()
    conInfo.SetAllowGuestControl(True)
    conInfo.SetConnected(True)
    conInfo.SetStartConnected(startConnected)
    nic.SetConnectable(GetCnxInfo(conInfo))
    nic.SetKey(GetFreeKey(cspec))
    ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualPCIController,
                           cfgInfo, cspec)
    nic.SetControllerKey(ctlrs[0].GetKey())
    nic.SetUnitNumber(unitNumber)

    return AddDeviceToSpec(cspec, nic, \
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add,\
                           None)



def AddDvPortBacking(cspec, portKey, switchUuid, cnxId = None, cfgOption = None, \
                     portgroupKey = None, startConnected = True,
                     type = "pcnet", mac = None, \
                     conInfo = None, unitNumber = -1, wakeOnLan = False, \
                     cfgInfo = None):
    """ Add a dvPort backed nic based on the specified options """
    cfgOption = GetCfgOption(cfgOption)

    # Nic backing ()
    portConnection = Vim.Dvs.PortConnection()
    portConnection.SetSwitchUuid(switchUuid)
    portConnection.SetPortKey(portKey)
    if portgroupKey != None:
        portConnection.SetPortgroupKey(portgroupKey)
    if cnxId != None:
        portConnection.SetConnectionCookie(cnxId)
    nicBacking = Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo(
    )
    nicBacking.SetPort(portConnection)

    nic = GetNic(type)

    nic.SetWakeOnLanEnabled(wakeOnLan)
    nic.SetBacking(nicBacking)
    conInfo = Vim.Vm.Device.VirtualDevice.ConnectInfo()
    conInfo.SetAllowGuestControl(True)
    conInfo.SetConnected(True)
    conInfo.SetStartConnected(startConnected)
    nic.SetConnectable(GetCnxInfo(conInfo))
    nic.SetKey(GetFreeKey(cspec))
    ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualPCIController,
                           cfgInfo, cspec)
    nic.SetControllerKey(ctlrs[0].GetKey())
    nic.SetUnitNumber(unitNumber)

    return AddDeviceToSpec(cspec, nic, \
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add,\
                           None)

def AddNic(cspec, cfgOption = None, cfgTarget = None, devName = None, \
           addressType = None, nicType = "pcnet", mac = None, \
           wakeOnLan = False, conInfo = None, cfgInfo = None, unitNumber = -1, \
           numaNode = None, uptEnabled = None):
    """ Add a nic to the config spec based on the options specified """
    # Get config options and targets
    cfgOption = GetCfgOption(cfgOption)
    cfgTarget = GetCfgTarget(cfgTarget)

    # Nic backing (should be configurable)
    nicBacking = Vim.Vm.Device.VirtualEthernetCard.NetworkBackingInfo()
    nicBacking.SetDeviceName(GetDeviceName(devName, cfgTarget.GetNetwork))

    nic = GetNic(nicType)

    # address type
    if addressType != None:
        nic.SetAddressType(addressType)

    # mac
    if mac != None:
        nic.SetMacAddress(mac)

    nic.SetWakeOnLanEnabled(wakeOnLan)
    nic.SetBacking(nicBacking)
    nic.SetConnectable(GetCnxInfo(conInfo))
    nic.SetKey(GetFreeKey(cspec))
    ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualPCIController,
                           cfgInfo, cspec)
    nic.SetControllerKey(ctlrs[0].GetKey())
    nic.SetUnitNumber(unitNumber)

    # vNUMA node for the NIC.
    if numaNode != None:
      nic.SetNumaNode(numaNode)

    if uptEnabled != None:
        nic.SetUptv2Enabled(uptEnabled)

    return AddDeviceToSpec(cspec, nic, \
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add,\
                           None)

def AddNVDIMMController(cspec):
    """ Add a NVDIMM ctlr to the config spec based on the options specified """

    ctrl = Vim.Vm.Device.VirtualNVDIMMController()
    ctrl.key = GetFreeKey(cspec)

    return AddDeviceToSpec(cspec, ctrl,
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add,
                           None)

def AddNVDIMM(cspec, cfgOption = None, cfgInfo = None, capacityInMB = 4,
              unitNumber = -1):
    """ Add a NVDIMM to the config spec based on the options specified """

    # Get config options
    cfgOption = GetCfgOption(cfgOption)

    ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualNVDIMMController,
                           cfgInfo, cspec)

    device = Vim.Vm.Device.VirtualNVDIMM()
    device.key = GetFreeKey(cspec)
    device.capacityInMB = capacityInMB
    device.SetControllerKey(ctlrs[0].GetKey())
    device.SetUnitNumber(unitNumber)
    backing = Vim.Vm.Device.VirtualNVDIMM.BackingInfo()
    device.SetBacking(backing)

    return AddDeviceToSpec(cspec, device,
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add,
                           Vim.Vm.Device.VirtualDeviceSpec.FileOperation.create)

def AddCdrom(cspec, cfgOption = None, cfgTarget = None, devName = None, \
             conInfo = None, cfgInfo = None, unitNumber = -1, isoFilePath = None, ctlrType = "ide"):
    """ Add a cdrom to the specified spec """

    # Get config options and targets
    cfgOption = GetCfgOption(cfgOption)
    cfgTarget = GetCfgTarget(cfgTarget)

    # Use file-backed CDROM if filename is specified
    if isoFilePath:
        devBacking = Vim.Vm.Device.VirtualCdrom.IsoBackingInfo(
            fileName=isoFilePath)
    else:
        devBacking = Vim.Vm.Device.VirtualCdrom.AtapiBackingInfo()
        devBacking.SetDeviceName(GetDeviceName(devName, cfgTarget.GetCdRom))

    cdrom = Vim.Vm.Device.VirtualCdrom()
    cdrom.SetKey(GetFreeKey(cspec))
    if ctlrType == "ide":
        ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualIDEController,
                               cfgInfo, cspec)
    elif ctlrType == "sata":
        ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualSATAController,
                               cfgInfo, cspec)
    else:
        raise Exception("Unknown controller type: %s" % ctlrType)

    cdrom.SetControllerKey(ctlrs[0].GetKey())
    cdrom.SetUnitNumber(unitNumber)
    cdrom.SetConnectable(GetCnxInfo(conInfo))
    cdrom.SetBacking(devBacking)

    return AddDeviceToSpec(cspec, cdrom, \
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add,\
                           None)


def AddSataCdrom(cspec,
                 cfgOption=None,
                 cfgTarget=None,
                 devName=None,
                 conInfo=None,
                 cfgInfo=None,
                 unitNumber=-1,
                 isoFilePath=None):
    return AddCdrom(cspec, cfgOption, cfgTarget, devName, conInfo, cfgInfo,
                    unitNumber, isoFilePath, "sata")


def AddIdeCdrom(cspec,
                cfgOption=None,
                cfgTarget=None,
                devName=None,
                conInfo=None,
                cfgInfo=None,
                unitNumber=-1,
                isoFilePath=None):
    return AddCdrom(cspec, cfgOption, cfgTarget, devName, conInfo, cfgInfo,
                    unitNumber, isoFilePath, "ide")

def AddIsoCdrom(cspec, fileName, cfgOption = None, cfgTarget = None, \
                conInfo = None, cfgInfo = None, unitNumber = -1):
    """ Add a cdrom to the specified spec """

    # Get config options and targets
    cfgOption = GetCfgOption(cfgOption)
    cfgTarget = GetCfgTarget(cfgTarget)

    devBacking = Vim.Vm.Device.VirtualCdrom.IsoBackingInfo()
    devBacking.SetFileName(fileName)

    cdrom = Vim.Vm.Device.VirtualCdrom()
    cdrom.SetKey(GetFreeKey(cspec))
    ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualIDEController,
                           cfgInfo, cspec)
    cdrom.SetControllerKey(ctlrs[0].GetKey())
    cdrom.SetUnitNumber(unitNumber)
    cdrom.SetConnectable(GetCnxInfo(conInfo))
    cdrom.SetBacking(devBacking)

    return AddDeviceToSpec(cspec, cdrom, \
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add,\
                           None)


def AddSoundCard(cspec,
                 cfgOption=None,
                 cfgTarget=None,
                 devName=None,
                 autodetect=False,
                 type="ensoniq",
                 numaNode=None):
    """ Add a sound card to the config spec """
    cfgOption = GetCfgOption(cfgOption)
    cfgTarget = GetCfgTarget(cfgTarget)

    backing = Vim.Vm.Device.VirtualSoundCard.DeviceBackingInfo()
    backing.SetUseAutoDetect(autodetect)
    #   backing.SetDeviceName(GetDeviceName(devName, cfgTarget.GetSound))

    if type == "ensoniq":
        sound = Vim.Vm.Device.VirtualEnsoniq1371()
    elif type == "hdaudio":
        sound = Vim.Vm.Device.VirtualHdAudioCard()
    else:
        sound = Vim.Vm.Device.VirtualSoundBlaster16()

    sound.SetKey(GetFreeKey(cspec))
    sound.SetBacking(backing)
    if numaNode is not None:
       sound.SetNumaNode(numaNode)
    return AddDeviceToSpec(cspec, sound,
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add)


def AddVideoCard(cspec,
                 cfgOption=None,
                 cfgTarget=None,
                 videoRamSize=-1,
                 enable3D=None):
    """ Add a video card to the config spec """
    cfgOption = GetCfgOption(cfgOption)
    video = None

    for device in cfgOption.GetDefaultDevice():
        if isinstance(device, Vim.Vm.Device.VirtualVideoCard):
            video = device
            break

    if video == None:
        raise Exception("No VideoCard found in ConfigOptions.")

    video.SetKey(GetFreeKey(cspec))
    if videoRamSize != -1:
        video.SetUseAutoDetect(False)
        video.SetVideoRamSizeInKB(long(videoRamSize))
    if enable3D != None:
        video.SetEnable3DSupport(enable3D)

    return AddDeviceToSpec(cspec, video,
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add)


def AddVMI(cspec, cfgOption=None, cfgInfo=None, unitNumber=-1):
    """ Add a VMI ROM device to the config spec """
    cfgOption = GetCfgOption(cfgOption)

    vmiDev = Vim.Vm.Device.VirtualVMIROM()
    vmiDev.SetKey(GetFreeKey(cspec))
    ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualPCIController,
                           cfgInfo, cspec)
    vmiDev.SetControllerKey(ctlrs[0].GetKey())
    vmiDev.SetUnitNumber(unitNumber)

    return AddDeviceToSpec(cspec, vmiDev,
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add)


def AddVMCI(cspec, allowUnrestricted=False, cfgOption=None):
    """ Add a VMCI device to the config spec """
    cfgOption = GetCfgOption(cfgOption)
    vmciDev = None

    for device in cfgOption.GetDefaultDevice():
        if isinstance(device, Vim.Vm.Device.VirtualVMCIDevice):
            vmciDev = device
            break

    if vmciDev == None:
        raise Exception("No VMCI device found in ConfigOptions.")
    vmciDev.SetAllowUnrestrictedCommunication(allowUnrestricted)
    vmciDev.SetKey(GetFreeKey(cspec))
    return AddDeviceToSpec(cspec, vmciDev,
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add)


def AddFileBackedSerial(cspec, fileName, yieldPoll=True):
    backing = Vim.Vm.Device.VirtualSerialPort.FileBackingInfo()
    backing.SetFileName(fileName)
    return AddSerial(cspec, backing, yieldPoll)


def AddDeviceBackedSerial(cspec,
                          cfgTarget=None,
                          devName=None,
                          autodetect=None,
                          yieldPoll=True):
    cfgTarget = GetCfgTarget(cfgTarget)
    backing = Vim.Vm.Device.VirtualSerialPort.DeviceBackingInfo()
    backing.SetUseAutoDetect(autodetect)
    backing.SetDeviceName(GetDeviceName(devName, cfgTarget.GetSerial))
    return AddSerial(cspec, backing, yieldPoll)


def AddPipeBackedSerial(cspec,
                        pipeName,
                        endpointType="client",
                        yieldPoll=True):
    backing = Vim.Vm.Device.VirtualSerialPort.PipeBackingInfo()
    backing.SetPipeName(pipeName)
    backing.SetEndpoint(endpointType)
    return AddSerial(cspec, backing, yieldPoll)


def AddURIBackedSerial(cspec,
                       serviceURI,
                       direction="connect",
                       proxyURI=None,
                       yieldPoll=True):
    backing = Vim.Vm.Device.VirtualSerialPort.URIBackingInfo()
    backing.SetServiceURI(serviceURI)
    backing.SetDirection(direction)
    backing.SetProxyURI(proxyURI)
    return AddSerial(cspec, backing, yieldPoll)


def AddSerial(cspec, backing, yieldPoll=True):
    """ Add a serial port to the config spec. """
    serial = Vim.Vm.Device.VirtualSerialPort()
    serial.SetYieldOnPoll(yieldPoll)
    serial.SetKey(GetFreeKey(cspec))
    serial.SetBacking(backing)
    return AddDeviceToSpec(cspec, serial,
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add)


def AddFileBackedParallel(cspec, fileName):
    """ Add a parallel port backed by a file to the config spec. """
    backing = Vim.Vm.Device.VirtualParallelPort.FileBackingInfo()
    backing.SetFileName(fileName)
    return AddParallel(cspec, backing)


def AddDeviceBackedParallel(cspec,
                            cfgTarget=None,
                            devName=None,
                            autodetect=None):
    """ Add a parallel port backed by a device to the config spec. """
    cfgTarget = GetCfgTarget(cfgTarget)
    backing = Vim.Vm.Device.VirtualParallelPort.DeviceBackingInfo()
    backing.SetUseAutoDetect(autodetect)
    backing.SetDeviceName(GetDeviceName(devName, cfgTarget.GetParallel))
    return AddParallel(cspec, backing)


def AddParallel(cspec, backing):
    """ Add a parallel port to the config spec. """
    parallel = Vim.Vm.Device.VirtualParallelPort()
    parallel.SetKey(GetFreeKey(cspec))
    parallel.SetBacking(backing)
    return AddDeviceToSpec(cspec, parallel,
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add)


def AddFloppy(cspec,
              cfgOption=None,
              cfgTarget=None,
              backingName=None,
              autodetect=False,
              type="device",
              unitNumber=-1,
              conInfo=None):
    """ Add a floppy to the config spec """
    cfgOption = GetCfgOption(cfgOption)
    cfgTarget = GetCfgTarget(cfgTarget)

    backing = None
    if type == "device":
        backing = Vim.Vm.Device.VirtualFloppy.DeviceBackingInfo()
        backing.SetDeviceName(GetDeviceName(backingName, cfgTarget.GetFloppy))
        backing.SetUseAutoDetect(autodetect)
    elif type == "remote":
        backing = Vim.Vm.Device.VirtualFloppy.RemoteDeviceBackingInfo()
        backing.SetDeviceName(GetDeviceName(backingName, cfgTarget.GetFloppy))
        backing.SetUseAutoDetect(autodetect)
    elif type == "image":
        backing = Vim.Vm.Device.VirtualFloppy.ImageBackingInfo()
        backing.SetFileName(backingName)

    floppy = Vim.Vm.Device.VirtualFloppy()
    floppy.SetKey(GetFreeKey(cspec))
    floppy.SetBacking(backing)
    #
    # XXX: unitNumber < 0 is invalid (should revisit as -1 is the default and
    # it is ignored)
    #
    if unitNumber >= 0:
        floppy.SetUnitNumber(unitNumber)
    floppy.SetConnectable(GetCnxInfo(conInfo))
    return AddDeviceToSpec(cspec, floppy,
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add)


def AddDisk(cspec,
            diskType="scsi",
            backingType="flat",
            fileName=None,
            cfgOption=None,
            cfgTarget=None,
            datastorename=None,
            diskmode="persistent",
            capacity=4096,
            cfgInfo=None,
            diskUuid=None,
            unitNumber=-1,
            thin=False,
            scrub=False,
            grainSize=-1,
            policy=None,
            crypto=None,
            deviceName=None,
            createNamedFile=False,
            capacityInBytes=None,
            reservedIOPS=0,
            compatibilityMode="virtualMode",
            reserveUnitNumber=False,
            guestReadOnly=None):
    """ Add a disk to the config spec """
    # Get config options and targets
    cfgOption = GetCfgOption(cfgOption)
    cfgTarget = GetCfgTarget(cfgTarget)

    if backingType == "flat":
        diskBacking = Vim.Vm.Device.VirtualDisk.FlatVer2BackingInfo()
        diskBacking.SetThinProvisioned(thin)
        diskBacking.SetEagerlyScrub(scrub)
    elif backingType == "sparse":
        diskBacking = Vim.Vm.Device.VirtualDisk.SparseVer2BackingInfo()
    elif backingType == "seSparse":
        diskBacking = Vim.Vm.Device.VirtualDisk.SeSparseBackingInfo()
        if grainSize != -1:
            diskBacking.SetGrainSize(grainSize)
    elif backingType == "pmem":
        diskBacking = Vim.Vm.Device.VirtualDisk.LocalPMemBackingInfo()
    elif backingType == "rdm":
        diskBacking = Vim.Vm.Device.VirtualDisk.RawDiskMappingVer1BackingInfo(
            deviceName=deviceName,
            lunUuid=diskUuid,
            compatibilityMode=compatibilityMode)
    else:
        print("Adding of " + backingType + " backing not implemented")
        return

    diskBacking.SetDiskMode(diskmode)
    if datastorename == None:
        datastore = FindDatastoreWithSpace(cfgTarget, capacity)
        datastorename = datastore.GetName()

    if fileName != None:
        diskBacking.SetFileName("[" + datastorename + "]" + " " + fileName)
    else:
        diskBacking.SetFileName("[" + datastorename + "]")

    if diskUuid != None:
        diskBacking.SetUuid(diskUuid)

    diskDev = Vim.Vm.Device.VirtualDisk()
    diskDev.SetKey(GetFreeKey(cspec))
    diskDev.SetBacking(diskBacking)
    diskDev.SetCapacityInKB(long(capacity))
    diskDev.SetCapacityInBytes(capacityInBytes)

    if guestReadOnly is not None:
        diskDev.SetGuestReadOnly(guestReadOnly)

    if cfgOption.GetCapabilities().GetDiskSharesSupported() == True \
      and diskType == "scsi":
        ioAllocation = Vim.StorageResourceManager.IOAllocationInfo()
        shares = Vim.SharesInfo()
        shares.SetShares(2000)
        shares.SetLevel(Vim.SharesInfo.Level.high)
        ioAllocation.SetShares(shares)
        ioAllocation.SetReservation(reservedIOPS)
        diskDev.SetStorageIOAllocation(ioAllocation)

    if diskType == "scsi":
        ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualSCSIController, \
                               cfgInfo, cspec)
    elif diskType == "ide":
        ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualIDEController, \
                              cfgInfo, cspec)

    elif diskType == "sata":
        ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualSATAController, \
                               cfgInfo, cspec)
    else:
        raise Exception(
            "Invalid disk type. Please specify 'ide', 'sata' or 'scsi'")

    # XXX Fix this up
    for ctlrIdx in range(len(ctlrs)):
        if reserveUnitNumber:
            try:
                assert cfgInfo != None
                unitNumber = GetFreeDiskUnitNumber(cspec, cfgInfo, cfgOption,
                                                   ctlrs[ctlrIdx], unitNumber)
            except Vim.Fault.InvalidController as err:
                # Ignore the controller with no available slots
                continue
        else:
            # In this branch we rely on Reconfigure to choose a slot.
            # Each AddDisk should be followed by Reconfigure.
            hasFreeSlot = GetFreeSlot(cspec, cfgInfo, cfgOption,
                                      ctlrs[ctlrIdx]) >= 0

        if reserveUnitNumber or hasFreeSlot:
            diskDev.SetControllerKey(ctlrs[ctlrIdx].GetKey())
            diskDev.SetUnitNumber(unitNumber)
            if fileName == None or createNamedFile == True:
                return AddDeviceToSpec(cspec, diskDev, \
                         Vim.Vm.Device.VirtualDeviceSpec.Operation.add, \
                         Vim.Vm.Device.VirtualDeviceSpec.FileOperation.create, \
                         policy, crypto)
            else:
                return AddDeviceToSpec(cspec, diskDev, \
                         Vim.Vm.Device.VirtualDeviceSpec.Operation.add, \
                         None, policy, crypto)

    raise Exception("Unable to add device as there are no available slots")


def AddIdeDisk(cspec,
               cfgOption=None,
               cfgTarget=None,
               fileName=None,
               datastorename=None,
               diskmode="persistent",
               capacity=4096,
               cfgInfo=None,
               diskUuid=None,
               unitNumber=-1,
               backingType="flat",
               capacityInBytes=None,
               policy=None,
               reserveUnitNumber=False):
    return AddDisk(cspec,
                   "ide",
                   backingType,
                   fileName,
                   cfgOption,
                   cfgTarget,
                   datastorename,
                   diskmode,
                   capacity,
                   cfgInfo,
                   diskUuid,
                   unitNumber,
                   policy=policy,
                   capacityInBytes=capacityInBytes,
                   reserveUnitNumber=reserveUnitNumber)


def AddScsiDisk(cspec,
                cfgOption=None,
                cfgTarget=None,
                fileName=None,
                datastorename=None,
                diskmode="persistent",
                capacity=4096,
                cfgInfo=None,
                diskUuid=None,
                unitNumber=-1,
                thin=False,
                scrub=False,
                backingType="flat",
                policy=None,
                crypto=None,
                createNamedFile=False,
                capacityInBytes=None,
                reservedIOPS=0,
                reserveUnitNumber=False):
    return AddDisk(cspec,
                   "scsi",
                   backingType,
                   fileName,
                   cfgOption,
                   cfgTarget,
                   datastorename,
                   diskmode,
                   capacity,
                   cfgInfo,
                   diskUuid,
                   unitNumber,
                   thin,
                   scrub,
                   policy=policy,
                   crypto=crypto,
                   createNamedFile=createNamedFile,
                   capacityInBytes=capacityInBytes,
                   reservedIOPS=reservedIOPS,
                   reserveUnitNumber=reserveUnitNumber)


def AddSataDisk(cspec,
                cfgOption=None,
                cfgTarget=None,
                fileName=None,
                datastorename=None,
                diskmode="persistent",
                capacity=4096,
                cfgInfo=None,
                diskUuid=None,
                unitNumber=-1,
                thin=False,
                scrub=False,
                backingType="flat",
                capacityInBytes=None,
                policy=None,
                reserveUnitNumber=False):
    return AddDisk(cspec, "sata", backingType, fileName, cfgOption, cfgTarget, \
                   datastorename, diskmode, capacity, cfgInfo, diskUuid,
                   unitNumber, thin, scrub, policy = policy,
                   capacityInBytes = capacityInBytes,
                   reserveUnitNumber = reserveUnitNumber)


def AddPMemDisk(cspec,
                diskType="scsi",
                cfgOption=None,
                cfgTarget=None,
                fileName=None,
                datastorename=None,
                capacity=4096,
                cfgInfo=None,
                diskUuid=None,
                unitNumber=-1,
                policy=None,
                crypto=None,
                createNamedFile=False,
                reservedIOPS=0,
                reserveUnitNumber=False):
    return AddDisk(cspec=cspec,
                   diskType=diskType,
                   backingType="pmem",
                   fileName=fileName,
                   cfgOption=cfgOption,
                   cfgTarget=cfgTarget,
                   datastorename=datastorename,
                   capacity=capacity,
                   capacityInBytes=capacity * 1024,
                   cfgInfo=cfgInfo,
                   diskUuid=diskUuid,
                   unitNumber=unitNumber,
                   policy=policy,
                   crypto=crypto,
                   createNamedFile=createNamedFile,
                   reservedIOPS=reservedIOPS,
                   reserveUnitNumber=reserveUnitNumber)


def AddRdmDisk(cspec,
               cfgInfo,
               datastoreName,
               disk=None,
               cfgOption=None,
               cfgTarget=None,
               fileName=None,
               compatibilityMode="physicalMode",
               reserveUnitNumber=False):
    if disk is None:
        cfgTarget = GetCfgTarget(cfgTarget)
        disks = cfgTarget.scsiDisk
        if len(disks) == 0:
            raise Exception("No free scsi LUNs found for RDM backing")

        lun = disks[0].disk
        name = lun.deviceName
        uuid = lun.uuid
    else:
        name = disk.deviceName
        uuid = disk.uuid

    return AddDisk(cspec,
                   "scsi",
                   backingType="rdm",
                   cfgOption=cfgOption,
                   cfgTarget=cfgTarget,
                   fileName=fileName,
                   deviceName=name,
                   diskUuid=uuid,
                   compatibilityMode=compatibilityMode,
                   cfgInfo=cfgInfo,
                   datastorename=datastoreName,
                   reserveUnitNumber=reserveUnitNumber)


def AddScsiCtlr(
        cspec,
        cfgOption=None,
        cfgTarget=None,
        sharedBus=Vim.Vm.Device.VirtualSCSIController.Sharing.noSharing,
        ctlrType="lsilogic",
        cfgInfo=None,
        unitNumber=-1,
        numaNode=None,
        key=None):
    """ Add a controller to the config spec """
    # Get config options and targets
    cfgOption = GetCfgOption(cfgOption)
    cfgTarget = GetCfgTarget(cfgTarget)

    if ctlrType == "buslogic":
        ctlr = Vim.Vm.Device.VirtualBusLogicController()
    elif ctlrType == "lsilogic":
        ctlr = Vim.Vm.Device.VirtualLsiLogicController()
    elif ctlrType == "lsisas":
        ctlr = Vim.Vm.Device.VirtualLsiLogicSASController()
    elif ctlrType == "pvscsi":
        ctlr = Vim.Vm.Device.ParaVirtualSCSIController()
    else:
        raise Exception("Unsupported Controller type " + ctlrType +
                        " specified!")

    if key != None:
        ctlr.SetKey(key)
    else:
        ctlr.SetKey(GetFreeKey(cspec))

    ctlr.SetSharedBus(sharedBus)

    ctlr.SetBusNumber(GetFreeBusNumber(cfgOption,\
                                       Vim.Vm.Device.VirtualSCSIController,\
                                       cfgInfo, cspec))
    ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualPCIController, \
                           cfgInfo, cspec)
    ctlr.SetUnitNumber(unitNumber)
    if numaNode is not None:
       ctlr.SetNumaNode(numaNode)
    return AddDeviceToSpec(cspec, ctlr,\
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add,\
                           None)

def AddIdeCtlr(cspec, cfgOption = None, cfgTarget = None, \
               cfgInfo = None, unitNumber = -1):
    """ Add a controller to the config spec """
    # Get config options and targets
    cfgOption = GetCfgOption(cfgOption)
    cfgTarget = GetCfgTarget(cfgTarget)

    ctlr = Vim.Vm.Device.VirtualIDEController()
    ctlr.SetKey(GetFreeKey(cspec))
    # ctlr.SetSharedBus(sharedBus)
    ctlr.SetBusNumber(0)
    ctlr.SetUnitNumber(unitNumber)

    return AddDeviceToSpec(cspec, ctlr,\
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add,\
                           None)

def AddSataCtlr(cspec, cfgOption = None, cfgTarget = None, \
                ctlrType = "ahci", cfgInfo = None, unitNumber = -1, \
                numaNode = None):
    """ Add a controller to the config spec """
    # Get config options and targets
    cfgOption = GetCfgOption(cfgOption)
    cfgTarget = GetCfgTarget(cfgTarget)

    if ctlrType == "ahci":
        ctlr = Vim.Vm.Device.VirtualAHCIController()
    else:
        raise Exception("Unsupported Controller type " + ctlrType +
                        " specified!")

    ctlr.SetKey(GetFreeKey(cspec))
    ctlr.SetBusNumber(GetFreeBusNumber(cfgOption,\
                                       Vim.Vm.Device.VirtualSATAController,\
                                       cfgInfo, cspec))
    ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualPCIController, \
                           cfgInfo, cspec)
    ctlr.SetUnitNumber(unitNumber)
    if numaNode is not None:
       ctlr.SetNumaNode(numaNode)

    return AddDeviceToSpec(cspec, ctlr,\
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add,\
                           None)


def AddPCIPassthrough(cspec,
                      cfgOption=None,
                      cfgTarget=None,
                      cfgInfo=None,
                      pciDev=None):
    """ Add a PCI passthrough device to the config spec """
    # Get config options and targets
    cfgOption = GetCfgOption(cfgOption)
    cfgTarget = GetCfgTarget(cfgTarget)

    if pciDev == None:
        # @todo: Should get PCI passthrough device from ConfigTarget
        # but envBrowser support for PCI passthrough not hooked in yet,
        # so use mockup values here.
        pciDev = Vim.Vm.Device.VirtualPCIPassthrough()
        pciDev.SetKey(GetFreeKey(cspec))
        ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualPCIController,
                               cfgInfo, cspec)
        pciDev.SetControllerKey(ctlrs[0].GetKey())

        backing = Vim.Vm.Device.VirtualPCIPassthrough.DeviceBackingInfo()
        backing.SetId("00:0.0")
        backing.SetDeviceId("0")
        backing.SetSystemId("0")
        backing.SetVendorId(0)
        pciDev.SetBacking(backing)

        return AddDeviceToSpec(cspec, pciDev,
                               Vim.Vm.Device.VirtualDeviceSpec.Operation.add)


def AddUSBCtlr(cspec,
               cfgOption=None,
               cfgInfo=None,
               unitNumber=-1,
               ehciEnabled=True,
               numaNode=None):
    """ Add a USB controller to the config spec """
    # Get config options and targets
    cfgOption = GetCfgOption(cfgOption)

    ctlr = Vim.Vm.Device.VirtualUSBController()
    ctlr.SetKey(GetFreeKey(cspec))

    ctlr.SetBusNumber(GetFreeBusNumber(cfgOption,\
                                       Vim.Vm.Device.VirtualPCIController,\
                                       cfgInfo, cspec))
    ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualPCIController, \
                           cfgInfo, cspec)
    ctlr.SetControllerKey(ctlrs[0].GetKey())
    ctlr.SetUnitNumber(unitNumber)
    ctlr.SetEhciEnabled(ehciEnabled)
    if numaNode is not None:
       ctlr.SetNumaNode(numaNode)
    return AddDeviceToSpec(cspec, ctlr,\
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add,\
                           None)


def AddUSBXHCICtlr(cspec, cfgOption=None, cfgInfo=None, unitNumber=-1, \
                   numaNode=None):
    """ Add a xHCI USB controller to the config spec """
    # Get config options and targets
    cfgOption = GetCfgOption(cfgOption)

    ctlr = Vim.Vm.Device.VirtualUSBXHCIController()
    ctlr.SetKey(GetFreeKey(cspec))

    ctlr.SetBusNumber(GetFreeBusNumber(cfgOption,\
                                       Vim.Vm.Device.VirtualPCIController,\
                                       cfgInfo, cspec))
    ctlrs = GetControllers(cfgOption, Vim.Vm.Device.VirtualPCIController, \
                           cfgInfo, cspec)
    ctlr.SetControllerKey(ctlrs[0].GetKey())
    ctlr.SetUnitNumber(unitNumber)
    if numaNode is not None:
       ctlr.SetNumaNode(numaNode)
    return AddDeviceToSpec(cspec, ctlr,\
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add,\
                           None)


def AddUSBDev(cspec,
              cfgOption=None,
              cfgTarget=None,
              cfgInfo=None,
              devName="foo",
              unitNumber=-1,
              allowVMotion=False,
              ctlr=Vim.Vm.Device.VirtualUSBController):
    """ Add a USB device to the config spec """
    # Get config options and targets
    cfgOption = GetCfgOption(cfgOption)
    cfgTarget = GetCfgTarget(cfgTarget)

    dev = Vim.Vm.Device.VirtualUSB()
    dev.SetKey(GetFreeKey(cspec))

    ctlrs = GetControllers(cfgOption, ctlr, cfgInfo, cspec)
    if len(ctlrs) == 0:
        raise Exception(
            "No USB controller present. Cannot add USB device to VM.")

    dev.SetControllerKey(ctlrs[0].GetKey())
    dev.SetUnitNumber(unitNumber)
    dev.SetConnected(False)
    if allowVMotion:
        backing = Vim.Vm.Device.VirtualUSB.RemoteHostBackingInfo()
    else:
        backing = Vim.Vm.Device.VirtualUSB.USBBackingInfo()
    backing.SetDeviceName(GetDeviceName(devName, cfgTarget.GetUsb))
    dev.SetBacking(backing)

    return AddDeviceToSpec(cspec, dev,\
                           Vim.Vm.Device.VirtualDeviceSpec.Operation.add,\
                           None)


def CheckDevice(config, deviceType, propMap=None):
    ##
    ## Given the configinfo, this function walks the virtual hardware
    ## searches for a device of type deviceType (Vim.Vm.Device.VirtualFloppy for example)
    ## Then it examines the propMap to check if the device has properties
    ## listed there with values matching the propMap. If value is None, it just
    ## checks for existence of the property
    ##
    devices = []
    for device in config.GetHardware().GetDevice():
        if isinstance(device, deviceType):
            ## Examine the prop map
            if propMap != None:
                prop = CheckPropMap(device, propMap)
                if prop == None:
                    devices.append(device)
                else:
                    print("Did not match property: ", prop)
            else:
                devices.append(device)
    return devices


def FindNextFunc(prop):
    ## Finds the next function for a prop
    ## For instance: backing -> [ "GetBacking", "" ]
    ##               backing.datastore.summary" -> [ "GetBacking", "datastore.summary" ]
    rest = ""
    prop = "Get" + prop[0].upper() + prop[1:]
    ix = prop.find(".")
    if ix > -1:
        rest = prop[ix + 1:]
        prop = prop[0:ix]
    return [prop, rest]


def CheckPropMap(obj, propMap):
    ##
    ## For the given object, checks to see if each attribute in PropMap
    ## is an attribute of the object and if values are specified, checks
    ## that the values match.
    ## Returns None if it succeeds in matching, else the property that failed
    ## to match.
    ##
    for prop, val in six.iteritems(propMap):
        tempObj = obj
        rest = prop
        total = ""
        while rest != "":
            [first, rest] = FindNextFunc(rest)
            total = total + "." + first + "()"
            try:
                fn = getattr(tempObj, first)
                tempObj = fn()
                if rest == "" and val != None:
                    if type(val) == type(type):
                        if isinstance(tempObj, val) == False:
                            return total
                    elif tempObj != val:
                        return total
            except AttributeError as e:
                return total
            except err:
                return total


def GetBackingStr(backing):
    ##
    ## For the given backing, tries to find a suitable printable string
    ## representing the backing.
    ##
    if isinstance(backing, Vim.Vm.Device.VirtualDevice.FileBackingInfo):
        return backing.GetFileName()
    elif isinstance(backing, Vim.Vm.Device.VirtualDevice.DeviceBackingInfo):
        return backing.GetDeviceName()
    elif isinstance(backing,
                    Vim.Vm.Device.VirtualDevice.RemoteDeviceBackingInfo):
        return backing.GetDeviceName()
    elif isinstance(backing, Vim.Vm.Device.VirtualDevice.PipeBackingInfo):
        return backing.GetPipeName()
    elif isinstance(backing, Vim.Vm.Device.VirtualDevice.URIBackingInfo):
        return backing.GetServiceURI()
    else:
        return None

def GetHWvFutureVmxString():
   # Returns the HWvFuture vmxVersion
   return "vmx-99"
