#!/usr/bin/env python

import os
from pyVim import integtest

# Failing to import this should result in this test being skipped.
import intentionally_fail_to_import

class TestFailToImport(integtest.TestCase):

    def test_FailToImport(self):
        self.failIf(1 == 1, "This test should have failed to load.")

