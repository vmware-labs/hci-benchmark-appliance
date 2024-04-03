#!/usr/bin/python

from __future__ import print_function

import sys
import time
import getopt
from pyVmomi import Vim
from pyVmomi import VmomiSupport
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm
from pyVim import vimutil
from pyVim.invt import *
import atexit

# Indicates verbosity level of the overall program
verbose = 0

def Usage():
    print("dmotioner.py [options]")
    print("Options:")
    print("  -s|--source <name>      [Required: Source host name ]")
    print("  -d|--dest <name>        [Required: Destination host name ]")
    print("  -v|--vc <name>          [Required: VirtualCenter name ]")
    print("  -c|--datacenter <name>  [Required: Datacenter name ]")
    print("  -n|--vm <name>          [Optional: Virtual machine name, default: DmotionTester ]")
    print("  -q|--cleanup            [Optional: Do cleanup after completion ]")
    print("  -u|--usage|--help|-h    [Optional: Usage information ]")
    print("  -b|--verbose            [Optional: Log every completed step ]")
    print("  -p|--repeat             [Optional: Number of times to repeat the program]")
    print("  --network               [Optional: Network to be used for any nics]")
    print("  --numnics               [Optional: Number of nics (default: 0)]")
    print("  --numdisks              [Optional: Number of disks (default: 1, max 7)]")
    print("  --disksize              [Optional: Size of each disk in mb (default: 4MB)]")
    print("  --attachcdrom           [Optional: Attach a cdrom]")
    print("  -m|--maxfailures        [Optional: Maximum allowed failures before stopping]")

def Log(x):
    global verbose
    if verbose == 1:
       print(x)

def main():
    global verbose
    # Process command line
    try:
	opts, args = getopt.getopt(sys.argv[1:], "bp:qs:d:uhv:c:n:m:", \
	      ["source=", "dest=", "vc=", "vm=", "datacenter=", \
	      "usage", "help", "cleanup", "verbose", "repeat=", \
	      "network=", "numnics=", "numdisks=", "disksize=", "attachcdrom", \
	      "maxfailures"])
    except getopt.GetoptError:
        Usage()
	sys.exit(-1)

    sourceHostName = None
    destHostName = None
    datacenterName = None
    vcName = None
    vmName = "DmotionTester"
    doCleanup = 0
    count = 1
    network = None
    numNics = 0
    numDisks = 1
    diskSize = 4
    attachCd = 0
    maxFailures = 0
    numFailures = 0

    for o, a in opts:
	if o in ("-s", "--source"):
	   sourceHostName = a
	if o in ("-d", "--dest"):
	   destHostName = a
	if o in ("-v", "--vc"):
	   vcName = a
	if o in ("-c", "--datacenter"):
	   datacenterName = a
	if o in ("-n", "--vm"):
	   vmName = a
	if o in ("-q", "--cleanup"):
	   doCleanup = 1
	if o in ("-b", "--verbose"):
	   verbose = 1
	   Log("Verbose level set")
	if o in ("-p", "--repeat"):
	   count = int(a)
	if o == "--network":
	   network = a
	if o == "--numnics":
	   numNics = int(a)
	if o == "--numdisks":
	   numDisks = int(a)
	if o == "--disksize":
	   diskSize = int(a)
	if o == "--attachcdrom":
	   attachCd = 1
	if o in ("-m", "--maxfailures"):
	   maxFailures = int(a)
	if o in ("-u", "--usage", "-h", "--help"):
	   Usage()
	   sys.exit(0)

    if (None in (sourceHostName, destHostName, vcName, datacenterName)) \
     or (numNics > 0 and  network == None):
       print("VC Host    : %s" % vcName)
       print("Datacenter : %s" % datacenterName)
       print("Source host: %s" % sourceHostName)
       print("Dest host  : %s" % destHostName)
       Usage()
       sys.exit(-1)

    # Connect
    Log("Connecting to VirtualCenter: " + vcName)
    si = Connect(vcName, 902, "Administrator", "ca$hc0w", "vpxd")
    atexit.register(Disconnect, si)

    # Assumes no folderization inside the datacenter root host folder.
    Log("Locating source and destination hosts: " + sourceHostName + ", " +  destHostName)
    hosts = GetHostFolder(datacenterName)
    sourceCrRef = FindChild(hosts, sourceHostName)
    destCrRef = FindChild(hosts, destHostName)

    # Get the environment browser for the source host
    browser = sourceCrRef.GetEnvironmentBrowser()

    # Get the datastore list for the dest host
    destDsList = destCrRef.GetDatastore()
    finalDs = None
    # Find a reasonable destination datastore ( > 4GB free and vmfs 3)
    for i in range(0, len(destDsList)):
        if (destDsList[i].GetCapability().GetDirectoryHierarchySupported()):
            if (destDsList[i].GetSummary().GetFreeSpace() > 4 * 1024 * 1024 * 1024):
                finalDs = destDsList[i]

    if finalDs == None:
        print("Failed to find a suitable datastore. quitting")
        sys.exit(-1)
    Log("Found a suitable destination datasource: " + finalDs.GetSummary().GetName())

    Log("Going to loop " + str(count) + " times")
    for i in range(0, count):
	# Create the virtual machine on source, power on the virtual machine\
	# and issue a relocate.
	try:
	   vmNameNew = vmName
	   if (count > 1):
	      vmNameNew = vmName + str(i)
	   Log("Creating virtual machine with name: " + vmNameNew)
	   vm1 = vm.CreateQuickDummy(vmNameNew, numDisks, numNics, attachCd, \
                sourceCrRef.GetHost()[0], sourceCrRef.GetResourcePool(), browser,
		diskSize, network)
	   Log("Powering on... ")
	   vm.PowerOn(vm1)
	   time.sleep(2)
	   relocSpec = Vim.Vm.RelocateSpec()
	   relocSpec.SetDatastore(finalDs)
	   relocSpec.SetHost(destCrRef.GetHost()[0])
	   relocSpec.SetPool(destCrRef.GetResourcePool())
	   Log("Invoking Dmotion... ")
	   vimutil.InvokeAndTrack(vm1.Relocate, relocSpec)
	   time.sleep(2)
	   if doCleanup == 1:
	      Log("Cleanup requested: Powering off")
	      vimutil.InvokeAndTrack(vm1.PowerOff)
	      Log("Destroying the successfully vmotioned virtual machine")
	      vm1.Destroy()
	      time.sleep(2)
	except Exception as e:
	   print("Failed test due to exception")
	   print("Info: ")
	   print(e.__str__)
	   if (numFailures >= maxFailures):
	      raise
	   else:
	      numFailures = numFailures + 1


# Start program
if __name__ == "__main__":
    main()
