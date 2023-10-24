import ssl

from pyVmomi import vim
from pyVim.connect import SmartStubAdapter, VimSessionOrientedStub

def _SmartSessionOrientedConnect(host, username, password):
   """Create a new session oriented stub that will
   automatically login when used.
   """

   # create a smart stub that will connect using the latest known
   # VIM version
   stub = SmartStubAdapter(host,
                           sslContext=ssl._create_unverified_context())

   # login with username and password
   loginMethod = VimSessionOrientedStub.makeUserLoginMethod(username, password)

   # and make the stub session oriented
   sessOrientedStub =  VimSessionOrientedStub(stub,
                                              loginMethod,
                                              retryDelay=0.5,
                                              retryCount=20)

   si = vim.ServiceInstance("ServiceInstance", sessOrientedStub)
   return si

def GetNfcSystemManagementTicket(host, username, password):
   """Ask for a System Management ticket from the NFC service
   of this host.
   """
   si = _SmartSessionOrientedConnect(host, username, password)
   nfcService = si.RetrieveInternalContent().GetNfcService()

   return nfcService.SystemManagement()
