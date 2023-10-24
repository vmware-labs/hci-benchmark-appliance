#!/usr/bin/python
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential

"""
@file conn/case_1.py --
TestCase 1 verifies *only* GetStubAdapter, its arguments and
various context (single and multiple threading). 
"""

__author__ = "VMware, Inc"

import os
import socket
import unittest
from pyVmomi import Vim, SoapStubAdapter

class FixtureConn(unittest.TestCase):
   """
   A base class to setup/cleanup test case objects derived from it.
   @see vimhost module for simpler way to run tests against hostd
   """
   adapters = [ "VMDB", "SOAP", "LOCAL" ]
   services = [ "hostd", "vpxd", "vpxa", "direct" ]
   # to specify ssl, port > 0, without, port < 0
   
   ## @post connection information (host,port,user,passwd) stored in instance
   def setUp(self):
      """
      Setup connection information.
      """
      self._cnx = None
      self._port = int(os.environ['VPORT'])
      self._host = os.environ['VHOST']
      self._user = os.environ['VLOGIN']
      self._pswd = os.environ['VPASSWD']
      self._ver = os.environ[r'VVERS']
      if self._ver is None:
          self._ver = "vim25/5.5"

   def tearDown(self):
      """
      Clean up.
      """
      self._cnx = None

class StubTest(FixtureConn):
   """
   This is a test stub class to make tests return success.
   """
   def test1_DoNothing(self):
      """Do nothing."""
      pass
   
class VerifyConnectionToHostd(FixtureConn):
   """
   This test case just checks connectivity between test app and hostd.     
   Verify a tcp/IPv4 connection can be made to the specified host and port.
   Verify peer is really hostd. We do a read expecting a greeting.
   """
   def test1_VerifyPortIsOpen(self):
      """
      Do TCP over IPv4 connection to port to verify connectivity
      """
      try:
         ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
         self.failIf(ss is None, "create tcp socket over IPv4")
      except Exception, msg:
         self.fail("Connect to host: %s: %s returned %s" % \
                   (self._host, self._port, str(msg)))
      try:
         try:
            self._cnx = ss.connect_ex((self._host, self._port))
            self.failIf(self._cnx is not 0,
                        "IPv4 connect to %s:%s failed, errno=%s %s" % \
                           (self._host,
                            str(self._port),
                            str(self._cnx),
                            os.strerror(self._cnx)
                           )
                       )
            SHUT_RDWR = 2
            ss.shutdown(SHUT_RDWR)
         except Exception, msg:
            print "ERROR: caught " + str(msg)
            raise msg
      finally:
         ss.close()

class VerifyHostdProtocolConnection(FixtureConn):
   """
   Verify connection to hostd over soap using ssl/tcp and tcp.
   """
   def test1_Connect2HostdOverSOAP(self):
      """
      Verify connection to hostd over soap over tcp.
      """
      self._cnx = SoapStubAdapter(self._host, self._port, ns=self._ver)

class VerifyHostdProtocolLogin(FixtureConn):
   """
   Verify Login works using userid and password to hostd
   over soap using ssl/tcp and tcp.
   """
   def test1_Login2HostdOverSOAPandSSL(self):
      """
      Verify protocol login to hostd over vmdb over ssl over tcp.
      """
      self._cnx = SoapStubAdapter(self._host, self._port, ns=self._ver)
      si = Vim.ServiceInstance("ServiceInstance", self._cnx)
      self.failUnless(isinstance(si, Vim.ServiceInstance),
                      "expected Vim.ServiceInstance, got %s" % \
                      si.__class__.__name__)
      content = si.RetrieveContent()
      self.failUnless(isinstance(content, Vim.ServiceInstanceContent),
                      "expected Vim.ServiceInstanceContent, got %s" % \
                      content.__class__.__name__)
      sm = content.GetSessionManager()
      self.failUnless(isinstance(sm, Vim.SessionManager),
                      "expected Vim.SessionManager, got %s" % \
                      sm.__class__.__name__)
      us = sm.Login(self._user.encode('utf8'), self._pswd.encode('utf8'), None)
      result = isinstance(us, Vim.UserSession)
      self.failUnless(result,
                      "expected Vim.UserSesion, got %s" % \
                      us.__class__.__name__)

