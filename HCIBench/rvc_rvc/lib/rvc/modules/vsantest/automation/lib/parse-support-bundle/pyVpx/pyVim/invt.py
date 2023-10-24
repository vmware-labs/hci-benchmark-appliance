## @file invt.py
## @brief Inventory functions
"""
Inventory functions

Detailed description (for [e]pydoc goes here)
"""

from pyVmomi import vmodl, vim
from . import connect
from itertools import chain


def GetEnv(dataCenter=None, si=None):
    """Get the default environment for this host"""
    cr = GetHostFolder(dataCenter, si).GetChildEntity()[0]
    return cr.GetEnvironmentBrowser()


def GetResourcePool(dataCenter=None, si=None):
    """Get the default resource pool"""
    computeResources = GetHostFolder(dataCenter, si).GetChildEntity()
    if len(computeResources) == 0:
        return None

    cr = computeResources[0]
    return cr.GetResourcePool()


def GetRootFolder(si=None):
    """Gets the root folder of the inventory"""
    if not si:
        si = connect.GetSi()
    return si.RetrieveContent().GetRootFolder()


def GetDatacenter(name=None, si=None):
    """
    Gets the datacenter with the given name. If the name is None, returns the first
    (and in the case of hostd, only) datacenter.
    """
    if not si:
        si = connect.GetSi()
    content = si.RetrieveContent()

    if name is None:
        if len(content.GetRootFolder().GetChildEntity()) == 0:
            return None
        else:
            for child in content.GetRootFolder().GetChildEntity():
                # Not all children of the root folder are Datacenters, so we need
                # to scan the list looking for one.
                if isinstance(child, vim.Datacenter):
                    return child

            return None
    else:
        return FindChild(content.GetRootFolder(), name)


def GetDatacenterAll(si=None):
    """ Returns an iterator object that walks the inventory tree and yields all
    Datacenter instances.
    """

    children = GetRootFolder(si).childEntity
    while children:
        entities, children = children, []
        for entity in entities:
            if isinstance(entity, vim.Datacenter):
                yield entity
            elif isinstance(entity, vim.Folder):
                children = chain(children, entity.childEntity)
            else:
                raise NotImplementedError


def GetVmFolder(dataCenter=None, si=None):
    """Retrieve the folder where virtual machines are stored on this host."""
    return GetDatacenter(dataCenter, si).GetVmFolder()


def GetVmFolderAll(datacenter=None, si=None):
    """ Returns an iterator object that walks the inventory tree and yields
    all vm Folder instances for each Datacenter object that satisfies
    the datacenter() predicate, if specified.
    """
    return (dc.GetVmFolder() for dc in GetDatacenterAll(si) \
               if not datacenter or datacenter(dc))


def GetHostFolder(dataCenter=None, si=None):
    """Retrieve the host folder for the given datacenter."""
    return GetDatacenter(dataCenter, si).GetHostFolder()


def GetHostFolderAll(datacenter=None, si=None):
    """ Returns an iterator object that walks the inventory tree and yields
    all host Folder instances for each Datacenter object that satisfies
    the datacenter() predicate, if specified.
    """
    return (dc.GetHostFolder() for dc in GetDatacenterAll(si) \
               if not datacenter or datacenter(dc))


def GetNetworkFolder(dataCenter=None, si=None):
    """Retrieve the network folder for the given datacenter."""
    return GetDatacenter(dataCenter, si).GetNetworkFolder()


def GetNetworkFolderAll(datacenter=None, si=None):
    """ Returns an iterator object that walks the inventory tree and yields
    all network Folder instances for each Datacenter object that satisfies
    the datacenter() predicate, if specified.
    """
    return (dc.GetNetworkFolder() for dc in GetDatacenterAll(si) \
               if not datacenter or datacenter(dc))


def GetDatastoreFolder(dataCenter=None, si=None):
    """Retrieve the datastore folder for the given datacenter."""
    return GetDatacenter(dataCenter, si).GetDatastoreFolder()


def GetDatastoreFolderAll(datacenter=None, si=None):
    """ Returns an iterator object that walks the inventory tree and yields
    all datastore Folder instances for each Datacenter object that satisfies
    the datacenter() predicate, if specified.
    """
    return (dc.GetDatastoreFolder() for dc in GetDatacenterAll(si) \
               if not datacenter or datacenter(dc))


def GetCluster(dataCenter=None, clusterName=None, si=None):
    """Retrieve the specified cluster object"""
    if si is None:
        si = connect.GetSi()
    content = si.RetrieveContent()

    return FindChild(GetHostFolder(dataCenter, si), clusterName)


def FindChild(parent, name):
    """
    Find the managed entity with the given name in the list of children for this
    entity. If the input name is None, returns the first child. Returns None if
    the child with the given name is not found
    """

    if name is None:
        return parent.GetChildEntity()[0]

    for child in parent.GetChildEntity():
        try:
            if child.GetName() == name:
                return child
        except vmodl.fault.ManagedObjectNotFound:
            # By the time GetName is called, child from parent.GetChildEntity
            # may have been destroyed, see PR 2012619
            pass
    return None


def GetLLPM():
    """Retrieve the internal LowLevelProvisioningManager object."""
    si = connect.GetSi()
    internalContent = si.RetrieveInternalContent()

    return internalContent.GetLlProvisioningManager()


def matchName(obj, pathToMatch):
    currentName = obj.GetName()
    currentName = currentName.replace("/", "%2f")
    if pathToMatch == "" or pathToMatch == "*":
        return [True, pathToMatch, True]

    pathSplit = pathToMatch.split("/", 1)
    if pathSplit[0] == "*":
        if len(pathSplit) == 1:
            return [True, "*", True]
        else:
            return [True, pathSplit[1], True]
    else:
        if pathSplit[0] == currentName:
            if len(pathSplit) == 1:
                return [True, "", False]
            else:
                return [True, pathSplit[1], True]
        else:
            return [False]


def checkfilter(flt, obj):
    # Does this item match the filter?
    # Simple "and" grammar and python regular expression test
    # Syntax for filter = "name=foo&&powerstate=bar"
    # XXX: Not implemented
    # XXX: Doesnt work with =, &
    if flt is not None and flt != "":
        if obj.GetName() != flt:
            return False

    return True


def recurseFolder(filter,
                  children,
                  recurseList,
                  entityType,
                  pathToMatch,
                  parentPath,
                  recurseFurther=True):
    """ Recurse folders and find certain types of children """
    results = []
    if type(children) != list:
        for recurseTypes in recurseList:
            if isinstance(children, recurseTypes[0]):
                if isinstance(children, entityType) and checkfilter(
                        filter, children):
                    results.append([children, parentPath])
                if not recurseFurther:
                    return results
                res = matchName(children, pathToMatch)
                if res[0] == False:
                    return results
                newPathToMatch = res[1]
                fnslist = recurseTypes[1]
                for fnname in fnslist:
                    fn = getattr(children, fnname)
                    babies = fn()
                    results = results + recurseFolder(
                        filter, babies, recurseList, entityType, res[1],
                        parentPath + "/" + children.GetName(), res[2])
                return results
    for child in children:
        res = matchName(child, pathToMatch)
        if res[0] == False:
            continue
        if isinstance(child, entityType) and checkfilter(filter, child):
            results.append([child, parentPath])
        if recurseFurther:
            for recurseTypes in recurseList:
                if isinstance(child, recurseTypes[0]):
                    fnslist = recurseTypes[1]
                    for fnname in fnslist:
                        fn = getattr(child, fnname)
                        babies = fn()
                        results = results + recurseFolder(
                            filter, babies, recurseList, entityType, res[1],
                            parentPath + "/" + child.GetName(), res[2])
    return results


def startFind(list, objType, parent, filter, si=None):
    if not si:
        si = connect.GetSi()
    sc = si.RetrieveContent()
    root = sc.GetRootFolder()
    children = root.GetChildEntity()
    # The first / in the path is always useless, get rid of it
    if len(parent) > 0 and parent[0] == "/":
        parent = parent[1:]
    results = recurseFolder(filter, children, list, objType, parent, "")
    return results


def findVms(parent, filter, si=None):
    return startFind(
        [[vim.Folder, ["GetChildEntity"]], [vim.Datacenter, ["GetVmFolder"]]],
        vim.VirtualMachine, parent, filter, si)


def findDatacenters(parent, filter, si=None):
    return startFind([[vim.Folder, ["GetChildEntity"]]], vim.Datacenter,
                     parent, filter, si)


def findFolders(parent, filter, si=None):
    return startFind([[vim.Folder, ["GetChildEntity"]],
                      [vim.Datacenter, ["GetVmFolder", "GetHostFolder"]]],
                     vim.Folder, parent, filter, si)


def findComputeResource(parent, filter, si=None):
    return startFind([[vim.Folder, ["GetChildEntity"]],
                      [vim.Datacenter, ["GetHostFolder"]]],
                     vim.ComputeResource, parent, filter, si)


def findHost(parent, filter, si=None):
    return startFind(
        [[vim.Folder, ["GetChildEntity"]], [vim.Datacenter, ["GetHostFolder"]],
         [vim.ComputeResource, ["GetHost"]]], vim.HostSystem, parent, filter,
        si)


def findResourcePools(parent, filter, si=None):
    return startFind(
        [[vim.Folder, ["GetChildEntity"]], [vim.Datacenter, ["GetHostFolder"]],
         [vim.ComputeResource, ["GetResourcePool"]],
         [vim.ResourcePool, ["GetResourcePool"]]], vim.ResourcePool, parent,
        filter, si)


def getInventoryPath(entity, si=None):
    if si is None:
        si = connect.GetSi().RetrieveContent()
    else:
        si = si.content
    pc = si.GetPropertyCollector()
    PC = vmodl.query.PropertyCollector
    # Retrieve the "name" and "parent" properties for all the managed entities
    # reachable by following "parent" properties starting from managedEntity.
    objectSet = pc.RetrieveContents([
        PC.FilterSpec(
            propSet=[
                PC.PropertySpec(type=vim.ManagedEntity,
                                pathSet=["name", "parent"])
            ],
            objectSet=[
                PC.ObjectSpec(
                    obj=entity,
                    selectSet=[
                        PC.TraversalSpec(
                            name="ParentTraversalSpec",
                            type=vim.ManagedEntity,
                            path="parent",
                            selectSet=[
                                PC.SelectionSpec(name="ParentTraversalSpec")
                            ])
                    ])
            ])
    ])

    # Create map containing an entry for each manaaged entity retrieved by
    # the RetrieveContents call above.  Each entry maps the MOID of the managed entity
    # to a dict with 'name' and 'parent' keys.
    entityMap = dict()
    for oc in objectSet:
        if len(oc.missingSet) != 0:
            raise RuntimeError('Missing properties: %s' %
                               [mp.path for mp in oc.missingSet])

        entityMap[oc.obj._moId] = dict([(p.name, p.val) for p in oc.propSet])
        entityMap[oc.obj._moId].setdefault('parent', None)

    # Use entityMap to walk the "parent" properties of the managed entities,
    # starting with entity, computing the inventory path (from end to
    # beginning) along the way.
    result = []
    current = entityMap[entity._moId]
    while current:
        parent = current['parent']
        if parent:
            result.insert(0, current['name'])
            current = entityMap[parent._moId]
        else:
            current = None
    return '/'.join(result)


def getContainingDatacenter(entity, si=None):
    if si is None:
        si = connect.GetSi().RetrieveContent()
    else:
        si = si.content
    pc = si.GetPropertyCollector()
    PC = vmodl.query.PropertyCollector
    # Retrieve the moRef of the datacenter reachable by following ResourcePool
    # "owner" and ManagedEntity "parent" properties starting from entity.
    #
    # Note: This does not (currently) work for virtual machines inside a VApp.
    objectSet = pc.RetrieveContents([
        PC.FilterSpec(
            propSet=[PC.PropertySpec(type=vim.Datacenter)],
            objectSet=[
                PC.ObjectSpec(
                    obj=entity,
                    selectSet=[
                        PC.TraversalSpec(
                            type=vim.HostSystem,
                            path="parent",
                            selectSet=[
                                PC.TraversalSpec(
                                    type=vim.ComputeResource,
                                    path="parent",
                                    selectSet=[
                                        PC.SelectionSpec(
                                            name='FolderParentTraversalSpec')
                                    ]),
                            ]),
                        PC.TraversalSpec(
                            type=vim.ResourcePool,
                            path="owner",
                            selectSet=[
                                PC.TraversalSpec(
                                    type=vim.ComputeResource,
                                    path="parent",
                                    selectSet=[
                                        PC.SelectionSpec(
                                            name='FolderParentTraversalSpec')
                                    ]),
                            ]),
                        PC.TraversalSpec(
                            type=vim.ManagedEntity,
                            path="parent",
                            selectSet=[
                                PC.TraversalSpec(
                                    name='FolderParentTraversalSpec',
                                    type=vim.Folder,
                                    path="parent",
                                    selectSet=[
                                        PC.SelectionSpec(
                                            name='FolderParentTraversalSpec')
                                    ]),
                            ])
                    ])
            ])
    ])
    if len(objectSet) == 0:
        return None
    elif len(objectSet) == 1:
        return objectSet[0].obj
    else:
        raise RuntimeError('multiple objects returned from property collector')
