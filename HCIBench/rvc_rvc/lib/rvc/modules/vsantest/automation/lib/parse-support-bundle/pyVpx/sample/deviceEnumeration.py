#!/usr/bin/python
import sys
from pyVmomi import Vim
from pyVim.connect import Connect
from pyVim import folder
from pyVim import vmconfig
from pyVim import arguments
from pyVim import pp

deviceMaps = {
    'pci': Vim.Vm.Device.VirtualPCIController,
    'scsi': Vim.Vm.Device.VirtualSCSIController,
    'ide': Vim.Vm.Device.VirtualIDEController,
    'sio': Vim.Vm.Device.VirtualSIOController,
    'sound': Vim.Vm.Device.VirtualSoundCard,
    'cd': Vim.Vm.Device.VirtualCdrom,
    'ctlr': Vim.Vm.Device.VirtualController,
    'disk': Vim.Vm.Device.VirtualDisk,
    'nic': Vim.Vm.Device.VirtualEthernetCard,
    'serial': Vim.Vm.Device.VirtualSerialPort,
    'parallel': Vim.Vm.Device.VirtualParallelPort,
    'floppy': Vim.Vm.Device.VirtualFloppy,
    'vmi': Vim.Vm.Device.VirtualVMIROM
}


def main():
    # Argument mgmt
    supportedArgs = [
        (["h:", "host="], "localhost", "Host name", "host"),
        (["u:", "user="], "root", "User name", "user"),
        (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
        (["v:",
          "vmname="], "CreateTest", "Name of the virtual machine", "vmname"),
        (["c:", "controller="], "",
         "Devices attached to specified controller type [pci, scsi, ide, sio]",
         "ctlr"),
        (["d:", "devicetype="], "",
         "Devices matching specified type (comma separated) [pci, ide, sio, sound, cd, ctlr, disk, nic, scsi, serial, parallel, floppy, vmi]",
         "dev"),
        (["s:", "sortcol="], "0", "Column to sort on (integer value)", "col")
    ]
    supportedToggles = []
    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)

    # Connect
    si = Connect(args.GetKeyValue("host"), 443, args.GetKeyValue("user"),
                 args.GetKeyValue("pwd"))

    # VM name
    vmname = args.GetKeyValue("vmname")

    # Sort column
    sortcol = int(args.GetKeyValue("col"))

    # Controller match
    ctlr = args.GetKeyValue("ctlr").lower()
    ctlrType = None
    if ctlr in deviceMaps:
        ctlrType = deviceMaps[ctlr]

    # Device type match
    dev = args.GetKeyValue("dev").lower()
    devList = [item.strip() for item in dev.split(",")]
    devTypeList = []
    devTypeList = [deviceMaps[dev] for dev in devList if dev in deviceMaps]
    if len(devTypeList) == 0:
        devTypeList.append(Vim.Vm.Device.VirtualDevice)

    # Get the hardware info
    vm1 = folder.Find(vmname)
    devices = vm1.GetConfig().GetHardware().GetDevice()

    # Get a list of keys corresponding to the selected controller type
    ctlrKeys = None
    if ctlrType:
        ctlrKeys = [
            device.GetKey() for device in devices
            if isinstance(device, ctlrType)
        ]

    # walk the device list finding devices that match
    fullMap = []
    for device in devices:
        for devType in devTypeList:
            if isinstance(device, devType):
                desc = device.GetDeviceInfo().GetLabel()
                back = vmconfig.GetBackingStr(device.GetBacking())
                if back == None:
                    back = ""
                if device.GetConnectable():
                    cnx = str(device.GetConnectable().GetConnected())
                else:
                    cnx = ""
                if ctlrKeys == None or device.GetControllerKey() in ctlrKeys:
                    fullMap.append([
                        str(device.GetControllerKey()),
                        str(device.GetKey()), desc,
                        str(device.GetUnitNumber()), cnx, back
                    ])
                break
    # Print the output
    fullMap.sort(key=lambda x: x[sortcol])
    labels = ('Ctlr Key', 'Device Key', 'Description', 'Unit number',
              'Connected', 'Backing')
    print pp.indent([labels] + fullMap,
                    hasHeader=True,
                    delim='    ',
                    prefix='    ')


# Start program
if __name__ == "__main__":
    main()
