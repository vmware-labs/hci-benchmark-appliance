#!/usr/bin/python
import sys

from pyVim.connect import Connect, GetSi
from pyVim import arguments
from pyVmomi import Vim
from pyVim import invt
from pyVim import pp
from pyVim import vm
from pyVim import vimutil


def Usage():
    print "Not yet there"


def main():
    supportedArgs = [(["h:",
                       "host="], "localhost", "Host name of VC/host", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd")]

    supportedToggles = [(["usage",
                          "help"], False, "Show usage information", "usage")]

    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
    if args.GetKeyValue("usage") == True:
        Usage()
        sys.exit(0)

    # Connect
    si = Connect(host=args.GetKeyValue("host"),
                 user=args.GetKeyValue("user"),
                 pwd=args.GetKeyValue("pwd"))

    # Initialize the lun uuid list
    lunMap = {}

    # Get all vms
    vmList = invt.findVms("", "")
    if vmList == None:
        print "No virtual machines found in the inventory"
        sys.exit(0)

    # Walk the vm list, looking for rdms
    for vmInfo in vmList:
        vm = vmInfo[0]
        config = vm.GetConfig()
        # Skip invalid vms without information available.
        if config == None:
            print "Skipping an invalid virtual machine without any identifier"
            continue

        debugStmt = "DEBUG: Examining vm " + config.GetName() + " ..."
        devices = config.GetHardware().GetDevice()
        # Get list of rdms available on vm
        rdms = [ device.GetBacking() for device in devices \
                  if isinstance(device, Vim.Vm.Device.VirtualDisk) and \
                  isinstance(device.GetBacking(), \
                            Vim.Vm.Device.VirtualDisk.RawDiskMappingVer1BackingInfo) ]
        # Add the listed rdms to a map
        if len(rdms) > 0:
            for rdm in rdms:
                lunid = rdm.GetLunUuid()
                currentList = []
                if lunMap.has_key(lunid):
                    # Ooh, a duplicate.
                    currentList = lunMap[lunid]

                currentList.append(config.GetName())
                lunMap[lunid] = currentList
            debugStmt += ",".join([rdm.GetDeviceName() for rdm in rdms])
            #print debugStmt

    # Check out the results
    print ""
    conflicts = 0
    for key, val in lunMap.iteritems():
        if len(val) > 1:
            if conflicts == 0:
                print "LUNs used by more than 1 virtual machine: "
                print "------------------------------------------"
            conflicts += 1
            print ""
            print "LUN ID          : " + key
            print "Virtual machines: " + (", ").join(val)

    if conflicts == 0:
        print "No LUNs used by more than 1 virtual machine. System is clean"

    print ""
    print ""


# Start program
if __name__ == "__main__":
    main()
