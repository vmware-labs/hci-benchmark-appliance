import logging
import sys

from pyNfcWrapper.cwrapper import *
from pyNfcWrapper.nfc import NfcConnection
from pyNfcWrapper.util import CreateLogFunc
logging.basicConfig(level=logging.DEBUG)

BUFFER_SIZE = 65536
BUFFER_COUNT = 1024 # number of buffers to write
FILE_NAME = 'test.bin'

def create_pattern_buffer(offset, length):
   """Create a deterministic buffer based on the offset
   and length.
   """
   pattern = chr((offset / length) % 256)
   return pattern * length


def main(args):
   logFunc = CreateLogFunc(logging)
   NfcWrapper_Init(NFC_LOGLEVEL_NONE, logFunc)

   with NfcConnection(args[0], args[1], args[2]) as nfcConn:
      nfcFile = nfcConn.OpenFile('/vmfs/volumes/{0}/{1}'.format(args[3], FILE_NAME),
                                 FILEIO_OPEN_ACCESS_READ | FILEIO_OPEN_ACCESS_WRITE |
                                 FILEIO_OPEN_SYNC | FILEIO_OPEN_LOCK_BEST,
                                 FILEIO_OPEN_CREATE_EMPTY)
      offset = 0

      if len(args) > 4 and args[4] == 'sync':
         for i in range(BUFFER_COUNT):
            buf = create_pattern_buffer(offset, BUFFER_SIZE)
            nfcFile.Write(offset, len(buf), buf)
            offset += BUFFER_SIZE
      else:
         from threading import Semaphore
         # we use this semaphore to make sure that we don't have too
         # many async requests in flight so that we don't run out
         # of memory
         sema = Semaphore(128)

         def CreateWriteCallback(length):
            def _callback(nfcErrorCode, callbackData, extraData):
               sema.release()
            return _callback

         for i in range(BUFFER_COUNT):
            buf = create_pattern_buffer(offset, BUFFER_SIZE)

            sema.acquire()
            nfcFile.Write(offset, len(buf), buf, asyncCallback=CreateWriteCallback(len(buf)))

            offset += BUFFER_SIZE

         # we will only be able to acquire the semaphore 128 times if there
         # are no more writes in-flight
         for i in range(128):
            sema.acquire()

      nfcFile.Close()

   NfcWrapper_Exit()

if __name__ == '__main__':
   if len(sys.argv) < 5:
      print 'Usage: {0} hostIp hostUser hostPass hostDatastore [sync]'
      sys.exit(1)
   main(sys.argv[1:])
