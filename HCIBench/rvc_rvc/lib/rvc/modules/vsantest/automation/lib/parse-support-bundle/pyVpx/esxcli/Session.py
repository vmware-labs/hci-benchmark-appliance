#!/usr/bin/env python
"""
Copyright (c) 2008-2022 VMware, Inc.  All rights reserved.
-- VMware Confidential

This module handles vim sessions.
"""
__author__ = "VMware, Inc"

import sys
import os
import re
import ssl
import time
from Formatters import isPython3

if isPython3():
   import http.client as http_client
else:
   import httplib as http_client

import hashlib
import base64

__all__ = [
   "GetDefaultEncodings",
   "IsInVisor",
   "LogException",
   "Session",
   "SessionArgumentException",
   "SessionException",
   "SessionLoginException",
   "SessionOptions",
]

# Note: Python 2.2 do not have logging
import logging

from pyVmomi import vmodl, vim, SoapAdapter, cis, SoapStubAdapter
from pyVmomi.Security import ThumbprintMismatchException

CIS_VMODL_VERSION = 'cis.cm.version.version1'
CM_MOID = 'ServiceManager'

SSO_PRODUCT_ID = 'com.vmware.cis'
SSO_TYPE_ID = 'cs.identity'
EP_SSO_PROTOCOL = 'wsTrust'
EP_SSO_TYPE_ID = 'com.vmware.cis.cs.identity.sso'

VC_PRODUCT_ID = 'com.vmware.cis'
VC_TYPE_ID = 'vcenterserver'
EP_VC_PROTOCOL = 'vmomi'
EP_VC_TYPE_ID = 'com.vmware.vim'


# Raw SOAP request to LookupServiceRegistration.list() method
# for getting STS (SSO) URL and VC URL from Lookup Service using pyCurl.
LSREG_LIST_SOAP = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope  xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
                   xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" >
<soapenv:Body>
   <List>
      <_this type="LookupServiceRegistration">ServiceRegistration</_this>
      <filterCriteria>
         <serviceType>
            <product>%s</product>
            <type>%s</type>
         </serviceType>
         <endpointType>
            <protocol>%s</protocol>
            <type>%s</type>
         </endpointType>
      </filterCriteria>
   </List>
</soapenv:Body>
</soapenv:Envelope>
'''


# Returns the SHA-* algorithm used to generate the thumbprint of such length.
# Or None if the thumbprint length didn't match any of the supported SHA variants.
def get_sha_variant(thumbprint_length):
    # SHA-1:   20 pairs of hex digits possibly with colons between each pair.
    # SHA-256: 32 pairs of hex digits possibly with colons between each pair.
    # SHA-512: 64 pairs of hex digits possibly with colons between each pair.
    if thumbprint_length in [20 * 2, 20 * 3 - 1]:
       return 1
    if thumbprint_length in [32 * 2, 32 * 3 - 1]:
       return 256
    if thumbprint_length in [64 * 2, 64 * 3 - 1]:
       return 512
    return None  # Making this explicit


# Returns the proper SHA-* hash function that was
# used for the thumbprint depending on its length.
def get_hasher_by_thumbprint(thumbprint):
   sha = get_sha_variant(len(thumbprint))
   if sha == 1:
      return hashlib.sha1
   if sha == 256:
      return hashlib.sha256
   if sha == 512:
      return hashlib.sha512
   # Default to SHA-256 if the given thumbprint's length
   # matched none of the supported versions.
   return hashlib.sha256


class ThumbprintVerifiedHTTPSConnection(http_client.HTTPSConnection):
   '''
   An HTTPSConnection class that verifies the server's certificate by thumbprint
   on connect. Usually used when using ssl._create_unverified_context() as
   value for 'context' argument.
   '''
   def __init__(self, *args, **kwargs):
      '''
      Initializer. See HTTPSConnection for other arguments than 'thumbprint'.

      @type    thumbprint: C(str)
      @param   thumbprint: Expected SHA-1/SHA-256/SHA-512 thumbprint of the server
                           certificate. If None, then no thumbprint verification is done.
      '''
      def valid_thumbprint_length(l): return l in [40, 64, 128]
      self.thumbprint = kwargs.pop('thumbprint')
      if self.thumbprint is not None:
         self.thumbprint = self.thumbprint.replace(":", "").lower()
         if not valid_thumbprint_length(len(self.thumbprint)):
            raise SessionException(
               "Invalid SHA-1/SHA-256/SHA-512 thumbprint: %s" % self.thumbprint)
      http_client.HTTPSConnection.__init__(self, *args, **kwargs)

   def connect(self):
      http_client.HTTPSConnection.connect(self)
      if self.thumbprint:
         peerCert = self.sock.getpeercert(True)
         hasher = get_hasher_by_thumbprint(self.thumbprint)
         peerTp = hasher(peerCert).hexdigest().lower()
         if self.thumbprint != peerTp:
            raise ThumbprintMismatchException(expected=self.thumbprint, actual=peerTp)


## Create ssl.SSLContext object based on the specified arguments.
#
#    If none of the arguments is set returns None.
#
# @param cacertsFile - if set use default SSL context with 'cafile'.
#                      This parameter overrides the parameter 'thumbprint'.
#
# @param thumbprint - if set use unverified SSL context.
#                     This should be used only when we'll verify the server
#                     certificate by thumbprint.
#
def CreateSslContext(cacertsFile, thumbprint):
   context = None
   if cacertsFile and hasattr(ssl, 'create_default_context'):
      context = ssl.create_default_context(cafile=cacertsFile)
   elif thumbprint and hasattr(ssl, '_create_unverified_context'):
      context = ssl._create_unverified_context()
   if context:
      context.options |= ssl.OP_NO_SSLv2
      context.options |= ssl.OP_NO_SSLv3
   return context


## Log exception with stack trace
#
# @param  err Exception
def LogException(err):
   """ Log exception with stack trace """
   import logging
   import traceback
   if IsInVisor():
      for line in traceback.format_exception(*sys.exc_info()):
         logging.critical(line)
   else:
      logging.critical("Exception:" + str(err))
      stackTrace = " ".join(traceback.format_exception(*sys.exc_info()))
      logging.critical(stackTrace)


## Option class
#
class Option:
   """ Options accessor class """
   def __init__(self, name, env, default, helpMsg, action=None, callback=None,
                shortname=None):
      """ Constructor """
      self.name = name
      self.shortname = shortname
      self.env = env
      self.default = default
      self.help = helpMsg
      self.action = action
      self.callback = callback


## Get vi sdk rc file
#
# @return vi sdk rc file location
def GetViSdkRcPath():
   """ Get VI Sdk rc file path """
   if sys.platform == "win32":
      viSdkRc = "visdk.rc"
   else:
      viSdkRc = ".visdkrc"

   home = os.environ.get("HOME") or os.environ.get("LOGDIR")
   if home:
      viSdkRc = home + "/" + viSdkRc
   return viSdkRc


## Get vi sdk credstore file
#
# @param platform name (expecting sys.platform string)
# @param pseudoEnv Do not expand environment path if set to True
#
# @return vi sdk credstore file location
def GetViSdkCredPlatformPath(platform, pseudoEnv=False):
   """ Get VI Sdk credstore file path """
   if platform == "win32":
      homeEnvName = "APPDATA"
      vmware = "VMware"
   else:
      homeEnvName = "HOME"
      vmware = ".vmware"

   if pseudoEnv:
      home = "".join(["<", homeEnvName, ">"])
   else:
      home = os.environ.get(homeEnvName)
      if not home:
         raise KeyError(homeEnvName)
   credStorePath = os.path.join(home, vmware, "credstore", "vicredentials.xml")
   return credStorePath


## Get login session user name (won't work on Windows)
#
# @return login session user name
def GetSessionUserName():
   """ Get login session user name (won't work on Windows) """
   try:
      if IsInVisor():
         # On ESXi getuid() is always 0, i.e. user 'root'.
         # But user 'root' is not guaranteed to have Admin role on the host,
         # e.g. when lockdown mode is enabled.
         # Since we can't fix all scripts/apps that call 'esxcli', then
         # we'd better connect as user 'dcui' instead of 'root'.
         #
         # See PR 1630690.
         #
         # Update: first try with environment variable 'USER'.
         name = os.environ.get("USER")
         if name:
            return name
         return "dcui"
      else:
         import pwd
         return pwd.getpwuid(os.getuid())[0]
   except:
      return None


## Check if we are in visor shell
#
# @return true if we are in visor shell
def IsInVisor():
   try:
      return os.uname()[0].lower() == "vmkernel"
   except Exception:
      return False


## Close a file, eat all exceptions
#
def CloseNoRaise(f):
   if f:
      try:
         f.close()
      except Exception:
         # Yeah, close could failed
         pass


## Python-ized encoding string
#
# cx_freeze hack: For some strange reason, a frozen exe failed to lookup
# encoding with "-". The kicker is it only failed for the current locale,
# i.e. if locale is euc-kr, "euc-kr" will fail but "euc-jp" will work fine
# I really can't explain why... just able to figure out a fix
def PythonizeEncodingStr(encoding):
   return encoding.replace("-", "_")


## Unpython-ized encoding string
#
def UnPythonizeEncodingStr(encoding):
   return encoding.replace("_", "-")


## Get active input and output encoding
#
# @return inputEncoding, outputEncoding
def GetDefaultEncodings():
   import locale
   outputEncoding = locale.getpreferredencoding()

   if sys.platform == "win32":
      # Windows
      from ctypes import windll

      # Get console output codepage
      codePage = windll.kernel32.GetConsoleOutputCP()

      # Known coding mapping from codepages to python encoding names
      encodeMap = {
         1200: "utf-16",
         1201: "utf-16BE",
         12000: "utf-32",
         12001: "utf-32BE",
         20932: "euc-jp",
         28591: "iso-8859-1",
         28592: "iso-8859-2",
         28593: "iso-8859-3",
         28594: "iso-8859-4",
         28595: "iso-8859-5",
         28596: "iso-8859-6",
         28597: "iso-8859-7",
         28598: "iso-8859-8",
         28599: "iso-8859-9",
         28603: "iso-8859-13",
         28605: "iso-8859-15",
         28606: "iso-8859-16",
         50220: "iso-2022-jp",
         50221: "iso-2022-jp-1",
         50222: "iso-2022-jp-2",
         50225: "iso-2022-kr",
         51932: "euc-jp",
         51936: "euc-cn",
         51949: "euc-kr",
         52936: "hz-gb-2312",
         54936: "gb18030",
         65000: "utf-7",
         65001: "utf-8",
      }
      codePageStr = "cp" + str(codePage)
      encoding = encodeMap.get(codePage, codePageStr)
      try:
         "".encode(encoding)
         outputEncoding = encoding
      except LookupError:
         pass

      # Windows is really... stupid
      inputEncoding = sys.getfilesystemencoding()
      if inputEncoding is None:
         # It is possible for getfilesystemencoding to returns None
         inputEncoding = outputEncoding
   else:
      if IsInVisor():
         # Visor shell did not normally have correct encoding.
         # Force default to utf-8
         outputEncoding = "utf-8"
      inputEncoding = outputEncoding

   # cx_freeze hack: For some strange reason, a frozen exe failed to lookup
   # encoding with "-". The kicker is it only failed for the current locale,
   # i.e. if locale is euc-kr, "euc-kr" will fail but "euc-jp" will work fine
   # I really can't explain why... just able to figure out a fix
   return PythonizeEncodingStr(inputEncoding), PythonizeEncodingStr(outputEncoding)


## Session options
#
class SessionOptions:
   """ Session options  """

   # Hack: Force a newline with textwrap
   newline = " " * 400

   # Options definition
   OptionsList = [
      # Config file
      Option(name="config", shortname="c", env="VI_CONFIG",
             default=GetViSdkRcPath(),
             helpMsg="(variable VI_CONFIG)" + newline + \
                     "Location of the configuration file"),

      # Encoding
      Option(name="encoding", env="VI_ENCODING",
             default=None,
             helpMsg="(variable VI_ENCODING, default 'utf8')" + newline + \
                     "Encoding: utf8, cp936 (Simplified Chinese), " \
                     "iso-8859-1 (German), shiftjis (Japanese)"),

      # Destination
      Option(name="server", shortname="s", env="VI_SERVER", default=None,
             helpMsg="(variable VI_SERVER)" + newline + \
                     "vCenter Server or ESXi host to connect to. "
                     "Required if url is not present"),
      Option(name="portnumber", env="VI_PORTNUMBER", default="443",
             helpMsg="(variable VI_PORTNUMBER)" + newline + \
                     "Port used to connect to server"),
      Option(name="protocol", env="VI_PROTOCOL", default="https",
             helpMsg="(variable VI_PROTOCOL, default 'https')" + newline + \
                     "Protocol used to connect to the server (http / https). "
                     "WARNING: using http is insecure."),
      Option(name="servicepath", env="VI_SERVICEPATH",
             default="/sdk/webService",
             helpMsg="(variable VI_SERVICEPATH, default '/sdk/webService')" + \
                     newline + "Service path used to connect to server"),
      Option(name="url", shortname="r", env="VI_URL", default=None,
             helpMsg="(variable VI_URL)" + newline + \
                     "VI SDK URL to connect to. " \
                     "Required if server is not present"),

      # ESXi host
      Option(name="vihost", shortname="h", env="VI_HOST", default=None,
             helpMsg="(variable VI_HOST, no default)" + newline + \
                     "ESXi host when connecting through vCenter Server"),

      # User / session
      Option(name="username", shortname="u", env="VI_USERNAME", default=None,
             helpMsg="(variable VI_USERNAME)" + newline + \
                     "Username"),
      Option(name="password", shortname="p", env="VI_PASSWORD", default=None,
             helpMsg="(variable VI_PASSWORD)" + newline + \
                     "Password"),

      Option(name="sessionfile", shortname="f", env="VI_SESSIONFILE",
             default=None,
             helpMsg="(variable VI_SESSIONFILE, no default)" + newline + \
                     "File containing session ID/cookie to utilize"),
      Option(name="savesessionfile", env="VI_SAVESESSIONFILE", default=None,
             helpMsg="(variable VI_SAVESESSIONFILE, no default)" + newline + \
                     "File to save session ID/cookie to utilize"),

      # Platform Services Controller (Lookup Service)
      Option(name="psc", env="VI_PSC", default=None,
             helpMsg="(variable VI_PSC, no default)" + newline + \
                     "Location of Platform Services Controller (PSC)." + \
                     newline + \
                     "Hostname or IP address with optional port number." + \
                     newline + \
                     "Examples:" + newline + \
                     "   --psc=psc.corp.local" + newline + \
                     "   --psc=psc.corp.local:9999" + newline + \
                     "Provides the endpoint for VMWare "\
                     "Security Token Service (STS) used for single sign on "\
                     "(SSO) authentication and the endpoint for VI SDK on "\
                     "vCenter Server." + newline + \
                     "This option implies user authentication with SSO." + \
                     newline + \
                     "If any of the options 'server' or 'url' is set, then "\
                     "VI SDK URL is not fetched from PSC."),

      Option(name="credstore", env="VI_CREDSTORE",
             default=None,
             helpMsg="(variable VI_CREDSTORE), defaults to " + \
                     GetViSdkCredPlatformPath("linux2", True) + \
                     " on Linux and " + \
                     GetViSdkCredPlatformPath("win32", True) + \
                     " on Windows)" + newline + \
                     "Credential store file path"),

      Option(name="passthroughauth", shortname="a", env="VI_PASSTHROUGHAUTH",
             default=False, action="store_true",
             helpMsg="(variable VI_PASSTHROUGHAUTH)" + newline + \
                     "Attempt to use pass-through authentication"),
      Option(name="passthroughauthpackage", env="VI_PASSTHROUGHAUTHPACKAGE",
             default="Negotiate",
             helpMsg="(variable VI_PASSTHROUGHAUTHPACKAGE, " \
                     "default 'Negotiate')" + newline + \
                     "Pass-through authentication negotiation package"),

      Option(name="cacertsfile", shortname="t", env="VI_CACERTFILE",
             default=None,
             helpMsg="(variable VI_CACERTFILE)" + newline + \
                     "CA certificates file"),
      Option(name="thumbprint", shortname="d", env="VI_THUMBPRINT",
             default=None,
             helpMsg="(variable VI_THUMBPRINT)" + newline + \
                     "Expected SHA-1/SHA-256/SHA-512 server certificate "
                     "thumbprint, if CA certificates file is not provided"),

      # TODO: "VI_VERBOSE"
   ]


   ## Constructor
   #
   # @param  options Options from optparser
   def __init__(self, options):
      """ Constructor """
      # Create attr in self, user can access option val with obj.name
      for option in self.OptionsList:
         # Make sure we will not overwrite current object attributes
         assert(getattr(self, option.name, None) is None)
         # Set default
         setattr(self, option.name, option.default)

      # At runtime, the appliance or Remote CLI package first processes any
      # options that are set in the configuration file, next any environment
      # variables, and finally command-line entries.

      # Pull in command line val to options
      # Read configuration file
      if getattr(options, "config", None):
         configFileName = options.config
      else:
         configFileName = os.environ.get("VI_CONFIG")
         if not configFileName:
            configFileName = GetViSdkRcPath()
      if configFileName:
         self._ReadConfigFile(configFileName)

      # Get config from environment variables
      for option in self.OptionsList:
         val = os.environ.get(option.env)
         if val is not None:
            setattr(self, option.name, val)

      # Pull in command line val to options
      for option in self.OptionsList:
         val = getattr(options, option.name, None)
         if val is not None:
            setattr(self, option.name, val)

   ## Get a list of optparser options
   #  Note: Do not log here. Logging is not yet setup
   #
   # @return optparser options
   @staticmethod
   def GetOptParseOptions():
      """ Get a list of optparser options """
      from optparse import make_option
      options = []
      for option in SessionOptions.OptionsList:
         kwargs = { "default": None,
                    "dest"   : option.name,
                    "help"   : option.help }
         if option.action:
            kwargs["action"] = option.action
         if option.callback:
            kwargs["callback"] = option.callback
         args = set()
         args.add("--" + option.name)
         if option.shortname:
            args.add("-" + option.shortname)
         optparseOption = make_option(*args, **kwargs)
         options.append(optparseOption)
      return options

   ## Set option from environment variable
   #
   # @param  env Environment variable name
   def _SetEnvOption(self, env, val):
      """ Set option from environment variable """
      for option in self.OptionsList:
         if option.env == env:
            setattr(self, option.name, val)
            break
      else: # for ... else
         logging.error("Unknown environment variable: " + env)

   ## Read options from config file
   #
   # @param  configFilename Config file name
   def _ReadConfigFile(self, configFileName):
      """ Read options from config file """
      configFile = None
      try:
         configFile = open(configFileName, "r")
         for line in configFile:
            if line.startswith("#"):
               continue
            keyVal = line.split("=", 1)
            if len(keyVal) != 2:
               continue
            # Match perl implementation: strip out leading spaces (not
            # trailing). Yes, you can't have password with leading spaces
            # in config file!
            key, val = keyVal[0].strip(), keyVal[1].lstrip().rstrip("\r\n")
            if key:
               self._SetEnvOption(key, val)
      except IOError:
         logging.info("Config file " + configFileName + " does not exist")

      CloseNoRaise(configFile)


## Session exception
#
class SessionException(Exception):
   """ Session exception """
   # Python 2.6+ deprecated 'message' attr from BaseException. Override the
   # BaseException.message attr and make this a simple str
   message = ""

   def __init__(self, message=None):
      """ Constructor """
      Exception.__init__(self)
      self.message = message

   def __str__(self):
      return self.message


## Session argument exception
#
class SessionArgumentException(SessionException):
   def __init__(self, message=None):
      SessionException.__init__(self, message)


## Session login exception
#
class SessionLoginException(SessionException):
   def __init__(self, err, message=None):
      SessionException.__init__(self, message)
      self.err = err


## Helper to call correct input version depending on python version
#
# @param User prompt to be printed
# @return String entered by user
def userInput(prompt):
   if isPython3():
      return input(prompt)
   else:
      return raw_input(prompt)


## Vim Session class
#
class Session:
   """ Vim session helper """

   ## Constructor
   #
   # @param  options SessionOptions
   def __init__(self, options):
      """ Constructor """
      self.options = options
      self._host = None
      self._stub = None
      self._sessionMgr = None
      self._reqLogout = True

   ## Desrtuctor (Not quite helpful, as python don't like to call destructor)
   #
   def __del__(self):
      """ Destructor """
      self.Logout()

   ## Vmomi soap stub
   #
   # @return vmomi soap stub
   @property
   def stub(self):
      """ Vmomi soap stub """
      if not self._stub:
         self.Login()
      return self._stub

   ## Service content
   #
   # @return service content
   @property
   def content(self):
      """ Get service content """
      # self._content is not intialized unless self._stub is initialized
      # Retrieve self._stub once to init self._stub
      _ = self.stub
      return self._content

   ## Session logout
   #
   # @param force Force logout even if not requried
   def Logout(self, force=False):
      """ Session logout """
      try:
         if self.options.savesessionfile:
            # Save session file, and do not call logout
            if hasattr(self._stub, "cookie"):
               self._SaveCookieFile(self.options.savesessionfile,
                                    self._stub.cookie)
      except Exception as err:
         LogException(err)

      try:
         # Logout if needed
         if force or self._reqLogout:
            if self._sessionMgr:
               self._sessionMgr.Logout()
      except Exception as err:
         LogException(err)

      self._sessionMgr = None
      self._stub = None

   ## Session login
   #
   def Login(self):
      """ Session login """
      if self._stub:
         return

      host = self.options.server
      protocol = self.options.protocol
      try:
         port = int(self.options.portnumber)
      except ValueError:
         message = "Invalid port number %s" % self.options.portnumber
         raise SessionArgumentException(message)
      path = self.options.servicepath
      user = self.options.username
      password = self.options.password
      url = self.options.url

      sessionFile = self.options.sessionfile
      saveSessionFile = self.options.savesessionfile
      if self.options.encoding:
         encoding = self._VerifyEncoding(self.options.encoding)
         if encoding:
            self.options.encoding = encoding
         else:
            message = "Unknown encoding %s" % self.options.encoding
            raise SessionArgumentException(message)
      # Using version8 to connect since LoginByToken was introduced then
      version = 'vim.version.version9'
      passthroughAuth = self.options.passthroughauth
      passthroughAuthPackage = self.options.passthroughauthpackage
      credStorePath = self.options.credstore
      try:
         if credStorePath is None or len(credStorePath.strip()) == 0:
            # Will throw if HOME not set
            credStorePath = GetViSdkCredPlatformPath(sys.platform)
      except KeyError:
         pass

      credStore = self._GetCredstoreFromPath(credStorePath)

      # Url override
      if url:
         host, port, protocol, path = self._ParseURL(url=url)

      # Session file override
      cookie = None
      if sessionFile:
         host, cookie = self._GetCookieFromFile(host, sessionFile)

      # Lookup Service URL
      psc = self.options.psc
      lsUrl = None
      if psc:
         lsUrl = "https://" + psc + "/lookupservice/sdk"

      # If not in visor, then host should already be set or --psc specified.
      if not host and not lsUrl:
         if IsInVisor():
            host = "localhost"
         else:
            message = "Must specify a server name"
            raise SessionArgumentException(message)

      # Local host
      useLocalLogin = False
      if IsInVisor() and host in ("localhost", "127.0.0.1", "::1") and \
         password is None:
         # Use local login for VMkernel
         useLocalLogin = True
         # Do not use SSL
         protocol = "http"
         port = 80

      cacertsFile = self.options.cacertsfile
      thumbprint = None
      if not useLocalLogin and not cacertsFile:
         # We need a thumbprint.
         thumbprint = self.options.thumbprint
         if not thumbprint and credStore:
            thumbprint = credStore.GetThumbprint(host)
         if not thumbprint:
            # Not found on command line or credstore.
            # Make up one, so that the check fails. Collision is impossible due to
            # the symbol K, which will never appear in a server thumbprint.
            thumbprint = "FA:KE:FA:KE:FA:KE:FA:KE:FA:KE:FA:KE:FA:KE:FA:KE:FA:KE:FA:KE:FA:KE:FA:KE:FA:KE:FA:KE:FA:KE:FA:KE"

      stsUrl = None
      stsThumbprint = None
      vcThumbprint = None

      # Check protocol
      # Negative port indicate http
      if protocol == "http":
         if port > 0:
            port = -port
      elif protocol == "https":
         if port < 0:
            port = -port
      else:
         message = "Unsupported protocol %s" % protocol
         raise SessionArgumentException(message)

      MAX_RETRY_SECONDS = 100
      connectStartTime = time.time()
      connected = False
      while not connected:
         localTicket = None
         try:

            # Look up VC URL only if none of --server and --url options are set.
            if not stsUrl and lsUrl and not host and not url:

               # TODO: In the future we may prompt the user to make a choice
               # if more than one VCs are registered with Lookup Service.
               # Until then we use the first VC URL that we find.
               url, vcThumbprint = self._GetVcUrlFromLookupService(
                  lsUrl, cacertsFile=cacertsFile, thumbprint=thumbprint)
               logging.info("Got VC URL from PSC: " + url)
               host, port, protocol, path = self._ParseURL(url=url)

               # TODO: In the future we may prompt the user to make a choice if
               # more than one SSO servers are registered with Lookup Service.
               # Until then we use the first STS URL that we find.
               stsUrl, stsThumbprint = self._GetStsUrlFromLookupService(
                  lsUrl, cacertsFile=cacertsFile, thumbprint=thumbprint)
               logging.info("Got STS URL from PSC: " + stsUrl)

               # We'll verify vCenter Server certificate by vcThumbprint
               # and SSO server certificate by stsThumbprint, so we don't need
               # cacertsFile any more.
               thumbprint = vcThumbprint
               cacertsFile = None

            # Create Soap stub
            reqLogin = True

            context = CreateSslContext(cacertsFile, thumbprint)

            stub = SoapAdapter.SoapStubAdapter(host=host, port=port,
                                               version=version, path=path,
                                               thumbprint=thumbprint,
                                               sslContext=context)
            if sessionFile:
               # Use session file
               if cookie:
                  stub.cookie = cookie.name + "=" + cookie.value + ";" + \
                                              " Path=" + cookie.path + ";"
               reqLogin = False

            elif passthroughAuth:
               # Do authentication below
               pass

            elif useLocalLogin:
               if not user:
                  user = GetSessionUserName()

            elif password is None and credStore:
               # Try to use credential store if no password is given.
               # If user is not specified and there is only 1 user in cred store,
               # then take the user and password from credstore
               if not user:
                  try:
                     users = credStore.GetUserNames(host)
                  except Exception as err:
                     errMsg = "Credential store file %s is corrupted" % credStorePath
                     logging.error(errMsg)
                     error = err
                     raise IOError(errMsg)

                  if len(users) == 1:
                     logging.info("Using user: %s" % users[0])
                     user = users[0]

               if not user:
                  user = userInput("Enter username: ")

               try:
                  # Get password from CredStore
                  password = credStore.GetPassword(host, user)
               except Exception as err:
                  errMsg = "Credential store file %s is corrupted" % credStorePath
                  logging.error(errMsg)
                  error = err
                  raise IOError(errMsg)

            logging.info("Connecting to " + host + "@" + str(port))
            content = self._GetServiceContent(stub)
            sessionMgr = content.sessionManager

            if reqLogin:
               # Ask for user / password if not given
               if not passthroughAuth:
                  if not user:
                     user = userInput("Enter username: ")
                  if password is None and not useLocalLogin:
                     import getpass
                     password = getpass.getpass("Enter password: ")

               userSession = None
               if passthroughAuth:
                  userSession = self._PassthroughLogin(host, sessionMgr,
                                                       passthroughAuthPackage)
               elif stsUrl:
                  context = CreateSslContext(None, stsThumbprint)
                  samlToken = self._GetSamlToken(stsUrl, user, password,
                                                 thumbprint=stsThumbprint,
                                                 context=context)
                  userSession = self._GetUserSessionFromSamlToken(samlToken, stub)
               elif useLocalLogin:
                  localTicket = sessionMgr.AcquireLocalTicket(user)
                  localTicketPasswd = ""
                  try:
                     localTicketPasswd = open(localTicket.passwordFilePath).read()
                  except IOError as err:
                     LogException(err)
                     logging.error("Failed to read local ticket")
                     error = err

                  userSession = sessionMgr.Login(localTicket.userName,
                                                 localTicketPasswd)
               else:
                  userSession = sessionMgr.Login(user, password, None)

               if not userSession:
                  raise SessionException("Invalid login")

            # Do we need to logout?
            reqLogout = reqLogin
            if saveSessionFile:
               reqLogout = False

            logging.info("Connected")
            connected = True

            self._host = host
            self._stub = stub
            self._content = content
            self._sessionMgr = sessionMgr
            self._reqLogout = reqLogout
         except vim.fault.InvalidLogin as err:
            exitMessage = "Invalid login: {0}".format(err.msg)
            timeDelta = time.time() - connectStartTime
            if localTicket is not None and timeDelta < MAX_RETRY_SECONDS:
               # The local ticket may have expired due to its short life time
               # of 10 seconds. Try again.
               # SessionManager.login() API has a dealy of ~4 sec.
               logging.error(exitMessage)
               logging.error("Will retry login in 1 second")
               error = None
               continue
            LogException(err)
            raise SessionLoginException(err, message=exitMessage)
         except vmodl.MethodFault as err:
            exitMessage = "Error: {0}.".format(err.msg)
            LogException(err)
            raise SessionLoginException(err, message=exitMessage)

         except ssl.CertificateError as err:
            exitMessage = "Certificate error: {0}".format(err)
            LogException(err)
            raise SessionLoginException(err, message=exitMessage)
         except ssl.SSLError as err:
            # Special handling for SSL error. Need to put before IOError, as
            # ssl.SSLError subclass IOError
            exitMessage = "SSL error 0x{0:x}".format(err.errno)
            LogException(err)
            raise SessionLoginException(err, message=exitMessage)
         except IOError as err:
            exitMessage = "IO error: {0}".format(str(err))
            LogException(err)
            raise SessionLoginException(err, message=exitMessage)
         except ThumbprintMismatchException as err:
            expected = ':'.join(re.findall(r'(..)', err.expected.upper()))
            actual = ':'.join(re.findall(r'(..)', err.actual.upper()))
            sha_variant = get_sha_variant(len(actual))
            # The actual thumbprint should always be valid.
            assert(sha_variant is not None)
            exitMessage = "Certificate error. Server SHA-{0} thumbprint: {1}".format(
               sha_variant,
               actual
            )
            if expected.find('FA:KE') == -1:
               exitMessage = "{0} (expected: {1})".format(exitMessage, expected)
            else:
               exitMessage = "{0} (not trusted)".format(exitMessage)

            # Don't log the fake thumbprint. exitMessage is fine.
            LogException(err)
            raise SessionLoginException(err, message=exitMessage)
         except SessionException as err:
            LogException(err)
            raise
         except Exception as err:
            exitMessage = "Connection failed"
            LogException(err)
            raise SessionLoginException(err, message=exitMessage)
      # End of "while not connected:" loop


   @staticmethod
   def _ParseURL(url):
      if url:
         # Prevent pylint from complaining about missing module with py2/3
         #pylint: disable=E0611
         if isPython3():
            import urllib.parse as parse
         else:
            import urlparse as parse

         url = parse.urlparse(url)
         protocol = url.scheme
         host = url.hostname
         if url.port:
            try:
               port = int(url.port)
            except ValueError:
               message = "Invalid port number %s in URL" % url.port
               raise SessionArgumentException(message)
         else:
            port = (protocol == "http") and 80 or 443
         path = url.path
         return host, port, protocol, path
      else:
         return None, None, None, None

   ##
   #
   @staticmethod
   def _GetServiceContent(stub):
      si = vim.ServiceInstance("ServiceInstance", stub)
      return si.RetrieveContent()


   ##
   #
   @staticmethod
   def _RaiseLsResultError(element, resultXml):
      logging.error(element + " not found in response: " + resultXml)
      raise SessionArgumentException("Error parsing Lookup Service result")

   ##
   #
   @staticmethod
   def _LookupServiceRequest(lsUrl, soapRequest, cacertsFile, thumbprint):
      # We always use HTTPS, so protocol is ignored.
      lsHost, lsPort, lsProtocol, lsPath = Session._ParseURL(url=lsUrl)

      headers = {'SOAPAction' : 'urn:lookup/2.0',
                 'Content-Type' : 'text/xml; charset=UTF-8'}

      context = CreateSslContext(cacertsFile, thumbprint)

      conn = ThumbprintVerifiedHTTPSConnection(lsHost, lsPort,
                                               thumbprint=thumbprint,
                                               context=context)

      conn.request("POST", lsPath,
                   body=soapRequest.encode('ascii'), headers=headers)
      data = conn.getresponse().read()

      conn.close()
      return data

   ##
   #
   @staticmethod
   def _GetUrlFromLookupService(lsUrl, soapRequest, cacertsFile, thumbprint):
      resultXml = Session._LookupServiceRequest(lsUrl, soapRequest,
                                                cacertsFile, thumbprint)

      import xml.dom.minidom
      dom = xml.dom.minidom.parseString(resultXml)

      sEnv = dom.getElementsByTagName('soapenv:Envelope')
      if len(sEnv) == 0:
         Session._RaiseLsResultError('soapenv:Envelope', resultXml)

      sBody = sEnv[0].getElementsByTagName('soapenv:Body')
      if len(sBody) == 0:
         Session._RaiseLsResultError('soapenv:Body', resultXml)

      listResp = sBody[0].getElementsByTagName('ListResponse')
      if len(listResp) == 0:
         Session._RaiseLsResultError('ListResponse', resultXml)

      retVal = listResp[0].getElementsByTagName('returnval')
      if len(retVal) == 0:
         Session._RaiseLsResultError('returnval', resultXml)

      srvEndp = retVal[0].getElementsByTagName('serviceEndpoints')
      if len(srvEndp) == 0:
         Session._RaiseLsResultError('serviceEndpoints', resultXml)

      url = srvEndp[0].getElementsByTagName('url')
      if len(url) == 0:
         Session._RaiseLsResultError('url', resultXml)
      urlData = url[0].firstChild.data

      sslTrust = srvEndp[0].getElementsByTagName('sslTrust')
      if len(sslTrust) == 0:
         Session._RaiseLsResultError('sslTrust', resultXml)
      sslTrustData = sslTrust[0].firstChild.data

      cert = base64.b64decode(sslTrustData)
      hasher = get_hasher_by_thumbprint(thumbprint)
      thumbprint = hasher(cert).hexdigest().lower()

      return urlData, thumbprint


   ##
   #
   @staticmethod
   def _GetStsUrlFromLookupService(lsUrl, cacertsFile, thumbprint):
      soapRequest = LSREG_LIST_SOAP % \
         (SSO_PRODUCT_ID, SSO_TYPE_ID, EP_SSO_PROTOCOL, EP_SSO_TYPE_ID)
      return Session._GetUrlFromLookupService(lsUrl, soapRequest,
                                              cacertsFile, thumbprint)


   ##
   #
   @staticmethod
   def _GetVcUrlFromLookupService(lsUrl, cacertsFile, thumbprint):
      soapRequest = LSREG_LIST_SOAP % \
         (VC_PRODUCT_ID, VC_TYPE_ID, EP_VC_PROTOCOL, EP_VC_TYPE_ID)
      return Session._GetUrlFromLookupService(lsUrl, soapRequest,
                                              cacertsFile, thumbprint)


   ##
   #
   @staticmethod
   def _GetSamlToken(stsUrl, user, password, thumbprint, context):
      from pyVim import sso
      au = sso.SsoAuthenticator(stsUrl, thumbprint=thumbprint)

      try:
         samlToken = au.get_bearer_saml_assertion(user, password,
                                                  ssl_context=context)
      except sso.SoapException as err:
         msg = "SSO error '{0}': {1}".format(err._fault_code, err._fault_string)
         LogException(err)
         raise SessionException(msg)
      return samlToken


   ##
   #
   def _GetUserSessionFromSamlToken(self, samlToken, stub):
      userSession = None
      stub.samlToken = samlToken
      content = self._GetServiceContent(stub)
      userSession = content.sessionManager.LoginByToken()
      return userSession


   ## Passthrough authentication with GSSAPI
   #
   def _PassthroughLoginGSSAPI(self, host, sessionMgr, passthroughAuthPackage):
      """ Passthrough Authentication """

      userSession = None
      try:
         import kerberos
      except ImportError as err:
         LogException(err)
         return userSession

      context = None
      service = "host@%s" % host
      try:
         result, context = kerberos.authGSSClientInit(service, 0)
         challenge = ""
         while True:
            # Call GSS step
            result = kerberos.authGSSClientStep(context, challenge)
            if result < 0:
               logging.error("authGSSClientStep failed for %s" % service)
               break
            secToken = kerberos.authGSSClientResponse(context)
            try:
               userSession = sessionMgr.LoginBySSPI(secToken)
               # No exception => logged in
               userName = kerberos.authGSSClientUserName(context)
               logging.info("Passthru authentication: Logged in %s as %s" % \
                                                            service, userName)
               del secToken
               break
            except vim.fault.SSPIChallenge as err:
               # Continue gssapi challenges
               challenge = err.base64Token

         del challenge
      except Exception as err:
         LogException(err)
         logging.error("Login failed for %s" % service)

      if context:
         try:
            kerberos.authGSSClientClean(context)
         except Exception as err:
            LogException(err)

      return userSession


   ## Passthrough authentication with SSPI
   #
   def _PassthroughLoginSSPI(self, host, sessionMgr, passthroughAuthPackage):
      """ Passthrough Authentication """
      userSession = None

      try:
         from base64 import b64encode, b64decode
         import sspi
      except ImportError as err:
         LogException(err)
         return userSession

      try:
         # Create client authorization
         clientAuth = sspi.ClientAuth(passthroughAuthPackage)
         secBufDesc = None
         outSecBufDesc = None
         err = True
         while err:
            # Call authorization API
            err, outSecBufDesc = clientAuth.authorize(secBufDesc)
            # LoginBySSPI requires token to be base64 encoded
            secToken = b64encode(outSecBufDesc[0].Buffer)
            try:
               userSession = sessionMgr.LoginBySSPI(secToken)
               # No exception => logged in
               del secToken
               break
            except vim.fault.SSPIChallenge as err:
               # Continue sspi challenges
               # Decode token back to native format
               outSecBufDesc[0].Buffer = b64decode(err.base64Token)
               secBufDesc = outSecBufDesc

         # Cleanup
         del clientAuth
         del outSecBufDesc
      except sspi.error as err:
         logging.error(err.message)

      return userSession


   ## Passthrough authentication stub
   #
   if sys.platform == "win32":
      _PassthroughLogin = _PassthroughLoginSSPI
   else:
      _PassthroughLogin = _PassthroughLoginGSSAPI


   ## Get session cookie from file
   @staticmethod
   def _GetCookieFromFile(host, sessionFile):
      # Use session file
      if isPython3():
         import http.cookiejar as http_cookiejar
      else:
         import cookielib as http_cookiejar

      jar = http_cookiejar.LWPCookieJar()
      jar.load(sessionFile, ignore_discard=True)

      cookie = None
      # Get the vmware soap session cookie from jar
      for aCookie in jar:
         if aCookie.name == "vmware_soap_session":
            # Nothing in the cookie is true, other than the domain is
            # somewhat true
            cookieHost = aCookie.domain
            if host:
               if host.lower() != cookieHost.lower():
                  try:
                     from socket import gethostbyaddr
                     hostPrimaryName = gethostbyaddr(host)[0]
                     cookiePrimaryName = gethostbyaddr(cookieHost)[0]
                     if hostPrimaryName.lower() != cookiePrimaryName.lower():
                        errMsg = "Server %s does not match cookie domain %s"\
                                       % (hostPrimaryName, cookiePrimaryName)
                        logging.error(errMsg)
                        continue
                  except Exception:
                     errMsg = "Lookup %s / %s failed" % (host, cookieHost)
                     logging.error(errMsg)
                     continue
            else:
               host = cookieHost
            # Can't use the cookie.port / cookie.path
            cookie = aCookie
            break
      return host, cookie


   ## Save session cookie to file
   #
   def _SaveCookieFile(self, sessionFile, sessionCookie):
      """ Save session cookie """
      # Generate cookie file
      if isPython3():
         import http.cookies as http_cookies
      else:
         import Cookie as http_cookies

      cookie = http_cookies.SimpleCookie(sessionCookie)

      # Generate cookie file
      f = None
      try:
         f = self._OpenPrivateFile(sessionFile, "w")
         lines = ["#LWP-Cookies-1.0", "\n"]
         for tag in ["vmware_soap_session", "vmware_soap_session_tag"]:
            tagVal = cookie.get(tag)
            if tagVal:
               lines.append(
                  "; ".join(['Set-Cookie3: %s="\\"%s\\""' % (tag, tagVal.value),
                             'path="/"',
                             'domain=%s' % self._host,
                             'path_spec',
                             'discard',
                             'version=0']))
               lines.append("\n")
         f.writelines(lines)
      finally:
         CloseNoRaise(f)


   ## Get the credstore from its file path
   #
   def _GetCredstoreFromPath(self, credStorePath):
      # Access credStore
      try:
         from CredStore import CredStore
         # Verify credStorePath exist and readable
         credStore = CredStore(credStorePath)
      except (IOError, ImportError):
         # Not an error
         credStore = None
      return credStore


   ## Open file without other / group rwx permission
   #
   def _OpenPrivateFile(self, filename, mode):
      f = open(filename, mode)
      if sys.platform == "win32":
         try:
            from win32security import \
               GetFileSecurity, SetFileSecurity, \
               DACL_SECURITY_INFORMATION, OWNER_SECURITY_INFORMATION, \
               ACCESS_ALLOWED_ACE_TYPE, ACCESS_DENIED_ACE_TYPE

            # Remove non-owner access from session file
            sd = GetFileSecurity(filename, DACL_SECURITY_INFORMATION |
                                           OWNER_SECURITY_INFORMATION)
            owner = sd.GetSecurityDescriptorOwner()
            dacl = sd.GetSecurityDescriptorDacl()
            for idx in reversed(range(dacl.GetAceCount())):
               (aceType, aceFlags), accessMask, sid = dacl.GetAce(idx)
               if aceType == ACCESS_ALLOWED_ACE_TYPE and sid != owner:
                  dacl.DeleteAce(idx)

            sd.SetSecurityDescriptorDacl(1, dacl, 0)
            SetFileSecurity(filename, DACL_SECURITY_INFORMATION, sd)
         except ImportError:
            pass
      else:
         import stat
         fd = f.fileno()
         currStat = os.fstat(fd)
         stMode = currStat.st_mode & ~(stat.S_IRWXG | stat.S_IRWXO)
         try:
            os.fchmod(fd, stMode)
         except AttributeError:
            os.chmod(filename, stMode)

      return f


   ## Verify encoding string
   #
   # @return python friendly encoding name
   def _VerifyEncoding(self, encoding):
      if encoding:
         try:
            "".encode(encoding)
            encoding = PythonizeEncodingStr(encoding)
         except LookupError:
            encoding = None
      return encoding
