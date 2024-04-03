## @file vc.py
## @brief Functions for interacting with VirtualCenter.
"""
Functions for interacting with VirtualCenter.

Detailed docs go here.
"""

from pyVmomi import Vim, Vmodl
from . import invt
from . import connect
from .task import WaitForTask


def AddHost(host,
            port=443,
            user='root',
            pwd=None,
            dataCenter=None,
            clusterName=None,
            sslThumbprint=None):
    """
    Adds the given host to the VC inventory. Should be
    invoked after the connection to the server has been established.
    """

    if connect.GetSi() is None:
        raise Vmomi.InternalError()

    vmFolder = invt.GetVmFolder(dataCenter)
    hostFolder = invt.GetHostFolder(dataCenter)

    cnxSpec = Vim.Host.ConnectSpec()
    cnxSpec.SetHostName(host)
    cnxSpec.SetPort(port)
    cnxSpec.SetUserName(user)
    cnxSpec.SetPassword(pwd)
    cnxSpec.SetVmFolder(vmFolder)
    cnxSpec.SetForce(True)
    if sslThumbprint:
        cnxSpec.SetSslThumbprint(sslThumbprint)

    if clusterName is None:
        task = hostFolder.AddStandaloneHost(spec=cnxSpec, addConnected=True)
    else:
        cluster = invt.GetCluster(dataCenter, clusterName)
        # add to cluster, default resource pool
        #task = cluster.AddHost(cnxSpec, True, invt.GetResourcePool(dataCenter))
        task = cluster.AddHost(cnxSpec, True, None)

    if WaitForTask(task) == "error":
        raise task.info.error
    else:
        return task.info.result


def AddHostWithUnknownSSLThumbprint(host,
                                    port=443,
                                    user='root',
                                    pwd=None,
                                    dataCenter=None,
                                    clusterName=None):
    try:
        return AddHost(host, port, user, pwd, dataCenter, clusterName, None)
    except Vim.fault.SSLVerifyFault as e:
        return AddHost(host, port, user, pwd, dataCenter, clusterName,
                       e.thumbprint)


def RemoveEntity(entity):
    if connect.GetSi() is None:
        raise Vmomi.InternalError()
    elif not isinstance(entity, Vim.ManagedEntity):
        raise TypeError("Must specify a managed entity")
    elif isinstance(entity, Vim.HostSystem):
        entity = entity.parent
        if isinstance(entity, Vim.ClusterComputeResource):
            raise Vmomi.InternalError(
                "Removing a host from a cluster not implemented")
    elif isinstance(entity, Vim.ComputeResource) and \
           not isinstance(entity, Vim.ClusterComputeResource):
        pass
    else:
        raise TypeError("Removing '%s' not implemented" %
                        entity.__class__.__name__)

    task = entity.Destroy()
    try:
        result = WaitForTask(task)
    except Vmodl.Fault.ManagedObjectNotFound:
        # PR252466: When the entity goes away, attempts to read the TaskInfo object
        # throw ManagedObjectNotFound trying to access the entity.  Assume that
        # the operation succeeded (seeing as the entity is gone and all).
        result = "success"

    if result == "error":
        raise task.info.error


def CreateDatacenter(name="default datacenter"):
    """ Creates a datacenter with the given name to the root folder. """

    rootFolder = invt.GetRootFolder()
    return rootFolder.CreateDatacenter(name)
