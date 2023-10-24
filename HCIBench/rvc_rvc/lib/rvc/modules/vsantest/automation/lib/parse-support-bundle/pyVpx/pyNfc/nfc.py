#!/bin/python

# Accommodate transition: Python 2 => 3
from __future__ import print_function

import sys
if sys.version_info[0] == 3:
   from queue import Queue
else:
   from Queue import Queue

import os, signal
import threading

from subprocess import Popen, PIPE

# Exception for NfcErrorCode
class NfcError(Exception):
   def __init__(self, errno):
      self.errno = errno

   def __str__(self):
      return repr(self.errno)

##
#
# A class to spawn threads to deal with IO on a process.
# Without this, it's possible for pipe read/writes to deadlock.
# This class decouples the IO from the consumer by always having
# a dedicated thread that can read/write to the pipe.
#
# XXX
# Ideally, we would use pexpect to control the process but that can be handled
# another time since pexpect isn't part of the standard set of python
# packages on test machines yet.
#
class NfcCmdPiper(threading.Thread):
   def __init__(self,
                pipe,
                reading,
                verbose,
                prefix):
      threading.Thread.__init__(self)
      self.pipe = pipe
      self.reading = reading
      self.setDaemon(True)
      self.requests = Queue(0)
      self.results = Queue(0)
      self.verbose = verbose
      self.prefix = prefix

   def run(self):
      if self.reading:
         while True:
            s = self.pipe.readline()
            if len(s) == 0:
               # A null readline means the pipe was closed at the far-end.
               self.results.put(s)
               break
            if self.verbose:
               print("%s RECV: %s" % (self.prefix, s), end='\n')
            self.results.put(s)
      else:
         while True:
            s = self.requests.get()
            if self.verbose:
               print("%s SEND: %s" % (self.prefix, s), end='\n')
            self.pipe.write(s)
            self.pipe.flush()
            self.requests.task_done()

   def recv(self):
      r = self.results.get()
      if len(r) == 0:
         # The process died.
         raise IOError("The nfcTest process died.")
      return r

   def send(self, s):
      self.requests.put(s)
      self.requests.join()

##
#  Represents a generic NfcTest instance where any NfcTest commands can
#  be invoked. The command output will be parsed and returned as a dictionary.
#  If the command returns any NFC error code, an exception will be raised.
#
class NfcCmdInst:
   def __init__(self,
                verbose,
                logLevel,
                nfcTestPath,
                prefix):
      try:
         self.proc = Popen([nfcTestPath, '-v', str(logLevel)],
                           stdin=PIPE, stdout=PIPE, stderr=sys.stderr,
                           bufsize=0, universal_newlines=True)
      except Exception as e:
         print("Failed to launch nfcTest: %s\n" % e)
         raise e

      self.stdin = NfcCmdPiper(pipe=self.proc.stdin,
                               reading=False,
                               verbose=verbose,
                               prefix=prefix)
      self.stdin.start()
      self.stdout = NfcCmdPiper(pipe=self.proc.stdout,
                                reading=True,
                                verbose=verbose,
                                prefix=prefix)
      self.stdout.start()


   def __del__(self):
      os.kill(self.proc.pid, signal.SIGTERM)

   def ParseCmdOutput(self, output):
      result = {}
      for line in output:
         pair = line.split('=')
         if len(pair) == 2:
            key = pair[0].strip()
            value = pair[1].strip()
            result[key] = value
      return result

   def GetResult(self):
      output = []
      while True:
         line = self.stdout.recv()
         result = line.split()

         # Skip blank lines
         if len(result) == 0:
            continue

         if result[0] == '[STATUS]':
            if result[1] == 'SUCCESS':
                return self.ParseCmdOutput(output)
            elif result[1] == 'FAILURE':
               errno = int(result[2].strip('()'))
               raise NfcError(errno)
         else:
            output.append(line)

   def SendCmd(self, *args):
      self.stdin.send(' '.join(args) + '\n')

   def RunCmd(self, *args):
      self.SendCmd(*args)
      return self.GetResult()


class NfcServer(NfcCmdInst):
   def __init__(self,
                verbose=False,
                logLevel=0,
                nfcTestPath='nfcTest'):
      NfcCmdInst.__init__(self,
                          verbose=verbose,
                          logLevel=logLevel,
                          nfcTestPath=nfcTestPath,
                          prefix="Server")

   def Run(self, port=55554):
      self.RunCmd('server', repr(port))

   def Start(self, port=55554):
      self.SendCmd('server', repr(port))

class NfcClient(NfcCmdInst):
   def __init__(self,
                verbose=False,
                logLevel=0,
                nfcTestPath='nfcTest'):
      NfcCmdInst.__init__(self,
                          verbose=verbose,
                          logLevel=logLevel,
                          nfcTestPath=nfcTestPath,
                          prefix="Client")

   def Connect(self, host='localhost', port=55554, user='root',
               passwd='', cnxType='direct'):
      self.RunCmd('SetUser', user)
      if passwd != '':
         self.RunCmd('SetPass', passwd)
      self.RunCmd('SetCnxType', cnxType)
      self.RunCmd('Connect', host, repr(port))

   def Disconnect(self):
      self.RunCmd('Disconnect')

   def SetMode(self, mode): # stream, fssrvr
      self.RunCmd('SetMode', mode)

   def SetFormat(self, format): # txt, raw, dsk
      self.RunCmd('SetFormat', format)

   def SetTransform(self, transform): # thin, thick, eagerzero
      self.RunCmd('SetTransform', transform)

   def SetOverwrite(self, overwrite):
      self.RunCmd('SetOverwrite', repr(overwrite))

   def SetKeepFilters(self, filters):
      self.RunCmd('SetKeepFilters', repr(filters))

   def SetOptimizeLazyZero(self, optimizeLazyZero):
      self.RunCmd('SetOptimizeLazyZero', repr(optimizeLazyZero))

   def SetPolicy(self, policy):
      self.RunCmd('SetPolicy', repr(policy))

   def SetSpifFilters(self, spifSpecList):
      self.RunCmd('SetSpifFilters', repr(spifSpecList))

   def SetDirectIO(self):
      self.RunCmd('SetDirectIO')

   def Reset(self):
      self.RunCmd('Reset')

   def SetSeSparse(self, sesparse):
      self.RunCmd('SetSeSparse', repr(sesparse))

   def SetGrainSize(self, size):
      self.RunCmd('SetGrainSize', str(size))

   def SetKeyServerID(self, keyServerId):
      self.RunCmd('SetKeyServerID', keyServerId)

   def SetKeyID(self, keyID):
      self.RunCmd('SetKeyID', keyID)

   def SetIntegrityProtection(self, integType):
      self.RunCmd('SetIntegrityProtection', repr(integType))

   def GetInfo(self, src, dst):
      return self.RunCmd('GetInfo', src, dst)

   def PutInfo(self, src, dst):
      return self.RunCmd('PutInfo', src, dst)

   def Get(self, src, dst):
      self.RunCmd('Get', src, dst)

   def Put(self, src, dst):
      self.RunCmd('Put', src, dst)

   def PutEx(self, src, dst, dstParent):
      self.RunCmd('PutEx', src, dst, dstParent)

   def Copy(self, src, dst):
      self.RunCmd('Copy', src, dst)

   def Clone(self, src, dst):
      self.RunCmd('Clone', src, dst)

   def CloneExt(self, src, dst, dstParent):
      self.RunCmd('CloneExt', src, dst, dstParent)

   def Rename(self, src, dst):
      self.RunCmd('Rename', src, dst)

   def Unlink(self, file):
      self.RunCmd('Unlink', file)

   def MkDir(self, dir):
      self.RunCmd('MkDir', dir)

   def Open(self, disk):
      self.RunCmd('Open', disk)

   def Close(self):
      self.RunCmd('Close')

   def DDBSet(self, key, value):
      self.RunCmd('DDBSet', key, value)

   def DDBRemove(self, key):
      self.RunCmd('DDBRemove', key)

   def DDBDump(self):
      return self.RunCmd('DDBDump')

   def ASMGet(self, disk):
      self.RunCmd('ASMGet', disk)

   def ASMGetRange(self,
                   startSector,
                   chunkSize,
                   numChunks,
                   linkOffset,
                   numLinks):
      return self.RunCmd('ASMGetRange', startSector, chunkSize, numChunks,
                        linkOffset, numLinks)

   def GetUnmapInfo(self):
      return self.RunCmd('UnmapInfo')

   def SetFssrvrOptions(self,
                        ioType='multiIO',
                        numIOsPerReq='8',
                        IOSize='262144',
                        compression='uncompressed'):
      self.RunCmd('FsOptions', ioType, numIOsPerReq, IOSize, compression)

   def FsIO(self,
            rw='read',
            offset='0',
            length='10485760',
            compressible=False,
            precompress=False,
            compression="none"):
      if compressible:
         return self.RunCmd('FsIO', rw, offset, length, "compressible")
      else:
         return self.RunCmd('FsIO', rw, offset, length)

   def FsIOEx(self,
              rw='read',
              offset='0',
              length='10485760',
              precompress=False,
              compressible=False,
              compression="none",
              sync=False):
      if compressible:
         comp="compressible"
      else:
         comp="uncompressible"

      if precompress:
         precomp="precompress"
      else:
         precomp="normal"

      if sync:
         dosync="sync"
      else:
         dosync="nosync"

      return self.RunCmd('FsIOEx', rw, offset, length, dosync,
                         comp, precomp, compression)

   def Checksum(self, checksumType, extents):
      # This takes a list of tuples of offset + len.
      # So we need to "flatten" it here for RunCmd
      args=[]
      for e in extents:
        args.append(str(e[0]))
        args.append(str(e[1]))

      return self.RunCmd("Checksum", checksumType, *args)

   def Sync(self):
      return self.RunCmd("Sync")
