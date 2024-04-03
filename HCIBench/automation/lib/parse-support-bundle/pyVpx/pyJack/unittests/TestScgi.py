# -*- coding: utf-8 -*-
"""
Copyright 2017-2020 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is used to test soap handler
"""
__author__ = "VMware, Inc"

import sys
import unittest

from six import BytesIO

sys.path.append("..")
from Scgi import ReadNetString, WriteNetString, UTF8


class TestScgi(unittest.TestCase):
    def test_readnetstring(self):
        f = BytesIO(b"5:abcde,")
        self.assertEqual('abcde', ReadNetString(f))

    def test_readnetstring_with_bom(self):
        s = u"5:abcde,".encode('utf-8-sig')
        f = BytesIO(s)
        self.assertEqual('abcde', ReadNetString(f))

    def test_readnetstring_non_ascii(self):
        unicode_str = u'©©©©©'
        encoded_str = unicode_str.encode(UTF8)
        encoded_len = len(encoded_str)
        unicode_input_str = u'{}:{},'.format(str(encoded_len), unicode_str)
        input_str = unicode_input_str.encode(UTF8)
        expected_str = u'©©©©©'
        f = BytesIO(input_str)
        self.assertEqual(expected_str, ReadNetString(f))

    def test_writenetstring(self):
        f = BytesIO()
        WriteNetString(f, b'abcde')
        self.assertEqual(b'5:abcde,', f.getvalue())

    def test_writenetstring_non_ascii(self):
        f = BytesIO()
        encoded_str = u'©©©©©'.encode(UTF8)
        WriteNetString(f, encoded_str)
        self.assertEqual(b'10:' + encoded_str + b',', f.getvalue())


# Test main
if __name__ == "__main__":
    unittest.main()
