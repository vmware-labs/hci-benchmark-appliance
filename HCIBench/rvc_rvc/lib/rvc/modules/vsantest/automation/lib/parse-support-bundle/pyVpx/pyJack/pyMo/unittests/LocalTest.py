#!/usr/bin/env python

"""
Copyright 2008-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module run the unittest directly with PyVmomiServer SoapHandler
"""
__author__ = "VMware, Inc"

from optparse import OptionParser, make_option
import TestDriver

try:
   import LocalClientStub
except ImportError:
   import sys
   sys.path.append("../..")
   import LocalClientStub

def main():
   """ This is the main program, obviously """

   # Command parser
   cmdOptionsList = [
      make_option("--printrequest", "--pq", dest="printRequest",
                  action="store_true", help="Print SOAP request"),
      make_option("--printresponse", "--pe", dest="printResponse",
                  action="store_true", help="Print SOAP response"),
      make_option("-?", action="help")
   ]
   cmdParser = OptionParser(option_list=cmdOptionsList)

   # Get command line options
   (options, args) = cmdParser.parse_args()
   # cmdParser should have a cmdParser.destroy() method, but it is missing
   del cmdParser

   # Create stub generator
   stubGenerator = lambda version : LocalClientStub.LocalClientStubAdapter(
                                           version=version,
                                           printRequest=options.printRequest,
                                           printResponse=options.printResponse)

   # Run test
   TestDriver.RunTest(stubGenerator)

if __name__ == "__main__":
   main()
