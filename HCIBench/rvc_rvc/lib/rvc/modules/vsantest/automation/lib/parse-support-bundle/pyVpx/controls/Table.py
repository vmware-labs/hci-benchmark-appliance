#!/usr/bin/python
# Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential
## Data structure for UI.
#
#  A utility class defining a table used by certain UI controls.  This
#  class frees the UI controls from having to keep track of their own data.

## Class that defines a table that can be rendered.
class Table:
   def __init__(self, tableName, columnNames):
      self._tableName = tableName
      self._columnNames = columnNames
      self._rows = []

   def GetTableName(self):
      return self._tableName

   def GetColumnNames(self):
      return self._columnNames

   # Row is a map from columnName => data
   def Insert(self, row):
      # XXX Validate schema
      self._rows.append(row)

   def GetRowIds(self):
      return range(len(self._rows))

   def Get(self, rowId, columnName):
      if not self._rows[rowId].has_key(columnName):
         return "<invalid>"
      
      return self._rows[rowId][columnName]

   def ToString(self):
      s = "Table '%s' has %d rows.\n" % (self._tableName, len(self._rows))

      s += str(',').join(self._columnNames)
      s += "\n"

      for row in self._rows:
         rs = map(lambda x: row[x], self._columnNames)
         s += str(',').join(rs)
         s += "\n"

      return s

   def __repr__(self):
      return self.ToString()
