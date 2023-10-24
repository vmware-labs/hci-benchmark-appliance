#!/usr/bin/env python

"""
Copyright 2008-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is responsible for building default vmomi client stub
"""
__author__ = "VMware, Inc"

# Configuration
_printRequest = True
_printResponse = True

# Stubs
stubs={}

## Client stub generator
#
# @param ns [in] namespace
def DefStubGenerator(version):
   # Return stub
   localClientStub = __import__("LocalClientStub")
   return localClientStub.LocalClientStubAdapter(version=version,
                                                 printRequest=_printRequest,
                                                 printResponse=_printResponse)

## Get VMOMI client stub from version
#
# @param version [in] version
def GetStub(obj, version):
   # Lookup client stub
   try:
      return stubs[version]
   except KeyError:
      pass

   # stub not found for this version
   try:
      stubGenerator = getattr(obj, "stubGenerator")
   except AttributeError:
      stubGenerator = DefStubGenerator

   # Generator stub
   stub = stubGenerator(version)
   stubs[version] = stub
   return stub
