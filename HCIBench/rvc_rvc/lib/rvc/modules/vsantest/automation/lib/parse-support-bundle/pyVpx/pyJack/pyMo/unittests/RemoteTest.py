#!/usr/bin/env python

"""
Copyright 2008-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module run the unittest through network
"""
__author__ = "VMware, Inc"

from optparse import OptionParser, make_option
import TestDriver

try:
   from pyVim import connect
except ImportError:
   import sys
   sys.path.append("../..")
   sys.path.append("../../..")
   from pyVim import connect

def main():
   """ This is the main program, obviously """

   # Command parser
   cmdOptionsList = [
      make_option("--host", default="localhost",
                   dest="host", help="Host name"),
      make_option("--port", type="int", default=443,
                   dest="port", help="Port number"),
      make_option("--user", default="root", dest="user", help="User name"),
      make_option("--pwd", "--password",
                  default="ca$hc0w", dest="pwd", help="Password"),
      make_option("-?", action="help")
   ]
   cmdParser = OptionParser(option_list=cmdOptionsList)

   # Get command line options
   (options, args) = cmdParser.parse_args()
   # cmdParser should have a cmdParser.destroy() method, but it is missing
   del cmdParser

   # Get stub generator
   stubGenerator = lambda ns: \
                     connect.Connect(host=options.host, port=options.port,
                                     namespace=ns,
                                     user=options.user, pwd=options.pwd)._stub

   # Run test
   TestDriver.RunTest(stubGenerator)

if __name__ == "__main__":
   main()
