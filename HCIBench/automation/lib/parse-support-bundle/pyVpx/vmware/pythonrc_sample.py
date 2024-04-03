from vmware.misc import DebugPrint,              \
                        EnableCommandHistory,    \
                        EnableTabCompletion,     \
                        ImportModuleList,        \
                        ModuleDirList

DebugPrint("\n# ~/.pythonrc.py")

ImportModuleList("""
   pyVim
   pyVmomi
   readline
   rlcompleter
   """)

from pprint import pprint as pp

# You can get autoimp at http://www.princeton.edu/~csbarnes/code/autoimp/
try:
   from autoimp import *
except Exception, e:
   print "Error while importing autoimp (\"%s\")" % str(e)

# Reimport frequently used modules so that first tab complete has all
# attributes; not just attributes of proxy obj from autoimp
import os, string, sys, vmware

EnableCommandHistory("$HOME/.pythonhistory")
EnableTabCompletion()

DebugPrint()
