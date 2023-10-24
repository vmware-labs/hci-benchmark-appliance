## @file nfclib.py --
## @brief A shallow implementation of nfc client functionality to verify nfcsvc
"""
Shallow implementation of nfc client functionality to verify nfcsvc

Detailed description (for [e]pydoc goes here).
"""

__author__ = "VMware, Inc"

import logging
from hashlib import sha1
from os import fstat, environ
from socket import SHUT_RDWR, create_connection
from struct import pack, unpack, unpack_from
from base64 import b64encode
from six.moves import range

_hasSSL = False
try:
    import ssl
    _hasSSL = True
except ImportError:
    pass
_systemRandom = None


def strToBytes(s):
    return s.encode('utf-8') if isinstance(s, str) else s


def PrintBufferDump(title, buf):
    """
    Print buffer content with specified title.

    @type  title: str or unicode
    @param title: Title of the buffer.
    @type  buf:   str
    @param buf:   Buffer to be printed.
    """
    blksz = 16
    sbuf = ["\n"]
    nbuf = []
    for ch in buf:
        # sbuf
        if 32 <= ord(ch) <= 126:
            sbuf.append(ch)
        else:
            sbuf.append('.')
        # nbuf
        nbuf.append("%02x " % ord(ch))
        if len(nbuf) == blksz:
            sbuf.append('  ')
            sbuf += nbuf
            sbuf.append('\n')
            nbuf = []
    if nbuf:
        sbuf.append(' ' * (blksz - len(nbuf) + 2))
        sbuf += nbuf
        sbuf.append('\n')
    sdata = ''.join(sbuf)
    logging.debug("=== %s (%d) ======", title, len(buf))
    logging.debug("%s", sdata)
    logging.debug("=== END ======")


def _ReceiveBytes(conn, length):
    """
    Receive length bytes from conn.

    @type  conn:   socket
    @param conn:   Socket from which to receive data.
    @type  length: int
    @param length: How many bytes to receive.
    @rtype:        str
    @return:       Buffer with received data.
    """
    buf = []
    while length > 0:
        dta = conn.recv(length)
        lenDta = len(dta)
        if not lenDta:
            raise EOFError()
        # If this is first element, and we got all data, then simply return them.
        # This path should be taken for majority of calls.
        #
        # Although python avoids making copy of string in ''.join([dta]), it is
        # still 3 times faster (regardless of the length of string) to return
        # string rather than going through appending element to the array, and
        # then doing join().
        if not buf and lenDta >= length:
            return dta
        buf.append(dta)
        length -= lenDta
    return ''.join(buf)


def GetRandomData():
    global _systemRandom

    if not _systemRandom:
        import random

        _systemRandom = random.SystemRandom()
    data = pack('<LLLL', _systemRandom.uniform(0, 1 << 32),
                _systemRandom.uniform(0, 1 << 32),
                _systemRandom.uniform(0, 1 << 32),
                _systemRandom.uniform(0, 1 << 32))
    return b64encode(data)


##
## @brief A buffer object that understands authd reponse messages.
##
class AuthdMsg:
    """ A buffer object that understands authd reponse messages. """
    def __init__(self, buf):
        """
        Initialize authd message with specified content.

        @type  buf: str
        @param buf: Message content.
        """
        self._buf = buf

    def DumpBuffer(self):
        """ Dump authd message. """
        PrintBufferDump("AuthdMsg", self._buf)

    # Upon connection to authd, it issues the following
    # "220 VMware Authentication Daemon Version 1.10: opts-go-here
    def RequestOk(self):
        """
        Check whether request completed successfully.

        @rtype:  bool
        @return: True if authd message is success, False otherwise.
        """
        return self._ReturnResponseCode() == '200'

    def GreetingOk(self):
        """
        Check whether buffer holds greeting.

        @rtype:  bool
        @return: True if authd message is a greeting, False otherwise.
        """
        return self._ReturnResponseCode() == '220'

    def _ReturnResponseCode(self):
        """
        Retrieve request completion code.

        @rtype:  str
        @return: Three letter completion code.
        """
        return self._buf[:3]

    def GetGreeting(self):
        """
        Retrieve request text.

        @rtype:  str
        @return: Authd message text.
        """
        return self._buf

    def SSLRequired(self):
        """
        Check whether SSL requirement is listed in the greeting.

        @rtype:  bool
        @return: True if SSL must be used, False otherwise.
        """
        return self._buf.find('SSL Required') >= 0


##
## @brief NFC file
##
class NfcFile:
    """ NFC file """

    modes = dict(
        READ_ONLY='rb',
        WRITE_ONLY='wb',
    )

    def __init__(self, fileId, mode):
        """
        Create NfcFile instance.

        @type  fileId: str, or file descriptor
        @param fileId: Local file name.
        @type  mode:   str
        @param mode:   open mode from NfcFile.modes[], used only for filenames
        """
        if isinstance(fileId, str) or isinstance(fileId, six.text_type):
            self._close = True
            self._fp = open(fileId, mode)
        else:
            self._close = False
            self._fp = fileId

    def __enter__(self):
        return self._fp

    def __exit__(self, excType, excValue, traceback):
        if self._close:
            self._fp.close()
            self._fp = None


##
## @brief Hold, decode nfc wire protocol msgs
##
class NfcMsg:
    """ Hold, decode nfc wire protocol msgs """

    _pad = "\0"

    (
        _NFC_HANDSHAKE,
        _NFC_FILE_PUT,
        _NFC_FILE_GET,
        _NFC_FILE_COMPLETE,
        _NFC_SESSION_COMPLETE,
        _,  # 5 obsolete
        _NFC_RATE_CONTROL,
        _NFC_FILE_DATA,
        _NFC_PING) = list(range(0, 9))
    (
        _NFC_ERROR,
        _NFC_FSSRVR_OPEN,
        _NFC_FSSRVR_DISKGEO,
        _NFC_FSSRVR_IO,
        _NFC_FSSRVR_CLOSE,
        _NFC_PUTFILESINFO,
        _NFC_GETFILESINFO,
        _NFC_PUTFILE_DONE,
        _NFC_FSSRVR_DDBENUM,
        _NFC_FSSRVR_DDBGET,
        _NFC_FSSRVR_DDBSET,
        _NFC_FILE_DELETE,
        _NFC_FILE_RENAME,
        _NFC_FILE_COPY,
        _NFC_FILE_CREATEDIR,
        _,  # 35 does not exist
        _NFC_FILEOP_STATUS,
        _NFC_ENUM_DISKEXTS,
        _NFC_FILENAME_LIST,
        _NFC_FSSRVR_MULTIIO,
        _NFC_FSSRVR_ASM_MAP,
        _NFC_FSSRVR_CHM_MAP,
        _NFC_FSSRVR_DDBREMOVE,
        _NFC_CLIENTRANDOM,
        _NFC_FSSRVR_UNMAP,
        _NFC_FSSRVR_CKSM_XTNT,
        _NFC_FSSRVR_IO_EX,
        _NFC_FSSRVR_MULTIIO_EX,
        _NFC_FSSRVR_SYNC,
        _NFC_FSSRVR_ASMR_MAP,
        _NFC_FSSSRVR_UNMAP_INF) = list(range(20, 51))
    _NFC_MSG_SZ = 264
    _NFC_GENERIC_SMALL_DATA_LEN = 32
    _NFC_FILE_MSG_HDR_SIZE = 8
    _NFC_FILE_HDR_MAGIC = 0xabcdefab

    def __init__(self):
        """Initialize NfcMsg object"""
        self._buf = ''  # nfc message

    def DumpBuffer(self):
        """Dump NfcMsg object"""
        PrintBufferDump("NfcMsg fixed", self._buf)

    def IsFileOpMsg(self):
        """
        Check whether message buffer holds NFC_FILEOP_STATUS message.

        @rtype:  bool
        @return: True if message is NFC_FILEOP_STATUS message.
        """
        return self._GetMsgType() == self._NFC_FILEOP_STATUS

    def IsPutFileDoneMsg(self):
        """
        Check whether message buffer holds NFC_PUTFILE_DONE message.

        @rtype:  bool
        @return: True if message is NFC_PUTFILE_DONE message.
        """
        return self._GetMsgType() == self._NFC_PUTFILE_DONE

    def IsPutFileMsg(self):
        """
        Check whether message buffer holds NFC_FILE_PUT message.

        @rtype:  bool
        @return: True if message is NFC_FILE_PUT message.
        """
        return self._GetMsgType() == self._NFC_FILE_PUT

    def IsFileDataMsg(self):
        """
        Check whether message buffer holds NFC_FILE_DATA message.

        @rtype:  bool
        @return: True if message is NFC_FILE_DATA message.
        """
        return self._GetMsgType() == self._NFC_FILE_DATA

    def IsSessionClosed(self):
        """
        Check whether message buffer holds NFC_SESSION_COMPLETE message.

        @rtype:  bool
        @return: True if message is NFC_SESSION_COMPLETE message.
        """
        return self._GetMsgType() == self._NFC_SESSION_COMPLETE

    def IsOk(self):
        """
        Check whether message buffer holds NFC_FILEOP_STATUS message without
        any error reported.

        @rtype:  bool
        @return: True if message is NFC_FILEOP_STATUS message reporting success.
        """
        msgType, errorSize = unpack_from('<LL', strToBytes(self._buf))
        return msgType == self._NFC_FILEOP_STATUS and errorSize == 0

    @staticmethod
    def _GetFailureInfo(errMsg):
        """
        Convert received error message into list of failed files.

        @type  errMsg: str
        @param errMsg: Received buffer with error message.
        @rtype:        [int, ...]
        @return:       Array of indices of failed files.
        """
        # if there were no error bytes, we are done
        if errMsg is None:
            return []
        # error list is list of 16bit integers - so odd length is bad
        (elements, bad) = divmod(len(errMsg), 2)
        if bad:
            raise ValueError("List of failed paths contains partial element")
        # retrieve all integers except last: last one is sentinel
        elements -= 1
        return unpack_from('<%uH' % elements, strToBytes(errMsg))

    def _GetMsgType(self):
        """
        Retrieve message type.

        @rtype:  int
        @return: Message type.
        """
        msgType, = unpack_from('<L', strToBytes(self._buf))
        return msgType

    def GetMsg(self):
        """
        Retrieve message text.

        @rtype:  str
        @return: Message text.
        """
        return self._buf

    def ReceiveFixedMsg(self, conn):
        """
        Set message text to message received from socket.

        @type  conn: socket
        @param conn: Socket from which message should be read.
        """
        self._buf = _ReceiveBytes(conn, self._NFC_MSG_SZ)

    def _SetMsg(self, msgId, fixed='', variable=''):
        """
        Set message content.

        @type  msgId:    str
        @param msgId:    Message type.
        @type  fixed:    str (opt)
        @param fixed:    Content of fixed part of NfcMsg.
        @type  variable: str (opt)
        @param variable: Content of variable part of NfcMsg.
        """
        if not isinstance(fixed, bytes):
            fixed = fixed.encode()
        if not isinstance(variable, bytes):
            variable = variable.encode()
        if self._buf:
            raise Exception("Message already exists")
        # command word is sent in little endian format
        self._buf = pack('<L%us' % (self._NFC_MSG_SZ - 4), msgId, fixed)
        if variable:
            self._buf += variable

    @classmethod
    def _GetASCIIZPath(cls, path):
        """
        Convert path to NUL terminated string.

        @type  path: str
        @param path: Path.
        @rtype:      str
        @return:     Path with NUL appended.
        """
        if path is None:
            return ''
        return path + cls._pad

    # NfcPutFileMsg|path data
    # uint32 type  NfcFileType enum
    # uint32 conversionFlags
    # uint32 pathLen
    # uint64 fileSize
    # uint64 spaceRequired
    def ReceivePutFileInfo(self, conn):
        """
        Receive variable portion of NFC_FILE_PUT.

        @type  conn: socket
        @param conn: Socket from which to read data.
        @rtype:      dict
        @return:     Dictionary with retrieved attributes.
        """
        _msgType, _fileType, conversionFlags, pathLen, _fileSize, \
           _spaceRequired, parentPathLen, rdmDevicePathLen, _isPassthrough, \
           storagePolicyLen = unpack_from('<LLLLQQLLBL', strToBytes(self._buf))
        attrs = dict()
        attrs['varMsg'] = _ReceiveBytes(conn, pathLen)
        attrs['parentPath'] = _ReceiveBytes(conn, parentPathLen)
        attrs['devicePath'] = _ReceiveBytes(conn, rdmDevicePathLen)
        attrs['storagePolicy'] = _ReceiveBytes(conn, storagePolicyLen)
        if conversionFlags & NfcClient.NFC_CONV_DSK_SESPARSE:
            attrs['grainSize'] = _ReceiveBytes(
                conn, self._NFC_GENERIC_SMALL_DATA_LEN)
        else:
            attrs['grainSize'] = None
        return attrs

    def ReceiveFileOpInfo(self, conn):
        """
        Receive variable portion of NFC_FILEOP_STATUS.

        @type  conn: socket
        @param conn: Socket from which to read data.
        @rtype:      ([int, ...], str)
        @return:     Tuple holding offsets of failed files, and unknown string.
        """
        _msgType, errorSize, dataSize, _failed, _succeded = \
           unpack_from('<LLLHH', strToBytes(self._buf))
        errMsg = self._GetFailureInfo(_ReceiveBytes(conn, errorSize))
        varMsg = _ReceiveBytes(conn, dataSize)
        return (errMsg, varMsg)

    @classmethod
    def ReceiveFileDataInfo(cls, conn):
        """
        Receive variable portion of NFC_FILE_DATA.

        @type  conn: socket
        @param conn: Socket from which to read data.
        @rtype:      str
        @return:     Received data.
        """
        dataHeader = _ReceiveBytes(conn, cls._NFC_FILE_MSG_HDR_SIZE)
        magic, dataLength = unpack('<LL', strToBytes(dataHeader))
        if magic != cls._NFC_FILE_HDR_MAGIC:
            raise Exception("Protocol violation, magic invalid %d" % magic)
        return _ReceiveBytes(conn, dataLength)


# Following subclasses create a buffer, contents are in
# NFCLIB protocol format


class NfcClientRandomMsg(NfcMsg):
    """ NFC_CLIENTRANDOM message """
    def __init__(self, randomData):
        NfcMsg.__init__(self)
        self._SetMsg(self._NFC_CLIENTRANDOM, randomData)


class NfcPingMsg(NfcMsg):
    """ NFC_PING message """
    def __init__(self):
        NfcMsg.__init__(self)
        self._SetMsg(self._NFC_PING)


class NfcEndSessionMsg(NfcMsg):
    """ NFC_SESSION_COMPLETE message """
    def __init__(self):
        NfcMsg.__init__(self)
        self._SetMsg(self._NFC_SESSION_COMPLETE)


class _NfcNameListMsg(NfcMsg):
    """ Message using NameList structure (RENAME + DELETE) """
    def __init__(self, msgId, nameList):
        NfcMsg.__init__(self)
        self._SetNameList(msgId, nameList)

    # NfcFileNameListMsg: size(4), flags(4), count(2)
    def _SetNameList(self, msgId, nameList):
        """
        Create NfcMsg holding name list.

        @type  msgId:    str
        @param msgId:    Message type.
        @type  nameList: [str, ...]
        @param nameList: List of names to operate on.
        """
        # variable header, append NUL terminated filenames, plus
        # NUL sentinel at the end
        if nameList:
            variable = self._pad.join(nameList) + self._pad + self._pad
        else:
            variable = self._pad
        # size, flags, count
        fixed = pack('<LLH', len(variable), 0, len(nameList))
        self._SetMsg(msgId, fixed, variable)


class NfcDeleteMsg(_NfcNameListMsg):
    """ NFC_FILE_DELETE message """
    def __init__(self, nameList):
        _NfcNameListMsg.__init__(self, self._NFC_FILE_DELETE, nameList)


class NfcRenameMsg(_NfcNameListMsg):
    """ NFC_FILE_RENAME message """
    def __init__(self, nameList):
        _NfcNameListMsg.__init__(self, self._NFC_FILE_RENAME, nameList)


class NfcPutFileMsg(NfcMsg):
    """ NFC_FILE_PUT message """
    def __init__(self, remoteFileName, props):
        NfcMsg.__init__(self)
        self._SetPutFileProps(self._NFC_FILE_PUT, remoteFileName, props)

    # NfcPutFileMsg: type(4),convFlags(4),pathLen(4),fileSize(8),spaceReqd(8)
    #                fileName\0
    def _SetPutFileProps(self, msgId, remoteFileName, props):
        """
        Create NfcMsg holding put file request.

        @type  msgId:          str
        @param msgId:          Message type.
        @type  remoteFileName: str
        @param remoteFileName: Local file name.
        @type  props:          NfcFileProps
        @param props:          Source file properties & transformations.
        """
        variable = self._GetASCIIZPath(remoteFileName)
        fixed = pack('<LLLqq', props.type, props.conversionFlags,
                     len(variable), props.fileSize, props.spaceRequired)
        self._SetMsg(msgId, fixed, variable)


class NfcGetFileMsg(NfcMsg):
    """ NFC_FILE_GET message """
    def __init__(self, filename, props):
        NfcMsg.__init__(self)
        self._GetFileProps(self._NFC_FILE_GET, filename, props)

    ## format of NfcGetFileMsg: type(4),pathLen(4),convFlags(4),
    #                fileName\0
    # filename is a string, props is NfcFileProps
    def _GetFileProps(self, msgId, filename, props):
        """
        Create NfcMsg holding get file request.

        @type  msgId:    str
        @param msgId:    Message type.
        @type  filename: str
        @param filename: Remote file name.
        @type  props:    NfcFileProps or int or None
        @param props:    Transfer type and conversion flags.
        """
        if props is None or type(props) == type(0):
            fp = NfcFileProps(None)
            if props is not None:
                fp.conversionFlags = props
            props = fp
        variable = self._GetASCIIZPath(filename)
        fixed = pack('<LLL', props.type, len(variable), props.conversionFlags)
        self._SetMsg(msgId, fixed, variable)


class NfcDataMsg(NfcMsg):
    """ aka NfcFileMessage = {NfcMsgHdr(4), NfcFileMsgHdr(8), file data} """

    NFCFILE_MAX_XFER_SIZE = 256 * 1024

    def __init__(self):
        NfcMsg.__init__(self)
        magic = pack('<L', self._NFC_FILE_HDR_MAGIC)
        self._SetMsg(self._NFC_FILE_DATA, variable=magic)
        self._prefix = self._buf
        self._buf = None

    def _SetData(self, blk):
        """
        Create message content from block of bytes.

        @type  blk:  str
        @param blk:  Block of bytes.
        """
        # Write dataLength
        sz = pack('<L', len(blk))
        self._buf = self._prefix + sz + blk

    def ReadData(self, fileId):
        """
        Update message with another block from the file.

        @type  fileId: file object
        @param fileId: file object to read from
        @rtype:        bool
        @return:       True if data were read, False if EOF.
        """
        blk = fileId.read(self.NFCFILE_MAX_XFER_SIZE)
        self._SetData(blk)
        return not not blk


class NfcFileProps:
    """ NFC file properties """
    def __init__(self, localFile):
        self.type = NfcProtocol.fileTypes['NFC_RAW']
        self.conversionFlags = 0
        self.fileSize = 0
        self.spaceRequired = 0
        if localFile is not None:
            try:
                statinfo = fstat(localFile.fileno())
                self.fileSize = statinfo.st_size
                # NFC_DISK may report this differently
                self.spaceRequired = statinfo.st_size
            except (AttributeError, TypeError, OSError):
                # Ignore inability to get size for non-standard objects
                logging.exception('Could not find size for %s', localFile)


class NfcProtocol:
    """ A hacked python implementation of NfcLib client protocol """

    # send handshake to nfclib server over tcpSocket
    # and process reply if any
    _NFC_SECRET_LEN = 128
    fileTypes = dict(NFC_RAW=0, NFC_TEXT=1, NFC_DISK=2)

    def __init__(self, tcpSocket):
        self._conn = tcpSocket
        # should a file mgmt command fail, this is updated
        self._failed = []
        # apparently this isn't needed if using tickets:
        # self.DoHandshake()

    ##
    # Should use explicit method but just in case...
    def __del__(self):
        self._conn = None
        # if attribute self._conn is still open, then do this
        # self._nfcProto.SendSessionComplete()

    ##
    # output contents of an NfcMsg onto _conn
    # @pre outMsg is of subclass of NfcMsg
    #      Connect() returned success
    def WriteMsg(self, outMsg):
        """
        Write message to the server.

        @type  outMsg: NfcMsg object
        @param outMsg: NfcMsg to send.
        """
        buf = outMsg.GetMsg()
        amt = self._conn.sendall(buf)
        logging.debug("sent %s bytes", amt)

    ##
    # update msg of type NfcMsg
    def ReadMsg(self, msg):
        """
        Update message with newly read data.

        @type  msg: NfcMsg
        @param msg: NfcMsg to hold new data
        """
        msg.ReceiveFixedMsg(self._conn)

    # Send random data to server to prove our identity
    def SendClientRandom(self, randomData):
        """
        Send clientrandom message to the server.

        @rtype:  bool
        @return: True
        """
        msg = NfcClientRandomMsg(randomData)
        self.WriteMsg(msg)
        return True

    # The remote side will just output
    # see nfcLib.c Nfc_SendPingMsg() and
    # the hostd.log will contain this NfcDebug("Received ping message\n");
    def SendPingMsg(self):
        """
        Send ping message to the server.

        @rtype:  bool
        @return: True
        """
        msg = NfcPingMsg()
        self.WriteMsg(msg)
        return True

    # Tell nfcLib to discontinue this session
    def SendSessionComplete(self):
        """
        Shut down communication channel to server.

        @rtype:  bool
        @return: True
        """
        msg = NfcEndSessionMsg()
        self.WriteMsg(msg)
        self._conn.shutdown(SHUT_RDWR)
        return True

    # request transfer of files from client to server
    def SendPutRequest(self, fileset, props):
        """
        Send upload request to server.

        @type  fileset:  [(str, str), ...]
        @param fileset:  Array of files to upload.
        @type  props:    None, int, or NfcFileProps
        @param props:    Conversion flags.
        @rtype:          bool
        @return:         True on success.
        """
        self._failed = []
        item = 0
        for localFileName, remoteFileName in fileset:
            try:
                with NfcFile(localFileName,
                             NfcFile.modes['READ_ONLY']) as localFile:
                    if props is None or type(props) == type(0):
                        fp = NfcFileProps(localFile)
                        if props is not None:
                            fp.conversionFlags = props
                    else:
                        fp = props
                    msg = NfcPutFileMsg(remoteFileName, fp)
                    self.WriteMsg(msg)
                    # server ack comes at end of file xfer, conn is dropped on error
                    self._TransferFile(localFile)
                    self.ReadMsg(msg)
                    if not msg.IsPutFileDoneMsg():
                        if not msg.IsSessionClosed():
                            raise IOError(
                                "Server dropped connection, path invalid, "
                                "file exists, or resource issue occured")
                        msg.DumpBuffer()
                        raise Exception("Protocol Violation, expected "
                                        "PutFileDone got Session Close")
            except IOError:
                logging.exception("put file on server failed")
                self._failed += fileset[item:]
                return False
            item += 1
        return True

    # request transfer of files from server to client
    def SendGetRequest(self, fileset, props):
        """
        Send download request to server.

        @type  fileset:  [(str, str), ...]
        @param fileset:  Array of files to download.
        @type  props:    NfcFileProps object or int or None
        @param props:    Properties for the file transfer.
        @rtype:          bool
        @return:         True on success.
        """
        self._failed = []
        item = 0
        for remoteFileName, localFileName in fileset:
            msg = NfcGetFileMsg(remoteFileName, props)
            self.WriteMsg(msg)
            # server ack comes at end of file xfer, tcp session is dropped on error
            try:
                with NfcFile(localFileName,
                             NfcFile.modes['WRITE_ONLY']) as localFile:
                    self._ReceiveFile(localFile)
            except Exception:
                logging.exception("get file from server failed")
                self._failed += fileset[item:]
                return False
            item += 1
        return True

    # Delete one or more files as specified in nameList
    def SendDeleteMsg(self, nameList):
        """
        Send delete request to server.

        @type  nameList: [str, ...]
        @param nameList: List of files to delete.
        @rtype:          bool
        @return:         True on success.
        """
        self._failed = []
        msg = NfcDeleteMsg(nameList)
        self.WriteMsg(msg)
        self.ReadMsg(msg)
        if msg.IsFileOpMsg():
            if msg.IsOk():
                return True
            else:
                erroredPathOffset = msg.ReceiveFileOpInfo(self._conn)[0]
                self._SetErroredPaths(erroredPathOffset, nameList)
        elif msg.IsSessionClosed():
            logging.error("session was closed by server side")
        else:
            logging.error(
                "unexpected msg type sent in response to delete request")
            msg.DumpBuffer()
        return False

    def SendRenameRequest(self, nameList):
        """
        Send rename request to server.

        @type  nameList: [str, ...]
        @param nameList: List of files to rename (odd src, even dst).
        @rtype:          bool
        @return:         True on success.
        """
        self._failed = []
        msg = NfcRenameMsg(nameList)
        self.WriteMsg(msg)
        self.ReadMsg(msg)
        if msg.IsFileOpMsg():
            if msg.IsOk():
                return True
            else:
                erroredPathOffset = msg.ReceiveFileOpInfo(self._conn)[0]
                self._SetErroredPaths(erroredPathOffset, nameList)
        elif msg.IsSessionClosed():
            logging.error("session was closed by server side")
        else:
            logging.error(
                "unexpected msg type sent in response to rename request")
            msg.DumpBuffer()
        return False

    # read data and block it for xfer
    def _TransferFile(self, localFile):
        """
        Transfer file content to server.

        @type  localFile: file object
        @param localFile: Local file to read from.
        """
        msg = NfcDataMsg()
        while msg.ReadData(localFile):
            self.WriteMsg(msg)
        # send len == 0 to signal EOF
        self.WriteMsg(msg)

    # read data from socket and write to disk
    # files is tuple (src,dst)
    # @pre a Get request has been issued
    def _ReceiveFile(self, localFile):
        """
        Receive file.

        @type  localFile: file object
        @param localFile: File where to store data.
        """
        msg = NfcMsg()
        self.ReadMsg(msg)
        if msg.IsPutFileMsg():
            msg.ReceivePutFileInfo(self._conn)
            try:
                while True:
                    self.ReadMsg(msg)
                    if msg.IsFileDataMsg():
                        data = msg.ReceiveFileDataInfo(self._conn)
                        if not data:
                            break
                        localFile.write(data)
            except IOError as msg:
                self.SendSessionComplete()
        else:
            if msg.IsSessionClosed():
                msg.DumpBuffer()
                raise Exception("Server rejected request get '%s'" %
                                localFile.name)

    def _SetErroredPaths(self, ep, pathList):
        """
        Convert list of indices for failed files and list of paths into list of
        failed paths.

        @type  ep:       [int, ...]
        @param ep:       Indices for failed files.
        @type  pathList: [str, ...]
        @param pathList: List of files.
        """
        failed = []
        for item in ep:
            try:
                failed.append(pathList[item])
            except IndexError:
                logging.exception("protocol received invalid path offset: %s",
                                  item)
            except Exception:
                logging.exception("protocol see buffer")
        self._failed = failed

    def ClearErroredPaths(self):
        """Clear list of the failed files."""
        self._failed = []

    def GetErroredPaths(self):
        """
        Retrieve list of paths that failed in last operation.

        @rtype:  bool
        @return: Array of filenames.
        """
        return self._failed


class Proxy(object):
    """
    The addition of this 'Proxy' class has been necessitated due to the porting
    from Python2 to Python3.
    In Python2, ssl.wrap_socket() in NfcClient's Connect() did not overwrite
    the raw socket used to create the SSL socket, and hence could be re-assigned
    back to the raw socket, once the SSL connection was done.
    However, in Python3, ssl.wrap_socket() internally calls sock.detach() which
    closes the raw socket (socket.socket [closed] fd=-1) and opens an SSL socket.
    Hence, overriding the read-only attribute detach() to be a no-op, in order
    to ensure that the raw socket remains open, even after wrap_socket is called.
    """
    __slots__ = ["_obj", "__weakref__"]

    def __init__(self, obj):
        object.__setattr__(self, "_obj", obj)

    # proxying (special cases)
    def __getattribute__(self, name):
        if name == 'detach':
            return lambda *args, **kwargs: None
        return getattr(object.__getattribute__(self, "_obj"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_obj"), name, value)


class NfcClient:
    """ Native Client side python implemenation of nfclib """

    # NfcFileType
    NFC_RAW = 0
    NFC_TEXT = 1
    NFC_DISK = 2
    # convFlags
    NFC_CONV_TEXT_UNIX = (1 << 0)
    NFC_CONV_TEXT_WIN = (1 << 1)
    NFC_CONV_DSK_VMDK = (1 << 2)
    NFC_CONV_DSK_VMFS = (1 << 3)
    NFC_CREATE_OVERWRITE = (1 << 4)
    NFC_CREATE_ALTERNATE = (1 << 5)
    NFC_CONV_DSK_FLATTEN = (1 << 6)
    NFC_CONV_DSK_THINPROV = (1 << 7)
    NFC_CONV_DSK_FORCELSILOGIC = (1 << 8)
    NFC_CONV_DSK_USETARGETVHW = (1 << 9)
    NFC_CONV_DSK_SESPARSE = (1 << 14)

    _AUTHD_PROTOCOL_LINEMSGLEN = 1016

    # setup host, port and session credtionals
    # @param hst [in] HostServiceTicket
    #
    def __init__(self, hst):
        self._hst = hst
        self._host = hst.GetHost()
        if self._host is None:
            self._host = environ[r'VHOST']
        self._port = hst.GetPort()
        if self._port is None:
            self._port = int(environ[r'VPORT'])
        self.wait_secs = 10
        # path names that failed transaction
        self._conn = None
        self._nfcProto = None

    def __del__(self):
        logging.info("closing nfc socket")
        nfcProto = getattr(self, '_nfcProto', None)
        if nfcProto:
            self._nfcProto.SendSessionComplete()
            self._nfcProto = None
        conn = getattr(self, '_conn', None)
        if conn:
            try:
                self._conn.shutdown(SHUT_RDWR)
            except Exception:
                pass
            self._conn = None

    def _SSLConnect(self, thumbprint):
        """
        Negotiate SSL on self._conn socket.

        @type  thumbprint: str
        @param thumbprint: Thumbprint in HH:HH:HH:HH... form.
        """
        if not _hasSSL:
            raise ImportError("SSL support missing (use python >= 2.6)")

        logging.info("Enabling ssl")
        # TODO handle ssl.SSLError
        sslSock = ssl.wrap_socket(self._conn, ssl_version=ssl.PROTOCOL_SSLv23)
        sslSock.do_handshake()
        cert = sslSock.getpeercert(True)
        certThumbprint = sha1(cert).hexdigest()
        expThumbprint = thumbprint.replace(':', '').lower()
        if certThumbprint != expThumbprint:
            raise Exception("Thumbprint mismatch")
        self._conn = sslSock

    ##
    # Connect to nfclib via authd using hostd NfcService API ticket information
    # "220 VMware Authentication Daemon Version 1.10: SSL Required,
    # ServerDaemonProtocol:SOAP, MKSDisplayProtocol:VNC ,"
    def Connect(self, timeout=None):
        """
        Connect to the server.

        @type  timeout: int
        @param timeout: How long to wait for connection.
        """
        logging.info("starting tcp connection to host: %s port: %d",
                     self._host, self._port)
        try:
            self._rawSock = Proxy(
                create_connection((self._host, self._port), timeout))
        except Exception:
            logging.exception("cannot connect to server -- %s %s", self._host,
                              self._port)
            raise
        self._conn = self._rawSock
        msg = self.GetAuthdResponse()
        if not msg.GreetingOk():
            msg.DumpBuffer()
            raise Exception(
                "authd protocol violation, expected greeting response")
        logging.info("authd greeting = %s", msg.GetGreeting())
        try:
            if msg.SSLRequired():
                self._SSLConnect(self._hst.sslThumbprint)

            cmd = "SESSION %s\r\n" % (self._hst.GetSessionId())
            logging.debug("sending: %s", cmd)
            self._conn.sendall(strToBytes(cmd))
            if self._hst.GetService().endswith("ssl"):
                randomData = GetRandomData()
            else:
                randomData = "PlainText"
            cmd = "THUMBPRINT %s\r\n" % (randomData)
            logging.debug("sending: %s", cmd)
            self._conn.sendall(strToBytes(cmd))
            msg = self.GetAuthdResponse()
            logging.debug("authd response to THUMBPRINT")
            msg.DumpBuffer()
            if msg.RequestOk():
                newThumbprint = msg.GetGreeting()[4:-2]
            else:
                randomData = None
                newThumbprint = self._hst.sslThumbprint
            cmd = "PROXY %s\r\n" % (self._hst.GetService())
            logging.debug("sending: %s", cmd)
            self._conn.sendall(strToBytes(cmd))
        except Exception:
            logging.exception("send authd control msg failed")
            raise
        msg = self.GetAuthdResponse()
        logging.debug("authd response")
        msg.DumpBuffer()

        if not msg.RequestOk():
            msg.DumpBuffer()
            raise Exception("authd connection to nfclib failed unexpectedly")
        try:
            # Technically, we should unwrap the connection, but the server
            # side does not do this, so we need to just switch directly over to
            # the raw socket.
            # self._conn = self._conn.unwrap()

            # Using sockRef here, to hold the ssl socket reference temporarily.
            # The current NfcClient instance must hold a reference
            # to both the raw socket and the ssl socket.
            # If either reference is lost, the other socket is closed
            # as well (since they share the fd) and a broken pipe error
            # is reported on subsequent reads/writes.
            sockRef = self._conn
            self._conn = self._rawSock
            if self._hst.GetService().endswith("ssl"):
                self._SSLConnect(newThumbprint)
            self._nfcProto = NfcProtocol(self._conn)
            if randomData is not None:
                self._nfcProto.SendClientRandom(randomData)
            self._conn = sockRef
            # Now, self._conn holds ssl socket reference
            # and self._rawSock holds raw socket reference
        except Exception:
            logging.exception("nfc handshake failed")
            raise
        return True

    def Disconnect(self):
        """Disconnect from server."""
        if self._nfcProto:
            self._nfcProto.SendSessionComplete()
            self._nfcProto = None
        return True

    # protocol 'authd', appears line oriented fmt: 'data\r\n'
    def GetAuthdResponse(self):
        """
        Retrieve authd response.

        @rtype:  AuthdMsg object
        @return: Received Authd message.
        """
        prev = None
        buf = []
        while len(buf) < self._AUTHD_PROTOCOL_LINEMSGLEN:
            cur = self._conn.recv(1)
            if not cur:
                raise Exception("ERROR: Authd protocol error, "
                                "connection was closed prematurely")
            cur = cur.decode()
            buf.append(cur)
            if prev == '\r' and cur == '\n':
                return AuthdMsg(''.join(buf))
            if prev == '\r' or cur == '\n':
                raise Exception("ERROR: Authd protocol error, "
                                "expected NL following CR")
            prev = cur
        raise Exception("ERROR: Authd protocol error, response too long")

    def __str__(self):
        return "{ host: %s, port: %d, service: %s, version: %s, session: %s }" % \
            (self._host, self._port, self._hst.GetService(),
             self._hst.GetServiceVersion(), self._hst.GetSessionId())

    def DeleteFiles(self, fileList):
        """
        Delete files.

        @type  fileList: [str, ...]
        @param fileList: List of files to delete.
        @rtype:          bool
        @return:         True if all files deleted, False if some files deleted.
        """
        if not self._nfcProto:
            raise ValueError("Call to Connect() must succeed first")
        if type(fileList) != type([]):
            raise TypeError("Expecting list of filenames")
        return self._nfcProto.SendDeleteMsg(fileList)

    def RenameFiles(self, fileset):
        """
        Rename files.

        @type  fileset: [(str, str), ...]
        @param fileset: List of files to rename.  In the tuple order is
                        (oldFile, newFile).
        @rtype:         bool
        @return:        True if all files renamed, False if some files renamed.
        """
        if not self._nfcProto:
            raise ValueError("Call to Connect() must succeed first")
        self._nfcProto.ClearErroredPaths()
        if fileset is None:
            return True
        if type(fileset) != type([]):
            raise TypeError("Expecting list of tuples [(srcPath,dstPath),...]")
        if type(fileset[0]) != type(()):
            raise TypeError("Expecting list to contain tuples "
                            "[(srcPath,dstPath),...]")
        rawList = self._CvtFromTuple(fileset)
        return self._nfcProto.SendRenameRequest(rawList)

    # unpack tuples in list
    @staticmethod
    def _CvtFromTuple(fileset):
        """
        Convert array of tuples into simple array.

        @type  fileset: [(str, str), ...]
        @param fileset: List of files to rename.
        @rtype:         [str, ...]
        @return:        Array of filenames.
        """
        rawList = []
        for oldFileName, newFileName in fileset:
            rawList.append(oldFileName)
            rawList.append(newFileName)
        return rawList

    # Last request found the following paths in error
    def GetErroredPaths(self):
        """
        Retrieve list of paths that failed during last command.

        @rtype:  [str, ...]
        @return: List of files that were not processed.
        """
        return self._nfcProto.GetErroredPaths()

    # list of tuple(local FileName, remote FileName) to transfer
    # props can be either an unsigned int convFlags or NfcFileProps object
    # convFlags can be NfcClient.NFC_CREATE_* or NFC_CONV_*
    def PutFiles(self, fileset, props=None):
        """
        Upload files.

        @type  fileset: [(str or file, str), ...]
        @param fileset: List of files to upload.
        @type  props:   NfcFileProps object or int or None (opt)
        @param props:   Conversion flags for the files.
        @rtype:         bool
        @return:        True if all files uploaded, False if some files uploaded.
        """
        if not self._nfcProto:
            raise ValueError("Call to Connect() must succeed first")
        self._nfcProto.ClearErroredPaths()
        if fileset is None:
            return True
        if type(fileset) != type([]):
            raise TypeError("Expecting list of tuples [(srcPath,dstPath),...]")
        if type(fileset[0]) != type(()):
            raise TypeError("Expecting list to contain tuples "
                            "[(srcPath,dstPath),...]")
        return self._nfcProto.SendPutRequest(fileset, props)

    # list of tuple(remote FileName, local FileName) to transfer
    def GetFiles(self, fileset, props=None):
        """
        Downoad files.

        @type  fileset: [(str, str or file), ...]
        @param fileset: List of files to download.
        @type  props:   NfcFileProps object or int or None (opt)
        @param props:   Conversion flags and type for the files.
        @rtype:         bool
        @return:        True if all files uploaded, False if some files uploaded.
        """
        if not self._nfcProto:
            raise ValueError("Call to Connect() must succeed first")
        self._nfcProto.ClearErroredPaths()
        if fileset is None:
            return True
        if type(fileset) != type([]):
            raise TypeError("Expecting list of tuples [(srcPath,dstPath),...]")
        if type(fileset[0]) != type(()):
            raise TypeError("Expecting list to contain tuples "
                            "[(srcPath,dstPath),...]")
        return self._nfcProto.SendGetRequest(fileset, props)

    def MakeDirs(self, dirs):
        """
        Create directories.

        @type  dirs: [str, ...]
        @param dirs: List of directories to create.
        @rtype:      bool
        @return:     True on success.
        """
        if not self._nfcProto:
            raise ValueError("Call to Connect() must succeed first")
        # @todo
        raise NotImplementedError()
