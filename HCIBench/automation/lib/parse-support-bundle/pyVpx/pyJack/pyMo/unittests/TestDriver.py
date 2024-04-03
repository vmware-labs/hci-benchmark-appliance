#!/usr/bin/env python

"""
Copyright 2008-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is the unittest driver
"""
__author__ = "VMware, Inc"

import sys
import os
import unittest

def RunTest(stubGenerator):
   # Hack... force include pyJack directory
   sys.path.append("../..")

   # Gather test files
   suitesDir = "suites"
   files = os.listdir(suitesDir)
   # For each file starts with "Test", strip ".py" & add prefix suitesDir "."
   testFiles = [suitesDir + "." + file[:-3] for file in files \
                if file.startswith("Test") and file.endswith(".py")]

   # Load tests
   testsuites = unittest.TestLoader().loadTestsFromNames(testFiles)

   # Override the stubGenerator used by unittest
   for testsuite in testsuites:
      for tests in testsuite:
         for test in tests:
            #assert(getattr(test, "stubGenerator") == None)
            setattr(test, "stubGenerator", stubGenerator)

   # Run tests
   runner = unittest.TextTestRunner()
   runner.run(testsuites)
