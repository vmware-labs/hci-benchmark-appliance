# Copyright (c) 2018-2022 VMware, Inc.  All rights reserved.
# -- VMware Confidential

#
# pyHbr.utility.py
#
# General utility functions useful for working with hbr servers.
#
import atexit
import base64
import hashlib
import logging
import os
import paramiko
import select
import shlex
import shutil
import signal
import socket
import ssl
import struct
import subprocess
import sys
import warnings
import re
import uuid

from _ssl import CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED
from _ssl import PROTOCOL_SSLv23
sys.path.append('/build/apps/lib')
from build.utils import buildapi
from contextlib import closing


logger = logging.getLogger('pyHbr.util')

#
# The thumbprint used to indicate to the HBR agent to use plaintext
# passthrough mode. The thumbprint is in binary form base64 encoded.
#
PASSTHROUGH_THUMBPRINT_BASE64 = base64.b64encode(hashlib.sha256().digest()).decode('ascii')

_exitFuncs = []
def _CallExitFuncs():
   global _exitFuncs
   for fn in reversed(_exitFuncs):
      try:
         fn()
      except:
         pass


def AtExit(fn):
   """Register a function that will run at process exit.

   Note: this replaces any SIGTERM handler that was already registered.
   """

   assert callable(fn), "Can't register a non-callable object"

   def SignalHandler(signum, stackframe):
      _CallExitFuncs()
      os._exit(signum)

   global _exitFuncs
   if not _exitFuncs:
      # atexit will not run if the process is killed by any signal
      # other than SIGINT. We only care about SIGTERM as SIGKILL
      # can't be handled
      signal.signal(signal.SIGTERM, SignalHandler)
      atexit.register(_CallExitFuncs)

   _exitFuncs.append(fn)


def CertToHash(cert):
   """Convert a certificate string to a SHA256 hash"""

   return hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert))


def CertToThumbprint(cert):
   """Convert a certificate string to a thumbprint."""

   # Generate the ASCII hex digest
   rawThumbprint = CertToHash(cert).hexdigest()

   #
   # Format the raw hex digest into a canonical thumbprint with
   # a colon between every two hex digits and everything in upper-case.
   #
   thumbprint = ":".join([rawThumbprint[x:x + 2]
                         for x in range(0, len(rawThumbprint), 2)])
   return thumbprint.upper()


def CertToBase64Thumbprint(cert):
   """Convert a certificate string to a base-64 encoded thumbprint."""

   rawThumbprint = CertToHash(cert).digest()
   return base64.b64encode(rawThumbprint).decode('ascii')


#
# XXX PR1220821, this is a temporary monkey patch to fix the obselete
# get_server_certificate function in python2.6/ssl.py in the toolchain
# need to be removed after toolchain team update the python library
#
# Note: we default to ssl_version=PROTOCOL_SSLv23 because that will
# happily upgrade to whatever the server wants. If we ask for
# TLSv1_2, we will only be able to connect using TLSv1_2 which might
# break in the future.
#
def FixedGetServerCertificate(addr, ssl_version=PROTOCOL_SSLv23, ca_certs=None):
   """Retrieve the certificate from the server at the specified address,
   and return it as a PEM-encoded string.

   Arguments:
      ssl_version: SSL version to use for this connection attempt.
      ca_certs: validate the server cert against these CA certificates.
   """
   warnings.warn("This is a monkey patch, remeber to remove it after upgrade python to 3.3")
   host, port = addr
   if (ca_certs is not None):
      cert_reqs = CERT_REQUIRED
   else:
      cert_reqs = CERT_NONE
   s = ssl.wrap_socket(socket.socket(socket.getaddrinfo(host, port)[0][0]),
                       ssl_version=ssl_version,
                       cert_reqs=cert_reqs,
                       ca_certs=ca_certs)
   s.connect(addr)
   dercert = s.getpeercert(True)
   s.close()
   return ssl.DER_cert_to_PEM_cert(dercert)

if sys.version_info<(3,3,0):
   ssl.get_server_certificate = FixedGetServerCertificate


def GetThumbprint(host, port):
   """Get the SSL thumbprint from a host/port."""
   hostPortSpec = (host, port)
   cert = ssl.get_server_certificate(hostPortSpec)
   return CertToThumbprint(cert)


def GetBase64Thumbprint(host, port):
   """Get the SSL base64-encoded thumbprint from a host/port."""
   hostPortSpec = (host, port)
   cert = ssl.get_server_certificate(hostPortSpec)
   return CertToBase64Thumbprint(cert)


def CertFileToThumbprint(fname):
   """Given a SSL cert filename, return a thumbprint string."""
   with open(fname) as f:
      return CertToThumbprint(f.read())


def CertFileToBase64Thumbprint(fname):
   """Given a SSL cert filename, return a base64-encoded thumbprint string."""
   with open(fname) as f:
      return CertToBase64Thumbprint(f.read())


def ParseHostUserPass(str):
   """Convert a "<user>:<pass>@<host>" string into a (host, user,
   password) tuple.

   User defaults to 'root', password defaults to '', and
   host defaults to 'localhost'.

   @throws ValueError if the given 'str' is badly formatted.
   """

   # Start with the defaults
   host="localhost"
   user='root'
   password=''

   if str:
      if str.find('@') != -1:
         # Check for a @, and get hostname
         (userpass, maybehost) = str.split('@', 1)
         if maybehost: host = maybehost

         if userpass:
            if userpass.find(':') != -1:
               # Get user or password (if supplied)
               (maybeuser, maybepass) = userpass.split(':',1)
               if maybeuser: user = maybeuser
               if maybepass: password = maybepass
            else:
               raise ValueError("Invalid <user>:<pass>.  Got '%s'.  Must contain ':'." % str)
      else:
         raise ValueError("Invalid <user>:<pass>@<host>.  Got '%s'.  Must contain '@'." % str)

   return (host, user, password)


def FindIPAddressFor(hostname):
   """Resolves the hostname to an IP address."""
   return socket.gethostbyname(hostname)


class CLI(object):
   """Wrapper for a CLI interface to a machine."""

   def __init__(self, cleanupTempDir=True):
      self.cleanupTempDir = cleanupTempDir
      self._cleanups = []

   def __enter__(self):
      return self

   def _RunCommand(self, command, *args, **kwargs):
      raise NotImplementedError()

   def RunCommand(self, command, print_output=False):
      """Run a command on the appliance.

      The command will be run as root and will assume
      a standard execution environment.
      """
      logger.info('Running command {0}'.format(command))
      (out, err, rc) = self._RunCommand(command, print_output)
      logger.debug('rc: {0}'.format(rc))
      if out and not print_output:
         logger.debug('out: \n{0}'.format(out.strip()))
      if err and not print_output:
         logger.debug('err: \n{0}'.format(err.strip()))
      return (out, err, rc)

   def _RunCommandInBackground(self, command):
      raise NotImplementedError()

   def RunCommandInBackground(self, command):
      """Run a command on the appliance in the background.

      Will not wait for command to finish and output will
      not be captured.
      """
      logger.info('Running command {0} in the background'.format(command))
      self._RunCommandInBackground(command)

   def _CopyFile(self, source_file, destination_file):
      raise NotImplementedError()

   def CopyFile(self, source_file, destination_file):
      """Copy a file from source to destination."""
      logger.debug('Copying file from {0} to {1}'.format(source_file, destination_file))
      self._CopyFile(source_file, destination_file)

   def _FileExists(self, file_path):
      raise NotImplementedError()

   def FileExists(self, file_path):
      """Check if a file exists."""
      logger.info('Checking if file {0} exists on the SSH server'.format(file_path))
      return self._FileExists(file_path)

   def GetTemporaryDirectory(self, destDir=None):
      """Request a temporary directory."""
      if not hasattr(self, '_tmpDir'):
         self._CreateTemporaryDirectory(destDir=destDir)
         if self.cleanupTempDir:
            self._cleanups += [lambda : self._CleanupTemporaryDirectory()]

      return self._tmpDir

   def _CreateTemporaryDirectory(self, destDir=None):
      if destDir is None: destDir = '/tmp'

      out, err, rc = self.RunCommand('mktemp -d {}/pyHbr.XXXXXX'.format(destDir))
      if rc != 0:
         raise RuntimeError('Could not create a temporary directory on '
                            'the appliance using the template {0}'.format(template))

      self._tmpDir = out.strip()

   def _CleanupTemporaryDirectory(self):
      if not hasattr(self, '_tmpDir'):
         return

      out, err, rc = self.RunCommand('rm -rf {0}'.format(self._tmpDir))
      if rc != 0:
         raise RuntimeError('Failed to remove the temporary directory')

   def __exit__(self, exc_type, exc_value, traceback):
      for cleanup in self._cleanups:
         cleanup()


class SSHCLI(CLI):
   """Wrapper for a deployed HMS virtual appliance that
   uses SSH for communication.
   """

   def __init__(self, host, username, password):
      CLI.__init__(self)
      self._host = host
      self._username = username
      self._password = password

      client = paramiko.SSHClient()
      client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      self._client = client

   def _Connect(self):
      """Connect to the host and also open a SFTP session."""
      logger.info('Connecting to {0}:{1}@{2}'.format(self._username,
                                                      self._password,
                                                      self._host))
      self._client.connect(self._host,
                           username=self._username,
                           password=self._password,
                           allow_agent=False,
                           look_for_keys=False)
      self._sftp = paramiko.SFTPClient.from_transport(
         self._client.get_transport())

   def _Reconnect(self):
      """Try to reconnect if the connection is not active anymore."""
      if (not self._client.get_transport() or
          not self._client.get_transport().is_active()):
         logger.warning('Connection timed out. Reconnecting')
         self._Connect()

   def __enter__(self):
      super(SSHCLI, self).__enter__()
      self._Connect()
      return self

   def _RunCommand(self, command, *args, **kwargs):
      self._Reconnect()

      channel = self._client.get_transport().open_session()

      with closing(channel):
         channel.exec_command(command)
         channel_stdout = ''
         while True:
            read_data = channel.recv(1000)
            if len(read_data) == 0:
               break
            channel_stdout += read_data.decode('utf-8')
         channel_stderr = ''
         while True:
            read_data = channel.recv_stderr(1000)
            if len(read_data) == 0:
               break
            channel_stderr += read_data.decode('utf-8')

         rc = channel.recv_exit_status()

         return (channel_stdout, channel_stderr, rc)

   def _RunCommandInBackground(self, command, *args, **kwargs):
      self._Reconnect()

      channel = self._client.get_transport().open_session()

      with closing(channel):
         channel.exec_command('nohup {} &'.format(command))

   def _CopyFile(self, source_file, destination_file):
      (_, _, rc) = self.RunCommand('cp {0} {1}'.format(source_file,
                                                       destination_file))
      if rc != 0:
         raise RuntimeError('Could not copy file {0} to {1}'.format(source_file,
                                                                    destination_file))

   def PutFile(self, source_file, destination_file):
      """Upload a file using SFTP to the SSH server."""
      self._Reconnect()
      logger.info('Uploading file {0} to destination {1}'.format(source_file,
                                                                 destination_file))

      self._sftp.put(source_file, destination_file)

   def GetFile(self, source_file, destination_file):
      """Download file using SFTP from the SSH server."""
      self._Reconnect()
      logger.info('Downloading file {0} to destination {1}'.format(source_file,
                                                                   destination_file))

      self._sftp.get(source_file, destination_file)

   def _FileExists(self, file_path):
      self._Reconnect()

      try:
         self._sftp.stat(file_path)
      except:
         return False

      return True

   def __exit__(self, exc_type, exc_value, traceback):
      super(SSHCLI, self).__exit__(exc_type, exc_value, traceback)
      self._sftp.close()
      self._client.close()


class ShellCLI(CLI):
   """Wrapper for running local commands."""

   def __init__(self):
      CLI.__init__(self)

   def _RunCommand(self, command, print_output=False):
      command = shlex.split(command)
      process = subprocess.Popen(command,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)

      def kill_process():
         try:
            process.send_signal(signal.SIGTERM)
            process.wait()
         except OSError:
            pass
      AtExit(kill_process)

      stdout = ''
      stderr = ''
      fds = [process.stdout, process.stderr]
      while True:
         ready = select.select(fds, [], [])
         for fd in ready[0]:
            buffer = fd.readline().decode('utf-8')
            out = sys.stdout if fd == process.stdout else sys.stderr

            if print_output:
               out.write(buffer)
               out.flush()
            if fd == process.stdout: stdout += buffer
            else: stderr += buffer

         if process.poll() != None:
            break

      return (stdout, stderr, process.returncode)

   def _CopyFile(self, source_file, destination_file):
      shutil.copy(source_file, destination_file)

   def _FileExists(self, file_path):
      return os.path.exists(file_path)


class ESXSSH(SSHCLI):
   def __init__(self, host, username, password, ds):
      SSHCLI.__init__(self, host, username, password)
      self._ds = ds

   def _CreateTemporaryDirectory(self, destDir=None):
      if destDir is not None:
         assert not os.path.isabs(destDir)
      else:
         destDir = ''

      vmfsPath = self._ds.VMFSPath(destDir)

      if self._ds.IsObjectBackend():
         # Lame check if datastore is vsan/vvol
         tmpDir = '{}/pyHbr.{}'.format(vmfsPath.rstrip('/'), str(uuid.uuid4()))
         logger.info('Creating temp dir {}'.format(tmpDir))
         cmd = '/usr/lib/vmware/osfs/bin/osfs-mkdir {}'.format(tmpDir)
      else:
         cmd = 'mktemp -d {}/pyHbr.XXXXXX'.format(vmfsPath.rstrip('/'))

      out, _, rc = self.RunCommand(cmd)
      if rc != 0:
         raise RuntimeError('Could not create a temporary directory on ESX')

      if self._ds.IsObjectBackend():
         self._tmpDir = tmpDir
      else:
         self._tmpDir = out.strip()

   def _CleanupTemporaryDirectory(self):
      if not hasattr(self, '_tmpDir'):
         return

      self._ds.CleanupDirectory(self._tmpDir)


def GetBuild(product=None, buildID=None, branch=None, kind='ob'):
   """Returns the URL to the AddOn OVF of the requested HMS build.

   If buildID was specified, the build information is fetched and
   the OVF URL is retrieved from it.
   If buildID is none, the build information for the latest saved
   build from the branch requested is fetched and the OVF URL is
   retrieved from it.

   @param buildID [in] the build identifier to get the OVF url for.
   @param branch  [in] branch to pickup build from.
   @param kind    [in] ob/sb (official/sandbox build)
   """
   if buildID:
      match = re.match('([os]b)-([0-9]+)', buildID)
      assert match is not None, 'Invalid build identifier: %s' % buildID

      kind = match.group(1)
      buildID = match.group(2)
      logger.debug('buildID is %s, kind is %s' % (buildID, kind))

   build = None
   api = buildapi.BuildApi(kind)
   if not buildID:
      query = api.Build.objects.all()
      query = query.filter(product=product, branch=branch, ondisk=1)

      build = query.order_by('-id')[0]
      if not build:
         logger.error('Cannot find a saved build for '\
                       'the product %s on branch %s' % (product, branch))
         return None
   else:
      build = api.Build.objects.get(pk=buildID)
      if not build.ondisk:
         logger.error('Build %s-%s is no longed '\
                       'saved on disk' % (kind, buildID))
         return None

   return build
