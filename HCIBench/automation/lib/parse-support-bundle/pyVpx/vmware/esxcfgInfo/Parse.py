#!/usr/bin/python
# Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential
## Routines to parse esxcfg-info output.
#
# Module prints out schema paths for an esxcfg-info output.  The schema paths
# are used to define object path to table column mappings.

import string
import os
import re
import sys
from sys import argv
import controls.Table

rootGroupRegex = re.compile('^\+([^:]+) :\s*$')
groupRegex = re.compile('^(\s+)\\\\==\+(.+) :\s*$')
dataRegex = re.compile('^(\s+)\|----([^.]+)\.+(.*)')

## Set debug log level
gLoglevel = 1

## Debug log function
def Log(level, message):
   if (level <= gLoglevel):
      print message

## Perform an exhaustive search based on the path specified in rowPath.
#
# When an array schema path is encountered, it means the traversal should branch
# and search all nodes at the path.
#
# When a path that satisfies the full pathSpec is reached, the pathVisitor
# function object is run on the node end node.
#
# pathSpec describes the next paths to traverse for the node.
def WalkNodes(node, pathSpec, pathVisitor):
   # Base case
   if len(pathSpec) == 0:
      Log(4, "WalkNodes: Visiting node.")
      pathVisitor.Visit(node)
   
   for i in range(len(pathSpec)):
      step = pathSpec[i]

      Log(4, "WalkNodes: node='%s' name='%s' pathsLeft=%d" % \
          (node.GetName(), step, len(pathSpec)))

      children = node.GetChildrenByName(step)
      Log(5, "WalkNode: found %d children by name '%s'" % (len(children), step))

      for child in children:
         WalkNodes(child, pathSpec[i + 1:], pathVisitor)


## Utility class to build a table from esxcfg-info data
#
# skipPrefix describes how many paths off the table definition to skip since the
# tree could be relative to some path.
def CreateTable(tableDefinition, groupNode, skipPrefix=0):
   tableName = tableDefinition.tableName
   columnDefinitions = tableDefinition.columnDefinitions

   rowPaths = tableDefinition.buildSpec.rowPaths
   columnBuilders = tableDefinition.buildSpec.columnBuilders

   # Walk down tree structure by rowPath
   node = groupNode

   if node.GetName() != rowPaths[skipPrefix]:
      msg = "Name of root node '%s' does not match first row path '%s'." % \
            (node.GetName(), rowPaths[skipPrefix])
      raise Exception(msg)

   columnNames = map(lambda x: x.name, columnDefinitions)
   table = controls.Table.Table(tableName, columnNames)

   class PathVisitor:
      def __init__(self, table, columnBuilders):
         self._table = table
         self._columnBuilders = columnBuilders

      def Visit(self, node):
         row = {}
         for columnName in self._columnBuilders.keys():
            row[columnName] = columnBuilders[columnName].GetValue(node)
         table.Insert(row)

   WalkNodes(node, rowPaths[skipPrefix + 1:], PathVisitor(table, columnBuilders))

   return table

## Represents a container node in the tree of esxcfg values
class GroupNode:
   def __init__(self, name, prefix=None):
      self._name = name
      self._table = {}
      self._children = []
      self._schemaBasePath = prefix
      self._lineNumber = -1;

   def GetName(self):
      return self._name

   def SetName(self, name):
      if self._name == None:
         self._prefix = name
      self._name = name

   def Get(self, key):
      if not self._table.has_key(key):
         msg = "Invalid key '%s' on table '%s'" % (key, self.GetName())
         Log(1, msg)
         return "<invalid>"
      return self._table[key]

   def Set(self, key, value):
      self._table[key] = value

   def GetKeys(self, schemaFilter = None):
      keys = self._table.keys()
      if schemaFilter != None:
         keys = filter(lambda x: schemaFilter(self.GetSchemaPath() + "/" + x), keys)
      keys.sort()
      return keys

   def GetChildren(self):
      return self._children

   def GetChildrenByName(self, name):
      children = filter(lambda x: x.GetName() == name, self._children)
      return children

   def AppendChild(self, node):
      self._children.append(node)

   def GetSchemaPath(self):
      return self._schemaBasePath

   def SetLineNumber(self, lineNumber):
      self._lineNumber = lineNumber

   def GetLineNumber(self):
      return self._lineNumber

   def ToDebugString(self):
      s = ''
      for key in self.GetKeys():
         value = self.Get(key)
         s += "%s/%s = %s (line %d)\n" % \
              (self.GetSchemaPath(), key, str(value), self.GetLineNumber())

      for child in self.GetChildren():
         s += child.ToDebugString()

      return s

   def PrettyPrint(self, schemaFilter=None, indent=0):
      indentString = '   ' * indent
      groupString = "%s%s\n" % (indentString, self.GetName())

      indent += 1
      indentString = '   ' * indent

      s = ''
      for key in self.GetKeys(schemaFilter):
         value = self.Get(key)
         s += "%s%s = %s\n" % (indentString, key, str(value))

      for child in self.GetChildren():
         s += child.PrettyPrint(schemaFilter, indent)

      if s != "":
         return groupString + s
      else:
         return ""

   def GetSchemaPaths(self):
      paths = {}

      prefix = self.GetName() + "/"
      
      for key in self.GetKeys():
         s = "%s%s" % (prefix, key)
         if not paths.has_key(s):
            paths[s] = 0

         paths[s] += 1

      for child in self.GetChildren():
         childPaths = child.GetSchemaPaths()
         for path in childPaths:
            s = prefix + path
            if not paths.has_key(s):
               paths[s] = 0
            paths[s] += 1

      pathList = paths.keys()
      pathList.sort()
      return pathList

   def __repr__(self):
      return self.PrettyPrint(None, 0)
   

## Utility class to parse an ESX cfg tree and to filter nodes
class TextParser:
   def __init__(self):
      self._parsedTree = []
      pass

   def FullyQualifiedGroupName(self, groupStack, groupName):
      names = map(lambda x: x.GetName(), groupStack)
      names.append(groupName)
      path = "/".join(names)
      return path
      
   def Parse(self, file):
      currentGroup = GroupNode('')
      self._parsedTree = currentGroup

      groupStack = []
      spacesStack = []

      currentSpaces = 0
      lineCount = 0
      for line in file:
         line = line.rstrip()
         
         lineCount = lineCount + 1
         Log(9, "TextParser.Parse: %d: %s" % (lineCount, line))

         groupName = None
         spaces = currentSpaces
         key = None
         valueString = None

         matched = False
         match = rootGroupRegex.match(line)
         if match:
            groupName = match.group(1)
            currentGroup.SetName(groupName)
            Log(8, "TextParser.Parse: matched root group '%s'" % groupName)
            continue
         
         match = groupRegex.match(line)
         if match:
            spaces = len(match.group(1))
            groupName = match.group(2)
            Log(8, "TextParser.Parse: matched group name='%s' space=%d" % \
                (groupName, spaces))
            matched = True
            
         match = dataRegex.match(line)
         if match:
            spaces = len(match.group(1))
            key = match.group(2)
            valueString = match.group(3)

            Log(8, "TextParser.Parse: matched value key='%s' value='%s' space=%d" % \
                (key, valueString, spaces))
            matched = True

         if not matched:
            Log(1, "TextParser.Parse: Failed to match line %d" % lineCount)
            Log(2, "TextParser.Parse: %s" % line)
            continue

         # Conditions under which we need to pop a level off the stack
         # 1. Encounter a group node that is indented equal to or less than the previous node.
         # 2. Encounter a non-group node that is indented equal to or less than the previous group node.
         while spaces <= currentSpaces and len(spacesStack) > 0:
            Log(7, "TextParser.Parse: pop  %d groupName='%s'" % \
                (len(groupStack), currentGroup.GetName()))
            currentSpaces = spacesStack.pop()
            currentGroup = groupStack.pop()
           
         # Determine if we're encountering a new level or not
         if groupName:
            spacesStack.append(currentSpaces)
            currentSpaces = spaces

            schemaPath = self.FullyQualifiedGroupName(groupStack, groupName)
            newGroup = GroupNode(groupName, schemaPath)
            newGroup.SetLineNumber(lineCount)

            currentGroup.AppendChild(newGroup)
            groupStack.append(currentGroup)
            currentGroup = newGroup
               
            Log(7, "TextParser.Parse: push %d groupName='%s'" % \
                (len(groupStack), currentGroup.GetName()))   
         else:
            currentGroup.Set(key, valueString)

   def GetRoot(self):
      return self._parsedTree;


def main():
   parser = TextParser()
   parser.Parse(sys.stdin)

   root = parser.GetRoot()
#   print "-------------------------- Pretty Print String ----------------------------"
#   print str(root)
#   print "---------------------------------------------------------------------"

#   print "-------------------------- Debug String ----------------------------"
#   print root.ToDebugString()
#   print "---------------------------------------------------------------------"

   schemaRegex = re.compile('^Host/Hardware Info/PCI Info/PCI Device/.*$')
   def regexSchemaFilter(schemaPath):
      return schemaRegex.match(schemaPath)

   print "-------------------------- Filtered Output --------------------------"
   print root.PrettyPrint(regexSchemaFilter)
   print "---------------------------------------------------------------------"

   schemaPaths = root.GetSchemaPaths()
   print "Schema paths:"
   print str("\n").join(schemaPaths)

if __name__ == "__main__":
    main()

