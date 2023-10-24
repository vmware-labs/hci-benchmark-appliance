## @file vimhost.py
## @brief Setup and manage Host Session operations
##
## Detailed description (for Doxygen goes here)
"""
Setup and manage Host Session operations.

Detailed description (for [e]pydoc goes here)
"""

__author__ = "VMware, Inc"

import os
from pyVmomi import Vim, Vmodl, SoapStubAdapter
from pyVim import vm
from pyVim import host
from . import vimutil


##
## @brief An abstraction to control a vim managed host system.
##
## NOTE: system message of the day is updated at login and reset at logout
##
class Host:
    """
    An abstraction to control a vim managed host system.

    NOTE: system message of the day is updated at login and reset at logout
    """

    ##
    # @param hostname is resolveable domain name string or IPv4 dotted quad
    # @param  port is string or numeric type containing a short value:
    #         range -65535-655535
    # @param login is a string identifier
    # @param passwd is a string
    # @throw exception (@todo type?) on on failure to connect and/or login
    # @post TCP connection established and autenticated with host on port
    #
    def __init__(self,
                 hostname=None,
                 port=None,
                 login=None,
                 passwd=None,
                 protocol=None,
                 namespace=None,
                 version=None):
        self._host = hostname or os.environ[r'VHOST']
        self._port = int(port or os.environ[r'VPORT'])
        self._user = (login or os.environ[r'VLOGIN']).encode('utf8')
        self._pswd = (passwd or os.environ[r'VPASSWD']).encode('utf8')
        self._protocol = protocol or os.environ[r'VPROTO']
        if self._protocol.lower() == "soap":
            if namespace is None and os.environ[r'VVERS']:
                self._namespace = os.environ[r'VVERS']
            elif namespace is None:
                self._namespace = "vim2/2.0"
            else:
                self._namespace = namespace
        self._version = version or os.environ[r'VVERS']
        self.__Login()

    ##
    #  Clear out reference to state held in this object
    #
    def __del__(self):
        try:
            if self._MsgUpdated is True:
                self._sm.UpdateMessage("")
            self._sm.Logout()
        except:
            pass
        self._sm = None
        self._cnx = None
        self._si = None
        self._content = None
        self._pc = None
        self._us = None

    ##
    #  Synchronous connection to given managed host
    #
    def __Login(self):
        print("INFO: connecting to hostd using '%s'" % (self._protocol))
        self._cnx = SoapStubAdapter(self._host, self._port, self._namespace)
        self._si = Vim.ServiceInstance("ServiceInstance", self._cnx)
        self._content = self._si.RetrieveContent()
        self._pc = self._content.GetPropertyCollector()
        self._sm = self._content.GetSessionManager()
        self._us = self._sm.Login(self._user, self._pswd, None)
        # report if anyone else is logged in
        sessionList = self._sm.GetSessionList()
        if (len(sessionList) > 1):
            self._MsgUpdated = True
            self._sm.UpdateMessage(
                "Integration Tests are running on this system")
            print("WARNING: more than one operator online during test run")
            for item in sessionList:
                print("%s login: %s last active: %s" % \
                (item.GetFullName(), item.GetLoginTime(), item.GetLastActiveTime()))

    ##
    # Return the name of this host
    #
    def GetName(self):
        return self._host

    ##
    # return Datacenter
    #
    def GetDatacenter(self):
        return self._content.GetRootFolder().GetChildEntity()[0]

    ##
    # @param dsName [in] is a name of a Datastore
    # @return Datastore with reqName or if None, first one found
    # @throw Exception if reqName is ambiguous
    #
    def GetDS(self, dsName=None):
        dsList = host.GetHostSystem(self._si).GetDatastore()
        if len(dsList) == 0:
            return None
        if dsName is None:
            return dsList[0]
        for item in dsList:
            try:
                if item.GetSummary().GetName() == dsName:
                    return item
            except Vmodl.Fault.ManagedObjectNotFound:
                pass
        return None

    ##
    # @return property collector
    #
    def GetPropertyCollector(self):
        return self._pc

    ##
    # @param reqName [in] is a name of a VM existing on this host
    # @return VM with reqName or None,
    # @throw Exception if reqName is ambiguous
    #
    def GetVM(self, reqName):
        vmList = self.GetFolderOfVMs().GetChildEntity()
        found = None
        theConfig = None
        for item in vmList:
            try:
                config = item.GetConfig()
                if config != None and config.GetName() == reqName:
                    if found is not None:
                        raise Exception("More than one VM has name: " +
                                        reqName)
                    found = item
                    theConfig = config
            except Vmodl.Fault.ManagedObjectNotFound:
                pass
        if found is not None:
            return vm.VM(found, self._pc, self.GetResourcePool(), theConfig)
        else:
            return None

    ## Register a VM with hostd
    # @param vm [in] is an unregistered VM object returned from prior GetVM call
    # @throw Exception if unable to register VM
    def RegisterVM(self, vm):
        cfg = vm._vmxFile
        template = vm._template
        host = vm._host
        pool = vm._pool
        rqt = vimutil.Request(self._pc, self.GetFolderOfVMs().RegisterVm, cfg, \
                              None, template, pool, host)
        rqt.Invoke()

    ##
    # @return Folder that contains VMs on this host
    #
    def GetFolderOfVMs(self):
        dc = self.GetDatacenter()
        if dc is None:
            raise Exception("No default datacenter object for" +
                            str(self._content))
        return dc.GetVmFolder()

    ##
    # @return resource pool tree
    #
    def GetResourcePool(self):
        dc = self.GetDatacenter()
        if dc is None:
            raise Exception("No default datacenter object for" +
                            str(self._content))
        hst = dc.GetHostFolder().GetChildEntity()[0]
        return hst.GetResourcePool()

    ##
    # @return NfcService or None
    # http://vmweb.vmware.com/~jcho/vmodldoc/vim/InternalServiceInstanceContent.html
    #
    def GetNfcService(self):
        return self._si.RetrieveInternalContent().GetNfcService()

    ##
    # @return FileManager interface or None
    # http://vmweb.vmware.com/~jcho/vmodldoc/vim/FileManager.html
    #
    def GetFileManager(self):
        return self._content.GetFileManager()

    ##
    # @return HostSystem interface or None
    #
    def GetHostSystem(self):
        return host.GetHostSystem(self._si)

    ## track the task that it returns
    # @param func [in] Invoke the input function
    # @param args [in] arguments to function
    # @param kw   [in] keyword arguments to function
    def InvokeAndTrack(self, func, *args, **kw):
        task = func(*args, **kw)
        vimutil.WaitForTask(task, pc=self.GetPropertyCollector())

    def EnterMaintenanceMode(self):
        """ Put host in maintenance mode. Blocks until op is complete. """
        self.InvokeAndTrack(self.GetHostSystem().EnterMaintenanceMode, 90,
                            False)

    def ExitMaintenanceMode(self):
        """ Take host out of maintenance mode. Blocks until op is complete. """
        self.InvokeAndTrack(self.GetHostSystem().ExitMaintenanceMode, 90,
                            False)
