#!/usr/bin/python

import sys
from pyVmomi import Vim
from pyVim import connect
from pyVim import vm, vmotion
from pyVim import folder
from pyVim import arguments


def main():
    supportedArgs = [
        (["1:", "host1="], "localhost", "Host name", "host1"),
        (["2:", "host2="], "localhost", "Host name", "host2"),
        (["u:", "user="], "root", "User name", "user"),
        (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
        (["v:",
          "vmname="], "CreateTest", "Name of the virtual machine", "vmname"),
        (["t:", "vmotionType="], "vmotion", "VMotion type", "vmotionType"),
        (["d:",
          "destDs="], None, "Target datastore for storage VMotions", "destDs"),
        (["e:", "encrypt="], False, "Whether to use encryption", "encrypt")
    ]

    supportedToggles = [(["usage",
                          "help"], False, "Show usage information", "usage")]

    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
    if args.GetKeyValue("usage") == True:
        args.Usage()
        sys.exit(0)

    host1 = args.GetKeyValue("host1")
    host2 = args.GetKeyValue("host2")
    encrypt = bool(args.GetKeyValue("encrypt"))
    vmotionType = args.GetKeyValue("vmotionType")
    destDs = args.GetKeyValue("destDs")
    supportedTypes = vmotion.GetSupportedVMotionTypes()
    if vmotionType not in supportedTypes:
        print "Unsupported vmotion type '%s'" % vmotionType
        print "Supported values are %s" % ", ".join(supportedTypes)
        sys.exit(-1)
    print "Using vmotion type: " + vmotionType

    # Connect to hosts
    print "Host 1: " + host1
    primarySi = connect.SmartConnect(host=host1,
                                     user=args.GetKeyValue("user"),
                                     pwd=args.GetKeyValue("pwd"))

    secondarySi = primarySi
    if vmotionType != Vim.Host.VMotionManager.VMotionType.disks_only:
        print "Host 2: " + host2
        secondarySi = connect.SmartConnect(host=host2,
                                           user=args.GetKeyValue("user"),
                                           pwd=args.GetKeyValue("pwd"))
        connect.SetSi(primarySi)

    print "Use encryption: " + str(encrypt)
    vmname = args.GetKeyValue("vmname")
    vm1 = folder.Find(vmname)
    if vm1 == None:
        print "Couldnt find the specified virtual machine " + vmname \
             + ". Check that the vm exists on host 1"
        sys.exit(-1)

    vm.Migrate(vm1,
               primarySi,
               secondarySi,
               vmotionType=vmotionType,
               encrypt=encrypt,
               destDs=destDs)


# Start program
if __name__ == "__main__":
    main()
