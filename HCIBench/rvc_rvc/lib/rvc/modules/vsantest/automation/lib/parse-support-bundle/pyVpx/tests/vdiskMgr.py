#!/usr/bin/python
import sys
from pyVmomi import Vim, Vmodl
from pyVim.connect import Connect, Disconnect
from optparse import OptionParser
from pyVim.helpers import Log
from pyVim.task import WaitForTask


"""
   Virtual Disk Manager API Test

   Usage:

   ../py.sh vdiskMgr.py -H <host name/ip> -u <user name> -p <password>

   This currently only tests the following:
      Create child disk.
      Consolidate disk.
      Reparent disk.

"""

def multidisk_arg_cb(option, opt_str, value, parser):
    assert value is None
    value = []

    for arg in parser.rargs:
        # stop on --foo like options
        if arg[:2] == "--" and len(arg) > 2:
            break
        # stop on -a, but not on -3 or -3.0
        if arg[:1] == "-" and len(arg) > 1:
            break

        value.append(arg)

    del parser.rargs[:len(value)]
    setattr(parser.values, option.dest, value)

def get_options():
    """
    Supports the command-line arguments listed below
    """

    parser = OptionParser()
    parser.add_option("-H", "--host",
                      default="localhost",
                      help="remote host to connect to")
    parser.add_option("-u", "--user",
                      default="root",
                      help="User name to use when connecting to hostd")
    parser.add_option("-p", "--password",
                      default="",
                      help="Password to use when connecting to hostd")
    parser.add_option("--createDisk",
                       help="Disk name when creating a new disk")
    parser.add_option("--copyDisk",
                       help="Copy the disk which you just created")
    parser.add_option("--parentDisk",
                       help="The parent disk when creating a new child disk")
    parser.add_option("--consolidate", dest="consolidate_args",
                       action="callback", callback=multidisk_arg_cb,
                       help="List of links to consolidate starting from base")
    parser.add_option("--reparent", dest="reparent_args",
                       action="callback", callback=multidisk_arg_cb,
                       help="List of disk pairs to reparent, " \
                            "e.g. --reparent 'c1,p1' 'c2,p2'")
    parser.add_option("--unlink", action="store_true",
                       help="Flag indicating if unlink consolidated units")
    parser.add_option("--markShared", action="store_false",
                       help="Flag indicating if reparent marks parent shared")
    (options, _) = parser.parse_args()
    return options

def main(argv):
    options = get_options()
    si = Connect(host=options.host,
                 user=options.user,
                 version="vim.version.version9",
                 pwd=options.password)

    vdiskMgr = si.content.virtualDiskManager
    Log("Test started.")

    try:
        # disk creation
        if options.createDisk != None:
            if options.parentDisk != None:
                try:
                    task = vdiskMgr.CreateChildDisk(options.createDisk,
                                                    None,
                                                    options.parentDisk,
                                                    None)
                    WaitForTask(task)
                except Exception as e:
                    Log("Failed to create child disk: " + str(e))
                    raise

            else:
                # XXX: this can be configurable
                createSpec = Vim.VirtualDiskManager.FileBackedVirtualDiskSpec()
                createSpec.adapterType = "busLogic"
                createSpec.diskType = "thin"
                createSpec.capacityKb = 1024
                try:
                    task = vdiskMgr.CreateVirtualDisk(options.createDisk,
                                                      None,
                                                      createSpec)
                    WaitForTask(task)
                except Exception as e:
                    Log("Failed to create disk: " + str(e))
                    raise

            Log("Successfully created disk: " + options.createDisk)

        # disk copy
        if options.copyDisk != None:
            if options.createDisk != None:
                try:
                    Log("  Copying: " + options.createDisk + " -> " + options.copyDisk)
                    task = vdiskMgr.CopyVirtualDisk(options.createDisk,
                                                    None,
                                                    options.copyDisk,
                                                    None,
                                                    None,
                                                    True)
                    WaitForTask(task)
                except Exception as e:
                    Log("Failed to copy disk: " + str(e))
                    raise

            Log("Successfully copy disk: " + options.copyDisk)


        # disk consolidation
        if options.consolidate_args != None and \
               len(options.consolidate_args) > 1:
            unlink = False
            if options.unlink != None and options.unlink:
                unlink = True

            diskUnits = []
            for elem in options.consolidate_args:
                aUnit = Vim.VirtualDiskManager.DiskUnit()
                aUnit.name = elem
                diskUnits.append(aUnit)

            try:
                task = vdiskMgr.ConsolidateDisks(diskUnits, unlink)
                WaitForTask(task)
            except Exception as e:
                Log("Failed to consolidate disks: " + str(e))
                raise

            Log("Successfully consolidated disks.")


        # disk reparent
        if options.reparent_args != None and \
               len(options.reparent_args) > 0:

            markShared = False
            if options.markShared != None and options.markShared:
                markShared = True

            reparentSpec = []
            for elem in options.reparent_args:
                aSpec = Vim.VirtualDiskManager.ReparentSpec()
                elem = elem.split(',')
                if len(elem) == 2:
                    aSpec.childFilename = elem[0]
                    aSpec.parentFilename = elem[1]
                    reparentSpec.append(aSpec)

            try:
                # print reparentSpec
                task = vdiskMgr.ReparentDisks(reparentSpec)
                WaitForTask(task)
            except Exception as e:
                Log("Failed to reparent disks: " + str(e))
                raise

            Log("Successfully reparented disks.")

    except Exception as e:
        Log("Failed:" + str(e))

    Disconnect(si)
    Log("Test completed.")

# Start program
if __name__ == "__main__":
    main(sys.argv[1:])

