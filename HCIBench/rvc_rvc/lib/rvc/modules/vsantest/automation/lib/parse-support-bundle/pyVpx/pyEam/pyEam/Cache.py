"""
Copyright 2008-2015 VMware, Inc.  All rights reserved. -- VMware Confidential

This module implements the cache decorator
"""
__author__ = "VMware, Inc"


def Cache(fn):
    """ Function cache decorator """
    def fnCache(*args, **kwargs):
        """ Cache function """
        key = (args and tuple(args)
               or None, kwargs and frozenset(list(kwargs.items())) or None)
        if key not in fn.__cached__:
            fn.__cached__[key] = cache = fn(*args, **kwargs)
        else:
            cache = fn.__cached__[key]
        return cache

    def ResetCache():
        """ Reset cache """
        fn.__cached__ = {}

    setattr(fn, "__cached__", {})
    setattr(fn, "__resetcache__", ResetCache)
    fnCache.__name__ = fn.__name__
    fnCache.__doc__ = fn.__doc__
    fnCache.__dict__.update(fn.__dict__)
    return fnCache
