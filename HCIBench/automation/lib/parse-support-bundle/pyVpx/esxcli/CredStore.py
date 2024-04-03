#!/usr/bin/env python
"""
Copyright 2008-2014, 2017 VMware, Inc.  All rights reserved. -- VMware Confidential

This module handle reading info from credstore
"""

__author__ = "VMware, Inc"

import sys
import logging
from base64 import b64decode

try:
   from ctypes import windll, create_string_buffer
   import msvcrt

   class AutoFileLockBase:
      # Size of 64 bits OVERLAPPED struct
      _OVERLAPPED_BUFSIZE = 8 * 2 + 4 * 2 + 8

      # Lock region low, high dword
      _LOCK_LOW, _LOCK_HIGH = 0x0, 0x80000000

      @staticmethod
      def _GetLockFlags():
         """ Returns flag for SHARED, EXCLUSIVE, FLAGS_NB """
         return 0x0, 0x2, 0x1

      @staticmethod
      def _GetHandle(fd):
         """ Get Windows Handle from python file handle """
         return msvcrt.get_osfhandle(fd.fileno())

      @staticmethod
      def _LockFile(fd, op):
         """ Lock file """
         hdl = AutoFileLockBase._GetHandle(fd)
         dwReserved = 0
         overlapped = create_string_buffer(AutoFileLockBase._OVERLAPPED_BUFSIZE)
         ret = windll.kernel32.LockFileEx(hdl, op, dwReserved,
                                          AutoFileLockBase._LOCK_LOW,
                                          AutoFileLockBase._LOCK_HIGH,
                                          overlapped)
         if ret == 0:
            dwError = windll.kernel32.GetLastError()
            ioError = IOError("%d" % dwError)
            if dwError == 33: # ERROR_LOCK_VIOLATION
               import errno
               ioError.errno = errno.EAGAIN
            raise ioError

      @staticmethod
      def _UnlockFile(fd):
         """ Unlock file """
         hdl = AutoFileLockBase._GetHandle(fd)
         dwReserved = 0
         overlapped = create_string_buffer(AutoFileLockBase._OVERLAPPED_BUFSIZE)
         ret = windll.kernel32.UnlockFileEx(hdl, dwReserved,
                                            AutoFileLockBase._LOCK_LOW,
                                            AutoFileLockBase._LOCK_HIGH,
                                            overlapped)
except ImportError:
   import fcntl

   class AutoFileLockBase:
      @staticmethod
      def _GetLockFlags():
         """ Returns flag for SHARED, EXCLUSIVE, FLAGS_NB """
         return fcntl.LOCK_SH, fcntl.LOCK_EX, fcntl.LOCK_NB

      @staticmethod
      def _LockFile(fd, op):
         """ Lock file """
         # Note:
         # - If IOError with [Errno 9] Bad file descriptor, check to make
         #   sure fd is opened with "r+" / "w+"
         # - If non-blocking, but will block, lockf will raise IOError, with
         #   errno set to EACCES or EAGAIN
         fcntl.lockf(fd, op)

      @staticmethod
      def _UnlockFile(fd):
         """ Unlock file """
         fcntl.lockf(fd, fcntl.LOCK_UN)


class AutoFileLock(AutoFileLockBase):
   """ AutoFileLock """
   SHARED, EXCLUSIVE, FLAGS_NB = AutoFileLockBase._GetLockFlags()

   # AutoFileLock init
   # @param fd Open file handle
   # @param op SHARED / EXCLUSIVE, optionally or with FLAGS_NB for
   #           non-blocking
   #           If non-blocking and will block, __init__ will raise IOError,
   #           with errno set to EACCES or EAGAIN
   def __init__(self, fd, op):
      self.fd = None
      self._LockFile(fd, op)
      self.fd = fd

   def __enter__(self):
      return self.fd

   def __exit__(self, exc_type, exc_value, traceback):
      if self.fd:
         self._UnlockFile(self.fd)
         self.fd = None


class CredStore:
   """ CredStore """

   _TAG_VERSION = "version"
   _PWD_ENTRY = "passwordEntry"
   _THM_ENTRY = "thumbprintEntry"
   _TAG_HOST = "host"
   _TAG_USER = "username"
   _TAG_PASSWD = "password"
   _TAG_THUMBPRINT = "thumbprint"

   def __init__(self, credStorePath):
      """ Setup credstore """

      import xml.dom.minidom
      self._TEXT_NODE = xml.dom.minidom.Node.TEXT_NODE

      self.dom = None
      # Open and share lock credstore file
      with open(credStorePath, "r+") as fd:
         with AutoFileLock(fd, AutoFileLock.SHARED) as fdLocked:
            self.dom = xml.dom.minidom.parse(fdLocked)

      # Warning about version
      if self.dom:
         try:
            versionNodes = self.dom.getElementsByTagName(self._TAG_VERSION)[0]
            version = float(versionNodes.firstChild.data)
            if version > 1.1:
               logging.error("CredStore may not support this version %f" % version)
         except Exception:
            pass

   def PasswordTuples(self):
      """ Password entries generator """

      if self.dom:
         tags = [self._TAG_HOST, self._TAG_USER, self._TAG_PASSWD]
         tuples = self.dom.getElementsByTagName(self._PWD_ENTRY)
         for tupleNode in tuples:
            nodes = [tupleNode.getElementsByTagName(tag)[0].firstChild \
                                                               for tag in tags]
            textNodes = [node for node in nodes if \
                                              node.nodeType == self._TEXT_NODE]
            if len(textNodes) != 3:
               continue
            yield textNodes

   def ThumbprintTuples(self):
      """ Thumbprint entries generator """

      if self.dom:
         tags = [self._TAG_HOST, self._TAG_THUMBPRINT]
         tuples = self.dom.getElementsByTagName(self._THM_ENTRY)
         for tupleNode in tuples:
            nodes = [tupleNode.getElementsByTagName(tag)[0].firstChild \
                                                               for tag in tags]
            textNodes = [node for node in nodes if \
                                              node.nodeType == self._TEXT_NODE]
            if len(textNodes) != 2:
               continue
            yield textNodes

   def GetUserNames(self, host):
      """ Get user names with host """

      usernames = []
      if self.dom and host:
         # Find users associated with host
         normalizedHost = host.lower()
         for hostNode, userNode, passwdNode in self.PasswordTuples():
            # Match host name and user name
            if normalizedHost == hostNode.data.lower():
               usernames.append(userNode.data)

      return usernames

   def GetPassword(self, host, user):
      """ Get password with host and user """

      if self.dom and host and user:
         # Find host / user, and decode password if found
         normalizedHost = host.lower()
         for hostNode, userNode, passwdNode in self.PasswordTuples():
            # Match host name and user name
            if normalizedHost != hostNode.data.lower() or user != userNode.data:
               continue

            # Decode password
            return self._Decode(normalizedHost + user, passwdNode.data)

      return None

   def GetThumbprint(self, host):
      """ Get certificate thumbprint for host """

      if self.dom and host:
         # Find host
         normalizedHost = host.lower()
         for hostNode, thumbprintNode in self.ThumbprintTuples():
            # Match host name
            if normalizedHost != hostNode.data.lower():
               continue

            return thumbprintNode.data

      return None

   @staticmethod
   def _Decode(key, encodedPasswd):
      """ Decode password with key """

      hashKey = CredStore._Hash(key) & 0xff
      rawPasswd = b64decode(encodedPasswd)

      # Decode password with the XOR algorithm
      passwdLst = []
      for ch in rawPasswd:
         if sys.version_info[0] >= 3:
            val = ch ^ hashKey
         else:
            val = ord(ch) ^ hashKey
         if val != 0:
            passwdLst.append(chr(val))
         else:
            break
      passwd = "".join(passwdLst)
      return passwd

   @staticmethod
   def _Hash(key):
      """ Hash key """

      hash = 0
      for ch in key:
         hash = hash * 31 + ord(ch)
         if hash & 0x80000000:
            hash |= ~0x7fffffff
         else:
            hash &= 0x7fffffff
      return hash
