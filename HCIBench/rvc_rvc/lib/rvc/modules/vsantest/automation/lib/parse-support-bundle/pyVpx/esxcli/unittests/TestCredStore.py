#!/usr/bin/env python
"""
Copyright 2008-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is used to test credstore
"""
__author__ = "VMware, Inc"

import unittest

# import SoapHandler
import sys
sys.path.append("..")
from CredStore import CredStore, AutoFileLock
import errno

class TestCredStore(unittest.TestCase):
   ## Setup
   #
   def setUp(self):
      self.credStorePath = "vicredentials.xml"
      self.pwdTuples = [("Foo", "Bar", "blah"), ("Foo1", "Bar1", "blah1")]
      self.thmTuples = [("Foo",  "AA:AA:AA:AA:AA:AA:AA:AA:AA:AA:AA:AA:AA:AA:AA:AA:AA:AA:AA:AA"),
                        ("Foo1", "BB:BB:BB:BB:BB:BB:BB:BB:BB:BB:BB:BB:BB:BB:BB:BB:BB:BB:BB:BB")]

   ## tearDown
   #
   def tearDown(self):
      pass

   ## Test credstore path not exists
   #
   def test_CredStorePathNotExist(self):
      try:
         credStore = CredStore("foo")
      except IOError:
         pass

   ## Test credstore GetUserNames (host not exists)
   #
   def test_CredStoreGetUserNamesNotExists(self):
      credStore = CredStore(self.credStorePath)
      self.failUnless(len(credStore.GetUserNames("NotExists")) == 0)

   ## Test credstore GetThumbprint (host not exists)
   #
   def test_CredStoreGetThumbprintNotExists(self):
      credStore = CredStore(self.credStorePath)
      self.failUnless(credStore.GetThumbprint("NotExists") is None)

   ## Test credstore GetUserNames (host exists)
   #
   def test_CredStoreGetUserNames(self):
      credStore = CredStore(self.credStorePath)
      for host, user, passwd in self.pwdTuples:
         users = credStore.GetUserNames(host)
         self.failIf(len(users) != 1)
         self.failIf(users[0] != user)

   ## Test credstore GetUserNames (host exists)
   #
   def test_CredStoreGetThumbprint(self):
      credStore = CredStore(self.credStorePath)
      for host, thumbprint in self.thmTuples:
         thm = credStore.GetThumbprint(host)
         self.failIf(thm is None)
         self.failIf(thm != thumbprint)

   ## Test credstore host / user not exists
   #
   def test_CredStoreHostUserNotExist(self):
      credStore = CredStore(self.credStorePath)
      self.failUnless(credStore.GetPassword("NotExists", "NotExists") is None)
      self.failUnless(credStore.GetPassword(self.pwdTuples[0][0], "NotExists") is None)
      self.failUnless(credStore.GetPassword("NotExists", self.pwdTuples[0][1]) is None)

   ## Test credstore host / user password match
   #
   def test_CredStoreGetPassword(self):
      credStore = CredStore(self.credStorePath)
      for host, user, passwd in self.pwdTuples:
         password = credStore.GetPassword(host, user)
         self.failIf(password is None)
         self.failIf(password != passwd)

   ## Test AutoFileLock recursive
   #
   def test_AutoFileLockRecursive(self):
      with open(self.credStorePath, "r+") as fd:
         with AutoFileLock(fd, AutoFileLock.SHARED) as autoFileLock:
            with AutoFileLock(fd, AutoFileLock.SHARED) as autoFileLock1:
               pass

      with open(self.credStorePath, "r+") as fd:
         with AutoFileLock(fd, AutoFileLock.EXCLUSIVE) as autoFileLock:
            with AutoFileLock(fd, AutoFileLock.SHARED) as autoFileLock1:
               pass

      if sys.platform == "linux2":
         # Hmmmm, difficult to test NB failure
         with open(self.credStorePath, "r+") as fd:
            with AutoFileLock(fd, AutoFileLock.SHARED) as autoFileLock:
               with AutoFileLock(fd, AutoFileLock.EXCLUSIVE) as autoFileLock1:
                  pass

         with open(self.credStorePath, "r+") as fd:
            with AutoFileLock(fd, AutoFileLock.EXCLUSIVE) as autoFileLock:
               with AutoFileLock(fd, AutoFileLock.EXCLUSIVE) as autoFileLock1:
                  pass
      else:
         # Windows cannot do lock upgrade or recursive exclusive
         with open(self.credStorePath, "r+") as fd:
            with AutoFileLock(fd, AutoFileLock.SHARED) as autoFileLock:
               op = AutoFileLock.EXCLUSIVE | AutoFileLock.FLAGS_NB
               try:
                  with AutoFileLock(fd, op) as autoFileLock1:
                     self.failIf(True)
               except IOError as err:
                  self.failUnless(err.errno == errno.EAGAIN or
                                  err.errno == errno.EACCES)

         with open(self.credStorePath, "r+") as fd:
            with AutoFileLock(fd, AutoFileLock.EXCLUSIVE) as autoFileLock:
               op = AutoFileLock.EXCLUSIVE | AutoFileLock.FLAGS_NB
               try:
                  with AutoFileLock(fd, op) as autoFileLock1:
                     self.failIf(True)
               except IOError as err:
                  self.failUnless(err.errno == errno.EAGAIN or
                                  err.errno == errno.EACCES)

   ## Test AutoFileLock non-blocking
   #
   def test_AutoFileLockNonBlocking(self):
      with open(self.credStorePath, "r+") as fd:
         op = AutoFileLock.SHARED | AutoFileLock.FLAGS_NB
         with AutoFileLock(fd, op) as autoFileLock:
            with AutoFileLock(fd, op) as autoFileLock1:
               pass

      with open(self.credStorePath, "r+") as fd:
         op = AutoFileLock.EXCLUSIVE | AutoFileLock.FLAGS_NB
         with AutoFileLock(fd, op) as autoFileLock:
            op = AutoFileLock.SHARED | AutoFileLock.FLAGS_NB
            with AutoFileLock(fd, op) as autoFileLock1:
               pass

## Test main
#
if __name__ == "__main__":
   unittest.main()
