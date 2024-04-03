#!/usr/bin/env python
"""
Copyright 2010-2022 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is the python implementation of the SCGI wire protocol.
http://www.python.ca/scgi/protocol.txt
With an enhancement to make the response work for stdin/stdout.
"""
__author__ = "VMware, Inc"

from pyVmomi import SoapAdapter, VmomiSupport
import re
import subprocess
from io import StringIO


class ScgiError(Exception):
    pass


class Scgi_EOF(ScgiError):
    pass


# To support microsoft libraries sending requests to our SCGI servers
# we need to be ready to decode the UTF8 BOM.  The utf-8-sig codec
# intelligently deals with UTF8 encoded strings with or without the BOM.
UTF8sig = 'utf-8-sig'
UTF8 = 'utf8'


def ReadNetString(fp):
    """Reads a net string from the File object fp, returning the string in
      unicode.
      A net string has the format  <len>:<str>,
      where <len> is decimal of the length of <str>, and comma ends the string.
      Returns:
         The unicode string contained in the netstring, or '' if no more chars
         can be read from the file.
      Raises:
         ScgiError - if the initial <len> cannot be converted to a number, or
                     the : does not occur after 10 bytes.
   """
    lenstr = ''
    lenstr = fp.read(10)
    try:
        lenstr, netstr = lenstr.split(b':', 1)
        lenstr = lenstr.decode(UTF8sig)
    except ValueError:
        raise ScgiError("Invalid netstring: unable to decode <len> (%s)" %
                        (lenstr))

    try:
        strlen = int(lenstr)
    except Exception as e:
        raise ScgiError("Could not convert [%s] to a number: %s" % (lenstr, e))

    netstr += fp.read(strlen - len(netstr))
    netstr = netstr.decode(UTF8)
    netstr += fp.read(1).decode(UTF8)
    lastchar = netstr[-1]
    if lastchar != ',':
        raise ScgiError("Netstring terminated with '%s' instead of ','" %
                        (lastchar))
    return netstr[:-1]


def WriteNetString(fp, string):
    """Writes a string as a net string to the file object fp.
   """
    fp.write('{}:'.format(len(string)).encode(UTF8))
    fp.write(string)
    fp.write(b',')


class ScgiRequest(object):
    """Represents an SCGI Request.
      Attributes:
         * headers - a dict containing the key/value pairs of the request
                     header.  NOTE: The keys CONTENT_LENGTH and SCGI do not
                     need to be part of this header.
         * message - the request message.
   """
    def __init__(self, headers=None, message=""):
        self.headers = headers
        if not self.headers:
            self.headers = dict()
        self.message = message

    def Write(self, fp):
        """Writes out the SCGI request to the file object fp."""
        kvlist = ['CONTENT_LENGTH', str(len(self.message)), 'SCGI', '1']
        for key, val in self.headers.items():
            if key not in ('CONTENT_LENGTH', 'SCGI'):
                kvlist.extend([key, val])
        WriteNetString(fp, ('\x00'.join(kvlist) + '\x00').encode(UTF8))
        fp.write(self.message)

    @classmethod
    def Parse(cls, fp, readmessage=True):
        """Reads in a SCGI request from the file object fp and creates an
         instance of ScgiRequest.
         Parameters:
         * fp          - Input file object, must support read()
         * readmessage - If True, the request message is read in.  If not,
                         fp will be left at the beginning of the message and
                         the ScgiRequest will be initialized with an empty
                         message.
         Raises:
            Scgi_EOF  - if the end of file has been reached
            ScgiError - Some other error in reading the headers
      """
        headerstr = ReadNetString(fp)
        if headerstr == '':
            raise Scgi_EOF()
        # headerstr has this format: key1\x00val1\x00key2\x00val2\x00...
        headerlist = headerstr.rstrip('\x00').split('\x00')
        headers = dict(list(zip(headerlist[::2], headerlist[1::2])))
        if not readmessage:
            return cls(headers=headers)
        try:
            reqlen = int(headers['CONTENT_LENGTH'])
        except Exception as e:
            raise ScgiError(
                "Unable to extract CONTENT_LENGTH out of headers: %s" % (e))

        return cls(headers=headers, message=fp.read(reqlen))


#  SOAP-over-stdio SCGI stub adapter object
#  Enables long-running SCGI server processes... much faster than
#  CGI for PyVmomiServer-based VMOMI handlers when called frequently
#  The process is forked when this object is constructed and stdin/stdout
#  kept open.
#
#  NOTE: In the future, explore using asynchat
#
class SoapScgiCmdStubAdapter(SoapAdapter.SoapStubAdapterBase):
    # Constructor
    #
    # @param self self
    # @param cmd command to execute
    # @param ns API namespace
    def __init__(self, cmd, version='vim.version.version9'):
        SoapAdapter.SoapStubAdapterBase.__init__(self, version=version)
        self.cmd = cmd
        self.systemError = SoapAdapter.GetVmodlType('vmodl.fault.SystemError')
        argv = self.cmd.split()
        self.p = subprocess.Popen(argv,
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE)

    # Invoke a managed method
    #
    # @param self self
    # @param mo the 'this'
    # @param info method info
    # @param args arguments
    def InvokeMethod(self, mo, info, args):
        req = self.SerializeRequest(mo, info, args)
        scgireq = ScgiRequest(
            {
                'REQUEST_METHOD': 'POST',
                'HTTP_SOAPACTION': self.versionId[1:-1]
            },
            message=req)
        scgireq.Write(self.p.stdin)
        self.p.stdin.flush()

        try:
            outText = ReadNetString(self.p.stdout)
        except Scgi_EOF:
            errText = "Unexpected EOF reading from process, maybe process died"
            raise self.systemError(msg=errText, reason=errText)
        except Exception as e:
            errText = "Error parsing output from SCGI process: %s" % (e)
            raise self.systemError(msg=errText, reason=errText)

        (responseHeaders,
         responseBody) = SoapAdapter.ParseHttpResponse(outText)

        # Parse status code from response headers [Status: 200 OK]
        error = False
        obj = None
        statusmatch = re.search(r'Status:\s+(\d+)\s+(.+)', responseHeaders)
        if not statusmatch:
            errText = "Could not find SOAP status in SOAP headers (%s)" % (
                responseHeaders)
            raise self.systemError(msg=errText, reason=errText)
        elif statusmatch.group(1) != '200':
            errText = statusmatch.group(2).rstrip()
            error = True

        # SoapResponseDeserializer can only handle XML
        if 'text/xml' in responseHeaders:
            try:
                obj = SoapAdapter.SoapResponseDeserializer(self).Deserialize(
                    responseBody, info.result)
            except:
                errText = "Failure parsing SOAP response (%s)" % (outText)
                raise self.systemError(msg=errText, reason=errText)

        if not error:
            return obj
        elif obj is None:
            raise self.systemError(msg=errText, reason=responseBody)
        else:
            raise obj


# Test code: input a bunch of messages, write them out as requests,
# read them back
if __name__ == "__main__":
    try:
        import readline
    except ImportError:  # readline is UNIX only
        pass

    messages = list()
    inputmsg = input("Message to send [Enter to stop]: ")
    while inputmsg:
        messages.append(inputmsg)
        inputmsg = input("Message to send [Enter to stop]: ")

    req = ScgiRequest(headers={'SOAPACTION': 'somesoapclass'})
    fp = StringIO()
    for msg in messages:
        req.message = msg
        req.Write(fp)

    fp.seek(0)
    while True:
        print("------")
        try:
            got = ScgiRequest.Parse(fp)
            print(got.headers)
            print(got.message)
        except Scgi_EOF:
            print("-- Reached EOF --")
            break
