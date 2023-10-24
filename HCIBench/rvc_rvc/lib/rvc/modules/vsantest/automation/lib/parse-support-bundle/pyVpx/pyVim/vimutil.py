## @file vimutil.py --
## @brief Utility classes for using the python bindings
##
## Detailed description (for Doxygen goes here)
"""
Utility classes for using the python bindings

Detailed description (for [e]pydoc goes here)
"""

__author__ = "VMware, Inc"

import re
import hashlib

from pyVmomi import Vim
from .task import WaitForTask


## track the task that it returns
# @param func [in] Invoke the input function
# @param args [in] arguments to function
# @param kw [in] keyword arguments to function
# @return the value returned by WaitForTask
def InvokeAndTrack(func, *args, **kw):
    task = func(*args, **kw)
    return WaitForTask(task)


## track the task that it returns
# @param func [in] Invoke the input function
# @param args [in] arguments to function
# @param kw [in] keyword arguments to function
# @return the task
def InvokeAndTrackWithTask(func, *args, **kw):
    task = func(*args, **kw)
    WaitForTask(task)
    return task


## Represent a request as an Object
class Request:
    def __init__(self, propC, func, *args, **kw):
        self._pc = propC
        self._func = func
        self._args = args
        self._kw = kw

    ## Block till the task, if any, is returned is complete
    # @return None on sucess
    # @throw Exception on error
    def Invoke(self):
        task = self._func(*self._args, **self._kw)
        if task is None:
            return
        WaitForTask(task, raiseOnError=True, pc=self._pc)


## Get the service locator object for a given service instance
# @param si [in] service instance
# @param username [in] username to login to the service
# @param passwd [in] passwd to login to the service
# @return the service locator
def GetServiceLocator(si, username, passwd):

    uuid = si.content.about.instanceUuid

    conn = si._GetStub().GetConnection()
    url = "https://%s:%d/sdk" % (conn.host, conn.port)

    derCert = conn.sock.getpeercert(True)
    sha1 = hashlib.sha1(derCert).hexdigest().upper()
    thumbprint = re.sub(r'(.{2}(?!$))', r'\1:', sha1)

    locator = Vim.ServiceLocator()
    locator.SetInstanceUuid(uuid)
    locator.SetUrl(url)
    locator.SetCredential(Vim.ServiceLocator.NamePassword())
    locator.credential.SetUsername(username)
    locator.credential.SetPassword(passwd)
    locator.SetSslThumbprint(thumbprint)

    return locator
