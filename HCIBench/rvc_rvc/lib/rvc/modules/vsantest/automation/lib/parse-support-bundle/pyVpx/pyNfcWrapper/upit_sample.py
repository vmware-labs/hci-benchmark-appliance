import logging
import sys
import time
import uuid

from pyNfcWrapper.cwrapper import *
from pyNfcWrapper.nfc import NfcConnection
from pyNfcWrapper.util import CreateLogFunc
from pyHbr.hostd import Hostd
from pyVmomi import Vim

logging.basicConfig(level=logging.DEBUG)

BUFFER_SIZE = 65536
ONE_GB = 1024 * 1024 * 1024
UPIT_ARCHIVE_NAME = 'upit.vmdk'

def main(args):
   logFunc = CreateLogFunc(logging)
   NfcWrapper_Init(NFC_LOGLEVEL_INFO, logFunc)

   hostd = Hostd(args[0], args[1], args[2])
   remoteStorage = hostd.RemoteStorage(args[3])
   try:
      remoteStorage.DeleteUPITByPath(UPIT_ARCHIVE_NAME)
   except Vim.Fault.FileNotFound:
      pass

   with NfcConnection(args[0], args[1], args[2], logLevel=NFC_LOGLEVEL_INFO) as nfcConn:
      fullName = '/vmfs/volumes/{0}/{1}'.format(args[3], UPIT_ARCHIVE_NAME)
      nfcConn.CreateDisk(fullName, ONE_GB)
      runningPoint = nfcConn.EnableUpit(fullName)

      print 'Running point ID is', runningPoint

      upitArchive = nfcConn.OpenUpit(
            runningPoint,
            '/vmfs/volumes/{0}'.format(args[3]),
            OBJ_OPEN_ACCESS_READ | OBJ_OPEN_ACCESS_WRITE)

      print "UPIT archive size is", upitArchive.GetFileSize()

      buffer = '1' * (BUFFER_SIZE - 1)
      upitArchive.Write(0, BUFFER_SIZE, buffer, sync=True)

      outBuffer = create_string_buffer(BUFFER_SIZE)
      upitArchive.Read(0, BUFFER_SIZE, outBuffer)

      print 'Running point read'
      print len(outBuffer), outBuffer[:BUFFER_SIZE]

      snapUuid = uuid.uuid4()
      objectID = upitArchive.Snapshot(str(snapUuid))
      print 'UUID is', snapUuid, 'Snapshot ID is', objectID

      snapUuid = uuid.uuid4()
      print 'UUID is', snapUuid
      print 'Snapshot ID is', upitArchive.Snapshot(str(snapUuid),
                                                   tags={
                                                      'a': 'b',
                                                      'c': 'd'
                                                   })

      buffer = '2' * (BUFFER_SIZE - 1)
      upitArchive.Write(0, BUFFER_SIZE, buffer)

      print 'Running point read'
      upitArchive.Read(0, BUFFER_SIZE, outBuffer)
      print len(outBuffer), outBuffer[:BUFFER_SIZE]

      print 'Checksumming 1 extent with size {0} from offset 0'.format(BUFFER_SIZE)
      upitArchive.Checksum(0, BUFFER_SIZE, 1, bkgThread=False)

      upitArchive.Close()

      upitSnapshot = nfcConn.OpenUpit(
            objectID,
            '/vmfs/volumes/{0}'.format(args[3]),
            OBJ_OPEN_ACCESS_READ)

      upitSnapshot.Read(0, BUFFER_SIZE, outBuffer)

      print 'Snapshot read'
      print len(outBuffer), outBuffer[:BUFFER_SIZE]

      upitSnapshot.Close()

   NfcWrapper_Exit()

if __name__ == '__main__':
   if len(sys.argv) < 5:
      print 'Usage: {0} hostIp hostUser hostPass hostDatastore'
      sys.exit(1)
   main(sys.argv[1:])
