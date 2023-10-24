#!/usr/bin/python

from __future__ import print_function

import types
import sys

def listToString(inList):
    rs = ''
    for item in inList:
        rs += item
        rs += "\n"
    return rs

def dictToString(inDict):
    rs = ''
    for k,v in inDict.iteritems():
        if (v):
            rs += k + " => " + repr(v)
            rs += "\n"
    return rs

def check():
    print("MODULE PATH:\t%s" % listToString(sys.path))
    print("LOADED MODULE:\t%s" % dictToString(sys.modules))

def interrogate(item):
    """Print useful information about item."""
    if hasattr(item, '__name__'):
        print("Name:\t%s" % item.__name__)
    if hasattr(item, '__class__'):
        print("CLASS:\t%s" % item.__class__.__name__)
    print("ID:\t%s" % id(item))
    print("TYPE:\t%s" % type(item))
    print("VALUE:\t%s" % repr(item))
    print("CALLABLE:\t", end='')
    if callable(item):
        print("Yes")
    else:
        print("No")
    if hasattr(item, '__doc__'):
        doc = getattr(item, '__doc__')
        print("DOC:\t%s" % doc)
    print("DUMP:\t%s" % dir(item))
