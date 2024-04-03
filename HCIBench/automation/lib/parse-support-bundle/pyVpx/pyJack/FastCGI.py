#!/usr/bin/env python
"""
Copyright 2010-2020 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is the python implementation of the FastCGI wire protocol.
It conforms to the FastCGI specification v1.0:
http://www.fastcgi.com/drupal/node/6?q=node/22#S8
"""
__author__ = "VMware, Inc"

import struct
import logging
import six

log = logging.getLogger('FastCGI')


class FCGIError(Exception):
    pass


class FCGIFormatError(FCGIError):
    pass


class FCGI_Header(object):
    """Defines a FastCGI header record and the associated constants.
    From the spec:
        typedef struct {
            unsigned char version;
            unsigned char type;
            unsigned char requestIdB1;
            unsigned char requestIdB0;
            unsigned char contentLengthB1;
            unsigned char contentLengthB0;
            unsigned char paddingLength;
            unsigned char reserved;
        } FCGI_Header;

    Attributes:
      * version    - One of the FCGI_VERSION constants identifying protocol version
      * headerType - One of the FCGI_ type constants; record type.
      * requestId  - An integer identifying the FastCGI request ID; used to
                     multiplex requests or handle multiple threads.
      * contentLength - An integer; length of the data itself.
      * paddingLength - An integer 0-255; # of padding bytes following the data
    """
    # Number of bytes in a FCGI_Header.  Future versions of the protocol
    # will not reduce this number.
    FCGI_HEADER_LEN = 8

    # Value for version component of FCGI_Header
    FCGI_VERSION_1 = 1

    # Values for type component of FCGI_Header
    FCGI_BEGIN_REQUEST = 1
    FCGI_ABORT_REQUEST = 2
    FCGI_END_REQUEST = 3
    FCGI_PARAMS = 4
    FCGI_STDIN = 5
    FCGI_STDOUT = 6
    FCGI_STDERR = 7
    FCGI_DATA = 8
    FCGI_GET_VALUES = 9
    FCGI_GET_VALUES_RESULT = 10
    FCGI_UNKNOWN_TYPE = 11
    FCGI_MAXTYPE = FCGI_UNKNOWN_TYPE

    # Values for requestId component of FCGI_Header
    FCGI_NULL_REQUEST_ID = 0

    _packformat = "!BBHHBx"

    def __init__(self, **kwargs):
        """Constructor for FCGI_Header."""
        self.version = kwargs.pop('version', self.FCGI_VERSION_1)
        self.headerType = kwargs.pop('headerType', self.FCGI_UNKNOWN_TYPE)
        self.requestId = kwargs.pop('requestId', self.FCGI_NULL_REQUEST_ID)
        self.contentLength = kwargs.pop('contentLength', 0)
        self.paddingLength = kwargs.pop('paddingLength', 0)

    def ToString(self):
        return struct.pack(self._packformat, self.version, self.headerType,
                           self.requestId, self.contentLength,
                           self.paddingLength)

    @classmethod
    def FromString(cls, str):
        """Creates a FCGI_Header instance from a string representing the
        bytes of the header.
        Parameters:
         * str - The string, of length FCGI_HEADER_LEN, with the header bytes
                 to parse
        Raises:
            FCGIFormatError  - if the stream is not a valid FCGI record
        """
        try:
            (vers, htype, reqid, clen,
             plen) = struct.unpack(cls._packformat, str)
        except struct.error as e:
            raise FCGIFormatError("Unable to parse header bytes '%s': %s" %
                                  (str, e))

        return cls(version=vers,
                   headerType=htype,
                   requestId=reqid,
                   contentLength=clen,
                   paddingLength=plen)


class FCGI_NameValuePairs(dict):
    """Represents a stream of FastCGI name-value pairs."""
    @staticmethod
    def _lentostring(len):
        assert len >= 0
        if len <= 127:
            return struct.pack('B', len)
        else:
            return struct.pack('!I', len | 0x80000000)

    @staticmethod
    def _lenfromstring(str, index):
        firstbyte = ord(str[index])
        if firstbyte & 0x80:
            (uint32, ) = struct.unpack('!I', str[index:index + 4])
            return (uint32 & 0x7fffffff, 4)
        else:
            return (firstbyte, 1)

    def ToString(self):
        """Serializes key-value pairs into FastCGI format string"""
        str = ""
        for key, val in six.iteritems(self):
            str += self._lentostring(len(key))
            str += self._lentostring(len(val))
            str += key
            str += val
        return str

    @classmethod
    def FromString(cls, str):
        """Creates an instance of FCGI_NameValuePairs from the string.
        Parameters:
         * str - The buffer containing FastCGI name value pairs.
        """
        keyvalpairs = list()
        index = 0
        while index < len(str):
            keylen, nbytes = self._lenfromstring(str, index)
            index += nbytes
            vallen, nbytes = self._lenfromstring(str, index)
            index += nbytes
            keyvalpairs.append(str[index:index + keylen])
            index += keylen
            keyvalpairs.append(str[index:index + vallen])
            index += vallen
        return cls(keyvalpairs)


class FCGIRecord(object):
    """An abstract base class for various FCGI record types.
    Each FCGI record consists of a header and a body.
    """
    # of bytes to align
    ALIGN = 8

    def __init__(self, **kwargs):
        self.header = kwargs.pop('header', None)
        self.body = kwargs.pop('body', None)

    @classmethod
    def ReadBody(cls, str):
        pass

    def WriteToFile(self, fp):
        """Writes the entire record to a File object."""
        bodystr = self.body.ToString()
        self.header.contentLength = len(bodystr)
        padding = (bodystr + (ALIGN - 1)) & ~(ALIGN - 1)
        self.header.paddingLength = padding
        fp.write(self.header.ToString())
        fp.write(self.body.ToString())
        fp.write(" " * padding)

    @classmethod
    def ReadFromFile(cls, fp):
        """Creates and returns an instance of FCGIRecord
        or a descendant class based on the header type.
        """
        header = FCGI_Header.FromString(fp.read(FCGI_Header.FCGI_HEADER_LEN))
        cls = HeaderTypeClassMap[header.headerType]
        body = cls.ReadBody(fp.read(header.contentLength))
        fp.read(header.paddingLength)
        return cls(header=header, body=body)
