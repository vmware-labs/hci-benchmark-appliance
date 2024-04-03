#!/usr/bin/env python
"""
Copyright (c) 2008-2021 VMware, Inc.  All rights reserved.
-- VMware Confidential

This module is the esxcli cmd module
"""
__author__ = "VMware, Inc"

import sys
import os
import random

# TODO: PR 1685913 - Source version string from vm_product_versions.h.
ESXCLI_VERSION_STR = "7.0.0"

_CLIINFOTYPE = "vim.CLIInfo"
NAME_INDENT = 2

MME_COMPATIBLE_VIM_VERSION = 'vim.version.version9'

# Force to use MME
gForceMME = False


# Import could take long time (e.g. import pyVmomi). So protect it with a try
# except block, and avoid printing stack trace upon Keyboard interrupt
try:
   import operator
   import os
   from copy import copy

   # Note: Python 2.2 do not have logging
   import logging, logging.handlers

   from optparse import OptionParser, make_option, IndentedHelpFormatter, SUPPRESS_HELP
   from pyVmomi import vmodl, vim, SoapAdapter, VmomiSupport, Cache, DynamicTypeManagerHelper
   from pyVmomi.Cache import Cache

   try:
      from vmware.esxcli.Session import *
      from vmware.esxcli.Formatters import *
   except ImportError:
      from Session import *
      from Formatters import *

except KeyboardInterrupt:
   # Keyboard interrupt
   sys.exit(1)
except Exception as err:
   LogException(err)
   sys.exit(1)


## Null logger
#
class NullHandler(logging.Handler):
   def emit(self, record):
      pass


## Set debug
#
# @param  prog Program name
def SetupLogging(prog):
   """ Set debug """
   try:
      if IsInVisor():
         handler = logging.handlers.SysLogHandler(address='/dev/log')
         fmt = '%(asctime)s esxcli[%(process)d]: %(message)s'
         datefmt = "%b %d %H:%M:%S"
         formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
         handler.setFormatter(formatter)
      else:
         handler = logging.handlers.RotatingFileHandler(filename='{}.log'.format(prog),
                                                        maxBytes=(100*1024),
                                                        backupCount=2)
         handler.setFormatter(logging.Formatter("[%(asctime)s %(name)s " \
                                                "%(levelname)s] %(message)s"))

      handler.setLevel(logging.ERROR)
      logging.getLogger().addHandler(handler)
   except IOError:
      # Suppress logging if failed to open log file
      # Comment this out to see error in stdout
      logging.getLogger().addHandler(NullHandler())

   # Turn off logging exceptions
   try:
      logging.raiseExceptions = 0
   except AttributeError:
      pass

   return logging.getLogger()


## Set debug
#
# @param  logger Logger
# @param  debug True if debug on
def SetupDebugLevel(logger, debug):
   """ Set debug level """
   if hasattr(SoapAdapter, "DebugRequest"):
      SoapAdapter.DebugRequest = debug
   if hasattr(SoapAdapter, "DebugResponse"):
      SoapAdapter.DebugResponse = debug

   if not logger:
      logger = logging.getLogger()

   if debug:
      level = logging.DEBUG
   else:
      level = logging.ERROR
   logger.setLevel(level)


@Cache
def GetFormatHelpWidth():
   """ Get width used to format help message """
   from Formatters import GetConsoleSize
   return GetConsoleSize()[1]


## Get min and max values from the specified constraints object
#
# @param  constraints List of constraints
def GetMinMax(constraints, paramType):
   """ Get min and max values from the specified constraints object """
   minVal = None
   maxVal = None
   if constraints:
      for limit in constraints:
         if limit.startswith("min="):
            minVal = paramType(limit[4:])
         elif limit.startswith("max="):
            maxVal = paramType(limit[4:])
         else:
            pass
   return (minVal, maxVal)


## Format name and description into wrapped string
#
# @param  name Name
# @param  desc Description
# @param  width Max line width
# @return Wrapped string, with name aligned to nameStart and desc aligned to
#         descStart
def FormatNameDesc(name, desc, width=0):
   """ Format name and description into wrapped string """

   # Must have name
   if not name:
      return ""

   def WrapText(width, indent, text):
      if width <= 0:
         # Do not wrap.
         return [indent + text]
      from textwrap import TextWrapper
      tw = TextWrapper(width=width, initial_indent=indent, subsequent_indent=indent)
      return tw.wrap(text)

   # Strip leading/trailing whitespace from the description
   desc = desc.strip()

   # Wrap name (if needed)
   nameIndent = " " * NAME_INDENT
   wrapped = WrapText(width, nameIndent, name)

   descStart = 24
   wrappedDesc = []
   if desc:
      # Wrap description (if needed)
      descIndent = " " * descStart
      splitLines = desc.split("\n")
      for item in splitLines:
         wrappedDesc.extend(WrapText(width, descIndent, item))

      # Do not merge line if name is longer than 1 line
      if wrappedDesc and len(wrapped) <= 1:
         lastName = wrapped[-1]
         if len(lastName) < descStart:
            # Name last line fit desc first line leading spaces. Do merge.
            firstDesc = wrappedDesc.pop(0)
            wrapped[-1] = lastName + firstDesc[len(lastName):]

      wrapped.extend(wrappedDesc)

   # Merge the wrapped line with '\n'
   return "\n".join(wrapped)


## Get type's display name
#
# @param  typ Type
# @return type display name
def TypeDisplayName(typ):
   """ Get type's display name """
   if issubclass(typ, VmomiSupport.Array):
      typName = TypeDisplayName(typ.Item) + "[]"
   else:
      typName = typ.__name__
   return typName


## Type help formatter class
#
class TypeHelpFormatter:
   """ Type help formatter class """

   ## Constructor
   #
   # @param  width Max screen width
   def __init__(self, width):
      """ Init type help formatter """
      self.width = width
      self.hiddenAttrs = ["dynamicType", "dynamicProperty"]
      self.indentInc = 2

   ## Format type
   #
   # @param  typ Type to format
   # @param  numIndent Current indentation
   # @return Formatted type string
   def Format(self, typ, numIndent=0):
      """ Format type into string """
      numIndent += self.indentInc
      ret = ""
      if issubclass(typ, VmomiSupport.Array):
         formatted = self.Format(typ.Item, numIndent)

         # Collapse formatted for simple type
         if formatted.count("\n") == 0:
            ret = OPEN_LIST + " " + formatted + " ... " + CLOSE_LIST
         else:
            indent = " " * numIndent
            ret = OPEN_LIST + "\n"
            ret += indent + formatted + "\n"
            ret += indent + "...\n"
            ret += indent[:-self.indentInc] + CLOSE_LIST
      elif issubclass(typ, VmomiSupport.DataObject):
         # Check for non-optional fields
         indent = " " * numIndent
         ret = OPEN_DATA + "\n"
         for info in typ._GetPropertyList():
            # Either optional or attr is set
            if info.name not in self.hiddenAttrs:
               formatted = self.Format(info.type, numIndent)
               ret += indent + info.name + "=" + formatted
               flags = []
               if not (info.flags & VmomiSupport.F_OPTIONAL):
                  flags.append("required")
               if info.flags & VmomiSupport.F_SECRET:
                  flags.append("secret")
               if len(flags):
                  ret += " (" + " ".join(flags)  + ")"
               ret += "\n"
         ret += indent[:-self.indentInc] + CLOSE_DATA
      else:
         ret = OPEN_TYPE + TypeDisplayName(typ) + CLOSE_TYPE
      return ret


## CLI execute exception class
#
class CLIExecuteException(Exception):
   """ CLI execute exception """
   # Python 2.6+ deprecated 'message' attr from BaseException. Override the
   # BaseException.message attr and make this a simple str
   message = ""

   def __init__(self, message=None):
      """ Constructor """
      Exception.__init__(self)
      self.message = message

   def __str__(self):
      return self.message


## CLI parse exception class
#
class CLIParseException(Exception):
   """ CLI parse exception """
   # Python 2.6+ deprecated 'message' attr from BaseException. Override the
   # BaseException.message attr and make this a simple str
   message = ""

   def __init__(self, message=None):
      """ Constructor """
      Exception.__init__(self)
      self.message = message

   def __str__(self):
      return self.message


## Base handler class with common code used by CLI and CGI handlers
#
class Handler:
   """ Base handler class used by CLI and CGI handlers """
   ## Version
   VERSION = ESXCLI_VERSION_STR

   ## Valid help options
   _CLIROOT = "vim.EsxCLI"

   ## Valid help options
   _HELPS = ["-?", "--help"]

   ## CLI fault type
   _CLIFAULTTYPE = _CLIROOT + ".CLIFault"

   ## Standard error msg for must be used with newer server
   #
   # @return Error message
   def _ErrMsgNeedNewerServer(self):
      return self.prog + \
                  " can only be used with version 5.0 or newer vCenter server or version 4.0 or newer ESX host"

   ## Is help option?
   #
   # @param  option
   # @return True / False
   @staticmethod
   def _IsHelp(option):
      """ Is help option? """
      return option in CLIHandler._HELPS

   ## Option regular expression
   import re
   _RE_OPTION = "-{1,2}\?$|-[a-zA-Z][=]{0,1}|--\w*[=]{0,1}"
   _PAT_OPTION = re.compile(_RE_OPTION)

   ## Is an option?
   #
   # @param  option
   # @return True / False
   # @note   It will not treat -[0--9] as option
   @staticmethod
   def _IsOption(option):
      """ Is an option? """
      return CLIHandler._PAT_OPTION.match(option)

   ## Constructor
   #
   def __init__(self):
      """ Constructor """
      self.session = None
      self.cmdNamespace = None
      self.app = None
      self.method = None
      self.usage = None
      self.options = None
      self.batchArgs = None
      self.batchParams = {}
      self.remainingArgs = None
      self.prog = None
      self.inputEncoding, self.outputEncoding = GetDefaultEncodings()

   ## Handle one command
   #
   # @param  argument List of arguments
   # @return result, message tuple
   def _HandleOneCmd(self, args):
      app, method, parameters = self._ParseCLIArgs(args)
      result = self._Execute(app, method, parameters)
      if result is not None:
         message = self._FormatResult(app, method, result)
      else:
         message = ""
      return result, message

   def _ParseContext(self, options):
      ctx = getattr(options, 'context', '')
      if ctx != '':
         self._ctxStr = '?%s' % options.context
      else:
        self._ctxStr = ''

   ## Handle cmdline
   #
   # @param  cliNS the CLI namespace (to narrow down cli object)
   # @param  prog the prog name
   # @param  argv the argument list
   # @return Execution result
   def HandleCmdline(self, prog=None):
      """ Handle cmdline arguments """
      self.prog = prog and prog or os.path.basename(sys.argv[0])
      logger = SetupLogging(self.prog)
      result = None
      message = None
      exitCode = 1

      try:
         # Handle internal arguments
         self._HandleArgs()

         # Set debug flags (Need to do this before logging happens)
         debug = getattr(self.options, 'debug', False)
         SetupDebugLevel(logger, debug)

         # Set up session
         sessionOptions = SessionOptions(self.options)
         self.session = Session(sessionOptions)
         if self.session.options.encoding != None:
            self.outputEncoding = self.session.options.encoding

         self._ParseContext(self.options)

         if not self.batchArgs:
            args = self.remainingArgs
            result, message = self._HandleOneCmd(args)
         else:
            # Handle cmd batching
            continueOnError = self.batchParams.get("continueOnError", False)
            printCommand = self.batchParams.get("printCommand", None)
            resultPrefixLine = self.batchParams.get("resultPrefixLine", None)
            resultSuffixLine = self.batchParams.get("resultSuffixLine", None)

            for args in self.batchArgs:
               # Handle cmd batching
               line = args.strip()
               if not line or line.startswith("#"):
                  continue
               args = line.split()

               if printCommand:
                  print(line)

               if resultPrefixLine:
                  print(resultPrefixLine)

               try:
                  result, message = self._HandleOneCmd(args)
                  if message:
                     self.Print(message)
                     message = ""
               except Exception as err:
                  if not continueOnError:
                     raise
                  else:
                     logging.error(line)
                     logging.error(err)
                     self.Print(err)

               if resultSuffixLine:
                  print(resultSuffixLine)

         exitCode = 0
      except (CLIParseException, SessionArgumentException) as err:
         # Parse error
         if err.message:
            logging.error(err.message)
         else:
            exitCode = 0

         message = self._FormatHelpNoRaise(self.cmdNamespace,
                                           self.app, self.method, err)
      except CLIExecuteException as err:
         # Execution exception
         message = err.message
      except SessionException as err:
         message = err.message
      except vmodl.MethodFault as err:
         message = "Runtime error: " + err.msg
      except Exception as err:
         LogException(err)
         message = "Runtime error: %s" % str(err)
      finally:
         # Remember to delete session
         del self.session
         self.session = None

      # Print message
      self.Print(message)
      return result, exitCode

   ## _FormatHelpNoRaise
   #  Format help, without raising exception
   #
   # @return Help message or error message (when generating help)
   def _FormatHelpNoRaise(self, cmdNs, app, method, error):
      try:
         if self.session:
            message = self._FormatHelp(cmdNs, app, method, error.message)
         else:
            if error.message:
               message = error.message
            else:
               message = self.usage
      except SessionArgumentException as err:
         # Session argument exception while formatting help -> Dump usage only
         message = self.usage
      except SessionException as err:
         message = "Error: " + err.message
      except (vmodl.Fault.MethodNotFound,
              vmodl.Fault.ManagedObjectNotFound) as err:
         LogException(err)
         message = "Error: " + self._ErrMsgNeedNewerServer()
      except vmodl.MethodFault as err:
         LogException(err)
         message = "Error: " + err.msg
      except CLIParseException as err:
         # Parse exception
         LogException(err)
         message = "Error: " + err.message
      except Exception as err:
         LogException(err)
         message = "Runtime error: %s" % str(err)
      return message

   ## Show version and exit
   #  Side effect: Exit program
   #
   def ShowVersionAndExit(self):
      """ Show version and exit """
      self.Print("Script '" + self.prog + "' version: " + self.VERSION)
      sys.exit(0)

   ## Get session attribute
   #  Side effect: Exit if failed to get attribute
   #
   # @return session attribute
   def _GetSessionAttr(self, attr):
      """ Get session attribute """
      try:
         # Will try login
         return getattr(self.session, attr)
      except SessionArgumentException as err:
         if err.message:
            message = "\n".join([err.message, "", self.usage])
         else:
            message = self.usage
         self.Print(message)
         sys.exit(1)
      except SessionException as err:
         self.Print(err.message)
         sys.exit(1)
      except Exception as err:
         LogException(err)
         message = "Runtime error: %s" % str(err)
         self.Print(message)
         sys.exit(1)

   ## Get session stub
   #  Side effect: Exit if failed to get stub
   #
   # @return Soap stub
   def _GetStub(self):
      """ Get session stub """
      return self._GetSessionAttr("stub")

   ## Get session service content
   #  Side effect: Exit if failed to get stub
   #
   # @return Service content
   def _GetContent(self):
      """ Get service content """
      return self._GetSessionAttr("content")

   ## Get stub for CLI
   #
   # CLI is using a different stub when going through vc. Hence a separate fn
   # to deal with this mme stub
   #
   # @return CLI stub
   @Cache
   def _GetCLIStub(self, version=None):
      targetHostName, hostSystem = self._GetHostSystem()

      global gForceMME
      if gForceMME or self._GetContent().about.productLineId == 'vpx':
         if not gForceMME:
            # vc passthru
            if not targetHostName:
               message = "Must specify ESX host on vCenter"
               raise CLIParseException(message)

            if not hostSystem:
               message = "Cannot find ESX host %s on vCenter" % targetHostName
               raise CLIParseException(message)
         else:
            if not hostSystem:
               message = "Cannot find hostSystem on localhost"
               raise CLIParseException(message)

         mme = None
         try:
            mme = hostSystem.RetrieveManagedMethodExecuter()
         except Exception:
            pass
         if not mme:
            message = self._ErrMsgNeedNewerServer()
            logging.error(message)
            raise CLIParseException(message)

         from pyVmomi import ManagedMethodExecuterHelper
         stub = ManagedMethodExecuterHelper.MMESoapStubAdapter(mme)
         # Use mme compatible version to connect. This is the vim version in which
         # MME was introduced in vsphere and should not be changed. This is
         # beacause the vc or the host can be of a version older than that used
         # to connect. The VMOMI allows the client to pass in a version newer
         # than the server as the server treats any version that it doesn't
         # understand as its latest version. However, The MME executeSoap method
         # on vc and the host verifies the version and complains if it doesn't
         # understand the version.
         stub.ComputeVersionInfo(MME_COMPATIBLE_VIM_VERSION)
      else:
         stub = self._GetStub()
      if version:
         stub = copy(stub)
         stub.ComputeVersionInfo(version)
      return stub

   ## Get dynamic type importer
   #  Side effect: Exit if failed to get stub
   #
   # @return dynamic type importer
   @Cache
   def _GetDynamicTypeImporter(self):
      """ Get dynamic type importer """
      stub = self._GetStub()
      _, hostSystem = self._GetHostSystem()
      return DynamicTypeManagerHelper.DynamicTypeImporter(stub, hostSystem)

   ## Get all managed object instances
   #
   # @return dynamic mo instances
   @Cache
   def _GetAllMoInstances(self):
      """ Get mo instances """
      try:
         # Use QueryMoInstances to get all object instances
         dynTypeMgr = self._GetDynamicTypeImporter().GetTypeManager()
         allMoInstances = dynTypeMgr.QueryMoInstances()
         ret = []
         for mo in allMoInstances:
            if mo.moType == _CLIINFOTYPE:
               ret.append(mo)
            elif self._ctxStr != '' and mo.id.endswith(self._ctxStr):
               ret.append(mo)
            elif mo.id.find('?') == -1:
               ret.append(mo)
         return ret
      except (SessionException, vmodl.MethodFault) as err:
         raise
      except Exception as err:
         LogException(err)
         return []

   ## Import types according to specific type prefix
   @Cache
   def _ImportTypes(self, prefix):
      """ Import types with DynamicTypeImporter """
      try:
         self._GetDynamicTypeImporter().ImportTypes(prefix)
      except (SessionException, vmodl.MethodFault) as err:
         raise
      except Exception as err:
         LogException(err)

   ## Get CLI info object
   #
   # @return CLI info object with associated stub.
   @Cache
   def _GetCLIInfoHelper(self, stub):
      """ Get cli info object """
      try:
         # Need to import dynamic types, as CLIInfo is a dynamic type
         self._ImportTypes(_CLIINFOTYPE)
         allMoInstances = self._GetAllMoInstances()
         return CLIInfo(allMoInstances, stub)
      except (SessionException, vmodl.MethodFault) as err:
         raise
      except Exception as err:
         LogException(err)
         return CLIInfo(None, stub)

   ## Get CLI info object
   #
   # @return CLI info object
   def _GetCLIInfo(self):
      return self._GetCLIInfoHelper(self._GetCLIStub())

   ## Get namespace from root path
   #
   # @param  path to get namespace from
   # @return prefix, namespace, suffix or None, None, None
   def _GetNS(self, path):
      """ Get namespace from root path """
      prefix = self._CLIROOT + "."
      if path.startswith(prefix):
         paths = path[len(prefix):].rsplit(".", 1)
         return self._CLIROOT, paths[0], len(paths) > 1 and paths[1] or None
      else:
         return None, None, None

   ## Check if command namespace exists
   #
   # @param  namespace Namespace
   # @return true if namespace exists, else False
   def _CheckCmdNamespace(self, namespace):
      """ Set Namespace """
      if namespace == '':
         return True

      allMoInstances = self._GetAllMoInstances()
      for instance in allMoInstances:
         prefix, ns, suffix = self._GetNS(instance.moType)
         if ns:
            if suffix != None:
               cmdNs = '.'.join([ns,suffix])
            else:
               cmdNs = ns
            if namespace == cmdNs or cmdNs.startswith(namespace + '.'):
               return True
      return False

   ## Check if 'child' is a descendent namespace of 'parent'
   #
   # @param  parent
   # @param child
   # @return true if 'child' is a descendent of 'parent', else false
   def _IsDescendentNamespace(self, parent, child):
      if parent == '':
         return child != ''

      if child.startswith(parent + '.'):
         return True

      return False

   ## Get namespaces
   #
   # @return A dict of namespaces infos
   def _GetNamespaces(self):
      """ Get namespaces infos """
      infos = {}

      cliInfo = self._GetCLIInfo()
      allMoInstances = self._GetAllMoInstances()
      for instance in allMoInstances:
         prefix, ns, suffix = self._GetNS(instance.moType)
         if ns:
            cliNS = prefix + "." + ns
            if not infos.get(cliNS):
               info = cliInfo.GetCLIInfo(cliNS)
               if info:
                  if not info.displayName:
                     info.displayName = info.name
                  if not info.help:
                     info.help = info.name
               else:
                  info = vim.CLIInfo.Info(name=ns, displayName=ns, help=ns)
               infos[cliNS] = info
      return infos

   ## Get namespace info
   #
   # @param  ns Namespace
   # @return CLIInfo object corresponding to the namespace
   def _GetNamespaceInfo(self, ns):
      cliInfo = self._GetCLIInfo()
      prefix = self._CLIROOT
      cliNS = prefix + '.' + ns
      info = cliInfo.GetCLIInfo(cliNS)
      if info:
         if not info.displayName:
            info.displayName = info.name
         if not info.help:
            info.help = info.name
      else:
         info = vim.CLIInfo.Info(name=ns, displayName=ns, help=ns)
      return info

   ## Get child namespaces
   #
   # @param  parentNs Namespace
   # @return CLIInfo objects for the children namespaces

   def _GetChildNamespaces(self, parentNs):
      cliInfo = self._GetCLIInfo()
      allMoInstances = self._GetAllMoInstances()
      ret = []
      if parentNs == '':
         parentOffset = 0
      else:
         parentOffset = len(parentNs) + 1

      for instance in allMoInstances:
         prefix, ns, suffix = self._GetNS(instance.moType)
         if ns and self._IsDescendentNamespace(parentNs, ns):
            endPos = ns.find('.', parentOffset)
            if endPos == -1:
               endPos = len(ns)
            childNs = ns[:endPos]
            if childNs not in ret:
               ret.append(childNs)
      return dict([(n, self._GetNamespaceInfo(n)) for n in ret])

   ## Get all CLI apps
   #
   # @return CLI apps
   def _GetApps(self, namespace, name=None):
      """ Get CLI apps """
      apps = []

      cliInfo = self._GetCLIInfo()
      allMoInstances = self._GetAllMoInstances()
      for instance in allMoInstances:
         # Filter out non CLI instances
         prefix, ns, suffix = self._GetNS(instance.moType)

         # If we have only one level of namespace here, treat that as the app name
         # rather than the namespace name
         if ns != None and suffix == None:
            ns = ''
            suffix = ns

         if namespace != None and ns != namespace:
            continue

         if name != None and not instance.moType.endswith("." + name):
            continue

         # Create app
         info = cliInfo.GetCLIInfo(instance.moType)
         if info:
            # Import the types now
            if name and instance.moType.startswith(self._CLIROOT + ".image"):
               # Import types from one level up. Temp hack to unblock PR 602324
               typesPrefix = instance.moType[:-(len(name) + 1)]
            else:
               typesPrefix = instance.moType
            self._ImportTypes(typesPrefix)
            version = VmomiSupport.GetVmodlType(instance.moType)._version
            app = CLIApp(info, instance, self._GetCLIStub(version))
            apps.append(app)

      return apps

   ## Format parameter
   #
   # @param  param Parameter
   # @param  paramType Parameter type
   # @param  deferredTypes Map of types definition that get deferred
   # @return Formatted string
   def _FormatParam(self, param, paramType, deferredTypes):
      """ Format parameter to help string """
      if issubclass(paramType, VmomiSupport.Array):
         ret = OPEN_LIST + " " + \
                  self._FormatParam(param, paramType.Item, deferredTypes) + \
                  " ... " + \
               CLOSE_LIST
      elif issubclass(paramType, VmomiSupport.DataObject):
         if paramType in deferredTypes:
            name = deferredTypes[paramType]
         else:
            name = OPEN_TYPE + param.name.upper() + CLOSE_TYPE
            deferredTypes[paramType] = name
         ret = name
      elif issubclass(paramType, VmomiSupport.ManagedMethod) or \
           issubclass(paramType, VmomiSupport.ManagedObject) or \
           issubclass(paramType, VmomiSupport.PropertyPath):
         ret = OPEN_TYPE + "str" + CLOSE_TYPE
      elif issubclass(paramType, VmomiSupport.Enum):
         ret = "|".join(paramType.values)
      else:
         ret = OPEN_TYPE + TypeDisplayName(paramType) + CLOSE_TYPE
      return ret

   ## Parse a single CLI parameter
   #
   def _ParseCLIParameter(self, method, option, argStream):
      param = method.GetParamFromAlias(option)
      if not param:
         # Error or Print help
         if self._IsHelp(option):
            message = None
         else:
            message = "Invalid option " + option
         raise CLIParseException(message)
      val = self._DeserializeParam(argStream, option, param)
      logging.info('%s = %s' % (param.displayName, val))
      return (param, val)

   ## Get the programmatic namespace name from the individial components
   #
   # @param nsComps  The components of the namespace
   def _GetNamespaceName(self, nsComps):
      return '.'.join(nsComps)

   ## Get the display name of the namespace from the individial components
   #
   # @param nsComps  The components of the namespace
   def _GetNamespaceDisplayName(self, nsComps):
      return ' '.join(nsComps)

   ## Raise CLI ParseException
   #  Sets self.cmdNamespace if namespace exists
   #
   # @param nsComps  The components of the namespace
   def _RaiseCLIParseException(self, nsComps):
      nsName = self._GetNamespaceName(nsComps)
      try:
         if self._CheckCmdNamespace(nsName):
            self.cmdNamespace = nsName
            raise CLIParseException()
         else:
            dispName = self._GetNamespaceDisplayName(nsComps)
            message = "Unknown command or namespace %s" % dispName
            raise CLIParseException(message)
      except (vmodl.Fault.MethodNotFound,
              vmodl.Fault.ManagedObjectNotFound) as err:
         message = self._ErrMsgNeedNewerServer()
         raise CLIParseException(message)

   ## Parse CLI arguments
   #
   # @param  args Command line arguments
   # @return Execution result
   def _ParseCLIArgs(self, args):
      """ Handle cli arguments """
      argStream = ArgStream(args)
      nsComps = []
      while (not argStream.Empty()) and (not argStream.Peek().startswith('-')):
         nsComps.append(argStream.Pop())

      if len(nsComps) < 2:
         self._RaiseCLIParseException(nsComps)

      nsName = self._GetNamespaceName(nsComps[:-2])
      appName = nsComps[-2]
      cmdName = nsComps[-1]
      logging.info('ns/app/method: "%s" "%s" "%s"' % (nsName, appName, cmdName))

      apps = self._GetApps(nsName, appName)
      if not apps:
         self._RaiseCLIParseException(nsComps)
      app = apps[0]

      method = app.GetMethodFromDisplayName(cmdName)
      if not method:
         self._RaiseCLIParseException(nsComps)

      self.cmdNamespace = self._GetNamespaceName(nsComps[:-1])
      self.app = app
      self.method = method

      # Get method parameters
      parameters = {}
      while not argStream.Empty():
         arg = argStream.Pop()
         if self._IsOption(arg) and (not arg == "-" or arg == "--"):
            # Split "="
            splitOption = arg.split("=", 1)
            if len(splitOption) > 1:
               argStream.Push(splitOption[1])
            option = splitOption[0]
            (param, val) = self._ParseCLIParameter(method, option, argStream)

            # Store parameters. Only array type can be duplicated
            valSet = parameters.setdefault(param.name, val)
            if valSet is not val:
               if issubclass(param.vmomiInfo.type, VmomiSupport.Array):
                  valSet += val
               else:
                  message = "Duplicated option " + option
                  raise CLIParseException(message)
         else:
            # Got the leftover option
            # For this version, do not allow leftover options
            #   argStream.Push(arg)
            #   break
            message = "Invalid option " + arg
            raise CLIParseException(message)

      # Execute method
      self.remainingArgs = argStream.Leftover()
      return app, method, parameters

   ## Execute CLI command
   #
   # @param  app Application
   # @param  method Command
   # @param  parameters Command parameters
   # @return Execution result
   def _Execute(self, app, method, parameters):
      """ Execute method with parameters """

      # Check method parameters
      errMessages = []
      for param in method.params.values():
         # Either optional or attr is set
         if not (param.vmomiInfo.flags & VmomiSupport.F_OPTIONAL
                 or param.name in parameters):
            message = "Missing required parameter " + "|".join(param.aliases)
            errMessages.append(message)

      if len(errMessages) > 0:
         raise CLIParseException("\n       ".join(errMessages))

      # Get vmomi method
      vmomiMethod = app.GetVmomiMethod(method.name)
      if not vmomiMethod:
         message = "'" + method.displayName + "' does not exist"
         raise CLIParseException(message)

      # Get fault type
      self._ImportTypes(self._CLIFAULTTYPE)
      CLIFaultType = VmomiSupport.GetVmodlType(self._CLIFAULTTYPE)

      # Call method
      result = None
      try:
         result = vmomiMethod(**parameters)

         # TODO: Handle task
         #if isinstance(result, vim.Task):
         #   # Wait for task
         #   # Deserialize result
         #   pass
      except CLIFaultType as err:
         message = '\n'.join(err.errMsg)
         logging.error(method.displayName + " failed: " + message)
         raise CLIExecuteException(message)
      except vmodl.Fault.MethodNotFound:
         message = self._ErrMsgNeedNewerServer()
         logging.error(message)
         raise CLIParseException(message)
      except vmodl.Fault.SystemError as err:
         if err.reason == 'vim.fault.NoPermission':
            message = "No permission to execute " + method.displayName
         else:
            message = method.displayName + " failed: " + err.msg
         logging.error(err)
         raise CLIExecuteException(message)
      except vmodl.MethodFault as err:
         message = method.displayName + " failed: " + err.msg
         logging.error(err)
         raise CLIExecuteException(message)
      except Exception as err:
         LogException(err)
         message = method.displayName + " failed: " + str(err)
         raise CLIExecuteException(str(err))
      return result

   ## Get hostSystem from hostName
   #
   # @param  hostName
   # @return hostSystem. None if not found
   def _GetHostSystemFromHostName(self, hostName=None):
      global gForceMME

      hostSystem = None

      # Get host system
      if hostName:
         content = self._GetContent()
         searchIdx = content.searchIndex
         hostSystem = searchIdx.FindByIp(None, hostName, False) or \
                      searchIdx.FindByDnsName(None, hostName, False)
         if not hostSystem:
            from socket import gethostbyaddr, gaierror
            try:
               name = gethostbyaddr(hostName)[0]
               if name != hostName:
                  hostSystem = searchIdx.FindByDnsName(None, name, False)

               if not hostSystem:
                  # Failed to find the host
                  logging.error("Cannot find hostSystem %s" % hostName)
            except gaierror:
               logging.error("gethostbyaddr failed %s" % hostName)
      elif gForceMME:
         content = self._GetContent()
         dataCenter = content.rootFolder.childEntity[0]
         computeResource = dataCenter.hostFolder.childEntity[0]
         hostSystem = computeResource.host[0]
      else:
         # Note: Optimize by avoid calling the server if not really needed
         # When talking to esx host directly, we can avoid 5 pyVmomi calls
         # by using the hardcoded name of HostSystem and
         # DynamicTypeManager-host. Just need to revert to old behaviour to
         # return None for hostSystem
         #
         #content = self._GetContent()
         #dataCenter = content.rootFolder.childEntity[0]
         #computeResource = dataCenter.hostFolder.childEntity[0]
         #hostSystem = computeResource.host[0]
         pass
      return hostSystem

   ## Get hostSystem
   #
   # @return targetHostName, hostSystem pair, where targetHostName is the
   #         vihost specified on command line (None if not specified)
   @Cache
   def _GetHostSystem(self):
      targetHostName = getattr(self.session.options, 'vihost', None)
      return targetHostName, self._GetHostSystemFromHostName(targetHostName)

   ## Deserialize CLI argument to pyVmomi object according to param definition
   #
   # @param  argStream Arguments
   # @param  option CLI option
   # @param  param Param definition
   # @return pyVmomi object
   def _DeserializeParam(self, argStream, option, param):
      """ Deserailize cmdline option to parameter object """

      paramType = param.vmomiInfo.type
      if param.flag:
         if not argStream.Empty() and not self._IsOption(argStream.Peek()):
            message = "'%s' is a flag and cannot accept any values." % (option)
            raise CLIParseException(message)
         val = True
      else:
         try:
            val = self._DeserializeType(argStream, paramType)
         except CLIParseException as err:
            message = err.message
            if message:
               message = "While processing '" + option + "'. " + message
               raise CLIParseException(message)

      if val is None:
         if param.vmomiInfo.flags & VmomiSupport.F_SECRET:
            # Secret param. Prompt for input
            import getpass
            prompt = 'Enter value for \'%s\': ' % param.displayName
            val = getpass.getpass(prompt)
         else:
            message = option + " must have value"
            raise CLIParseException(message)

      constraints = param.constraints
      if issubclass(paramType, str):
         # Check param constraints
         if constraints and val not in constraints:
            message = "'" + str(val) + "' is not in " + str(constraints)
            raise CLIParseException(message)
      elif issubclass(paramType, bool):
         # Note: bool is subclass of int. Must put BEFORE int check
         pass
      elif isIntegerSubClass(paramType) or issubclass(paramType, float):
         # Check param constraints
         if constraints:
            (minVal, maxVal) = GetMinMax(constraints, paramType)
            if minVal and val < minVal:
               message = "'" + str(val) + "' < " + str(maxVal)
               raise CLIParseException(message)

            if maxVal and val > maxVal:
               message = "'" + str(val) + "' > " + str(maxVal)
               raise CLIParseException(message)
      elif issubclass(paramType, VmomiSupport.Enum):
         if val not in paramType.values:
            message = "'%s' must be one of [%s]" % (val, '|'.join(paramType.values))
            raise CLIParseException(message)
      else:
         pass
      return val

   ## Deserialize CLI argument to pyVmomi object
   #
   # @param  argStream Arguments
   # @param  option CLI option
   # @return pyVmomi object
   def _DeserializeType(self, argStream, paramType):
      """ Deserialize argument to a object with type paramType """

      # Can't deserialize without argument
      if argStream.Empty() or not paramType:
         return None

      arg = argStream.Pop()
      if self._IsOption(arg):
         argStream.Push(arg)
         return None

      ret = None
      if issubclass(paramType, VmomiSupport.Array):
         openToken = OPEN_LIST
         closeToken = CLOSE_LIST

         # Array object: [ val1 val2 ... ] or val
         itemType = paramType.Item
         ret = paramType()
         if arg == openToken:
            while not argStream.Empty() and argStream.Peek() != closeToken:
               obj = self._DeserializeType(argStream, itemType)
               if obj:
                  ret.append(obj)

            arg = argStream.Pop()
            if arg != closeToken:
               message = "Expecting '" + closeToken + "'. Got '" + arg + "'"
               raise CLIParseException(message)
         else:
            # Deserialize single array element
            argStream.Push(arg)
            obj = self._DeserializeType(argStream, itemType)
            if obj:
               ret.append(obj)

      elif issubclass(paramType, VmomiSupport.DataObject):
         # Data object: { key1=val1 key2=val2 ...}
         openToken = OPEN_DATA
         closeToken = CLOSE_DATA

         # Read open data token
         if arg != openToken:
            message = "Expecting '" + openToken + "'. Got '" + arg + "'"
            raise CLIParseException(message)

         attrSet = {}
         ret = paramType()
         while not argStream.Empty() and argStream.Peek() != closeToken:
            arg = argStream.Pop()

            # Parse Key=Val
            splitOption = arg.split("=", 1)
            if not (len(splitOption) > 1 and splitOption[0] and splitOption[1]):
               message = "Invalid attribute format '" + arg + "'"
               raise CLIParseException(message)
            key = splitOption[0]
            argStream.Push(splitOption[1])

            # Check for member properties
            try:
               propInfo = VmomiSupport.GetPropertyInfo(paramType, key)
            except AttributeError:
               message = "No attribute '" + key + "' in " + str(paramType)
               raise CLIParseException(message)

            # Set Val
            obj = self._DeserializeType(argStream, propInfo.type)
            setattr(ret, key, obj)

            attrSet[propInfo.name] = True

         # Read close data token
         arg = argStream.Pop()
         if arg != closeToken:
            message = "Expecting '" + closeToken + "'. Got '" + arg + "'"
            raise CLIParseException(message)

         # Check for non-optional fields
         for info in ret._GetPropertyList():
            # Either optional or attr is set
            if not (info.flags & VmomiSupport.F_OPTIONAL
                    or attrSet.get(info.name)):
               message = "'" + info.name + "' must be set for data object"
               raise CLIParseException(message)

      elif issubclass(paramType, VmomiSupport.ManagedObject):
         # Create moRef
         ret = paramType(arg)
      elif issubclass(paramType, VmomiSupport.Enum):
         if arg in paramType.values:
            ret = paramType(arg)
         else:
            message = "'" + arg + "' is not in " + paramType.values
            raise CLIParseException(message)
      elif issubclass(paramType, bool):
         # Note: bool is subclass of int. Must put BEFORE int check
         boolArg = arg.lower()
         if boolArg in ("0", "false", "f", "no", "n", "off"):
            ret = paramType(0)
         elif boolArg in ("1", "true", "t", "yes", "y", "on"):
            ret = paramType(1)
         else:
            message = \
               "Argument type mismatch. " + \
               "Expecting one of {0, 1, n[o], y[es], f[alse], t[rue], off, on}. " + \
               "Got '" + str(arg) + "'"
            raise CLIParseException(message)
      elif isStringSubClass(paramType):
         try:
            ret = arg
         except ValueError:
            message = "Argument type mismatch. " + \
                      "Expecting string. Got '" + str(arg) + "'"
            raise CLIParseException(message)
      elif isIntegerSubClass(paramType):
         try:
            ret = paramType(arg)
         except ValueError:
            message = "Argument type mismatch. " + \
                      "Expecting integer value. Got '" + str(arg) + "'"
            raise CLIParseException(message)
      elif issubclass(paramType, float):
         try:
            ret = paramType(arg)
         except ValueError:
            message = "Argument type mismatch. " + \
                      "Expecting numeric value. Got '" + str(arg) + "'"
            raise CLIParseException(message)
      else:
         try:
            ret = paramType(arg)
         except ValueError:
            message = "Argument type mismatch. " + \
                      "Expecting " + str(paramType) + ". Got '" + str(arg) + "'"
            raise CLIParseException(message)
      return ret


## CLI handler class
#
class CLIHandler(Handler):
   """ CLI handler class """
   def __init__(self):
      Handler.__init__(self)
      self.formatters = {
         "xml": XmlVisitor,
         "csv": CsvVisitor,
         "keyvalue": KeyValueVisitor,
      }

      # For testing purpose
      self.debugFormatters = {
         "python": PythonVisitor,
         "json": JsonVisitor,
         "html": HtmlOutputFormatter,
         "table": TextOutputFormatter,
         "simple": TextOutputFormatter,
      }

   ## Parse cmdline apps's argument
   #
   # @param  argv the argument list
   def _HandleCLIArgs(self, esxcliOptionsList):
      """ Handle arguments """
      argv = sys.argv[1:]

      # Command parser
      if IsInVisor():
         # No session options running in Visor
         cmdOptionsList = []
      else:
         cmdOptionsList = SessionOptions.GetOptParseOptions()
      cmdOptionsList.extend(esxcliOptionsList)

      _STR_USAGE = "%prog [options] {namespace}+ {cmd} [cmd options]"
      cmdParser = OptionParser(option_list=cmdOptionsList, usage=_STR_USAGE,
                               add_help_option=False)
      cmdParser.disable_interspersed_args()

      # Get command line options
      (options, remainingArgs) = cmdParser.parse_args(argv)

      if options.version:
         self.ShowVersionAndExit()

      # Override console width.
      if options.screenWidth is not None:
         screenWidth = 0
         try:
            screenWidth = int(options.screenWidth)
         except ValueError:
            pass
         if screenWidth <= 0 or screenWidth > 10000:
            raise CLIParseException("Invalid screen width")
         import builtins
         builtins._esxcli_screen_width = screenWidth

      width = GetFormatHelpWidth()
      formatter = IndentedHelpFormatter(width=width if width > 0 else None)
      self.usage = cmdParser.format_help(formatter)

      try:
         # optparser does not have a destroy() method in older python
         cmdParser.destroy()
      except Exception:
         pass
      del cmdParser, formatter

      self.options = options
      self.remainingArgs = remainingArgs

   ## Parse cmdline apps's argument
   #
   # @param  argv the argument list
   def _HandleArgs(self):
      formatters = list(self.formatters.keys())
      esxcliOptionsList = [
         # Formatter
         make_option("--formatter", dest="formatter", default=None,
                     help="Override the formatter to use for a given command. Available formatter: %s" % ", ".join(formatters)),
         # Set a formatter parameter to give the formatter information about
         # how to format the command (internal use only)
         make_option("--format-param", dest="formatParams",
                     action="append", default=[],
                     help=SUPPRESS_HELP),

         make_option("--screen-width", dest="screenWidth", default=None,
                     help="Use the specified screen width when formatting text"),

         # TODO: For debug
         make_option("--debug", action="store_true", dest="debug",
                     default=False, help="Enable debug or internal use options"),
         # Batch mode (internal use only)
         make_option("--batch", dest="batch", default="",
                     help=SUPPRESS_HELP),
         # Batch mode parameters (internal use only)
         make_option("--batch-param", dest="batchParam",
                     action="append", default=[],
                     help=SUPPRESS_HELP),

         # Force MME (internal use only)
         make_option("--forceMME", action="store_true", dest="forceMME",
                     default=False, help=SUPPRESS_HELP),

         # Generate help (internal use only)
         make_option("--generate-xml-help", action="store_true",
                     dest="generateXmlHelp",
                     default=False, help=SUPPRESS_HELP),

         # Context attributes
         make_option("--context", dest="context",
                     default='', help=SUPPRESS_HELP),

         # Version and help
         make_option("--version", action="store_true", dest="version",
                     help="Display version information for the script"),
         make_option("-?", "--help", action="store_true",
                     help="Display usage information for the script"),
      ]
      self._HandleCLIArgs(esxcliOptionsList)

      # Check formatter type
      formatter = self.options.formatter
      if formatter is not None:
         if formatter not in formatters \
            and not (self.options.debug and formatter in self.debugFormatters):
            message = "Unable to find requested formatter: %s" % formatter
            raise CLIParseException(message)

      # Handle batch mode (only available in debug for now)
      # TODO: Add custom seperator beteen batch result
      if self.options.debug and self.options.batch:
         try:
            self.batchArgs = open(self.options.batch, "r")
         except IOError:
            message = "Failed to open batch file: %s" % self.options.batch
            raise CLIParseException(message)

         # Provide some oontrol on how the batch mode should operate
         for batchParam in self.options.batchParam:
            params = batchParam.split("=", 1)
            if len(params) > 0:
               key, tmpval = params[0], params[1]
               val = None
               if key in ("continueOnError", "printCommand"):
                  val = tmpval.lower() not in ("0", "false", "f", "no", "n")
               elif key in ("resultPrefixLine", "resultSuffixLine"):
                  val = tmpval
               else:
                  message = "Unknown batch param %s" % batchParam
                  raise CLIParseException(message)

               if val:
                  self.batchParams[key] = val

      # Handle force MME (only available in debug)
      if self.options.debug and self.options.forceMME:
         global gForceMME
         gForceMME = True

   ## Format help string
   #
   # @param  err Error message
   # @return Formatted help string
   def _FormatHelp(self, ns, app, method, err):
      """ Format help string """
      if self.options.generateXmlHelp:
         return self._FormatXmlHelp(ns, app, method)

      ret = []
      if err:
         ret.extend(["Error: " + err, ""])

      if ns != None and ns == '':
         ret.append(self.usage)

      if method != None:
         methodRet = self._FormatMethodHelp(ns, app, method)
         ret.append(methodRet)
      elif ns != None:
         #TODO if ns is root namespace and no children found, error about versioning
         if ns != '':
            ret.extend(["Usage: %s %s {cmd} [cmd options]" %
                                             (self.prog, ns.replace(".", " ")),
                        ""])

         childNamespaces = self._GetChildNamespaces(ns)
         nsHelp = [self._FormatNamespaceHelp(childNs)
                   for name, childNs in sorted(childNamespaces.items(),
                                               key=operator.itemgetter(0))]
         childApps = self._GetApps(ns)
         if len(nsHelp) > 0 or childApps:
            ret.append("Available Namespaces:")
            ret.extend(nsHelp)

            for childApp in childApps:
               if childApp.name not in childNamespaces:
                  ret.append(self._FormatAppNamespaceHelp(childApp))
            ret.append("")

         if ns != '':
            nsComps = ns.rsplit('.', 1)
            if len(nsComps) > 1:
               nsName = nsComps[0]
               appName = nsComps[1]
            else:
               nsName = ''
               appName = ns

            appObj = self._GetApps(nsName, appName)
            if appObj:
               ret.append("Available Commands:")
               ret.extend(self._FormatAppMethodHelp(appObj[0]))

      return "\n".join(ret)

   ## Format the help for a namespace
   #
   # param ns Namespace
   def _FormatNamespaceHelp(self, ns):
      width = GetFormatHelpWidth()
      return FormatNameDesc(ns.displayName, ns.help, width)

   ## Format the help text for an app, treating it as a namespace
   #
   # param app
   def _FormatAppNamespaceHelp(self, app):
      width = GetFormatHelpWidth()
      return FormatNameDesc(app.displayName, app.help, width)

   ## Format the help text for the methods of an app
   #
   # param app
   def _FormatAppMethodHelp(self, app):
      width = GetFormatHelpWidth()
      ret = []
      for name, method in sorted(app.GetMethods().items(),
                                 key=operator.itemgetter(0)):
         ret.append(FormatNameDesc(method.displayName, method.help, width))

      return ret

   def _FormatMethodHelp(self, ns, app, method):
      width = GetFormatHelpWidth()
      ret = []
      fullCommand = "%s %s %s %s" % (self.prog,
                                     self._GetNamespaceDisplayName(ns.split(".")[:-1]),
                                     app.displayName,
                                     method.displayName)
      usage = "Usage: %s [cmd options]"
      ret.extend([usage % (fullCommand),
                  "",
                  "Description: ",
                  FormatNameDesc(method.displayName, method.help, width),
                  "",
                  "Cmd options:"])

      # Sort param by name
      deferredTypes = {}
      for name, param in sorted(method.params.items(),
                                key=operator.itemgetter(0)):
         if issubclass(param.vmomiInfo.type, bool) and param.flag:
            # For CLI, bool param implies true. (What is this comment saying?).
            # Flag parameters do not need =<type> help message.
            val = ""
         else:
            val = self._FormatParam(param, param.vmomiInfo.type,
                                    deferredTypes)
         if val:
            val = "=" + val
         aliases = "|".join(param.aliases) + val
         paramHelp = param.help
         flags = []
         if not (param.vmomiInfo.flags & VmomiSupport.F_OPTIONAL):
            flags.append("required")
         if param.vmomiInfo.flags & VmomiSupport.F_SECRET:
            flags.append("secret")
         if len(flags):
            paramHelp += " (" + " ".join(flags)  + ")"
         if param.vmomiInfo.flags & VmomiSupport.F_SECRET:
            paramHelp += \
               "\nWARNING: Providing secret values on the command line is insecure "\
               "because it may be logged or preserved in history files. "\
               "Instead, specify this option with no value on the command line, "\
               "and enter the value on the supplied prompt."
         ret.append(FormatNameDesc(aliases, paramHelp, width))

         # Print deferred type def
         if deferredTypes:
            formatter = TypeHelpFormatter(width)
            ret.extend(["", "Types definition:"])
            for paramType, name in deferredTypes.items():
               formatted = formatter.Format(paramType, NAME_INDENT)
               ret.append(" " * NAME_INDENT + name + "=" + formatted)

      if len(method.examples) > 0:
         ret.extend(["", "Examples:"])
         for example in method.examples:
            ret.append("")
            ret.append(" " * NAME_INDENT + example.description)
            ret.append("# %s %s " % (fullCommand, example.example))

      return "\n".join(ret)

   ## A quick hack to format help in xml
   #
   # @param  result Xml help
   def _FormatXmlHelp(self, ns, app, method):
      from pyVmomi.SoapAdapter import XmlEscape

      self.outputEncoding = "utf-8"

      result = []
      result.append('<structure typeName="EsxCliCommand">')
      result.append('   <field name="Command">')
      result.append('      <string>%s</string>' % method.displayName)
      result.append('   </field>')
      result.append('   <field name="Description">')
      result.append('      <string>%s</string>' % XmlEscape(method.help))
      result.append('   </field>')
      result.append('   <field name="Namespace">')
      result.append('      <string>%s</string>' % ns)
      result.append('   </field>')

      # Command arguments
      arguments = []
      for name, param in sorted(method.params.items(),
                                key=operator.itemgetter(0)):
         help = param.help
         paramName = param.displayName
         flags = []
         if not (param.vmomiInfo.flags & VmomiSupport.F_OPTIONAL):
            flags.append('required')
         if (param.vmomiInfo.flags & VmomiSupport.F_SECRET):
            flags.append('secret')
         shortname = ''
         for alias in param.aliases:
            if alias.startswith('-') and not alias.startswith('--'):
               shortname = alias[1:]
               break
         arguments.append( (help, paramName, flags, shortname) )

      # Help
      help = 'Show the help message.'
      paramName = 'help'
      flags = []
      shortname = ''
      arguments.append( (help, paramName, flags, shortname) )

      result.append('   <field name="Parameters">')
      result.append('      <list type="structure">')
      for help, paramName, flags, shortname in arguments:
         required = True if 'required' in flags else False
         if len(flags):
            help += ' (' + ' '.join(flags) + ')'
         result.append('         <structure typeName="EsxCliCommandParameter">')
         result.append('            <field name="Description">')
         result.append('               <string>%s</string>' % XmlEscape(help))
         result.append('            </field>')
         result.append('            <field name="Name">')
         result.append('               <string>%s</string>' % paramName)
         result.append('            </field>')
         result.append('            <field name="Required">')
         result.append('               <string>%s</string>' % str(required).lower())
         result.append('            </field>')
         result.append('            <field name="ShortName">')
         result.append('               <string>%s</string>' % shortname)
         result.append('            </field>')
         result.append('         </structure>')
      result.append('      </list>') # Parameters structure
      result.append('   </field>') # Parameters
      result.append('</structure>')

      return '\n'.join(result)

   ## Format result
   #
   # @param  result Result
   def _FormatResult(self, app, method, result):
      """ Format result """
      # Create formatter
      formatterName = self.options.formatter
      formatter = self.formatters.get(formatterName)
      if not formatter:
         if self.options.debug and formatterName in self.debugFormatters:
            formatter = self.debugFormatters[formatterName]
         else:
            formatter = TextOutputFormatter
            formatterName = ""

      if formatter in [TextOutputFormatter, HtmlOutputFormatter]:
         # TODO: Add format-param to hints
         hints = method.hints.copy()
         if formatterName:
            hints["formatter"] = formatterName
         formatter = formatter(method.fqName, method.result.vmomiInfo, hints)
         message = formatter.Format(result)
         self.Print(message)
      else:
         # Use utf-8 for xml formatter instead of console encoding
         if self.session.options.encoding == None and formatter == XmlVisitor:
            encoding = "utf-8"
         else:
            encoding = self.outputEncoding
         fp = EncodedOutputFactory(fp=sys.stdout, encoding=encoding)
         formatParams = self.options.formatParams
         formatter(fp=fp,
                   root=method.fqName, retType=method.result.vmomiInfo,
                   formatParams=formatParams).Format(result)

      # Stream formatting, don't need to return message
      return ""

   ## Print localized message
   #
   # @param  message Message to print
   def Print(self, message):
      """ Print localized message """
      if message:
         try:
            if isPython3():
               print(message.decode(self.outputEncoding, 'replace'))
            else:
               print(message.encode(self.outputEncoding, 'replace'))
         except:
            try:
               print(message)
            except:
               pass


## An argument stream class
#
class ArgStream:
   """ Argument stream class """
   def __init__(self, aList):
      """ Init argument stream """
      self.list = aList
      logging.info("ArgStream: " + str(aList))

   ## Check if argument stream is empty
   #
   # @returns True if no more argument. Otherwise False
   def Empty(self):
      """ Check if argument stream is empty """
      return self.list is None or len(self.list) == 0

   ## Push arg
   #
   # @param  arg argument to push on stack
   def Push(self, arg):
      """ Push argument """
      if arg is not None:
         self.list.insert(0, arg)
      logging.info("Push: " + str(arg))

   ## Pop arg
   #
   # @returns next arg on stream. None if empty
   def Pop(self):
      """ Pop argument """
      if self.list:
         arg = self.list.pop(0)
      else:
         arg = None
      logging.info("Pop: " + str(arg))
      return arg

   ## Peek next arg
   #
   # @returns next on stream. None if empty
   def Peek(self):
      """ Peek top argument """
      if self.list:
         arg = self.list[0]
      else:
         arg = None
      logging.info("Peek: " + str(arg))
      return arg

   ## Returns the left over arguments
   #
   # @returns leftover arguments
   def Leftover(self):
      """ Return left over arguments """
      return self.list


## CLI app method param class
#
class CLIParam:
   """ CLI Parameter """
   def __init__(self, cliInfo, vmomiInfo):
      """ Constructor """
      self.cliInfo = cliInfo
      self.vmomiInfo = vmomiInfo

   @property
   def name(self):
      """ Raw param name. Same as vmodl param name """
      return self.cliInfo.name

   @property
   def displayName(self):
      """ Display name """
      name = self.cliInfo.name
      try:
         if self.cliInfo.displayName:
            name = self.cliInfo.displayName
      except AttributeError:
         pass
      return name

   @property
   def default(self):
      """ Default param value """
      try:
         return self.vmomiInfo.type(self.cliInfo.default)
      except AttributeError:
         return None
      except TypeError:
         return None

   @property
   def help(self):
      """ Help string """
      try:
         return self.cliInfo.help and self.cliInfo.help or ""
      except AttributeError:
         return ""

   @property
   def constraints(self):
      """ Constraints """
      try:
         return self.cliInfo.constraint
      except AttributeError:
         return None

   @property
   def aliases(self):
      """ Aliases """
      try:
         return self.cliInfo.aliases
      except AttributeError:
         return []

   @property
   def flag(self):
      """ Flag """
      try:
         return self.cliInfo.flag
      except AttributeError:
         return False


## CLI app method class
#
class CLIMethod:
   """ CLI Method """
   def __init__(self, cliMethod, methodInfo):
      """ Constructor """
      self.cliInfo = cliMethod
      self.vmomiInfo = methodInfo
      self.params = self._CreateParams(cliMethod.param, methodInfo.params)

   @property
   def name(self):
      """ Raw method name. Same as vmodl method name """
      return self.cliInfo.name

   @property
   def help(self):
      """ Help string """
      try:
         return self.cliInfo.help and self.cliInfo.help or ""
      except AttributeError:
         return ""

   @property
   def displayName(self):
      """ Display name """
      name = self.cliInfo.name
      try:
         if self.cliInfo.displayName:
            name = self.cliInfo.displayName
      except AttributeError:
         pass
      return name

   @property
   def result(self):
      """ Method result """
      try:
         return CLIParam(self.cliInfo.ret, self.vmomiInfo.result)
      except AttributeError:
         return None

   @property
   def hints(self):
      """ Hints """
      try:
         cliHints = {}
         if self.cliInfo.hints:
            # Convert KeyValue to dict
            for keyval in self.cliInfo.hints:
               cliHints[keyval.key] = keyval.value
         return cliHints
      except AttributeError:
         return {}

   @property
   def examples(self):
      """ Examples """
      try:
         if self.cliInfo.examples:
            return self.cliInfo.examples
         else:
            return []
      except AttributeError:
         return []

   @property
   def fqName(self):
      """ Fully qualified vmodl name """
      return VmomiSupport.GetVmodlName(self.vmomiInfo.type) + "." + self.name

   def GetParamFromAlias(self, alias):
      """ Get CLIParam from alias  """
      for param in self.params.values():
         if alias in param.aliases:
            return param
      return None

   def _CreateParams(self, cliParams, paramInfo):
      """ Create CLIParams """
      params = {}
      for iParam in range(len(cliParams)):
         cliParam = cliParams[iParam]
         vmomiInfo = paramInfo[iParam]
         params[cliParam.name] = CLIParam(cliParam, vmomiInfo)
      return params


## CLI app class
#
class CLIApp:
   """ CLI Application """
   def __init__(self, cliInfo, instance, stub):
      """ Constructor """

      # Make sure it is a CLI managed type
      moType = VmomiSupport.GetVmodlType(instance.moType)
      if not issubclass(moType, VmomiSupport.ManagedObject):
         message = str(moType) + " is not a managed object "
         logging.error(message)
         raise TypeError(message)

      # Create a moRef (to access the remote object)
      # TODO: serverGuid=instance.serverGuid
      self.vmomiInfo = moType
      self.moObj = moType(instance.id, stub)

      # Get cli info (across network)
      self.cliInfo = cliInfo

      # Collect command information from type
      self.methods = self._CreateMethods(self.cliInfo.method,
                                         moType._methodInfo)

   @property
   def name(self):
      """ Raw app name. Same as vmodl app name """
      return self.cliInfo.name

   @property
   def help(self):
      """ Help string """
      try:
         return self.cliInfo.help and self.cliInfo.help or ""
      except AttributeError:
         return ""

   @property
   def displayName(self):
      """ Display name """
      name = self.cliInfo.name
      try:
         if self.cliInfo.displayName:
            name = self.cliInfo.displayName
      except AttributeError:
         pass
      return name

   def GetMethods(self):
      """ Get a dict of CLIMethods """
      return self.methods

   def GetMethodFromDisplayName(self, displayName):
      """ Get named CLIMethod """
      method = self.methods.get(displayName, None)
      if not method:
         method = self.methods.get(VmomiSupport.Capitalize(displayName), None)
      return method

   def GetVmomiMethod(self, name):
      """ Get vmomi method (callable) """
      method = getattr(self.moObj, name, None)
      if not method:
         method = getattr(self.moObj, VmomiSupport.Capitalize(name), None)
      return method

   def _CreateMethods(self, cliMethods, methodInfos):
      """ Create CLIMethods """
      methods = {}
      for cliMethod in cliMethods:
         capMethodName = VmomiSupport.Capitalize(cliMethod.name)
         methodInfo = methodInfos[capMethodName]
         method = CLIMethod(cliMethod, methodInfo)
         capMethodDisplayName = VmomiSupport.Capitalize(method.displayName)
         methods[capMethodDisplayName] = method

      return methods


## CLIInfo class
#
class CLIInfo:
   """ CLIInfo class """

   def __init__(self, allMoInstances, stub):
      """ Constructor """
      self._cliInfos = []
      if allMoInstances:
         for instance in allMoInstances:
            if instance.moType == _CLIINFOTYPE:
               # Build cliInfoObj
               self._cliInfos.append(vim.CLIInfo(instance.id, stub))

   ## Get CLI info
   #
   @Cache
   def GetCLIInfo(self, name):
      """ Get cli info """
      cliInfo = None
      for obj in self._cliInfos:
         try:
            cliInfo = obj.FetchCLIInfo(name)
            break
         except Exception:
            pass
      return cliInfo

   ## Get CLI info from display name
   #
   @Cache
   def GetCLIInfoFromDisplayName(self, name):
      """ Get cli info from display name """
      cliInfo = None
      for obj in self._cliInfos:
         try:
            cliInfo = obj.FetchCLIInfoFromDisplayName(name)
            break
         except Exception:
            pass
      return cliInfo


## Main
#
def main():
   """ Main """

   #
   # Workaround when none of environment variables LANG or LC_ALL are set.
   # This can happen if esxcli is called from some daemon or some other
   # non-interactive script.
   # We should not have this problem when invoking esxcli from a user shell,
   # since the user should have these variables set in the environment.
   #
   # See PR 1617885.
   #
   if os.environ.get('LANG') is None and os.environ.get('LC_ALL') is None:
      os.environ['LANG'] = "en_US.UTF-8"
      # Global name '__file__' is not defined when running under py2exe.
      if '__file__' in globals():
         os.execve(__file__, sys.argv, os.environ)

   # Set "operationID" request context to identify the source of operations.
   reqCtx = VmomiSupport.GetRequestContext()
   reqCtx["operationID"] = 'esxcli-' + format(random.randrange(0, 256), '02x')

   exitCode = 1
   handler = CLIHandler()
   try:
      result, exitCode = handler.HandleCmdline()
   except KeyboardInterrupt as err:
      # Keyboard interrupt
      pass
   except Exception as err:
      LogException(err)
   sys.exit(exitCode)


if __name__ == "__main__":
   main()
