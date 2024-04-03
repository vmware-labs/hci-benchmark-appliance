#!/usr/bin/python
# Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential
## A command line tool that summarizes data from esxcfg-info output.
#
# Usage:
# esxcfg-info-process.py
#    Prints out usage information listing defined tables.
#
# esxcfg-info-process.py all
#    Prints out all defined tables.
#
# esxcfg-info-process.py tableName0 [tableName1] [tableName2] [...]
#    Prints out tables specified on command line.
# 
#

import os
import sys
import re

# Append to search path where import modules can be found in source tree
scriptDir = os.path.dirname(sys.argv[0])
importDir = os.path.join(scriptDir, "..")
sys.path.append(importDir)

import vmware.esxcfgInfo.Parse
import vmware.esxcfgInfo.TableDefs
import controls.cli.ListView

sys.path.pop()
# Restore search path


allTableDefinitions = vmware.esxcfgInfo.TableDefs.GetAll()
allTableNames = map(lambda x: x.tableName, allTableDefinitions)

def Usage(msg=""):
   tableDefinitions = allTableDefinitions
   tableNames = allTableNames
   
   s = ''
   if len(msg) > 0:
      s = msg + "\n"
   s += "Usage: %s tableName0 [tableName1] ...\n\n" % sys.argv[0]
   s += "Valid tables include:\n"
   s += "   " + str("\n   ").join(tableNames)

   print s

def main():
   if len(sys.argv) < 2:
      Usage()
      return 1

   parser = vmware.esxcfgInfo.Parse.TextParser()
   parser.Parse(sys.stdin)
   root = parser.GetRoot()

#   print "-------------------------- Pretty Print String ----------------------------"
#   print str(root)
#   print "---------------------------------------------------------------------"

   tableNames = sys.argv[1:]

   for arg in sys.argv[1:]:
      if arg == "all":
         tableNames = allTableNames
         break
   
   for tableName in tableNames:
      tableDefinitions = filter(lambda x: x.tableName == tableName, allTableDefinitions)
      if len(tableDefinitions) < 1:
         print "Invalid table '%tableName' specified."
         continue
      if len(tableDefinitions) > 1:
         print "Too many tables defined (%d) for name '%s'." % \
               (len(tableDefinitions), tableName)

      tableDef = tableDefinitions[0]
      table = vmware.esxcfgInfo.Parse.CreateTable(tableDef, parser.GetRoot(), 0)
      
      print "-- Table '%s' --\n" % tableDef.tableName
      listView = controls.cli.ListView.ListView(table)
      print listView.ToString() + "\n"
#      print listView.ToCsvString() + "\n"

if __name__ == "__main__":  
   main()

