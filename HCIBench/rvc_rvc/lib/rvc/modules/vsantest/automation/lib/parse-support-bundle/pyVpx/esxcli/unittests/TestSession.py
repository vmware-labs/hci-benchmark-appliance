#!/usr/bin/env python

"""
Copyright (c) 2008-2021 VMware, Inc.  All rights reserved.
-- VMware Confidential

This module is used to test Session
"""
__author__ = "VMware, Inc"

import unittest

# import SoapHandler
import sys
import os
import stat

sys.path.append("..")

from Session import IsInVisor, Session, SessionOptions, SessionLoginException
from pyVmomi import vmodl, vim

from optparse import OptionParser, make_option

class AnObject(object):
   pass

#print "Make sure hostd is running locally"

class TestSession(unittest.TestCase):
   ## Setup
   #
   def setUp(self):
      if sys.platform == "win32":
         sessionFile = "lwpCookie.txt"
      else:
         sessionFile = "/tmp/lwpCookie.txt"

      optionsList = [
         make_option("--host", dest="host", default="localhost",
                     help="ESX hostname"),
         make_option("-u", "--user", dest="user", default = "root",
                     help="User name"),
         make_option("-p", "--pwd", dest="password", default="ca$hc0w",
                     help="Password"),
      ]

      cmdParser = OptionParser(option_list=optionsList)
      (options, remainingArgs) = cmdParser.parse_args(sys.argv[1:])
      try:
         # optparser does not have a destroy() method in older python
         cmdParser.destroy()
      except Exception:
         pass
      del cmdParser

      self.sessionFile = sessionFile
      self.user = options.user
      self.host = options.host
      if sys.platform == "win32":
         if options.password == "''":
            options.password = ""
      self.password = options.password

   ## tearDown
   #
   def tearDown(self):
      pass

   ## Perform an action (which requires authentication)
   #
   def AuthenticatedAction(self, stub):
      # Get session list require authentication
      si = vim.ServiceInstance("ServiceInstance", stub)
      return si.RetrieveContent().sessionManager.sessionList

   ## Perform an action (which requires authentication).
   #  Succeed if action failed
   #
   def FailIfRemainAuthenticated(self, stub):
      try:
         self.AuthenticatedAction(stub)
         raise Exception("Remain authenticated after logout!!!")
      except vim.Fault.NotAuthenticated:
         pass

   ## Get a valid root session
   #
   def GetValidRootSession(self):
      options=AnObject()
      options.server = self.host
      options.username = self.user
      options.password = self.password

      sessionOptions = SessionOptions(options)
      return Session(sessionOptions)

   ## Helper fn to login and then logout
   #
   def LoginLogout(self, options, skipLogoutTest=False):
      # Get session
      sessionOptions = SessionOptions(options)
      session = Session(sessionOptions)

      # Login, do something and then logout
      stub = session.stub
      # Not need. Auto login when getting stub:
      # session.Login()
      self.AuthenticatedAction(stub)
      session.Logout()
      if not skipLogoutTest:
         self.FailIfRemainAuthenticated(stub)

   ## Test GetOptParseOptions
   #
   def test_GetOptParseOptions(self):
      # Make sure GetOptParseOptions returns valid options for optparse
      optionsList = SessionOptions.GetOptParseOptions()

      from optparse import OptionParser
      cmdParser = OptionParser(option_list=optionsList)

   ## Test local login
   #
   def test_LocalLogin(self):
      if IsInVisor():
         options=AnObject()
         options.host = "localhost"
         self.LoginLogout(options)
      else:
         print("Skipped local login test")

   ## Test PassthroughAuthentication Negotiate
   #
   def test_PassthroughAuthentication_Negotiate(self):
      if sys.platform != "win32":
         try:
            import kerberos
         except ImportError:
            print("Must installed pykerberos")
            print("Skipped passthrough authentication negotiate test")
            return

      options=AnObject()
      options.server = self.host
      options.passthroughauth = True
      options.passthroughauthpackage = "Negotiate"
      self.LoginLogout(options)

   ## Test PassthroughAuthentication NTLM
   #
   def test_PassthroughAuthentication_NTLM(self):
      if sys.platform == "win32":
         options=AnObject()
         options.server = self.host
         options.passthroughauth = True
         options.passthroughauthpackage = "NTLM"
         self.LoginLogout(options)
      else:
         print("Skipped passthrough authentication ntlm test")

   ## Test default root / password
   #
   def test_RootLoginLogout(self):
      options=AnObject()
      options.server = self.host
      options.username = self.user
      options.password = self.password
      self.LoginLogout(options)

   ## Test stub
   #
   def test_SessionStub(self):
      session = self.GetValidRootSession()
      stub = session.stub
      del stub

   ## Test invalid login
   #
   def test_InvalidLogin(self):
      options=AnObject()
      options.server = self.host
      options.username = "johndoe"
      options.password = self.password
      try:
         self.LoginLogout(options)
         raise Exception("Failed to throw invalid login")
      except SessionLoginException as err:
         pass

   ## Test load session from file
   #
   def test_SessionFile(self):
      session = self.GetValidRootSession()
      stub = session.stub
      # Do not logout from stub yet

      # Save lwp cookie
      session._SaveCookieFile(self.sessionFile, stub.cookie)

      # Load cookie
      options=AnObject()
      options.sessionfile = self.sessionFile

      sessionOptions = SessionOptions(options)
      session2 = Session(sessionOptions)

      # Check the session is valid
      self.AuthenticatedAction(session2.stub)

      # Now we can logout
      stub = session.stub
      stub2 = session2.stub
      session.Logout(force=True)

      # Make sure both stub are invalid
      self.FailIfRemainAuthenticated(stub)
      self.FailIfRemainAuthenticated(stub2)

   ## Test load logged out session from file. Should not work
   #
   def test_SessionFile_Already_Loggedout(self):
      session = self.GetValidRootSession()
      stub = session.stub

      # Save lwp cookie
      session._SaveCookieFile(self.sessionFile, stub.cookie)

      # Logout. See what will happen...
      session.Logout()

      # Load cookie
      options=AnObject()
      options.sessionfile = self.sessionFile

      sessionOptions = SessionOptions(options)
      session = Session(sessionOptions)
      session.Login()
      self.FailIfRemainAuthenticated(session.stub)

   ## Test savesessionfile option
   #
   def test_SaveSessionFile(self):
      options=AnObject()
      options.server = self.host
      options.username = self.user
      options.password = self.password
      options.savesessionfile = self.sessionFile

      sessionOptions = SessionOptions(options)
      session = Session(sessionOptions)

      session.Login()
      stub = session.stub
      session.Logout()

      # Make sure session file exists and readable by user only
      if sys.platform == "win32":
         # Windows os.stat().st_mode always returns og rw
         # TODO: Use some other way to test
         pass
      else:
         st = os.stat(options.savesessionfile)
         if (st.st_mode & (stat.S_IRWXG | stat.S_IRWXO)) != 0:
            raise Exception("Session file is world readable!!!")

      # Should remain authenticated after logout
      self.AuthenticatedAction(stub)

      # Close this session
      del session

      # Test session file is usable
      options=AnObject()
      options.sessionfile = self.sessionFile
      self.LoginLogout(options, skipLogoutTest=True)


## Test main
#
if __name__ == "__main__":
   #unittest.main()
   suite = unittest.TestLoader().loadTestsFromTestCase(TestSession)
   unittest.TextTestRunner().run(suite)

