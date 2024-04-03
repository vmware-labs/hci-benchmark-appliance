#!/usr/bin/env python

import os
from pyVim import integtest

class BarException:
   def __init__(self, msg):
      self._msg = msg

   def __str__(self):
      return self._msg

class TestAsserts(integtest.TestCase):
    def Foo(self, one, plusTwo, result):
        self.assertEqual(one + plusTwo, result, "Should be equal.")

    def Bar(self):
        raise BarException, "Whoo-hoo!"

    def test_Asserts(self):
        # test false
        self.failIf(1 == 0, "One is not equal to zero.")
        # test truth
        self.failUnless(2*2 == 4, "Two times two is four.")
        # Foo expected not to raise
        self.failIfRaises("Foo should not raise.", self.Foo, 1, 2, 3)
        # Foo expected not to raise, kword parameters
        self.failIfRaises("Foo should not raise.", self.Foo, result=3, plusTwo=2, one=1)
        # Bar expected to raise
        self.failUnlessRaises("Bar is expected to raise.",
                              BarException, self.Bar)

