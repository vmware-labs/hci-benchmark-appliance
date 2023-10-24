#!/usr/bin/python
import sys
import time
import thread
from pyVmomi import Vim, SoapStubAdapter
from pyVim import arguments
from pyVim.connect import Connect


def GetRootFolder(si):
    content = si.RetrieveContent()
    rootFolder = content.GetRootFolder()
    return rootFolder


def Indent(depth):
    return "   " * depth


def WalkFolder(folder, depth=0):
    indent = Indent(depth)
    childEntities = folder.GetChildEntity()
    print indent + "%s: %s" % \
          (folder.GetName(), folder)

    for i in range(len(childEntities)):
        childEntity = childEntities[i]
        WalkManagedEntity(childEntity, depth + 1)


def WalkManagedEntity(entity, depth):
    if isinstance(entity, Vim.Folder):
        WalkFolder(entity, depth)
    elif isinstance(entity, Vim.Datacenter):
        WalkDatacenter(entity, depth)
    elif isinstance(entity, Vim.VirtualMachine):
        WalkVirtualMachine(entity, depth)
    elif isinstance(entity, Vim.HostSystem):
        WalkHostSystem(entity, depth)
    elif isinstance(entity, Vim.ComputeResource):
        WalkComputeResource(entity, depth)
    elif isinstance(entity, Vim.ClusterComputeResource):
        WalkComputeResource(entity, depth)
    else:
        print Indent(depth) + entity


def WalkDatacenter(datacenter, depth=0):
    indent = Indent(depth)

    print indent + "%s: %s" % \
          (datacenter.GetName(), datacenter)

    hostFolder = datacenter.GetHostFolder()
    vmFolder = datacenter.GetVmFolder()
    WalkFolder(hostFolder, depth + 1)
    WalkFolder(vmFolder, depth + 1)
    datastores = datacenter.GetDatastore()
    WalkDatastores(datastores, depth + 1)
    networks = datacenter.GetNetwork()
    WalkNetworks(networks, depth + 1)


def WalkComputeResource(computeResource, depth=0):
    indent = Indent(depth)

    print indent + "%s: %s" % \
          (computeResource.GetName(), computeResource)

    resourcePool = computeResource.GetResourcePool()
    WalkResourcePool(resourcePool, depth + 1)

    hostSystems = computeResource.GetHost()
    WalkHostSystems(hostSystems, depth + 1)

    datastores = computeResource.GetDatastore()
    WalkDatastores(datastores, depth + 1)

    networks = computeResource.GetNetwork()
    WalkNetworks(networks, depth + 1)


def WalkResourcePool(resourcePool, depth=0):
    indent = Indent(depth)

    print indent + "%s: %s" % \
          (resourcePool.GetName(), resourcePool)


def WalkVirtualMachine(vm, depth=0):
    indent = Indent(depth)

    print indent + "%s: %s" % \
          (vm.GetSummary().GetConfig().GetName(), vm)


def WalkHostSystems(hostSystems, depth=0):
    indent = Indent(depth)
    print indent + "Hosts:"
    for hostSystem in hostSystems:
        WalkHostSystem(hostSystem, depth + 1)


def WalkHostSystem(hostSystem, depth=0):
    indent = Indent(depth)

    print indent + "%s: %s" % \
          (hostSystem.GetSummary().GetConfig().GetName(), hostSystem)
    datastores = hostSystem.GetDatastore()
    WalkDatastores(datastores, depth + 1)
    networks = hostSystem.GetNetwork()
    WalkNetworks(networks, depth + 1)


def WalkDatastores(datastores, depth=0):
    indent = Indent(depth)
    print indent + "Datastores:"
    for datastore in datastores:
        WalkDatastore(datastore, depth + 1)


def WalkDatastore(datastore, depth=0):
    indent = Indent(depth)
    print indent + datastore.GetSummary().GetName()


def WalkNetworks(networks, depth=0):
    indent = Indent(depth)
    print indent + "Networks:"
    for network in networks:
        WalkNetwork(network, depth + 1)


def WalkNetwork(network, depth=0):
    indent = Indent(depth)
    print indent + network.GetSummary().GetName()


def WalkInventory(si):
    print "ServiceInstance Inventory:"
    rootFolder = GetRootFolder(si)
    WalkFolder(rootFolder)


def main():
    supportedArgs = [(["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "vmprefix="], "", "Prefix for virtual machine",
                      "vmprefix")]

    supportedToggles = [(["usage",
                          "help"], False, "Show usage information", "usage")]

    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
    if args.GetKeyValue("usage") == True:
        args.Usage()
        sys.exit(0)

    # Connect
    si = Connect(host=args.GetKeyValue("host"),
                 user=args.GetKeyValue("user"),
                 pwd=args.GetKeyValue("pwd"))

    WalkInventory(si)


# Start program
if __name__ == "__main__":
    main()
