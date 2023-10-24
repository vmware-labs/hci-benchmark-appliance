#!/usr/bin/env python
"""
Copyright (c) 2008-2022 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is the esxcli cmd module
"""
__author__ = "VMware, Inc"

__all__ = [
   "CLOSE_DATA",
   "CLOSE_LIST",
   "CLOSE_TYPE",
   "CsvVisitor",
   "EncodedOutputFactory",
   "HtmlOutputFormatter",
   "JsonVisitor",
   "KeyValueVisitor",
   "OPEN_DATA",
   "OPEN_LIST",
   "OPEN_TYPE",
   "PythonVisitor",
   "SplitCamelCaseName",
   "TextOutputFormatter",
   "XmlVisitor",
   "isIntegerSubClass",
   "isStringSubClass",
   "isPython3"
]

import logging
import re
from pyVmomi import VmomiSupport
from pyVmomi.SoapAdapter import XmlEscape
from pyVmomi.Cache import Cache
import sys
import os

VmodlTypes = VmomiSupport.types

# Define open / close: array / data / type
OPEN_LIST = "["
CLOSE_LIST = "]"
OPEN_DATA = "{"
CLOSE_DATA = "}"
OPEN_TYPE = "<"
CLOSE_TYPE = ">"

## Check python version
#
# @return True if python 3 is running, false otherwise
def isPython3():
   return sys.version_info[0] >= 3

## Return correct string type according to python version
#
# @return basestring in python 2, str otherwise
def stringType():
   if isPython3():
      return str
   else:
      return basestring

## Return correct integer type according to python version
#
# @return int if python 3 is running, (int, long) otherwise
def integerType():
   if isPython3():
      return int
   else:
      return (int, long)

## Check if val is a string type
#
# @param  val
# @return True if val is a string (basestring in Python 2, str in Python 3).
def isString(val):
   return isinstance(val, stringType())


## Check if val is a string subclass
#
# @param  val
# @return True if val is a string subclass (basestring in Python 2, str in Python 3).
def isStringSubClass(val):
   return issubclass(val, stringType())


## Check if val is an integer type
#
# @param  val
# @return True if val is an integer (int or long in Python 2, int in Python 3).
def isInteger(val):
   return isinstance(val, integerType())


## Check if val is an integer subclass
#
# @param  val
# @return True if val is an integer subclass (int or long in Python 2, int in Python 3).
def isIntegerSubClass(val):
   return issubclass(val, integerType())


## Check if the type is formatted as primitive
#
# @param  typ Vmomi type
# @return True / False
def _IsPrimitiveFormat(typ):
   """ Check if the type is formatted as primitive """
   if typ is type(None) or issubclass(typ, bool) or \
      isIntegerSubClass(typ) or \
      isStringSubClass(typ) or \
      issubclass(typ, float) or \
      issubclass(typ, VmodlTypes.ManagedMethod) or \
      issubclass(typ, VmodlTypes.ManagedObject) or \
      issubclass(typ, type):
      return True
   else:
      return False


## Get console size (height, width).
#
# @return height and width of the current console.
def GetConsoleSize():
   """ Get console height and width """
   # Twisted from ActiveState receipe 440694
   height, width = 25, 0
   import struct
   try:
      # Windows
      from ctypes import windll, create_string_buffer

      structFmt = "hhhhhhhhhhh"
      bufSize = len(structFmt) * 2
      hdl = windll.kernel32.GetStdHandle(-12)
      screenBufInf = create_string_buffer(bufSize)
      ret = windll.kernel32.GetConsoleScreenBufferInfo(hdl, screenBufInf)

      if ret:
         (dwSizeX, dwSizeY, dwCursorPositionX, dwCursorPositionY, wAttributes,
          srWindowsLeft, srWindowsTop, srWindowsRight, srWindowsBottom,
          dwMaximumWindowsSizeX, dwMaximumWindowsSizeY) = \
                                    struct.unpack(structFmt, screenBufInf.raw)
         width = srWindowsRight - srWindowsLeft
         height = srWindowsBottom - srWindowsTop
   except ImportError as err:
      # Posix
      try:
         import fcntl, termios
         tioGetWindowsSize = struct.pack("HHHH", 0, 0, 0, 0)
         ret = fcntl.ioctl(1, termios.TIOCGWINSZ, tioGetWindowsSize)
         height, width = struct.unpack("HHHH", ret)[:2]
      except Exception as err:
         # Unknown error
         pass
   else:
      # Unknown error
      pass

   import builtins
   if hasattr(builtins, '_esxcli_screen_width'):
      width = builtins._esxcli_screen_width
   return height, width


## Format primitive type value
#
# @param  val Vmomi type
# @return Formatted primitive value
def _FormatPrimitive(val):
   """ Format primitive type value """
   result = ""
   if val is None:
      pass
   elif isinstance(val, bool):
      result = val and "true" or "false"
   elif isInteger(val) or isinstance(val, float):
      result = str(val)
   elif isString(val):
      result = val
   elif isinstance(val, VmodlTypes.ManagedMethod):
      result = val.info.name
   elif isinstance(val, VmodlTypes.ManagedObject):
      result = val._moId
   elif isinstance(val, type):
      result = val.__name__
   else:
      # assert(not _IsPrimitiveFormat(type(val)))
      result = str(val)
   return result


## Format display name by splitting at CamelCase boundaries
#
# @param  name
# @return Capitalized and space-seperated camel case name
RE_CAMEL_SPLIT = re.compile('(?<=[a-z])(?=[A-Z])')
def SplitCamelCaseName(name):
   name = RE_CAMEL_SPLIT.sub(' ', name)
   return name[0].capitalize() + name[1:]


## Container to store type hints
#
class TypeHints:
   def __init__(self, typ, propList=None):
      assert(issubclass(typ, VmodlTypes.DataObject))
      self.typ = typ
      if propList:
         displayNameList = [SplitCamelCaseName(prop.name) for prop in propList]
      else:
         displayNameList, propList = [], []
      self.displayNameList, self.propList = displayNameList, propList
      self.header = []
      self.show_header = True
      self.wrap_last = False
      self.fieldHints = {}


## Container to store primitive hints
#
class PrimitiveHints:
   def __init__(self, typ):
      self.typ = typ
      self.unit = None
      self.format = None


## Type hints parser
#
class TypeHintsParser:
   ## Constructor
   #
   # @param  fnGetPropertyList Function to get property list from type
   def __init__(self, fnGetPropertyList):
      self._fnGetPropertyList = fnGetPropertyList

   ## Parse boolean val
   #
   # @param val string boolean val
   # @return True / False
   @staticmethod
   def ParseBool(val):
      return val.lower() not in ("0", "false", "f", "no", "n")

   ## Strip cisplay name (for use as variable name)
   #
   # @param  name to strip
   # @return Stripped name
   @staticmethod
   def _StripName(name):
      """ Strip name (for use as variable name) """
      return "".join([ch for ch in name
                         if ch.isalpha() or ch.isdigit() or ch == "_"])

   ## Order properties
   #
   # @param  doType     Data object type
   # @param  propOrder  Comma separated property name
   # @return Ordered lists of [display name], [property]
   def _OrderProp(self, doType, propOrder=None):
      """ Order properties """
      assert(issubclass(doType, VmodlTypes.DataObject))
      orderedNames, orderedProps = [], []
      propList = self._fnGetPropertyList(doType)

      if propOrder:
         # Ignore a single ending ',' to be consistent with /bin/localcli.
         if propOrder.endswith(','):
            propOrder = propOrder[:-1]

         propNames = propOrder.split(",")
         propDict = dict([(prop.name.lower(), prop) for prop in propList])

         # Order prop according to hints
         for displayName in propNames:
            name = TypeHintsParser._StripName(displayName.lower())
            prop = propDict.get(name)
            if prop:
               orderedNames.append(displayName.strip())
               orderedProps.append(prop)
            else:
               message = "Error: Unknown field in field list: " + displayName
               raise Exception(message)
      else:
         # Build prop dict (indexed with prop.name)
         orderedNames = [SplitCamelCaseName(prop.name) for prop in propList]
         orderedProps = propList
      return orderedNames, orderedProps

   ## Get vmodl type
   #
   # @param  typeName Vmodl type name
   # @return Returns type if exists, None if not found
   @staticmethod
   def _GetVmodlType(typeName):
      try:
         return VmomiSupport.GetVmodlType(typeName)
      except KeyError:
         return None

   ## Get type and fieldname
   #
   # @param  typeAndField  Vmodl typename, where the last componend is the
   #                       field name e.g. foo.bar => type foo fieldname bar
   # @return Returns type, fieldName tuples
   def _GetTypeAndFieldName(self, typeAndField):
      idx = typeAndField.rfind(".")
      if idx < 0:
         return None, None
      typeName, fieldName = typeAndField[:idx], typeAndField[idx + 1:]
      typ = self._GetVmodlType(typeName)
      if typ:
         fieldNames, _ = self._OrderProp(typ, fieldName)
         fieldName = fieldNames[0]
      return typ, fieldName

   ## Parse format-params
   #
   # @param  root Root vmodl name (to look for types)
   # @param  defType Default type associated with hints
   # @param  formatParams Format params in key=val sequence
   # @return dict of type to hints mapping
   def ParseFormatParams(self, root, defType, formatParams):
      # TODO: Better error handling
      hints = dict([param.split("=", 1) for param in formatParams
                                        if param.find("=") > 0])
      return self.ParseHints(root, defType, hints)

   ## Parse hints
   #
   # @param  root Root vmodl name (to look for types)
   # @param  defType Default type associated with hints
   # @param  formatParams Format params in key=val sequence
   # @return dict of type to hints mapping
   def ParseHints(self, root, defType, hints):
      """ Parse type hints """
      typeHints = {}

      if not root or not defType or not hints:
         return typeHints

      # Insert def return val formatter
      if issubclass(defType, VmomiSupport.Array):
         typ = defType.Item
      else:
         typ = defType
      if issubclass(typ, VmodlTypes.DataObject):
         # Add default type hints
         defType = typ

         # Insert type info
         info = TypeHints(defType, propList=self._fnGetPropertyList(defType))
         typeHints.setdefault(typ, info)

         # Parse struct hints
         fieldGrpName = "field"
         regex = re.compile("%(?P<" + fieldGrpName + ">.*)%")

         for key, val in hints.items():
            if key.startswith("header"):
               # Handle header
               # Find type
               if key.find(":") >= 0:
                  typeName = ".".join([root, key.split(":", 1)[1]])
               else:
                  typeName = defType.__name__
               typ = self._GetVmodlType(typeName)

               if typ:
                  # TODO: Remove "<NONE>" case
                  if val and val != "<NONE>":
                     info = typeHints.setdefault(typ, TypeHints(typ))

                     # field should appear in val as %{field}%
                     match = regex.search(val)
                     if match:
                        name = match.group(fieldGrpName)

                        _, props = self._OrderProp(typ, name)
                        headerProp = props[0]

                        header = [val[:match.start()],
                                  headerProp,
                                  val[match.end():]]
                     else:
                        # No header field
                        header = [val]

                     info.header = header
               else:
                  message = "Invalid key val: key (%s) val (%s)" % (key, val)
                  logging.error(message)
            elif key == "list-header":
               # Find type
               typeName = defType.__name__
               typ = self._GetVmodlType(typeName)

               if typ and val:
                  info = typeHints.setdefault(typ, TypeHints(typ))

                  # Parse val
                  _, header = self._OrderProp(typ, val)
                  info.header = header
               else:
                  message = "Invalid key val: key (%s) val (%s)" % (key, val)
                  logging.error(message)
            elif key.startswith("fields") \
                  or key == "table-columns" \
                  or key == "list-order":
               # Handle fields
               if key.find(":") >= 0:
                  typeName = ".".join([root, key.split(":", 1)[1]])
               else:
                  typeName = defType.__name__
               typ = self._GetVmodlType(typeName)

               if typ and val:
                  info = typeHints.setdefault(typ, TypeHints(typ))

                  # Parse val
                  info.displayNameList, info.propList = self._OrderProp(typ, val)
               else:
                  message = "Invalid key val: key (%s) val (%s)" % (key, val)
                  logging.error(message)
            elif key.startswith("units"):
               # Extract units
               if key.find(":") >= 0 and val:
                  typeName = ".".join([root, key.split(":", 1)[1]])
                  # Find type, and fieldName
                  typ, fieldName = self._GetTypeAndFieldName(typeName)
                  if typ and fieldName:
                     info = typeHints.setdefault(typ, TypeHints(typ))

                     # Parse val
                     hints = info.fieldHints.setdefault(fieldName,
                                                        PrimitiveHints(typ))
                     hints.unit = val
                  else:
                     message = "Invalid key val: key (%s) val (%s)" % (key, val)
                     logging.error(message)
            elif key.startswith("printf"):
               # Extract printf
               if key.find(":") >= 0 and val:
                  typeName = ".".join([root, key.split(":", 1)[1]])
                  # Find type, and fieldName
                  typ, fieldName = self._GetTypeAndFieldName(typeName)
                  if typ and fieldName:
                     info = typeHints.setdefault(typ, TypeHints(typ))

                     # Parse val
                     hints = info.fieldHints.setdefault(fieldName,
                                                        PrimitiveHints(typ))

                     # TODO: Regex check val to make sure it is valid
                     hints.format = val
                  else:
                     message = "Invalid key val: key (%s) val (%s)" % (key, val)
                     logging.error(message)
            elif key.startswith("show-header"):
               # Find type
               if key.find(":") >= 0:
                  typeName = ".".join([root, key.split(":", 1)[1]])
               else:
                  typeName = defType.__name__
               typ = self._GetVmodlType(typeName)

               if typ and val:
                  info = typeHints.setdefault(typ, TypeHints(typ))

                  # Parse val
                  info.show_header = self.ParseBool(val)
               else:
                  message = "Invalid key val: key (%s) val (%s)" % (key, val)
                  logging.error(message)
            elif key == "wrap-last":
               typeName = defType.__name__
               typ = self._GetVmodlType(typeName)
               if typ and val:
                  info = typeHints.setdefault(typ, TypeHints(typ))

                  # Parse val
                  info.wrap_last = self.ParseBool(val)
            elif key == "align-fields": # TODO:
               pass
            elif key == "header-line": # TODO:
               pass

      return typeHints


## Text Output formatter
#
class TextOutputFormatter:
   """ Output formatter class """

   ## Output formattor
   #
   # @param  root Root vmodl name (to look for types)
   # @param  retType Return type associated with hints
   # @param  hints Format hints
   def __init__(self, root=None, retType=None, hints=None):
      """ Constructor """
      self.indentInc = 3

      # Set list formatter
      listFormatter = self._FormatDoList
      if hints:
         formatter = hints.get("formatter")
         if formatter == "table":
            listFormatter = self._FormatDoListAsTable
         elif not formatter:
            listFormatter = None
      self.listFormatter = listFormatter

      # Handle other hints
      self.typeHints = {}
      hintsParser = TypeHintsParser(self._GetPropertyList)
      self.typeHints = hintsParser.ParseHints(root, retType, hints)

   ## Get non hidden properties list
   #
   # @param  typ Vmomi type
   # @return Non-hidden properties list
   @Cache
   def _GetPropertyList(self, typ):
      """ Get non hidden properties list """
      hiddenAttrs = ["dynamicType", "dynamicProperty"]
      return [prop for prop in typ._GetPropertyList()
                   if prop.name not in hiddenAttrs]

   ## Get format hints
   #
   # @param  typ Vmomi type
   # @return Format hints
   def _GetHints(self, typ):
      hints = self.typeHints.get(typ)
      if not hints:
         # Create default hints
         hints = TypeHints(typ, self._GetPropertyList(typ))
         self.typeHints[typ] = hints
      return hints

   ## Format data object header
   #
   # @param  do Data object
   # @param  header Do header (generate by _AddHints)
   # @return Formatted header lines
   def _FormatDoHeader(self, do, header):
      headerLines = []
      for prop in header:
         if isString(prop):
            formatted = prop
         else:
            propVal = getattr(do, prop.name)
            formatted = self.Format(propVal)
         headerLines.append(formatted)
      return headerLines

   ## Format primitive type value
   #
   # @param  val Vmomi type
   # @param  hints Type hints
   # @return Formatted primitive value
   def _FormatPrimitive(self, val, hints):
      formatted = _FormatPrimitive(val)
      if hints:
         printFmt = hints.format
         if printFmt:
            try:
               formatted = printFmt % val
            except Exception:
               # In case printFmt is bad...
               pass
         unit = hints.unit
         if unit:
            formatted = " ".join([formatted, unit])
      return formatted

   ## Format list of data object into table (for data obj with only primitive
   #  format properties)
   #
   # @param  val Vmomi type
   # @param  hints Type hints
   # @return str of val formatted as table
   def _FormatDoListAsTable(self, val, hints):
      """ Format list of val into table """
      # Generate header
      # Separate loop for clarity. If looping through propList multiple time is
      # cauing performance problem, can put them back into one loop
      displayNameList = hints.displayNameList
      lines = []

      # Init min len (property name len)
      minLen = [len(name) for name in displayNameList]

      # Per col info
      RIGHT_JUSTIFY = 0x1
      flags = [0] * len(displayNameList)

      # Loop through list to format properties and update min len
      propList = hints.propList
      for item in val:
         props = []
         for idx, (displayName, prop) in enumerate(zip(displayNameList,
                                                       propList)):
            # Integer need to right justified
            if isIntegerSubClass(prop.type) or isinstance(prop.type, float):
               # Right justify value
               flags[idx] |= RIGHT_JUSTIFY

            # Get property value
            propVal = getattr(item, prop.name)
            fieldHints = hints.fieldHints.get(displayName)
            formatted = self.Format(propVal, hints=fieldHints)
            # Find min property name
            minLen[idx] = max(minLen[idx], len(formatted))
            props.append(formatted)
         lines.append(props)

      if hints.wrap_last:
         # Wrap last column.
         lastColumnName = displayNameList[-1]
         terminalWidth = GetConsoleSize()[1]
         wrapIndent = 0;
         for tmpMinLen in minLen[:-1]: # Skip last column length.
            wrapIndent += tmpMinLen + 2 # 2 for column separator

         # Do not wrap last column if not enough space.
         if wrapIndent + len(lastColumnName) <= terminalWidth:
            minLen[-1] = terminalWidth - wrapIndent

         indent = ' ' * wrapIndent

         def WrapText(width, indent, text):
            if width <= 0:
               # Do not wrap.
               return [indent + text]
            from textwrap import TextWrapper
            tw = TextWrapper(width=width)
            tw.initial_indent = tw.subsequent_indent = indent
            return tw.wrap(text)

         for line in lines[1:]: # Skip first line with column names.
            val = line[-1]
            # Handle \n in val.
            valLines = val.split("\n")
            newValLines = []
            for currentValLine in valLines:
               newValLines.extend(WrapText(terminalWidth, indent, currentValLine))

            # Remove the initial indent from the beginning.
            if len(newValLines) > 0:
               newValLines[0] = newValLines[0][wrapIndent:]

            line[-1] = "\n".join(newValLines)
      if hints.show_header:
          separator = ["-" * size for size in minLen]
          if flags[-1] == 0:
             # If RIGHT_JUSTIFY is not set, the separator for the last column
             # should be the size of the column name.
             separator[-1] = "-" * len(displayNameList[-1])
          lines.insert(0, displayNameList)
          lines.insert(1, separator)

      # Merge result
      colSep = " " * 2
      result = []
      for item in lines:
         props = []
         for col, size, flag in zip(item, minLen, flags):
            pad = " " * (size - len(col))
            if flag & RIGHT_JUSTIFY:
               props.append(pad + col)
            else:
               if len(props) == len(item) - 1:
                  # Do not pad the last column.
                  pad = ""
               props.append(col + pad)

         line = colSep.join(props)
         result.append(line.rstrip())

      return result

   ## Format a data object (simple one property per line format)
   #
   # @param  item Vmomi data object
   # @param  hints Type hints
   # @return str of val formatted as list
   def _FormatDataObject(self, item, hints):
      """ Format data object (one property per line) """
      result = []
      # Header
      header = hints.header
      if len(header) > 0:
         headerLines = self._FormatDoHeader(item, header)
         result.append("".join(headerLines))

      # The rest of value
      indent = " " * self.indentInc
      for displayName, prop in zip(hints.displayNameList, hints.propList):
         propVal = getattr(item, prop.name)
         fieldHints = hints.fieldHints.get(displayName)
         formatted = self.Format(propVal, self.indentInc * 2, fieldHints)
         line = indent + displayName + ": "
         if formatted.find("\n") >= 0:
            line += "\n" + formatted
         else:
            line += formatted[self.indentInc * 2:]
         result.append(line)
      return result

   ## Format list of data object (simple one property per line format)
   #
   # @param  val Vmomi type
   # @param  hints Type hints
   # @return str of val formatted as list
   def _FormatDoList(self, val, hints):
      """ Format list of data object (one property per line) """
      result = []
      for item in val:
         result.extend(self._FormatDataObject(item, hints))
         result.append("")
      # Remove extra line break from the last line
      if len(result) > 0 and result[-1] == "":
         result.pop()
      return result

   ## Format list of primitives
   #
   # @param  val Vmomi type
   # @param  hints Type hints
   # @return str of val formatted as list
   def _FormatPrimitiveList(self, val, hints):
      # Put everything in one line
      listVal = ", ".join([self._FormatPrimitive(item, hints) for item in val])
      result = [listVal]
      return result

   # Format value
   #
   # @param  val Value to format
   # @param  numIndent Indentation
   # @param  hints Type hints
   # @return Formatted value, suitable for output to screen
   def Format(self, val, numIndent=0, hints=None):
      """ Format val """
      # Handle null formatter
      if not self.listFormatter:
         return

      result = ""
      indent = " " * numIndent
      if isinstance(val, VmodlTypes.DataObject):
         # DataObject. Trest as an array with 1 element
         result = self.Format([val], numIndent, hints)
      elif isinstance(val, list) or isinstance(val, VmomiSupport.Array):
         if val:
            # If Item type are data object
            valType = getattr(val, "Item", val[0].__class__)
            if issubclass(valType, VmodlTypes.DataObject):
               if not hints:
                  hints = self._GetHints(valType)
               lines = self.listFormatter(val, hints)
            else:
               assert(not issubclass(valType, list))
               # List of simple type
               lines = self._FormatPrimitiveList(val, hints)
            result = indent + ("\n" + indent).join(lines)
         else:
            # Empty list
            result = indent
      else:
         # Primitive value
         result = indent + self._FormatPrimitive(val, hints)
      return result


## HTML output formatter
#
class HtmlOutputFormatter(TextOutputFormatter):
   """ Output formatter class that generates HTML-formatted output """

   ## HTML output formattor
   #
   # @param  root Root vmodl name (to look for types)
   # @param  retType Return type associated with hints
   # @param  hints Format hints
   def __init__(self, root=None, retType=None, hints=None):
      TextOutputFormatter.__init__(self, root, retType, hints)

   ## Format display name by CGI-escaping and splitting at CamelCase boundaries
   #
   # @param name Display name
   # @return Formatted display name
   def _FormatDisplayName(self, name):
      """ Format display name by CGI-escaping and splitting at CamelCase boundaries """
      import cgi
      return cgi.escape(SplitCamelCaseName(name))

   ## Format value by CGI-escaping and replacing newlines with <br/>
   #
   # @param val Value
   # @param hints Type hints
   # @return Formatted value
   def _FormatValue(self, val, hints):
      """ Format value by CGI-escaping and replacing newlines with <br> """
      import cgi
      return cgi.escape(self.Format(val, hints=hints).replace('\n', '<br/>'))

   ## Format list of data object into table (for data obj with only primitive
   #  format properties)
   #
   # @param  val Vmomi type
   # @param  hints Type hints
   # @return str of val formatted as table
   def _FormatDoListAsTable(self, val, hints):
      """ Format list of val into HTML table """
      rows = []
      # Generate header
      rows += [''.join(['<th>%s</th>' % self._FormatDisplayName(displayName)
                           for displayName in hints.displayNameList])]

      # Loop through list to format properties
      for item in val:
         props = []
         for displayName, prop in zip(hints.displayNameList, hints.propList):
            # Get property value
            propVal = getattr(item, prop.name)
            fieldHints = hints.fieldHints.get(displayName)
            value = self._FormatValue(propVal, fieldHints)
            props.append('<td>%s</td>' % value)
         rows += [''.join(props)]

      # Merge result
      logging.info(rows)
      return ['<table>'] + ['<tr>%s</tr>' % r for r in rows] + ['</table>']

   ## Format list of data object (simple one property per line format)
   #
   # @param  val Vmomi type
   # @param  hints Type hints
   # @return str of val formatted as list
   def _FormatDoList(self, val, hints):
      """ Format list of data object (one property per line) """
      result = []
      for item in val:
         # Header
         header = hints.header
         if len(header) > 0:
            headerLines = self._FormatDoHeader(item, header)
            result.append('<h3>%s</h3>' % "".join(headerLines))

         # The rest of value
         result.append('<table>')
         for displayName, prop in zip(hints.displayNameList, hints.propList):
            propVal = getattr(item, prop.name)
            label = self._FormatDisplayName(displayName)
            fieldHints = hints.fieldHints.get(displayName)
            value = self._FormatValue(propVal, fieldHints)
            result.append('<tr><th class="rt">%s</th><td width="90%%">%s</td></tr>' % (label, value))
         result.append('</table><br/>')

      return result


## Encoding factory
#
def EncodedOutputFactory(fp, encoding=None):
   """ Encoding output factory """
   if fp and encoding:
      return EncodedOutput(fp, encoding)
   else:
      return fp


## Encoded output
#
class EncodedOutput:
   """ Encoded output """
   def __init__(self, fp, encoding):
      assert(fp)
      assert(encoding)
      self.fp = fp
      self.encoding = encoding

   def write(self, text):
      self.fp.write(self._Encode(text))

   def writelines(self, seq):
      self.fp.writelines([self._Encode(l) for l in seq])

   def _Encode(self, text):
      if text and not isPython3():
         return text.encode(self.encoding)
      else:
         return text


## Output with indentation
#
class IndentableOutput:
   """ Indentable output """
   def __init__(self, fp=None, inc=3, indentChar=" "):
      if not fp:
         fp = sys.stdout
      self.fp = fp
      self._inc = inc
      self._indChr = indentChar
      self._currIndent = 0
      self._indented = False
      self._eol = os.linesep
      self.encoding = fp.encoding

   def write(self, text):
      self.fp.write(self._Indent(text))

   def writelines(self, seq):
      self.fp.writelines([self._Indent(l) for l in seq])

   def writeln(self, text):
      """ Write a line, adding eol """
      self.fp.write(self._Indentln(text))

   def writelnlines(self, seq):
      """ Write lines, adding eol to each line """
      self.fp.writelines([self._Indentln(l) for l in seq])

   def _Indent(self, text):
      """ Adding indentation to text """
      if not text or self._currIndent <= 0:
         return text

      # Optimize for single linesep
      if text == self._eol:
         self._indented = False
         return text

      indentStr = self._indChr * self._currIndent
      prevIndented = self._indented
      if not prevIndented:
         text = indentStr + text

      # Check text and if there is trailing \n, reset _indented to False
      lines = text.split(self._eol)
      if lines[-1] == '':
         result = (self._eol + indentStr).join(lines[:-1]) + self._eol
         self._indented = False
      else:
         result = (self._eol + indentStr).join(lines)
         self._indented = True
      return result

   def _Indentln(self, text):
      """ Adding indentation and linesep to text """
      return self._Indent(text + self._eol)

   def indent(self, cnt=1):
      """ Indent """
      self._currIndent += self._inc * cnt

   def dedent(self, cnt=1):
      """ Dedent """
      dedentCnt = self._inc * cnt
      if self._currIndent > dedentCnt:
         self._currIndent -= dedentCnt
      else:
         self.reset()

   def reset(self, indent=0):
      """ Reset indentation """
      currIndent = self._currIndent
      self._currIndent = indent
      return currIndent


## Script output formatter
#
class BaseVisitor:
   """ All visit flags """
   FLAG_NONE = 0x0
   FLAG_LAST_ITEM = 0x1

   """ Base script format visitor """
   def __init__(self):
      pass

   # Override-able visitor fn
   #
   # def VisitRootBegin(self, val):
   # def VisitRootEnd(self, val):
   # def VisitDoBegin(self, do):
   # def VisitDoEnd(self, do):
   # def VisitDoFieldBegin(self, fieldName, flags, val):
   # def VisitDoFieldEnd(self, fieldName, flags, val):
   # def VisitListBegin(self, lst):
   # def VisitListEnd(self, lst):
   # def VisitListItemBegin(self, idx, flags, val):
   # def VisitListItemEnd(self, idx, flags, val):
   # def VisitPrimitive(self):

   ## Get non hidden properties list
   #
   # @param  typ Vmomi type
   # @return Non-hidden properties list
   @Cache
   def _GetPropertyList(self, typ):
      """ Get non hidden properties list """
      hiddenAttrs = ["dynamicType", "dynamicProperty"]
      return [prop for prop in typ._GetPropertyList()
                   if prop.name not in hiddenAttrs]

   def _Fn(self, fnName):
      # TODO: Should also check if fn is callable or not
      return getattr(self, fnName, self._NullFn)

   def _NullFn(self, *args, **kwargs):
      pass

   def VisitDo(self, do):
      self._Fn("VisitDoBegin")(do)

      fnVisitDoFieldBegin = self._Fn("VisitDoFieldBegin")
      fnVisitDoFieldEnd = self._Fn("VisitDoFieldEnd")

      # Iterate through each prop and format
      propList = self._GetPropertyList(VmomiSupport.Type(do))
      lastIdx = len(propList)
      for idx, prop in zip(range(0, lastIdx), propList):
         flags = self.FLAG_NONE
         if idx == (lastIdx - 1):
            flags |= self.FLAG_LAST_ITEM
         propVal = getattr(do, prop.name)
         fnVisitDoFieldBegin(prop.name, flags, propVal)
         self.Visit(propVal)
         fnVisitDoFieldEnd(prop.name, flags, propVal)

      self._Fn("VisitDoEnd")(do)

   def VisitList(self, lst):
      self._Fn("VisitListBegin")(lst)
      lastIdx = len(lst)
      for idx, val in zip(range(0, lastIdx), lst):
         flags = self.FLAG_NONE
         if idx == (lastIdx - 1):
            flags |= self.FLAG_LAST_ITEM
         self._Fn("VisitListItemBegin")(idx, flags, val)
         self.Visit(val)
         self._Fn("VisitListItemEnd")(idx, flags, val)
      self._Fn("VisitListEnd")(lst)

   def VisitRoot(self, val):
      """ Visit @ root level """
      self._Fn("VisitRootBegin")(val)
      self.Visit(val)
      self._Fn("VisitRootEnd")(val)

   def Visit(self, val):
      """ Visit val """
      if isinstance(val, VmodlTypes.DataObject):
         self.VisitDo(val)
      elif isinstance(val, list) or isinstance(val, VmomiSupport.Array):
         self.VisitList(val)
      else:
         self._Fn("VisitPrimitive")(val)


## Base esxscript formatter
#
class EsxscriptVisitor(BaseVisitor):
   def __init__(self, root=None, retType=None, formatParams=None):
      BaseVisitor.__init__(self)
      self.typeHints = {}
      hintsParser = TypeHintsParser(self._GetPropertyList)
      self.typeHints = hintsParser.ParseFormatParams(root, retType,
                                                     formatParams)

   ## Sorted property list in alphabetical order
   #
   # @param  typ Vmomi type
   # @return Sorted non-hidden properties list
   @Cache
   def _GetPropertyList(self, typ):
      import operator
      return sorted(BaseVisitor._GetPropertyList(self, typ),
                    key=operator.attrgetter("name"))

   ## Get format hints
   #
   # @param  typ Vmomi type
   # @return Format hints
   def _GetHints(self, typ):
      hints = self.typeHints.get(typ)
      if not hints:
         # Create default hints
         hints = TypeHints(typ, self._GetPropertyList(typ))
         self.typeHints[typ] = hints
      return hints

   ## Script type name
   #
   # @param  typ Vmomi type
   # @return esxscript type name
   @staticmethod
   def _ScriptTypeName(typ):
      if issubclass(typ, VmodlTypes.DataObject):
         typeName = "structure"
      elif issubclass(typ, bool):
         typeName = "boolean"
      elif isIntegerSubClass(typ):
         typeName = "integer"
      else:
         # All else assumed to be string
         typeName = "string"
      return typeName

   ## Script data object name
   #
   # @param  do Vmomi data object
   # @return The leaf type name
   @staticmethod
   def _DoName(do):
      return VmomiSupport.Type(do).__name__.split(".")[-1]

   ## Format a val
   #
   # @param  val Value to format
   def Format(self, val):
      """ Format a val. Alias to VisitRoot """
      self.VisitRoot(val)


## Xml format visitor
#
class XmlVisitor(EsxscriptVisitor):
   """ Xml format visitor """
   def __init__(self, fp=None, root=None, retType=None, formatParams=[]):
      EsxscriptVisitor.__init__(self, root, retType, formatParams)
      self.fp = IndentableOutput(fp)

   def VisitRootBegin(self, val):
      # Xml tag attribute
      attrs = ['version="1.0"']
      # TODO: Make sure encoding name is mappable to xml encoding
      encoding = getattr(self.fp, "encoding", None)
      if encoding:
         attrs.append('encoding="%s"' % encoding.lower().replace("_", "-"))

      # TODO: Add <meta-data> after root tag
      self.fp.writelnlines(
            ['<?xml %s?>' % " ".join(attrs),
             '<output xmlns="http://www.vmware.com/Products/ESX/5.0/esxcli">',
             '<root>'])
      self.fp.indent()

   def VisitRootEnd(self, val):
      self.fp.dedent()
      self.fp.writelines(['</root>', os.linesep,
                          '</output>', os.linesep])

   def VisitDoBegin(self, do):
      typeName = self._DoName(do)
      self.fp.writeln('<structure typeName="%s">' % XmlEscape(typeName))
      self.fp.indent()

   def VisitDoEnd(self, do):
      self.fp.dedent()
      self.fp.writeln('</structure>')

   def VisitDoFieldBegin(self, fieldName, flags, val):
      self.fp.writeln('<field name="%s">' % XmlEscape(fieldName))
      self.fp.indent()

   def VisitDoFieldEnd(self, fieldName, flags, val):
      self.fp.dedent()
      self.fp.writeln('</field>')

   def VisitListBegin(self, lst):
      itemType = lst.Item
      typeName = self._ScriptTypeName(itemType)
      self.fp.writeln('<list type="%s">' % XmlEscape(typeName))
      self.fp.indent()

   def VisitListEnd(self, lst):
      self.fp.dedent()
      self.fp.writeln('</list>')

   def VisitPrimitive(self, val):
      typ = VmomiSupport.Type(val)
      typeName = self._ScriptTypeName(typ)

      formatted = _FormatPrimitive(val)
      self.fp.writeln("<%s>%s</%s>" % (typeName,
                                       XmlEscape(formatted),
                                       typeName))


## Key-value pair format visitor
#
class KeyValueVisitor(EsxscriptVisitor):
   """ Key-value pair format visitor """
   def __init__(self, fp=None, root=None, retType=None, formatParams=[]):
      EsxscriptVisitor.__init__(self, root, retType, formatParams)
      if fp is None:
         fp = sys.stdout
      self.fp = fp
      self.keys = []

   def VisitRootBegin(self, val):
      self.keys = []

   def VisitRootEnd(self, val):
      self.keys = []

   def VisitDoBegin(self, do):
      typeName = self._DoName(do)
      self.keys.append(typeName)

   def VisitDoEnd(self, do):
      self.keys.pop()

   def VisitDoFieldBegin(self, fieldName, flags, val):
      self.keys.append(fieldName)

   def VisitDoFieldEnd(self, fieldName, flags, val):
      self.keys.pop()

   def VisitListBegin(self, lst):
      itemType = lst.Item
      typeName = self._ScriptTypeName(itemType)
      self.keys.append(typeName)
      if len(lst) == 0:
         self.fp.write(".".join(self.keys) + "[] = ")
         self.fp.write(os.linesep)

   def VisitListEnd(self, lst):
      self.keys.pop()

   def VisitListItemBegin(self, idx, flags, val):
      key = self.keys[-1] + "[%d]" % idx
      self.keys[-1] = key

   def VisitListItemEnd(self, idx, flags, val):
      key = self.keys[-1]
      self.keys[-1] = key[:key.rfind("[")]

   def VisitPrimitive(self, val):
      typ = VmomiSupport.Type(val)
      typeName = self._ScriptTypeName(typ)

      # Avoid extra dot for top level primitive
      keys = [typeName]
      if self.keys:
         keys.insert(0, ".".join(self.keys))
      key = ".".join(keys)

      # Escape multi lines output
      val = _FormatPrimitive(val).replace("\n", "\\n")

      self.fp.write("=".join([key, val]))
      self.fp.write(os.linesep)


## Csv format visitor
#
# TODO: Eliminate trailing comma from csv
class CsvVisitor(EsxscriptVisitor):
   """ Csv format visitor """

   def __init__(self, fp=None, root=None, retType=None, formatParams=[]):
      EsxscriptVisitor.__init__(self, root, retType, formatParams)
      if fp is None:
         fp = sys.stdout
      self.fp = fp
      self._checkHeader = False
      self._quoteLevel = 0
      self._sep = "," # Change to ';' for German csv
      self._quote = '"'

   def _GetPropertyList(self, typ):
      hints = self.typeHints.get(typ)
      if hints:
         return hints.propList
      else:
         return EsxscriptVisitor._GetPropertyList(self, typ)

   def _BeginQuote(self):
      if self._quoteLevel > 0:
         self.fp.write(self._quote * self._quoteLevel)
      self._quoteLevel += 1

   def _EndQuote(self):
      self._quoteLevel -= 1
      if self._quoteLevel > 0:
         self.fp.write(self._quote * self._quoteLevel)

   def VisitRootBegin(self, val):
      self._checkHeader = True
      if isinstance(val, list) or isinstance(val, VmomiSupport.Array):
         self._quoteLevel = 0
      else:
         self._quoteLevel = 1

   def VisitRootEnd(self, val):
      if isinstance(val, list) or isinstance(val, VmomiSupport.Array):
         assert(self._quoteLevel == 0)
      else:
         assert(self._quoteLevel == 1)

   def VisitListBegin(self, lst):
      if lst and len(lst) > 0:
         self._BeginQuote()

   def VisitListEnd(self, lst):
      if lst and len(lst) > 0:
         self._EndQuote()

   def VisitListItemBegin(self, idx, flags, val):
      if idx == 0:
         self._checkHeader = True

   def VisitListItemEnd(self, idx, flags, val):
      self._checkHeader = False
      if not isinstance(val, VmodlTypes.DataObject):
         self.fp.write(self._sep)

   def VisitDoBegin(self, do):
      if self._checkHeader:
         typ = VmomiSupport.Type(do)
         show_header = self._GetHints(typ).show_header
         if show_header:
            # Iterate through each prop and print header
            propList = self._GetPropertyList(typ)
            self.fp.write(self._sep.join([prop.name for prop in propList]))
            # TODO: Eliminate trailing comma
            self.fp.write(self._sep)
            self.fp.write(os.linesep)
      self._checkHeader = False

   def VisitDoEnd(self, do):
      self.fp.write(os.linesep)

   def VisitDoFieldBegin(self, fieldName, flags, val):
      if isinstance(val, VmodlTypes.DataObject):
         self._BeginQuote()

   def VisitDoFieldEnd(self, fieldName, flags, val):
      if isinstance(val, VmodlTypes.DataObject):
         self._EndQuote()
      self.fp.write(self._sep)

   def VisitPrimitive(self, val):
      # Escape multi lines output, and escape comma
      formatted = _FormatPrimitive(val)
      fQuoteFormatted = False

      # Follow the csv wiki / RFC4180:
      # Enclosed val with double quotes if val contains , " or line break
      # Also esacpe double quotes with double quote
      if formatted.find(self._sep) >=0:
         fQuoteFormatted = True
      if formatted.find("\n") >=0:
         # TODO: Use the following if \n is allowed in string value
         # fQuoteFormatted = True

         # Escape \n in string value
         formatted = formatted.replace("\n", "\\n")
      if formatted.find(self._quote) >=0:
         # Escape double quote
         formatted = formatted.replace(self._quote,
                                       self._quote * self._quoteLevel * 2)
         fQuoteFormatted = True
      if fQuoteFormatted:
         quotes = self._quote * self._quoteLevel
         self.fp.writelines([quotes, formatted, quotes])
      else:
         self.fp.write(formatted)


## Python format visitor
#
class PythonVisitor(EsxscriptVisitor):
   """ Python format visitor """
   def __init__(self, fp=None, root=None, retType=None, formatParams=[]):
      EsxscriptVisitor.__init__(self, root, retType, formatParams)
      if fp is None:
         fp = sys.stdout
      self.fp = fp

   def VisitRootBegin(self, val):
      pass

   def VisitRootEnd(self, val):
      self.fp.write(os.linesep)

   def VisitDoBegin(self, do):
      self.fp.write("{")

   def VisitDoEnd(self, do):
      self.fp.write("}")

   def VisitDoFieldBegin(self, fieldName, flags, val):
      self.fp.write('"%s": ' % fieldName)

   def VisitDoFieldEnd(self, fieldName, flags, val):
      if (flags & self.FLAG_LAST_ITEM) == 0:
         self.fp.write(", ")

   def VisitListBegin(self, lst):
      self.fp.write("[")

   def VisitListEnd(self, lst):
      self.fp.write("]")

   #def VisitListItemBegin(self, idx, flags, val):
   #   pass

   def VisitListItemEnd(self, idx, flags, val):
      if (flags & self.FLAG_LAST_ITEM) == 0:
         self.fp.write(", ")

   @staticmethod
   def _EscapeStr(val):
      return val.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')

   def _FormatPrimitive(self, val):
      result = ""
      if isinstance(val, bool):
         result = val and "True" or "False"
      elif isInteger(val) or isinstance(val, float):
         result = str(val)
      else:
         result = self._EscapeStr(_FormatPrimitive(val)).join(['"', '"'])
      return result

   def VisitPrimitive(self, val):
      val = self._FormatPrimitive(val)
      self.fp.write(val)


## Json format visitor
#
# Exactly like python vistor, except
# - No trailing , for field / list item
# - true / false (vs True / False)
# - Only double quotes
# - Must escape ", \, /, \b, \f, \n, \r, \t, and no control char in string
# - null instead of None
class JsonVisitor(PythonVisitor):
   """ Json format visitor """
   _EscapeLst = [(b"\\", b"\\\\"),
                 (b"/", b"\/"), # Not a must in python json implementaion
                 (b"\b", b"\\b"),
                 (b"\f", b"\\f"),
                 (b"\n", b"\\n"),
                 (b"\r", b"\\r"),
                 (b"\t", b"\\t"),
                 (b'"', b'\\"')]

   def __init__(self, fp=None, root=None, retType=None, formatParams=[]):
      PythonVisitor.__init__(self, fp, root, retType, formatParams)

   @staticmethod
   def _EscapeStr(val):
      ctrlChars = b"".join([b'%c' % c for c in range(32)])

      if isPython3():
         valBytes = val.encode()
      else:
         valBytes = val

      # Escape known control chars
      for org, new in JsonVisitor._EscapeLst:
         valBytes = valBytes.replace(org, new)

      # Remove all other control chars
      # TODO: Translate control char to \uXXXX ?
      valBytes.translate(None, ctrlChars)

      if isPython3():
         valBytes = valBytes.decode()

      return valBytes

   def _FormatPrimitive(self, val):
      result = ""
      if isinstance(val, bool):
         result = val and "true" or "false"
      elif isInteger(val) or isinstance(val, float):
         result = str(val)
      else:
         result = self._EscapeStr(_FormatPrimitive(val)).join(['"', '"'])
      return result
