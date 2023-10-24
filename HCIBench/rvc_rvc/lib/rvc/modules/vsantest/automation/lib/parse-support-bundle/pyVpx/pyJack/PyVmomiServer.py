#!/usr/bin/env python
"""
Copyright 2008-2021 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is the python vmomi server module. This hosted python managed
object implementation and serves SOAP requests from extern entities
"""
__author__ = "VMware, Inc"

import sys
import os

# The following imports are for main and HTTPServer
import threading
import time
import re
import io

import six
from six import BytesIO
if six.PY3:
    from http.cookies import SimpleCookie
    from http.server import BaseHTTPRequestHandler
    from http.server import HTTPServer
else:
    from Cookie import SimpleCookie
    from BaseHTTPServer import BaseHTTPRequestHandler
    from BaseHTTPServer import HTTPServer

import six.moves.socketserver as socketserver
import six.moves.queue as queue

from pyVmomi import VmomiSupport

# logging
import logging, logging.handlers
from contrib.logUtils import LoggingFactory

# SOAPAction string
_STR_SOAP_ACTION = "SOAPAction"

# SOAPAction bytes
_STR_SOAP_ACTION_BYTES = b"SOAPAction"

# Global variables
gCmdOptions = None
gCmdRemainingOptions = None
gLogPath = os.path.normpath("./")
gLogLevel = "INFO"
gSoapHandlerCls = None
gAuthChecker = None
UTF8 = 'utf-8'


def SetupLogging(options):
    """Setup debug logging"""
    LoggingFactory.ParseOptions(options)


def GetSoapHandler(stubs):
    global gSoapHandlerCls
    if gSoapHandlerCls:
        return gSoapHandlerCls(stubs)
    else:
        return SoapHandler(stubs)


def SetSoapHandlerCls(cls):
    global gSoapHandlerCls
    gSoapHandlerCls = cls


def SetAuthChecker(checker):
    global gAuthChecker
    if gAuthChecker:
        raise RuntimeError("The auth checker is already set")
    gAuthChecker = checker


def ParseArguments(argv):
    """Parse arguments"""

    from optparse import OptionParser, make_option

    # Internal cmds supported by this handler
    _CMD_OPTIONS_LIST = [
        make_option("-p",
                    "--port",
                    dest="port",
                    default="443",
                    help="TCP port number"),
        make_option(
            "-H",
            "--host",
            dest="host",
            default="",
            help="Hostname, IPv4/IPv6 address of the server. By default, "
            "server will listen on all interfaces. This is only used "
            "when --port option is provided."),
        make_option(
            "-w",
            "--maxworkers",
            dest="max_workers",
            type="int",
            default=8,
            help="Set the maximum number of HTTP server workers."),
        make_option("--unix", dest="unix", help="Unix socket path"),
        make_option("--keyfile",
                    dest="keyfile",
                    default=None,
                    help="Https server private key"),
        make_option("--certfile",
                    dest="certfile",
                    default=None,
                    help="Https server certificate"),
        make_option("-i",
                    "--interactive",
                    dest="interactive",
                    action="store_true",
                    help="Interactive mode"),
        make_option("-f", "--file", dest="file",
                    help="Read request from file"),
        make_option(
            "-g",
            "--cgi",
            dest="cgi",
            action="store_true",
            help="CGI mode: process a single SOAP request as a CGI script"),
        make_option(
            "--scgi",
            dest="scgi",
            action="store_true",
            help="SCGI mode: process multiple SOAP requests over stdio",
            default=False),
        make_option("--rhost",
                    dest="rhost",
                    default=None,
                    help="Proxy mode: Remote host"),
        make_option("--rport",
                    dest="rport",
                    default="443",
                    help="Proxy mode: Remote port"),
        make_option("--rns",
                    dest="rns",
                    default="vim25/5.5",
                    help="Proxy mode: Remote namespace"),
        make_option("--rpath",
                    dest="rpath",
                    default="/sdk",
                    help="Proxy mode: Remote path"),
        make_option(
            "--ignorePyMo",
            action="store_true",
            default=False,
            dest="ignorePyMo",
            help="Do not load the managed objects or types under pyMo"),
        make_option("-?", action="help")
    ]
    _STR_USAGE = "%prog [options]"

    # Get command line options
    cmdParser = OptionParser(option_list=_CMD_OPTIONS_LIST, usage=_STR_USAGE)
    cmdParser.allow_interspersed_args = False
    LoggingFactory.AddOptions(cmdParser)

    # Parse arguments
    (options, remainingOptions) = cmdParser.parse_args(argv)
    try:
        # optparser does not have a destroy() method in older python
        cmdParser.destroy()
    except Exception:
        pass
    del cmdParser
    return (options, remainingOptions)


def Initialize(options=None, remainingOptions=None):
    """Initialize global options variables"""
    global gCmdOptions
    gCmdOptions = options != None and options or {}
    global gCmdRemainingOptions
    gCmdRemainingOptions = remainingOptions != None and remainingOptions or {}
    ImportTypesAndManagedObjects()


def ImportTypesAndManagedObjects():
    """Import dynamic types
    Note: Import DynTypeMgr to bring in GetDynTypeMgr(). Do not remove
    """
    import DynTypeMgr
    import MoManager

    # Note: Import pyMo to bring in all managed objects. Do not remove
    ignorePyMo = getattr(gCmdOptions, "ignorePyMo", False)
    if not ignorePyMo:
        import pyMo


# Parse arguments
if __name__ == "__main__":
    gCmdOptions, gCmdRemainingOptions = ParseArguments(sys.argv[1:])
    SetupLogging(gCmdOptions)
    Initialize(options=gCmdOptions, remainingOptions=gCmdRemainingOptions)

# Modules that might use logging must be declared after calling SetupLogging
from SoapHandler import SoapHandler, ExceptionMsg


# Utility fn to log an exception with traceback
#
# @param msg Message to print
# @param err The exception
def LogException(msg, err):
    """Log exception with stack trace"""
    try:
        import traceback
        stackTraces = traceback.format_exception(sys.exc_info()[0],
                                                 sys.exc_info()[1],
                                                 sys.exc_info()[2])
        logging.critical(msg + ExceptionMsg(err))
        for line in stackTraces:
            logging.critical(line.rstrip())
    except Exception:
        pass


# Get the wire version from URN string
#
# @param  urn the URN in the form of "urn:namespace/versionId"
# @return wire version string (namespace/versionId)
def _GetWireVersion(urn):
    """Get version from URN string"""

    # Strip whitespaces
    urn = urn.strip()
    if urn.startswith('"'):
        urn = urn.strip('"')
    elif urn.startswith("'"):
        urn = urn.strip("'")

    return urn[4:].strip() if urn.startswith("urn:") else None


gPasswordPattern = "<password>[^>]*</password>|<password[^>]*/>"
gReText = re.compile(gPasswordPattern, re.IGNORECASE)
gReUTF8 = re.compile(gPasswordPattern.encode(), re.IGNORECASE)

gPasswordReplacement = "<password>(not shown)</password>"
gPasswordReplacementUTF8 = gPasswordReplacement.encode()


def _LogFilteredXML(xml):
    """Log debug XML password filter"""

    if not logging.getLogger().isEnabledFor(logging.DEBUG):
        return

    if isinstance(xml, six.text_type):
        global gReText, gPasswordReplacement
        message = gReText.sub(gPasswordReplacement, xml)
    elif isinstance(xml, six.binary_type):
        global gReUTF8, gPasswordReplacementUTF8
        message = gReUTF8.sub(gPasswordReplacementUTF8, xml)
    else:
        return

    logging.debug(message)


# Message body reader.  Read message body up to a specified length.
# Also avoid reading the whole request into memory
class _MessageBodyReader:
    """
    Read message body up to a specified length (unlimited if maxLen is None
    """
    def __init__(self, rfile, maxLen=None):
        self.rfile = rfile
        self.len = maxLen
        if maxLen is None:
            # Read until EOF
            self.read = self.readAll
        else:
            self.read = self.readChunk

    def readChunk(self, bytes):
        """Read bytes"""
        if self.len > 0:
            if self.len < bytes:
                bytes = self.len
            ret = self.rfile.read(bytes)
            _LogFilteredXML(ret)
            self.len -= len(ret)
        else:
            ret = b""
        return ret

    def readAll(self, bytes):
        """Read until eof"""
        ret = self.rfile.read(bytes)
        _LogFilteredXML(ret)
        return ret


# Generic HTTP handler class
class GeneralHttpHandler(BaseHTTPRequestHandler):
    """Http handler"""

    # Override base class's protocol_version
    # Note: need to include accurate "Content-Length" in send_header()
    protocol_version = "HTTP/1.1"

    class _ChunkedMessageBodyReader:
        """Chunked message body reader"""
        def __init__(self, rfile):
            self.rfile = rfile
            self.chunkSize = 0
            self._StartNextChunk()

        def _StartNextChunk(self):
            """Start next chunk"""
            line = self.rfile.readline()
            chunkSize = int(line.split(b";", 1)[0], 16)
            if chunkSize == 0:
                # Remove trailer
                while True:
                    line = self.rfile.readline()
                    if line == b"\r\n":
                        break
            self.chunkSize = chunkSize

        def _ReadChunk(self, bytes):
            """Read bytes from current chunk"""
            assert (self.chunkSize >= bytes)
            ret = self.rfile.read(bytes)
            self.chunkSize -= bytes
            if self.chunkSize == 0:
                # Discard CRLF
                self.rfile.read(2)
                self._StartNextChunk()
            return ret

        def read(self, bytes):
            """Read bytes"""
            ret = []
            while bytes > 0 and self.chunkSize > 0:
                readSize = min(self.chunkSize, bytes)
                # Read chunk
                ret.append(self._ReadChunk(readSize))
                bytes -= readSize
            ret = b"".join(ret)
            if ret:
                _LogFilteredXML(ret)
            return ret

    class _ChunkedMessageBodyWriter:
        """Chunked message body writer"""
        def __init__(self, wfile, chunkSize=8192):
            self.wfile = wfile
            self.chunkSize = chunkSize

            self.currChunkSize = 0
            self.chunks = []

        def _WriteChunk(self):
            if not self.wfile:
                return

            if self.currChunkSize > self.chunkSize:
                chunkSize = self.chunkSize
                leftoverBytes = self.currChunkSize - self.chunkSize
            else:
                chunkSize = self.currChunkSize
                leftoverBytes = 0

            # Write chunk header
            if six.PY3:
                chunkHeader = b"%x\r\n" % chunkSize
            else:
                chunkHeader = "%x\r\n" % chunkSize
            self.wfile.write(chunkHeader)

            chunks = self.chunks
            if leftoverBytes > 0:
                # Split the last chunk
                lastChunk = chunks.pop()
                chunks.append(lastChunk[:-leftoverBytes])
                leftoverChunks = [lastChunk[-leftoverBytes:]]
            else:
                leftoverChunks = []

            # Write chunks
            for chunk in chunks:
                self.wfile.write(chunk)
            self.wfile.write(b"\r\n")

            # Reset state
            self.currChunkSize = leftoverBytes
            self.chunks = leftoverChunks

        def write(self, buf):
            if not buf or not self.wfile:
                return

            if six.PY3 and isinstance(buf, six.string_types):
                buf = buf.encode()

            size = len(buf)
            self.currChunkSize += size

            self.chunks.append(buf)
            while self.currChunkSize >= self.chunkSize:
                self._WriteChunk()

        def close(self):
            if not self.wfile:
                return

            # Flush chunks
            self.flush()

            # Write ending zero bytes chunk
            self._WriteChunk()

            # TODO: Write trailer if needed

            # No more write
            self.wfile = None

        def __del__(self):
            self.close()

        def flush(self):
            # Flush buffer
            if self.currChunkSize:
                self._WriteChunk()

    class DeflateWriter:
        """Deflate (zlib) writer"""
        def __init__(self, wfile, compresslevel=5):
            import zlib
            self.wfile = wfile
            self.compress = zlib.compressobj(compresslevel, zlib.DEFLATED,
                                             zlib.MAX_WBITS)
            self.flushFlag = zlib.Z_SYNC_FLUSH
            self.closeFlushFlag = zlib.Z_FINISH

        def write(self, buf):
            if not buf or not self.wfile:
                return

            self.wfile.write(self.compress.compress(buf))

        def flush(self):
            if not self.wfile:
                return

            self.wfile.write(self.compress.flush(self.flushFlag))

        def close(self):
            if not self.wfile:
                return

            self.wfile.write(self.compress.flush(self.closeFlushFlag))
            self.wfile.close()

            # No more write
            self.wfile = None
            self.compress = None

        def __del__(self):
            self.close()

    # In all Python 3 versions up to 3.5, there is a bug that wfile.write
    # may write partial message. The bug is fixed in 3.6.
    # See https://bugs.python.org/review/26721/
    # This class works around the issue and make sure the complete message is
    # sent out.
    class _SafeWriter:
        def __init__(self, wfile):
            self.wfile = wfile

        def write(self, buf):
            if not buf or not self.wfile:
                return

            totalsent = 0
            buflen = len(buf)
            while totalsent < buflen:
                sent = self.wfile.write(buf[totalsent:])
                totalsent = totalsent + sent

    def _FindToken(self, tokens, findToken):
        """Find token from a comma separated tokens"""
        # Split token with ,
        for token in tokens.lower().split(","):
            # Split again with ;
            tokenAndVal = token.split(";", 1)
            if tokenAndVal[0].strip() == findToken:
                if len(tokenAndVal) > 1:
                    val = tokenAndVal[1].strip()
                else:
                    val = ""
                return (findToken, val)
        return None

    def do_POST(self):
        """Handle HTTP Post"""
        logging.debug("In do_POST: %s" % str(self.client_address))
        responseCode = 500
        response = ""
        closeConnection = False
        httpVersion = float(self.request_version.split("/")[1])

        # Handle SOAPAction (for request version in SOAPAction)
        # Can we have multiple SOAPAction??? No. I guess it is not valid
        soapAction = self.headers.get(_STR_SOAP_ACTION, "")
        wireVersion = _GetWireVersion(soapAction)

        cookies = SimpleCookie(self.headers.get('cookie'))
        VmomiSupport.GetHttpContext()['cookies'] = cookies

        # Look for non-identity transfer-encoding before content-length
        reqChunking = False
        gzipResponse = False
        deflateResponse = False
        respChunking = False
        if httpVersion >= 1.1:
            # Request chunking
            xferEncoding = self.headers.get("transfer-encoding", "")
            reqChunking = (self._FindToken(xferEncoding, "chunked")
                           is not None)

            # Accept-Encoding
            acceptEncoding = self.headers.get("accept-encoding", "")
            # Support gzip only for now
            gzipResponse = (self._FindToken(acceptEncoding, "gzip")
                            is not None)
            if not gzipResponse:
                deflateResponse = (self._FindToken(acceptEncoding, "deflate")
                                   is not None)

            # Response chunking
            te = self.headers.get("TE", "chunked")
            respChunking = (self._FindToken(te, "chunked") is not None)

        if reqChunking:
            request = self._ChunkedMessageBodyReader(self.rfile)
        else:
            # Get content length. Max is 16 M
            maxContentLen = 16 * 1024 * 1024
            content_len = maxContentLen

            # Get content length from header
            contentLength = self.headers.get("content-length")
            if contentLength:
                try:
                    contentLength = int(contentLength)
                    if contentLength > maxContentLen:
                        # Larger than max content length allowed.  Truncate
                        # length
                        logging.warn("Request content length %d > %d" % \
                                                   (contentLength, maxContentLen))
                        contentLength = maxContentLen
                    content_len = contentLength
                except TypeError:
                    pass
            request = _MessageBodyReader(self.rfile, content_len)

        try:
            # Invoke handler
            responseCode, response = self.server.InvokeHandler(
                request, wireVersion)
            _LogFilteredXML(response)
        except Exception as err:
            assert (responseCode == 500)

        try:
            # Char encoding
            encoding = "utf-8"

            # Determine if response is string or not
            isStringResponse = isinstance(response, six.text_type) or \
                               isinstance(response, six.binary_type)
            if isinstance(response, six.text_type):
                response = response.encode(encoding)

            # Send Header
            self.send_response(responseCode)
            self.send_header("content-type", "text/xml; charset=" + encoding)
            self.send_header("cache-control", "no-cache")
            cookies = VmomiSupport.GetHttpContext()['cookies']
            for cookie in cookies:
                headerValue = cookies[cookie].output(header='')
                self.send_header("set-cookie", headerValue)

            hasContentLength = isStringResponse and not (gzipResponse or \
                                                         deflateResponse or \
                                                         respChunking)
            if hasContentLength:
                # Content length
                responseLen = len(response)
                self.send_header("content-length", str(responseLen))
            else:
                if not respChunking:
                    closeConnection = True

            if httpVersion >= 1.1:
                # Chunking?
                if respChunking:
                    self.send_header("transfer-encoding", "chunked")

                # Gzip content?
                if gzipResponse:
                    self.send_header("content-encoding", "gzip")
                elif deflateResponse:
                    self.send_header("content-encoding", "deflate")

                # Close connection?
                if closeConnection:
                    self.send_header("connection", "close")
            else:
                if closeConnection:
                    self.close_connection = 1

            # End headers
            self.end_headers()

            # Send response
            wfile = self.wfile
            needClose = False
            chunkSize = 8192

            # Work around the partial write bug in python 3 versions up to 3.5
            if sys.version_info.major == 3 and sys.version_info < (3, 6):
                wfile = self._SafeWriter(wfile=wfile)

            # Handle chunking
            if respChunking:
                wfile = self._ChunkedMessageBodyWriter(wfile, chunkSize)
                # Need explicit close for chunked response
                needClose = True

            # Handle compression
            if gzipResponse:
                import gzip
                wfile = gzip.GzipFile(fileobj=wfile, mode="wb")
                needClose = True
            elif deflateResponse:
                wfile = self.DeflateWriter(wfile=wfile)
                needClose = True

            if response:
                if isStringResponse:
                    wfile.write(response)
                else:
                    while True:
                        chunk = response.read(chunkSize)
                        if not chunk:
                            break
                        wfile.write(chunk)
                wfile.flush()

            if needClose:
                wfile.close()

            # Cleanup
            if wfile != self.wfile:
                del wfile

            if not isStringResponse:
                response.close()
            del response

            logging.debug("Done do_POST: %s" % str(self.client_address))
        except Exception as err:
            LogException("Error: Send response exception: ", err)
            self.close_connection = 1

    def log_message(self, format, *args):
        """Override the BaseHTTPServer.BaseHTTPRequestHandler method to send
        the log message to the log file instead of stderr.
        """
        logging.info("%s - - %s" % (self.client_address, format % args))


class CgiBaseHandler(object):
    """Base class for handling CGI requests.
    Attributes:
      * headers  - A dict containing CGI headers and their values
      * rfile    - a File-compatible object exposing a read method.  Used for
                   reading the request XML string.
      * wfile    - a File-compatible object exposing a write method.  Used for
                   writing the CGI response including headers.
    """
    def __init__(self, headers, rfile, wfile, stubs=None, authChecker=None):
        self.headers = headers
        self.rfile = rfile
        self.wfile = wfile
        self.stubs = stubs
        self.authChecker = authChecker

    @staticmethod
    def _CgiResponse(msg='',
                     statusmsg='500 Internal Server Error',
                     contenttype='text/plain',
                     extraheaders=''):
        return 'Content-Type: %s\r\nStatus: %s\r\n%s\r\n%s\r\n' % (
            contenttype, statusmsg, extraheaders, msg)

    # Handle one CGI request
    def HandleRequest(self):
        """protocol-independent CGI request handler.  Reads CONTENT_LENGTH bytes
        from rfile, processing the SOAP request using version and stubs.
        The REQUEST_METHOD must be POST.
        The response is written to wfile.
        If the REQUEST_METHOD is not POST, the content length is negative,
        or a fault happened, appropriate error responses are returned.
        Returns:
            A boolean, True if the response is a fault.
        """
        request_method = self.headers['REQUEST_METHOD']
        if request_method != 'POST':
            if 'REQUEST_URI' in self.headers:
                request_uri = self.headers['REQUEST_URI']
            else:
                request_uri = '%s/%s?%s' % (self.headers.get(
                    'SCRIPT_NAME', ''), self.headers.get(
                        'PATH_INFO', ''), self.headers.get('QUERY_STRING', ''))
            msg = ('HTTP method %s not supported for URL: %s' %
                   (request_method, request_uri))
            logging.warning(msg)
            self.wfile.write(
                self._CgiResponse(msg,
                                  statusmsg='405 Method Not Allowed',
                                  extraheaders='Allow: POST\r\n'))
            self.wfile.flush()
            return True

        # Get SOAP request
        contentlen = int(self.headers['CONTENT_LENGTH'])
        if contentlen < 0:
            self.wfile.write(
                self._CgiResponse(statusmsg='400 Bad Request',
                                  msg='Content-Length is a negative value'))
            self.wfile.flush()
            return True
        soapRequest = _MessageBodyReader(self.rfile, contentlen)

        # Handle request
        wireVersion = _GetWireVersion(self.headers.get('HTTP_SOAPACTION', ''))
        isFault, response = GetSoapHandler(self.stubs).HandleRequest(
            soapRequest, wireVersion)
        _LogFilteredXML(response)

        # Compose response string
        if isFault:
            status = '500 Internal Server Error'
        else:
            status = '200 OK'
        self.wfile.write(
            self._CgiResponse(statusmsg=status,
                              msg=response,
                              contenttype='text/xml').encode((UTF8)))
        self.wfile.flush()
        return isFault


# Thread pool for the HTTP server
class HttpServerThreadPoolMixin(socketserver.ThreadingMixIn):
    """Pooled SocketServer ThreadingMixin"""
    @classmethod
    def SetMaxWorkers(cls, workers=8):
        """Set the threadpool size.
        0 - means infinite (i.e.) each client connection is handled in a new
        thread.
        """
        cls.thread_max_workers = workers
        # Because of persistent HTTP connections, there is no point
        # in having more # of connections queued than the # of available
        # workers. However, to maintain backward compatibility, max queued
        # limit is set to workers only when changing workers to larger than
        # max queue items.
        if workers > cls.thread_pool_max_queued_works:
            cls.thread_pool_max_queued_works = workers

    @classmethod
    def init(cls, maxWorkers=8, maxQueuedWorks=256):
        """Init all class variables"""
        cls.thread_quit_request = object()
        cls.thread_max_workers = maxWorkers
        cls.thread_pool_workers = 0
        cls.thread_pool_worker_list = None
        cls.thread_pool_workitems = None
        cls.thread_pool_max_queued_works = maxQueuedWorks

    def process_request_worker(self):
        """Process request worker"""
        while self.thread_looping:
            try:
                # Wait for request
                # TODO: Stop thread if it has been idle for a long time
                args = self.thread_pool_workitems.get()
                if args == self.thread_quit_request:
                    # It's a request to exit the loop.
                    break
                logging.debug("Handling workitem: " + str(args))

                # Start work
                socketserver.ThreadingMixIn.process_request_thread(self, *args)
                logging.debug("Done workitem: " + str(args))
            except Exception as err:
                LogException("Thread caught exception: ", err)
                time.sleep(1)
        logging.debug("%s:thread pool worker exiting" %
                      threading.currentThread())

    def process_request(self, request, client_address):
        """Use a worker thread from pool to process this request
        Note: This is running in serialized context
        """

        # When max number of workers are unlimited then simply forward the
        # request to ThreadingMixIn (parent) class.
        if self.thread_max_workers == 0:
            socketserver.ThreadingMixIn.process_request(
                self, request, client_address)
            return

        if self.thread_pool_workitems == None:
            # First time init
            self.thread_pool_workitems = queue.Queue(0)
            self.thread_pool_worker_list = []
            self.thread_looping = True

        if self.thread_pool_workers < self.thread_max_workers:
            thd = threading.Thread(target=self.process_request_worker)
            thd.setDaemon(True)
            thd.start()
            self.thread_pool_worker_list.append(thd)
            self.thread_pool_workers += 1

        # Bound work items length
        workItem = (request, client_address)
        qSize = self.thread_pool_workitems.qsize()
        if qSize >= self.thread_pool_max_queued_works:
            # Drop request
            logging.error("Too many queued work (%d) Dropping workitem: %s" % \
                                                           (qSize, str(workItem)))
            self.close_request(request)

            # A crude way to prevent DoS: sleep
            time.sleep(1)
            return

        # Put work item into q to wake up worker thread
        self.thread_pool_workitems.put(workItem)
        logging.debug("Queued workitem: " + str(workItem))

    # Shutdown the threads in the threadpool and wait for them to exit.  The
    # BaseServer.shutdown() method should be called before calling this method.
    # The worker threads are shutdown by sending them a "quit" request and then
    # waiting for them to exit up until the given timeout.  No extra measures
    # are taken to interrupt their current processing.  It is expected that the
    # threads are relatively short lived or there is a low likelihood that
    # something bad will happen if the process exits in the middle of
    # processing.
    #
    #  @param timeout The number of seconds to wait for each worker thread.
    def shutdown_threadpool(self, timeout=1.0):
        # When max number of workers are unlimited there is no threadpool
        # to shutdown
        if self.thread_max_workers == 0:
            return
        logging.info("shutting down thread pool")
        self.thread_looping = False
        if self.thread_pool_worker_list:
            # Only go through the following operations
            # if thread_pool_worker_list is initialized.
            for _worker in self.thread_pool_worker_list:
                self.thread_pool_workitems.put(self.thread_quit_request)

            for worker in self.thread_pool_worker_list:
                worker.join(timeout)


class SoapHttpServer(HttpServerThreadPoolMixin, HTTPServer):
    """SOAP HTTP server"""
    @classmethod
    def SetMaxWorkers(cls, workers=8):
        logging.debug("Setting max workers: %s" % str(workers))
        HttpServerThreadPoolMixin.SetMaxWorkers(workers)

    # Init HttpServerThreadPoolMixin
    HttpServerThreadPoolMixin.init()

    # SOAP stubs
    soapStubs = None

    # SSL parameters
    ssl = False
    sslArgs = {}
    ssl_wrap_socket = None

    # SOAP handler
    #
    # @param request the SOAP request
    # @param version the request version (namespace/versionId)
    # @return a tuple of (isFault, SOAP response)
    def InvokeHandler(self, request, version=None):
        """SOAP handler"""
        isFault, response = GetSoapHandler(self.soapStubs).HandleRequest(
            request, version)
        return isFault and 500 or 200, response

    # Set SSL arguments
    #
    # @param  keyfile Server PEM private key file
    # @param  certfile Server PEM certificate file
    # @param  kwargs Other ssl arguments
    def SetSSL(self, keyfile, certfile, **kwargs):
        try:
            import ssl
            self.ssl = True

            self.sslArgs = kwargs.copy()

            # Override ssl arguments
            self.sslArgs.setdefault("server_side", True)
            self.sslArgs.setdefault("keyfile", keyfile)
            self.sslArgs.setdefault("certfile", certfile)

            self.ssl_wrap_socket = ssl.wrap_socket
        except ImportError as err:
            logging.error("Failed to import ssl. Ssl not supported")

    # Override get_request in BaseHTTPServer.HTTPServer
    #
    # @returns request and client address
    def get_request(self):
        newSock, fromAddr = HTTPServer.get_request(self)
        logging.debug("Connection from: %s" % str(fromAddr))

        # Disable nagle
        if newSock:
            try:
                import socket
                newSock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass

        if self.ssl:
            newSock = self.ssl_wrap_socket(newSock, **self.sslArgs)

        return newSock, fromAddr

    # Shutdown the server and the worker threads.
    def shutdown(self):
        HTTPServer.shutdown(self)
        self.shutdown_threadpool()


# HTTP SOAP server over UNIX socket
# Only available on UNIX-like systems
try:
    # Cleanup UNIX socket
    def CleanupUnixSocket(file):
        try:
            os.unlink(file)
        except Exception as err:
            pass

    from socketserver import UnixStreamServer

    class SoapHttpServerOverUnixSocket(UnixStreamServer, SoapHttpServer):
        pass
except ImportError as err:
    class SoapHttpServerOverUnixSocket:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError("Unix stream server not available")


# SCGI over anonymous pipe server class
class ScgiServer(object):
    """SCGI server.
    For more info, see http://python.ca/scgi/protocol.txt
    """
    def __init__(self, rfile=None, wfile=None, stubs=None, authChecker=None):
        """Constructs an instance of ScgiServer.
        Parameters:
            * rfile - The input File object to read requests from.  If None,
                      defaults to sys.stdin.
            * wfile - The output File object to write responses to.  If None,
                      defaults to sys.stdout.
            * stubs - SOAP stub adapter object, used for remote invocation.
        """
        self.rfile = rfile
        self.wfile = wfile
        self.stubs = stubs
        self.authChecker = authChecker
        self.debugout = None
        if rfile is None:
            self.rfile = getattr(sys.stdin, 'buffer', sys.stdin)
        if wfile is None:
            self.wfile = getattr(sys.stdout, 'buffer', sys.stdout)
            # Stop errant print statements from affecting output to stdout
            self.debugout = BytesIO()
            sys.stdout = self.debugout

        # NOTE: On Windows, need to set the input/output to binary mode to
        # prevent \n <--> \r\n translation.  The translation messes
        # up netstring output as the string length count becomes inaccurate.
        if sys.platform == "win32":
            import msvcrt
            msvcrt.setmode(self.wfile.fileno(), os.O_BINARY)
            msvcrt.setmode(self.rfile.fileno(), os.O_BINARY)

    # Handle one request.  May be repeated in a loop.
    def _HandleOneSCGIRequest(self):
        """Handles one SCGI request from filein.
        Returns:
            The response string to write out to the output stream, or
            '' if EOF has been reached on filein.
        """
        try:
            req = Scgi.ScgiRequest.Parse(self.rfile, readmessage=False)
            logging.debug('Got SCGI request with headers: %s' % (req.headers))
            responsefile = BytesIO()
            handler = CgiBaseHandler(req.headers, self.rfile, responsefile,
                                     self.stubs, self.authChecker)
            handler.HandleRequest()
            if self.debugout:
                debugstr = self.debugout.getvalue()
                if debugstr:
                    logging.debug(debugstr)
                    self.debugout.close()
                    self.debugout = BytesIO()
                    sys.stdout = self.debugout
            return responsefile.getvalue()
        except Scgi.Scgi_EOF:
            return b''
        except KeyError as e:
            return CgiBaseHandler._CgiResponse('Missing header key: %s' %
                                               (e)).encode(UTF8)
        except Scgi.ScgiError as e:
            return CgiBaseHandler._CgiResponse('SCGI parsing error: %s' %
                                               (e)).encode(UTF8)
        except Exception as e:
            import traceback
            return CgiBaseHandler._CgiResponse(
                'General exception: %s\n%s' %
                (e, traceback.format_exc())).encode(UTF8)

    def serve_forever(self):
        """Main server loop.
        Exits if the input pipe is closed.
        """
        while True:
            resp = self._HandleOneSCGIRequest()
            if not resp:
                logging.info('SCGI input pipe has been closed, exiting server')
                break
            Scgi.WriteNetString(self.wfile, resp)
            self.wfile.flush()


# Server main class
class ServerMain:
    """The python mo server main"""

    def __init__(self, authChecker=None):
        self.authChecker = authChecker
        self.options = None
        self.remainingOptions = None
        self.httpd = None
        self.stdin = getattr(sys.stdin, 'buffer', sys.stdin)
        self.stdout = getattr(sys.stdout, 'buffer', sys.stdout)

    # Start server
    #
    # @param argv the argument list
    def Start(self, options, remainingOptions):
        """Start the server"""

        # Save internal options
        self.options = options
        self.remainingOptions = remainingOptions

        # Run server
        self._RunServer()

    # Read xml helper. Avoid reading the whole request into memory
    class _XmlFileReader:
        """Read xml until eof"""
        def __init__(self, rfile, buf):
            self.rfile = rfile
            self.buf = buf

        def read(self, bytes):
            """Read bytes"""
            bufLen = len(self.buf)
            if bufLen > 0:
                if bufLen < bytes:
                    ret = b"".join([self.buf, self.rfile.read(bytes - bufLen)])
                    self.buf = b""
                else:
                    ret = self.buf[:bytes]
                    self.buf = self.buf[bytes:]
                return ret
            else:
                return self.rfile.read(bytes)

    # Get SOAP request
    #
    # @param  fileIn Input file handle
    # @return (soapRequest, version) (SOAP request, SOAP request version)
    def _GetSoapRequest(self, fileIn):
        """Get SOAP request from file handle"""
        soapRequest = ""
        wireVersion = None
        while True:
            line = fileIn.readline()
            if not line:
                break
            line = line.strip()

            if line.startswith(b"<?xml"):
                soapRequest = self._XmlFileReader(fileIn, line)
                break
            elif line.startswith(_STR_SOAP_ACTION_BYTES + b":"):
                # Get SOAPAction
                urn = line[len(_STR_SOAP_ACTION_BYTES) + 1:].decode(UTF8)
                wireVersion = _GetWireVersion(urn)

        return soapRequest, wireVersion

    # Run server
    def _RunServer(self):
        """Internal server start function
        Note that self.options can be passed in via an API and not necessarily
        via optparse.  So, please make sure to use getattr while accessing
        'optional' fields
        """
        if getattr(self.options, 'rhost', None):
            from pyVmomi.SoapAdapter import SoapStubAdapter
            proxyStub = SoapStubAdapter(host=self.options.rhost,
                                        port=int(self.options.rport),
                                        ns=self.options.rns,
                                        path=self.options.rpath)
            stubs = {'default': (None, proxyStub)}
        else:
            stubs = None

        if getattr(self.options, 'interactive', False):
            # Handle SOAP request from stdin
            from six.moves import cStringIO

            # TODO: Verify logging is currently redirected to file
            # logging.disable(logging.CRITICAL + 1)

            # Turn off logging to stdout & stderr
            orgSysStdout = sys.stdout
            orgSysStderr = sys.stderr
            debugOut = cStringIO()

            # DEBUG: Remove the next 2 lines to show debug output
            sys.stdout = debugOut
            sys.stderr = debugOut

            # Get SOAP request
            soapRequest, wireVersion = self._GetSoapRequest(self.stdin)

            # Handle request
            isFault, response = GetSoapHandler(stubs).HandleRequest(
                soapRequest, wireVersion)

            # Write response after setting stdout back to original
            sys.stdout = orgSysStdout
            sys.stderr = orgSysStderr
            # print response.replace("\n","") # Strip linefeed
            print(response)
            sys.stdout = debugOut
            sys.stderr = debugOut

            # logging will crash if I close the debugOut with logging to stdout
            # debugOut.close()
            sys.exit(isFault and 1 or 0)
        elif getattr(self.options, 'file', None):
            # Handle SOAP request from file

            try:
                # Get SOAP request
                fileIn = open(self.options.file, "rb")
            except IOError:
                message = "Cannot open " + str(self.options.file)
                logging.error(message)
                print(message)
                return

            # Get SOAP request
            soapRequest, wireVersion = self._GetSoapRequest(fileIn)

            # Handle request
            isFault, response = GetSoapHandler(stubs).HandleRequest(
                soapRequest, wireVersion)
            fileIn.close()
            print(response)
            sys.exit(isFault and 1 or 0)
        elif getattr(self.options, 'cgi', False):
            logging.info("Starting CGI server on stdin/stdout")
            handler = CgiBaseHandler(os.environ, self.stdin, self.stdout,
                                     stubs)
            try:
                isFault = handler.HandleRequest()
            except KeyError as err:
                isFault = True
                print((handler._CgiResponse("Missing environment variable " +
                                            str(err))))
            sys.exit(isFault and 1 or 0)
        elif getattr(self.options, 'scgi', False):
            import Scgi
            global Scgi
            logging.info("Starting SCGI server on stdin/stdout")
            scgid = ScgiServer(stubs=stubs)
            scgid.serve_forever()
            sys.exit(0)
        else:
            # Handle SOAP request from HTTP
            if getattr(self.options, 'unix', None):
                addr = self.options.unix
                soapHttpdConstructor = SoapHttpServerOverUnixSocket
            elif getattr(self.options, 'port', None):
                # "" is the same as local host
                h = getattr(self.options, 'host', "")
                addr = (h, int(self.options.port))
                soapHttpdConstructor = SoapHttpServer
            else:
                print("Must specific a socket address")
                return

            logging.info("Listening on %s" % str(addr))
            soapHttpd = soapHttpdConstructor(addr, GeneralHttpHandler)
            self.httpd = soapHttpd
            if soapHttpdConstructor == SoapHttpServerOverUnixSocket:
                # Make sure we cleanup the unix socket file
                import atexit
                atexit.register(CleanupUnixSocket, addr)

            # set the custom worker thread pool size
            if soapHttpdConstructor == SoapHttpServer:
                soapHttpd.SetMaxWorkers(self.options.max_workers)

            keyfile = getattr(self.options, 'keyfile', None)
            certfile = getattr(self.options, 'certfile', None)
            if keyfile and certfile:
                soapHttpd.SetSSL(keyfile, certfile)
            soapHttpd.soapStubs = stubs
            soapHttpd.serve_forever()


def Run(authChecker=None):
    """Server main"""

    try:
        ServerMain(authChecker).Start(gCmdOptions, gCmdRemainingOptions)
    except KeyboardInterrupt:
        print('^C received, shutting down the server')
    except Exception as err:
        message = str(err)
        if message:
            print(message)
            logging.info(message)


if __name__ == "__main__":
    Run()
