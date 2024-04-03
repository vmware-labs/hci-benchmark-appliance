import logging
import sys
import time

from pyNfcWrapper.cwrapper import *
from pyNfcWrapper.nfc import NfcConnection
from pyNfcWrapper.util import CreateLogFunc
from pyHbr.hostd import Hostd
from pyVmomi import Vim

logging.basicConfig(level=logging.DEBUG)

DISK_NAME = 'disk.vmdk'
TWO_GB = 2 * 1024 * 1024 * 1024

def main(args):
   logFunc = CreateLogFunc(logging)
   NfcWrapper_Init(NFC_LOGLEVEL_NONE, logFunc)

   hostd = Hostd(args[0], args[1], args[2])
   remoteStorage = hostd.RemoteStorage(args[3])

   try:
      remoteStorage.DeleteDisk(DISK_NAME)
   except Vim.Fault.FileNotFound:
      pass

   with NfcConnection(args[0], args[1], args[2]) as nfcConn:
      fullName = '/vmfs/volumes/{0}/{1}'.format(args[3], DISK_NAME)

      nfcConn.CreateDisk(fullName, TWO_GB)

      print 'Open the disk'

      disk = nfcConn.OpenDisk(
            fullName,
            OPEN_PARENT | OPEN_LOCK | OPEN_BUFFERED)

      print disk.GetFileSize()
      if disk.GetFileSize() != TWO_GB:
         print 'Size mismatch'

      buffer = String(create_string_buffer('1' * (1024 * 1024 * 10 - 1)))

      print 'First write'
      disk.Write(0, 1024, buffer)

      print 'Second write'
      disk.Write(2 * 1024 * 1024, 1024, buffer)

      print 'Third write'
      disk.Write(2048, 1024 * 1024, buffer)

      print 'Fourth write'
      disk.Write(23 * 1024 * 1024, 1024, buffer)

      # these two calls are needed because syncing while doing IO
      # is currently bugged so we must wait for the IO to finish
      # and then issue a sync
      disk.Wait()
      disk.Sync()

      print disk.GetAllocatedSectorChunks(0, 1024 * 1024, 256)

      disk.Close()

   NfcWrapper_Exit()

if __name__ == '__main__':
   if len(sys.argv) < 5:
      print 'Usage: {0} hostIp hostUser hostPass hostDatastore'
      sys.exit(1)
   main(sys.argv[1:])
