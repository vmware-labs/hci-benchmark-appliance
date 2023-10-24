#! /build/toolchain/lin32/python-2.5/bin/python
# -*- coding: iso-8859-1 -*-
#-------------------------------------------------------------------
# misc.py
#-------------------------------------------------------------------
# Copyright 2008 VMware, Inc.  All rights reserved. -- VMware Confidential

"""
VMware Utility functions for debugging, path management, etc.

The functions in this module are meant to be called from
~/.pythonrc.py (see sample file bora/vim/py/vmware/pythonrc_sample.py)
in order to make working in the python interactive shell much more
comfortable and convenient.

https://wiki.eng.vmware.com/PythonKillerSetup

"""

__author__ = "Marc Abramowitz, VMware Host Agent Team"

#---------
# Imports
#---------

import sys
import os
import readline
import atexit

#---------------------------------------------------------
# Some useful functions
#---------------------------------------------------------

def Break():
   __import__("pdb").set_trace()

def DebugPrint(*argsTuple):
   """
   Print if PYTHONVERBOSE or VMWAREPYTHONVERBOSE environment variables are set.

   >>> DebugPrint("Hello world")
   """

   if os.getenv("PYTHONVERBOSE") or os.getenv("VMWAREPYTHONVERBOSE"):
      if not argsTuple:
         print
      for arg in argsTuple:
         print(arg)

def FindBoraDir(dirArg):
   """
   Search up from dirArg looking for bora directory.

   >>> FindBoraDir("/build/trees/vmkernel-main/bora/vim/py")
   '/build/trees/vmkernel-main/bora'
   """

   searchDir = dirArg

   if not os.path.isdir(searchDir):
      DebugPrint("   Could not find bora root for \"%s\"; not a directory."
                 % searchDir)
      return None

   while not os.path.isdir("%s/bora" % searchDir):
      if searchDir == os.path.sep or searchDir == os.path.dirname(searchDir):
         DebugPrint("   Could not find bora root for \"%s\"."
                    % dirArg)
         return None
      searchDir = os.path.dirname(searchDir)

   return "%s/bora" % searchDir

def GetBoraDir():
   """
   >>> vmtree = os.environ["VMTREE"]

   >>> os.environ["VMTREE"] = "/bldmnt/trees/vmkernel-main/bora/vim/py"; GetBoraDir()
   '/bldmnt/trees/vmkernel-main/bora'

   >>> del(os.environ["VMTREE"]); os.chdir("/tmp"); GetBoraDir()  # No bora in /tmp

   >>> os.chdir("/bldmnt/trees/vmkernel-main/bora/vim/py"); GetBoraDir()
   '/bldmnt/trees/vmkernel-main/bora'

   >>> os.environ["VMTREE"] = vmtree
   """

   searchDirList = [d for d in os.getenv("VMTREE"), os.getcwd() if d]

   for searchDir in searchDirList:
      boraDir = FindBoraDir(searchDir)
      if boraDir:
         return boraDir

   return None

def AddToSysPath(sysPathDir):
   """
   Adds sysPathDir to sys.path and logs it.

   >>> AddToSysPath("/home/mabramow/lib/python")
   """

   if sysPathDir not in sys.path:
      sys.path.append(sysPathDir)
      DebugPrint("   sys.path.append(\"%s\")" % sysPathDir)

def ProcessStringTemplate(stringTemplate):
   """
   Perform template substitutions on stringTemplate, replacing $VMTREE,
   $HOME, etc. E.g.:

   >>> result1 = ProcessStringTemplate("$HOME/lib/python")
   >>> result2 = "%s/lib/python" % os.getenv("HOME")
   >>> result1 == result2 or (result1, result2)
   True

   >>> result1 = ProcessStringTemplate("$VMTREE/vim")
   >>> result2 = "%s/vim" % GetBoraDir()
   >>> result1 == result2 or (result1, result2, 'GetBoraDir() => "%s"' % GetBoraDir(), 'VMTREE = "%s"' % os.getenv("VMTREE"))
   True
   """

   return os.path.expanduser(os.path.expandvars(stringTemplate))

def ModuleDirList(moduleDirTemplateList):
   """
   Add directories to sys.path, using a list of templated strings. E.g.:

   >>> ModuleDirList(["$VMTREE/vim/py",
   ...                "$VMTREE/build/scons/package/devel/linux32/$BLDTYPE/esx/rpm/hostd/stage/usr/lib/python2.2",
   ...                "$VMTREE/build/vmodl"])
   """

   if hasattr(moduleDirTemplateList, "split"):
      moduleDirTemplateList = moduleDirTemplateList.split()

   for dirTemplate in moduleDirTemplateList:
      try:
         d = ProcessStringTemplate(dirTemplate)
      except KeyError, e:
         DebugPrint("""   KeyError while trying to do substitution on
                       template '%s' with key %s"""
                    % (dirTemplate, str(e)))

      if d:
         AddToSysPath(d)

def ImportModuleList(moduleNameList):
   """
   Import modules using a list of module name strings, catching
   ImportError and printing a warning. E.g.:

   >>> ImportModuleList(["pyVim",
   ...                   "pyVmomi",
   ...                   "readline",
   ...                   "rlcompleter"])
   """

   if hasattr(moduleNameList, "split"):
      moduleNameList = moduleNameList.split()

   for moduleName in moduleNameList:
      try:
         __import__(moduleName)
      except ImportError, e:
         DebugPrint("   Warning: Couldn't import %s (\"%s\")."
                    % (moduleName, str(e)))

def EnableCommandHistory(historyFileTemplate):
   """
   Enable readline command-line history in the python interactive
   shell, using historyFileTemplate to store the history - E.g.:

   Don't uncomment the following line - it may cause the history
   file to grow exponentially when running doctest.

   >>> # EnableCommandHistory("$HOME/.pythonhistory")
   """

   #
   # Protect against executing more than once as this will cause us to
   # write to the history file multiple times and cause it to grow
   # exponentially
   #
   if globals().has_key("commandHistoryEnabled"):
      return

   historyFile = ProcessStringTemplate(historyFileTemplate)

   try:
      readline.read_history_file(historyFile)
   except IOError, e:
      DebugPrint("   Warning: Failed to read history from \"%s\". %s"
                 % (historyFile, str(e)))

   atexit.register(readline.write_history_file, historyFile)

   globals()["commandHistoryEnabled"] = True

def EnableTabCompletion():
   """
   Enable readline tab completion in the python interactive
   shell. E.g.:

   >>> EnableTabCompletion()
   """

   readline.parse_and_bind("tab: complete")


def _test():
   """
   >>> import doctest
   """

   import doctest
   doctest.testmod()


boraDir = GetBoraDir()
if boraDir:
   os.environ["BORA_ROOT"] = boraDir
   os.environ["VMTREE"] = boraDir

os.environ["BLDTYPE"] = os.getenv("BLDTYPE", "obj")

if __name__ == "__main__":
   _test()
