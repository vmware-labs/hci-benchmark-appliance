## @file folder.py
## @brief Functions for getting lists of vms in the inventory's vm folder.
##
## Detailed description (for Doxygen goes here)
"""
Synchronous FileManager functions

Note: This module is written explicitly for host agent and will need
to be modified to work against a virtual center.
"""

from pyVmomi import Vim
from pyVmomi import Vmodl
from . import vimutil
from . import invt
from itertools import chain


def GetVmAll(datacenter=None, si=None):
    """ Returns an iterator object that walks the inventory tree and yields
    all VirtualMachine instances for each Datacenter object that satisfies
    the datacenter() predicate, if specified.
    """
    children = invt.GetVmFolderAll(datacenter, si)
    while children:
        entities, children = children, []
        for entity in entities:
            if isinstance(entity, Vim.VirtualMachine):
                yield entity
            elif isinstance(entity, Vim.Folder):
                children = chain(children, entity.childEntity)
            elif isinstance(entity, Vim.ResourcePool):  # handles VirtualApp
                children = chain(children, entity.vm, entity.resourcePool)
            else:
                raise NotImplementedError


def GetAll():
    """ Get the list of virtual machines on the host. """
    return list(GetVmAll())


def FindCfg(cfg):
    """ Find a virtual machine with the specified config path. """

    vms = GetAll()
    for vm in vms:
        try:
            config = vm.GetConfig()
            if config != None and config.GetFiles().GetVmPathName() == cfg:
                return vm
        except Vmodl.Fault.ManagedObjectNotFound:
            pass
    return None


def Find(name):
    """
    Find the first instance of a virtual machine with the specified name.

    """

    vms = GetAll()
    for vm in vms:
        try:
            config = vm.GetConfig()
            if config != None and config.GetName() == name:
                return vm
        except Vmodl.Fault.ManagedObjectNotFound:
            pass
    return None


def GetAllNetworkEntities():
    """ Get all the portgroups in the network folder """
    netFolder = invt.GetNetworkFolder()
    pgs = netFolder.GetChildEntity()
    return pgs


def FindPg(pgName):
    """ Find the first instance of a dvPortgroup """

    pgs = GetAllNetworkEntities()
    for pg in pgs:
        try:
            if pg.GetName() == pgName:
                return pg
        except Vmodl.Fault.ManagedObjectNotFound:
            pass
    return None


def FindBySummaryPath(path):
    """ Find a virtual machine with the specified summary path. """

    vms = GetAll()
    for vm in vms:
        try:
            config = vm.GetSummary().GetConfig()
            if config != None and config.GetVmPathName() == path:
                return vm
        except Vmodl.Fault.ManagedObjectNotFound:
            pass
    return None


def FindBySummaryName(name):
    """
    Find the first instance of a virtual machine with the specified name.

    """

    vms = GetAll()
    for vm in vms:
        try:
            summary = vm.GetSummary()
            config = summary.GetConfig()
            if config != None and config.GetName() == name:
                return vm
        except Vmodl.Fault.ManagedObjectNotFound:
            pass
    return None


def FindPrefix(prefix):
    """
    Find all virtual machines with the specified prefix in their
    name.  Can be used to manage a set of test virtual machines needed
    for a specific test.

    """

    result = []
    for vm in GetVmAll():
        try:
            config = vm.GetConfig()
            if config is not None and config.GetName().startswith(prefix):
                result.append(vm)
        except (Vmodl.Fault.ManagedObjectNotFound, AttributeError):
            pass

    return result


def Register(cfg, asTemplate=False, pool=None, host=None):
    """
    Register a vm with the given path config path. Throws an
    exception or returns successfully.

    """

    vmFolder = invt.GetVmFolder()
    if pool == None:
        pool = invt.GetResourcePool()
    vimutil.InvokeAndTrack(vmFolder.RegisterVm, cfg, None,\
          asTemplate, pool, host)


def Unregister(cfg):
    """
    Unregister a vm with the given path. Throws an exception or
    returns.
    """

    vm = FindCfg(cfg)
    if vm == None:
        raise Vmodl.Fault.ManagedObjectNotFound()
    vm.Unregister()


def FindUniqueName(prefix):
    """
    Find a unique name for a virtual machine with prefix
    supplied by user.
    """

    vmname = prefix
    i = 0
    vm = None
    while 1:
        vm = Find(vmname)
        if vm != None:
            vmname = vmname + str(i)
            i = i + 1
        else:
            break
    return vmname


def GetHostAll(datacenter=None, si=None):
    """ Returns an iterator object that walks the inventory tree and yields
    all HostSystem instances for each Datacenter object that satisfies
    the datacenter() predicate, if specified.
    """
    children = invt.GetHostFolderAll(datacenter, si)
    while children:
        entities, children = children, []
        for entity in entities:
            if isinstance(entity, Vim.ComputeResource):
                for host in entity.host:
                    yield host
            elif isinstance(entity, Vim.Folder):
                children = chain(children, entity.childEntity)
            else:
                raise NotImplementedError


def GetNetworkAll(datacenter=None, si=None):
    """ Returns an iterator object that walks the inventory tree and yields
    all Network instances for each Datacenter object that satisfies
    the datacenter() predicate, if specified.
    """
    children = invt.GetNetworkFolderAll(datacenter, si)
    while children:
        entities, children = children, []
        for entity in entities:
            if isinstance(entity, Vim.Network):
                yield entity
            elif isinstance(entity, Vim.Folder):
                children = chain(children, entity.childEntity)
            elif isinstance(entity, Vim.DistributedVirtualSwitch):
                children = chain(children, entity.portgroup)
            else:
                raise NotImplementedError


def GetDatastoreAll(datacenter=None, si=None):
    """ Returns an iterator object that walks the inventory tree and yields
    all Datastore instances for each Datacenter object that satisfies
    the datacenter() predicate, if specified.
    """
    children = invt.GetDatastoreFolderAll(datacenter, si)
    while children:
        entities, children = children, []
        for entity in entities:
            if isinstance(entity, Vim.Datastore):
                yield entity
            elif isinstance(entity, Vim.Folder):  # handles Vim.StoragePod too
                children = chain(children, entity.childEntity)
            else:
                raise NotImplementedError
