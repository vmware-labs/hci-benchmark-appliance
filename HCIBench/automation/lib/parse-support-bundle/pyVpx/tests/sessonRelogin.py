#! /usr/bin/env python

#
# Test for the pyVim.connect.SessionOrientedStub wrapper for the SoapStubAdapter
#
# This test has dummy implementations of the Vim.SessionManager to make it
# easier to test the automatic Login mechanism when the server is restarting
# constantly.
#

from __future__ import print_function

import os
import sys
import time
import random
import signal
import socket
import httplib
import logging
import datetime

from MoManager import GetMoManager

from pyVmomi import Vim, Vmodl, SoapStubAdapter
from pyVim.connect import VimSessionOrientedStub

from PyVmomiServer import SoapHttpServer, GeneralHttpHandler

PORT = 8091

class SessionManagerImpl(Vim.SessionManager, object):
    '''Dummy implementation of the Vim.SessionManager class.'''
    def __init__(self, moId):
        Vim.SessionManager.__init__(self, moId)
        self.loggedIn = False

    @property
    def sessionList(self):
        '''Return an empty session list if the user is logged in, otherwise
        throw a NotAuthenticated exception.'''
        if not self.loggedIn:
            raise Vim.fault.NotAuthenticated(
                object=self,
                privilegeId="Like.A.Boss")
        return []

    def Login(self, userName, password, locale):
        '''Allow anyone but "Mallory" to login to this server.'''
        self.loggedIn = True
        if userName == "Mallory":
            raise Vim.fault.InvalidLogin()
        return Vim.UserSession(key="hi",
                               userName=userName,
                               fullName=userName,
                               loginTime=datetime.datetime.now(),
                               lastActiveTime=datetime.datetime.now(),
                               locale="en",
                               messageLocale="en")

    def Logout(self):
        self.loggedIn = False

class FolderImpl(Vim.Folder, object):
    '''Dummy Vim.Folder implementation used to make sure method exceptions are
    making it through the wrapper stub unharmed.'''
    def CreateFolder(self, name):
        raise Vim.fault.DuplicateName(name=name,
                                      object=Vim.Folder("Original"))

class ServiceInstanceImpl(Vim.ServiceInstance, object):
    def RetrieveContent(self):
        try:
            retval = Vim.ServiceInstanceContent(
                about=Vim.AboutInfo(),
                rootFolder=Vim.Folder("RootFolder"),
                sessionManager=Vim.SessionManager("SessionManager"),
                propertyCollector=Vmodl.query.PropertyCollector(
                    "PropertyCollector"))

            return retval
        except:
            logging.exception("retrieve content")
            return
    content = property(RetrieveContent)

def server():
    '''Dummy pyVmomi server that implements the minimal vim API for logging in
    and calling a couple of methods.'''
    nullfd = os.open("/dev/null", os.O_RDONLY)
    os.dup2(nullfd, 1)
    os.dup2(nullfd, 2)

    moman = GetMoManager()

    si = ServiceInstanceImpl("ServiceInstance")
    moman.RegisterObject(si)

    sm = SessionManagerImpl("SessionManager")
    moman.RegisterObject(sm)

    rf = FolderImpl("RootFolder")
    moman.RegisterObject(rf)

    SoapHttpServer.allow_reuse_address = True
    soapHttpd = SoapHttpServer(
        ("127.0.0.1", PORT),
        GeneralHttpHandler)
    soapHttpd.timeout = 300
    soapHttpd.soapStubs = None
    soapHttpd.serve_forever()

def serialKiller():
    '''Randomly starts and stops the server process so we can test that the
    client is handling errors correctly.'''
    while True:
        rc = os.fork()
        if rc == 0:
            server()
        else:
            time.sleep(random.uniform(0.0, 0.3))
            os.kill(rc, signal.SIGTERM)
            os.wait()

def main(_args):
    # logging.basicConfig(level=logging.DEBUG)
    rc = os.fork()
    if rc == 0:
        serialKiller()
    else:
        try:
            # Create the communication stub.
            soapStub = SoapStubAdapter(host="127.0.0.1", port=-PORT,
                                       version="vim.version.version9")

            # Create a stub to check that the wrapper is not silently eating
            # login-related any exceptions.
            badSessionStub = VimSessionOrientedStub(
                soapStub,
                VimSessionOrientedStub.makeUserLoginMethod("Mallory", "vmware"),
                retryDelay=0.1,
                retryCount=100000)

            try:
                si = Vim.ServiceInstance("ServiceInstance", badSessionStub)
                print(si.content.sessionManager)
                assert False, "able to login as Mallory?"
            except Vim.fault.InvalidLogin:
                # XXX Is it wrong, perhaps even immoral, for a non-Login method
                # to raise an InvalidLogin exception?
                pass


            # Create a session stub that should work correctly.  We set the
            # retryCount really high so that no method calls should ever fail.
            sessionStub = VimSessionOrientedStub(
                soapStub,
                VimSessionOrientedStub.makeUserLoginMethod("alice", "vmware"),
                retryDelay=0.05,
                retryCount=1000)

            si = Vim.ServiceInstance("ServiceInstance", sessionStub)
            # Sit in a loop and do RPCs.
            while True:
                try:
                    print(si.content.sessionManager.sessionList)

                    try:
                        # Make sure regular method calls can throw exceptions
                        # through the wrapper.
                        si.content.rootFolder.CreateFolder("Test")
                        assert False, "duplicate name fault wasn't thrown?"
                    except Vim.fault.DuplicateName:
                        pass
                except (socket.error, httplib.HTTPException):
                    logging.exception("cannot get sessionList")
                    time.sleep(0.1)
        except KeyboardInterrupt:
            logging.info("got interrupt")
        except:
            logging.exception("goodbye!")
        finally:
            os.kill(0, signal.SIGTERM)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
