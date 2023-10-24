#!/usr/bin/python

import logging
import sys
import datetime

from pyVmomi import Vim
from pyVim.connect import Connect, GetSi
from pyVim import arguments
from pyVim import vm
from pyVim import vimutil
from pyVim.task import WaitForTask


def findHost(hostName, searchIndex):
    host = searchIndex.FindByDnsName(dnsName=hostName, vmSearch=False)
    if host == None:
        host = searchIndex.FindByIp(ip=hostName, vmSearch=False)

    return host


def getSharedDatastore(src, dest):
    srcDs = src.GetDatastore()
    destDs = dest.GetDatastore()
    for ds in srcDs:
        for ds2 in destDs:
            if ds.GetSummary().GetUrl() == ds2.GetSummary().GetUrl():
                # Found it!
                return ds
    return None


def searchHostForVm(vmname, host):
    vms = [a for a in host.GetVm() if a.GetName() == vmname]
    if len(vms) == 1:
        return vms[0]
    return None


def createSuitableVm(src, dest, vmname):
    # Find a shared datastore
    ds = getSharedDatastore(src, dest)
    if ds == None:
        logging.error(
            "Couldnt find a shared datastore between the two hosts; " +
            "VMotion not possible")
        sys.exit(-1)

    # Find the compute resource for the host
    cr = src.GetParent()

    # Find the datacenter for this host
    curr = src
    while not isinstance(curr, Vim.Datacenter):
        curr = curr.GetParent()
    vmFolder = curr.GetVmFolder()

    # Create the vm
    cspec = vm.CreateQuickDummySpec(vmname,
                                    numScsiDisks=1,
                                    memory=4,
                                    envBrowser=cr.GetEnvironmentBrowser(),
                                    datastoreName=ds.GetSummary().GetName())
    try:
        vimutil.InvokeAndTrack(vmFolder.CreateVm, cspec, cr.GetResourcePool(),
                               src)
    except Exception, e:
        raise
    vmotionVM = None
    searchIndex = GetSi().RetrieveContent().GetSearchIndex()
    vmotionVM = searchIndex.FindChild(vmFolder, vmname)
    if vmotionVM == None:
        logging.error("Unexpected error!")
        sys.exit(-1)

    return vmotionVM


def doVmotion(vm1, dest, destName, priority, rp):
    logging.debug("Migrating to: " + destName)
    start = datetime.datetime.now()
    task = vm1.Migrate(rp, dest, priority,
                       Vim.VirtualMachine.PowerState.poweredOn)
    try:
        WaitForTask(task)
    except Exception, e:
        logging.error("Migration failure noted: " + str(e))
        return [e, None]
    end = datetime.datetime.now()
    timetaken = (end - start)
    logging.debug("Migrated to host: " + destName + " in time " +
                  str(end - start))
    return [None, timetaken]


def main():
    supportedArgs = [(["h:", "VC host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "vmname="], "VMotionTest",
                      "Name of the virtual machine", "vmname"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter"),
                     (["s:", "source="], "", "Source host", "src"),
                     (["d:", "dest="], "", "Destination host", "dest")]
    supportedToggles = [(["usage",
                          "help"], False, "Show usage information", "usage")]

    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
    if args.GetKeyValue("usage") == True:
        args.Usage()
        sys.exit(0)

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')

    # Connect
    si = Connect(host=args.GetKeyValue("host"),
                 user=args.GetKeyValue("user"),
                 pwd=args.GetKeyValue("pwd"))

    if args.GetKeyValue("src") == "" or args.GetKeyValue("dest") == "":
        logging.error("Both source and destination hosts must be specified")
        args.Usage()
        sys.exit(-1)

    # Virtual machine name
    vmname = args.GetKeyValue("vmname")

    # Number of iterations to run
    iterations = int(args.GetKeyValue("iter"))

    searchIndex = si.RetrieveContent().GetSearchIndex()

    # Find the source host
    srcName = args.GetKeyValue("src")
    src = findHost(srcName, searchIndex)
    if src == None:
        logging.error("Couldnt find the source host: " + srcName)
        sys.exit(-1)

    # Find the destination host
    destName = args.GetKeyValue("dest")
    dest = findHost(destName, searchIndex)
    if dest == None:
        logging.error("Couldnt find the destination host: " + destName)
        sys.exit(-1)

    sourceHostName = src.GetSummary().GetConfig().GetName()
    destHostName = dest.GetSummary().GetConfig().GetName()

    # Find the virtual machine
    vmotionVM = None
    vms = src.GetVm()
    vmotionVM = searchHostForVm(vmname, src)
    if vmotionVM == None:
        vmotionVM = searchHostForVm(vmname, dest)
        if vmotionVM != None:
            # Switch up source and destination
            temp = src
            src = dest
            dest = temp

    # If the virtual machine doesnt exist, create it.
    create = 0
    if vmotionVM == None:
        vmotionVM = createSuitableVm(src, dest, vmname)
        create = 1
    else:
        # Verify the vm is on a datastore available on both hosts
        dsList = vmotionVM.GetDatastore()
        for ds in dsList:
            if len([a for a in src.GetDatastore() \
                    if a.GetSummary().GetUrl() == ds.GetSummary().GetUrl() ]) == 0:
                logging.error("Part of the virtual machine is on: " \
                              + ds.GetSummary().GetName() + " which is not accessible on: " \
                              + sourceHostName)
                sys.exit(-1)
            if len([a for a in dest.GetDatastore() \
                    if a.GetSummary().GetUrl() == ds.GetSummary().GetUrl() ]) == 0:
                logging.error("Part of the virtual machine is on: " \
                              + ds.GetSummary().GetName() + " which is not accessible on: " \
                              + destHostName)
                sys.exit(-1)

    # power it on
    if vmotionVM.GetRuntime().GetPowerState(
    ) != Vim.VirtualMachine.PowerState.poweredOn:
        vimutil.InvokeAndTrack(vmotionVM.PowerOn)

    # resource pools
    srcRp = src.GetParent().GetResourcePool()
    destRp = dest.GetParent().GetResourcePool()

    # All systems are go
    logging.info("Ready for vmotion")

    timetaken = datetime.timedelta()
    backwardsTime = datetime.timedelta()
    for i in range(iterations):
        # ping
        res = doVmotion(vmotionVM, dest, destHostName,
                        Vim.VirtualMachine.MovePriority.highPriority, destRp)
        if res[0] != None:
            print "Failure source: " + sourceHostName + ", destination: " + destHostName
            break
        timetaken = timetaken + res[1]

        # pong
        res = doVmotion(vmotionVM, src, sourceHostName,
                        Vim.VirtualMachine.MovePriority.highPriority, srcRp)
        if res[0] != None:
            print "Failure source: " + destHostName + ", destination: " + sourceHostName
            break
        backwardsTime = backwardsTime + res[1]
        logging.info("Iteration completed: " + str(i))

    logging.info("Summary: ")
    logging.info("Ping pongs requested (2 vmotions): " + str(iterations))
    logging.info("Virtual machine name: " + vmname)
    logging.info("Host 1: " + sourceHostName)
    logging.info("Host 2: " + destHostName)
    logging.info("Successful ping/pongs (2 vmotions): " + str(i + 1))
    logging.info("Avg. time going from source to destination (seconds): " + \
                 str(timetaken.seconds/iterations))
    logging.info("Avg. time going from destination to source (seconds): " + \
                 str(backwardsTime.seconds/iterations))
    logging.info("Total time: " + str(timetaken + backwardsTime))
    logging.info("Avg. time for vmotion (seconds): " + \
          str((backwardsTime + timetaken).seconds/(iterations * 2)))
    if create == 1:
        # Cleanup behind self
        vimutil.InvokeAndTrack(vmotionVM.PowerOff)
        vmotionVM.Destroy()


# Start program
if __name__ == "__main__":
    main()
