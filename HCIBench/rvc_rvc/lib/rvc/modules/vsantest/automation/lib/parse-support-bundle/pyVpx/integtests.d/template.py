#!/usr/bin/env python

__doc__ = """
@file template.py --
Copyright 2007-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

@todo This module verifies ...
"""

__author__ = "VMware, Inc"

import os
import unittest
import testoob
from pyVmomi import Vim

#import pyVim.vimhost

class FixtureTemplate(unittest.TestCase):
    """
    Perform common setup tasks for all derived classes.
    """
    def setUp(self):
        """
        Called before each test function.
        """
        ## E.g., setup connection/login:
        ## self._host = pyVim.vimhost.host()
        pass

    def tearDown(self):
        """
        Called after each test function.
        """
        ## E.g.: self._host = None
        pass

class TestTemplate(FixtureTemplate):
    """
    @todo Place comments here to describe what this integration 
    test suite covers as this will show up in the man page.
    """

    def test1_VerifySomething(self):
        """
        @todo This test case verifies ...
        """
        try:
            # exercise mutators, accessors
            # and verify invariants after each one
            self.failUnless(1 == 1, 
                            "Comparing 1 to 1 should yeild true: %s" % 
                            type(1))
        finally:
            # perform invariant check
            pass

