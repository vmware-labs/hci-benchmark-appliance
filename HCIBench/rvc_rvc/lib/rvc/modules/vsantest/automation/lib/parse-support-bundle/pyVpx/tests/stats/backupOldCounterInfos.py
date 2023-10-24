#!/usr/bin/python

from __future__ import print_function

import sys
import atexit
from pyVmomi import Vim
from pyVmomi import VmomiSupport
from pyVim.connect import SmartConnect, Disconnect
from optparse import OptionParser

def GetOptions():
    """
    Supports the command-line arguments listed below
    """
    parser = OptionParser()
    parser.add_option("-H", "--host",
                      default="localhost",
                      help="Remote host to connect to.")
    parser.add_option("-u", "--user",
                      default="root",
                      help="User name to use when connecting to hostd.")
    parser.add_option("-p", "--password",
                      default="",
                      help="Password to use when connecting to hostd.")
    (options, _) = parser.parse_args()
    return options

def Main():
   # Process command line
   options = GetOptions()

   si = SmartConnect(host=options.host,
                     user=options.user,
                     pwd=options.password)
   content = si.RetrieveContent()
   prfrmncMngr = content.perfManager

   perfCounters = prfrmncMngr.perfCounter

   print("perfCountersOld = {")
   for i in range(len(prfrmncMngr.perfCounter)):
      print("%d : '''\n%s\n'''," % (perfCounters[i].key, perfCounters[i]))
   print("}")

   atexit.register(Disconnect, si)

# Start program
if __name__ == "__main__":
    Main()
