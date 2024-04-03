#!/usr/bin/python
# Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file nfc/__init__.py --
## Integration Test framework loads TestCases from this
## module by invoking suite()


__author__ = "VMware, Inc"


## TestCase objects found in all files that start with: case_*.py    
## @return a unittest.TestSuite object made up of
def suite():
    import testoob
    return testoob.collecting.collect_from_files("case_*.py")
