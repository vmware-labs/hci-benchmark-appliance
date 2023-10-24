import logging

from cwrapper import *
from servercnx import *
from util import *

#
# These classes provide an OOP interface to the functions
# present in cwrapper. They are not a complete implementation
# of the NFC API but that's because they are a work in progress
# (they are augmented as needed).
#

def GetNfcError(nfcErrorCode, errEx=None):
   res = '(%d, %d) ' % (nfcErrorCode, errEx)
   if errEx is not None and errEx != NFC_EX_SUCCESS:
      if Nfc_ErrExType(errEx) == NFC_ERROR_EX_TYPE_OBJLIB:
         res += str(Nfc_NfcErrExToObjLibErr(errEx))
      else:
         res += str(Nfc_ErrExToString(errEx))
   else:
      res += str(Nfc_ErrCodeToString(nfcErrorCode))

   return res

class _NfcResource(object):
   """Base class for NFC resources (file/disk)."""
   def __init__(self, connection, fileInfo=None, **kwargs):
      self._connection = connection
      self._fileInfo = fileInfo
      self._callbacks = {}
      self._callbackNo = 0

   def _AsyncCallback(self, actualCallback, callbackData, buf):
      """Wrap around an async callback. We need to do this to make
      sure that all the data necessary to this callback won't fall
      out of scope and get garbage collected.

      We use a dictionary to keep track of all the pending callbacks.
      """
      id = self._callbackNo
      self._callbackNo += 1

      def _callback(nfcErrorCode, cbData, extraData):
         actualCallback(nfcErrorCode, cbData, extraData)
         del self._callbacks[id]

      callback = NfcAioCB(_callback)
      self._callbacks[id] = (callback, callbackData, buf)
      return callback

   def Write(self,
             offset,
             length,
             buffer,
             sync=False,
             precompressed=None,
             compressType=NFC_COMPRESS_NONE,
             asyncCallback=None,
             callbackData=None):
      """Write a chunk of data to this resource."""
      if self._connection.IsAsync():
         if asyncCallback != None:
            callback = self._AsyncCallback(asyncCallback, callbackData, buffer)
         else:
            callback = NfcAioCB()

         parms = None

         flags = NFC_AIO_IO_NONE
         if sync:
            flags = flags | NFC_AIO_IO_SYNC
         if precompressed:
            assert compressType != NFC_COMPRESS_NONE, \
                  'Can\'t send precompressed data with no compression type'
            parms = NfcAioIoParms()
            flags = flags | NFC_AIO_IO_PRECOMPRESSED
            parms.unnamed_1.preCompWrite.uncompressedLen = precompressed
            parms = byref(parms)

         errEx = NfcErrorCodeEx()
         result = NfcAio_AIO(self._fileInfo.fileHandle,
                             flags,
                             compressType,
                             offset,
                             length,
                             buffer,
                             parms,
                             byref(errEx),
                             callback,
                             None,
                             NfcAioCB(),
                             None);
         if result != NFC_SUCCESS and result != NFC_ASYNC:
            raise RuntimeError('NfcAio_AIO error: {0}'.format(
               GetNfcError(result, errEx.value)))
      else:
         diskLibErr = uint32()
         result = NfcFssrvr_IOEx(self._connection.GetSession(),
                                 NFC_IO_EX_WRITE,
                                 NFC_IO_EX_FLAGS_NONE,
                                 NFC_COMPRESS_NONE,
                                 offset,
                                 length,
                                 buffer,
                                 None,
                                 byref(diskLibErr))
         if result != NFC_SUCCESS:
            raise RuntimeError('NfcFssrvr_IOEx error: {0}'.format(
               GetNfcError(result, Nfc_DiskLibErrToNfcErrEx(diskLibErr.value))))

   def Read(self,
            offset,
            length,
            buffer,
            compressType=NFC_COMPRESS_NONE,
            asyncCallback=None,
            callbackData=None):
      """Read a chunk of data to this resource."""
      if self._connection.IsAsync():
         if asyncCallback != None:
            callback = self._AsyncCallback(asyncCallback, callbackData, buffer)
         else:
            callback = NfcAioCB()

         errEx = NfcErrorCodeEx()
         result = NfcAio_AIO(self._fileInfo.fileHandle,
                             NFC_AIO_IO_READ,
                             compressType,
                             offset,
                             length,
                             buffer,
                             None,
                             byref(errEx),
                             callback,
                             None,
                             NfcAioCB(),
                             None);
         if result != NFC_SUCCESS and result != NFC_ASYNC:
            raise RuntimeError('NfcAio_AIO error: {0}'.format(
               GetNfcError(result, errEx.value)))
      else:
         assert false, "Unsupported operation (yet)"

   def Sync(self):
      errEx = NfcErrorCodeEx()
      result = NfcAio_Sync(self._fileInfo.fileHandle,
                           byref(errEx),
                           NfcAioCB(),
                           None)
      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_Sync error: {0}'.format(
            GetNfcError(result, errEx.value)))

   def Wait(self):
      errEx = NfcErrorCodeEx()
      result = NfcAio_Wait(self._fileInfo.fileHandle,
                           byref(errEx))
      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_Wait error: {0}'.format(
            GetNfcError(result, errEx.value)))

   def Close(self):
      """Close this resource."""
      self._connection.RemoveResource(self)
      if self._connection.IsAsync():
         errEx = NfcErrorCodeEx()
         result = NfcAio_CloseFile(self._fileInfo.fileHandle,
                                   byref(errEx),
                                   NfcAioCB(),
                                   None)
         if result != NFC_SUCCESS:
            raise RuntimeError('NfcAio_CloseFile error: {0}'.format(
               GetNfcError(result, errEx.value)))

   def DDBGet(self, key):
      errEx = NfcErrorCodeEx()
      cValue = c_char_p(None)

      result = NfcAio_DDBGet(self._fileInfo.fileHandle,
                             key,
                             byref(cValue),
                             byref(errEx),
                             NfcAioCB(),
                             None)
      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_DDBGet error: {0}'.format(
            GetNfcError(result, errEx.value)))

      value = cValue.value
      Nfc_Free(byref(cValue))

      return value

class _NfcFile(_NfcResource):
   """Class that represents an NFC opened file."""
   def __init__(self, connection, fileInfo=None, fileSize=None):
      _NfcResource.__init__(self, connection, fileInfo)
      self._fileSize = fileSize

   def GetFileSize(self):
      if self._connection.IsAsync():
         return self._fileInfo.size
      else:
         return self._fileSize

class _NfcDisk(_NfcResource):
   """Class that represents an NFC opened disk."""
   def DDBEnum(self):
      errEx = NfcErrorCodeEx()
      cKeys = NfcDDBKeys()

      result = NfcAio_DDBEnum(self._fileInfo.fileHandle,
                              byref(errEx),
                              byref(cKeys),
                              NfcAioCB(),
                              None)
      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_DDBEnum error: {0}'.format(
            GetNfcError(result, errEx.value)))

      keys = []
      for i in range(cKeys.length):
         # String uses the raw data. We need to copy that into a str because
         # once we call NfcFssrvr_FreeDDBKeys, that data will dissapear
         keys += [str(String(cKeys.names[i]))]

      NfcFssrvr_FreeDDBKeys(byref(cKeys))

      return keys

   def GetAllocatedSectorChunks(self, offset, chunkSize, numChunks):
      bv = BitVector_Alloc(numChunks)

      errEx = NfcErrorCodeEx()
      info = NfcAioASMRInfo()
      info.bv = bv
      info.numChunks = numChunks

      result = NfcAio_GetAllocatedSectorChunksInRange(
         self._fileInfo.fileHandle,
         0, # linkOffsetFromBottom
         0, # numLinks
         chunkSize,
         offset,
         byref(info),
         byref(errEx),
         NfcAioCB(),
         None)
      if result != NFC_SUCCESS:
         BitVector_Free(bv)
         raise RuntimeError('NfcAio_GetAllocatedSectorChunksInRange error: {0}'.format(
            GetNfcError(result, errEx.value)))

      allocInfo = []
      start = c_uint(0)
      while BitVector_NextBit(bv, start, True, byref(start)):
         allocInfo += [start.value]
         start = c_uint(start.value + 1)

      BitVector_Free(bv)
      return allocInfo

   def Checksum(self, offset, extentSize, numExtents, bkgThread=True,
                checksumType=NFC_AIO_CHECKSUM_FLAG_TYPE_MD5):
      extents = (NfcAioExtentInfo * numExtents)()
      for i in range(numExtents):
         extents[i].offset = extentSize * i + offset
         extents[i].length = extentSize

      flags = checksumType
      if bkgThread:
         flags = flags | NFC_AIO_CHECKSUM_FLAG_BKG_PROCESS

      cksmOut = (numExtents * NfcAioChecksumMD5)()

      errEx = NfcErrorCodeEx()
      result = NfcAio_GetExtentChecksums(self._fileInfo.fileHandle,
                                         numExtents,
                                         extents,
                                         flags,
                                         cksmOut,
                                         byref(errEx),
                                         NfcAioCB(),
                                         None,
                                         NfcAioProgressCB(),
                                         None)
      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_GetExtentChecksums error: {0}'.format(
            GetNfcError(result, errEx.value)))

      return cksmOut

   def GetFileSize(self):
      return self._fileInfo.geo.size

class _NfcUpit(_NfcResource):
   """Class that represents a UPIT archived opened through NFC."""
   def GetFileSize(self):
      return self._fileInfo.geo.size

   def Snapshot(self, snapshotUuid=None, tags={}, allocType=NFC_ALLOC_ON_DEMAND):
      tagsBuf = DynBuf()
      DynBuf_Init(byref(tagsBuf))

      for k, v in tags.iteritems():
         DynBuf_Append(byref(tagsBuf), k, len(k) + 1)
         DynBuf_Append(byref(tagsBuf), v, len(v) + 1)

      cObjectID = String(None)
      errEx = NfcErrorCodeEx()
      result = NfcAio_CreateSnapshot(self._fileInfo.fileHandle,
                                     allocType,
                                     snapshotUuid,
                                     byref(cObjectID),
                                     byref(tagsBuf),
                                     byref(errEx),
                                     NfcAioCB(),
                                     None,
                                     NfcAioProgressCB(),
                                     None)
      DynBuf_Destroy(byref(tagsBuf))
      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_CreateSnapshot error: {0}'.format(
            GetNfcError(result, errEx.value)))

      objectID = str(cObjectID)
      Nfc_Free(byref(cObjectID))

      return objectID

   def Checksum(self, offset, extentSize, numExtents, bkgThread=True,
                checksumType=NFC_AIO_CHECKSUM_FLAG_TYPE_MD5):
      extents = (NfcAioExtentInfo * numExtents)()
      for i in range(numExtents):
         extents[i].offset = extentSize * i + offset
         extents[i].length = extentSize

      flags = NFC_AIO_CHECKSUM_FLAG_TYPE_MD5
      if bkgThread:
         flags = flags | NFC_AIO_CHECKSUM_FLAG_BKG_PROCESS

      cksmOut = (numExtents * NfcAioChecksumMD5)()

      errEx = NfcErrorCodeEx()
      result = NfcAio_GetExtentChecksums(self._fileInfo.fileHandle,
                                         numExtents,
                                         extents,
                                         flags,
                                         cksmOut,
                                         byref(errEx),
                                         NfcAioCB(),
                                         None,
                                         NfcAioProgressCB(),
                                         None)
      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_GetExtentChecksums error: {0}'.format(
            GetNfcError(result, errEx.value)))

      return cksmOut

class NfcConnection(object):
   """Class that represents an NFC connection."""
   def __init__(self, host, username, password, isAsync=True, logLevel=NFC_LOGLEVEL_NONE):
      self._host = host
      self._username = username
      self._password = password
      self._isAsync = isAsync
      self._resOpen = []
      self._logLevel = logLevel

   def IsAsync(self):
      return self._isAsync

   def GetSession(self):
      return self._nfcConnection.nfcSession

   def RemoveResource(self, resource):
      self._resOpen.remove(resource)

   def Connect(self,
               aioBufSize=NFC_AIO_DEFAULT_BUF_SIZE,
               aioBufCount=NFC_AIO_DEFAULT_BUF_COUNT):
      """Ask for a ticket from the host and connect to it."""
      ticket = GetNfcSystemManagementTicket(self._host,
                                            self._username,
                                            self._password)
      connectInfo = NfcWrapperConnectInfo(String(self._host),
                                          String(ticket.sessionId),
                                          String(ticket.sslThumbprint),
                                          ticket.port,
                                          NFC_HOST_AGENT)

      self._nfcConnection = NfcWrapperConnection()
      result = NfcWrapper_Connect(byref(connectInfo), byref(self._nfcConnection))
      if result != NFC_SUCCESS:
         raise RuntimeError('NfcWrapper_Connect returned {0}'.format(result))

      if self.IsAsync():
         aioParams = NfcAioSessionParams(NFC_AIO_SESSION_SET_SRV_LOGLEVEL,
                                         aioBufSize, aioBufCount,
                                         self._logLevel)
         result = NfcAio_OpenSession(self._nfcConnection.nfcSession, byref(aioParams))
         if result != NFC_SUCCESS:
            NfcWrapper_Disconnect(byref(self._nfcConnection))
            raise RuntimeError('NfcAio_OpenSession error: {0}'.format(
               GetNfcError(result)))

   def Disconnect(self):
      """Disconnect from the host."""
      assert len(self._resOpen) == 0, 'Resources still open'
      if self.IsAsync():
         NfcAio_CloseSession(self._nfcConnection.nfcSession)
      NfcWrapper_Disconnect(byref(self._nfcConnection))

   def OpenFile(self, path, flags, action):
      """Open a file."""
      openFlags = NfcFileRawOpenFlags(flags, action)
      if self.IsAsync():
         openFile = NfcAioOpenFileInfo()
         errEx = NfcErrorCodeEx()

         result = NfcAio_OpenFile(self._nfcConnection.nfcSession,
                                  path,
                                  openFlags,
                                  byref(openFile),
                                  byref(errEx),
                                  NfcAioCB(),
                                  None)
         if result != NFC_SUCCESS:
            raise RuntimeError('NfcAio_OpenFile error: {0}'.format(
               GetNfcError(result, errEx.value)))

         openFile = _NfcFile(self, fileInfo=openFile)
      else:
         assert len(self._resOpen) == 0, "Can only open one resource "\
                                         "in sync mode"
         fileSize = uint64()
         fileIOErr = uint64()

         result = NfcFssrvr_FileOpen(self._nfcConnection.nfcSession,
                                     path,
                                     openFlags,
                                     byref(fileSize),
                                     byref(fileIOErr))
         if result != NFC_SUCCESS:
            raise RuntimeError('NfcFssrvr_FileOpen error: "{0}"'.format(
               GetNfcError(result, fileIOErr)))

         openFile = _NfcFile(self, fileSize=fileSize)

      self._resOpen += [openFile]
      return openFile

   def CreateDisk(self, path, capacity,
                  createType=NFC_DISK_CREATETYPE_VMFS,
                  allocType=NFC_ALLOC_ON_DEMAND,
                  adapterType=NFC_ADAPTER_LSILOGIC):
      errEx = NfcErrorCodeEx()
      result = NfcAio_CreateDisk(self._nfcConnection.nfcSession,
                                 path,
                                 createType,
                                 allocType,
                                 adapterType,
                                 capacity,
                                 byref(errEx),
                                 NfcAioCB(),
                                 None,
                                 NfcAioProgressCB(),
                                 None)
      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_CreateDisk error: {0}'.format(
            GetNfcError(result, errEx.value)))

   def OpenDisk(self, path, flags):
      """Open a disk."""
      assert self._isAsync, 'We only support async NFC connections for disks '\
                            '(for now)'

      openDisk = NfcAioOpenDiskInfo()
      errEx = NfcErrorCodeEx()

      result = NfcAio_OpenDisk(self._nfcConnection.nfcSession,
                               path,
                               flags,
                               byref(openDisk),
                               byref(errEx),
                               NfcAioCB(),
                               None)

      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_OpenDisk error: {0}'.format(
            GetNfcError(result, errEx.value)))

      disk = _NfcDisk(self, fileInfo=openDisk)
      self._resOpen += [disk]
      return disk

   def CreateUpit(self, path, capacity,
                  allocType=NFC_ALLOC_ON_DEMAND):
      cObjectID = String(None)
      errEx = NfcErrorCodeEx()
      result = NfcAio_CreateUpit(self._nfcConnection.nfcSession,
                                 path,
                                 allocType,
                                 capacity,
                                 byref(cObjectID),
                                 byref(errEx),
                                 NfcAioCB(),
                                 None,
                                 NfcAioProgressCB(),
                                 None)
      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_CreateUpit error: {0}'.format(
            GetNfcError(result, errEx.value)))

      objectID = str(cObjectID)
      Nfc_Free(byref(cObjectID))

      return objectID

   def EnableUpit(self, diskPath):
      cObjectID = String(None)
      errEx = NfcErrorCodeEx()
      result = NfcAio_EnableUpit(self._nfcConnection.nfcSession,
                                 diskPath,
                                 byref(cObjectID),
                                 byref(errEx),
                                 NfcAioCB(),
                                 None)
      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_EnableUpit error: {0}'.format(
            GetNfcError(result, errEx.value)))

      objectID = str(cObjectID)
      Nfc_Free(byref(cObjectID))

      return objectID

   def OpenUpit(self, uri, basepath, access, action=OBJ_OPEN):
      """Open a disk."""
      assert self._isAsync, 'UPIT is only supported on async NFC connections'

      openArchive = NfcAioOpenObjInfo()
      objFlags = NfcFileObjOpenFlags(access, action)
      errEx = NfcErrorCodeEx()

      result = NfcAio_OpenUpit(self._nfcConnection.nfcSession,
                               uri,
                               basepath,
                               objFlags,
                               byref(openArchive),
                               byref(errEx),
                               NfcAioCB(),
                               None)

      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_OpenUpit error: {0}'.format(
            GetNfcError(result, errEx.value)))

      archive = _NfcUpit(self, fileInfo=openArchive)
      self._resOpen += [archive]
      return archive

   def DeleteUpit(self, objectID, basePath,
                  deleteFlags=NFC_DELETE_SNAPSHOT_UNMANAGED):
      errEx = NfcErrorCodeEx()
      result = NfcAio_DeleteSnapshot(self._nfcConnection.nfcSession,
                                     objectID,
                                     basePath,
                                     deleteFlags,
                                     byref(errEx),
                                     NfcAioCB(),
                                     None,
                                     NfcAioProgressCB(),
                                     None)
      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_DeleteSnapshot error: {0}'.format(
            GetNfcError(result, errEx.value)))

   def GetFileInfo(self, fileType, filePath):
      assert fileType in [ NFC_DISK, NFC_RAW, NFC_TEXT, NFC_OBJDESC, NFC_OBJECT]
      errEx = NfcErrorCodeEx()
      fileInfo = NfcFileInfo()
      fileInfo.fileType = fileType
      fileInfo.srcPath = String(create_string_buffer(filePath))
      fileInfo.srcPathLen = len(filePath) + 1

      result = NfcAio_GetFileInfo(self._nfcConnection.nfcSession,
                                  byref(fileInfo),
                                  byref(errEx),
                                  NfcAioCB(),
                                  None)
      if result != NFC_SUCCESS:
         raise RuntimeError('NfcAio_GetFileInfo error: {0}'.format(
            GetNfcError(result, errEx.value)))

      if fileType == NFC_DISK:
         return fileInfo.u.diskFileInfo
      elif fileType == NFC_RAW:
         return fileInfo.u.rawFileInfo
      elif fileType == NFC_TEXT:
         return fileInfo.u.txtFileInfo
      elif fileType == NFC_OBJDESC:
         return fileInfo.u.objDescFileInfo
      elif fileType == NFC_OBJECT:
         return fileInfo.u.objFileInfo

   def __enter__(self):
      self.Connect()
      return self

   def __exit__(self, exc_type, exc_val, exc_tb):
      if exc_type is not None:
         logging.error('Exception raised', exc_info=(exc_type, exc_val, exc_tb))
      self.Disconnect()


