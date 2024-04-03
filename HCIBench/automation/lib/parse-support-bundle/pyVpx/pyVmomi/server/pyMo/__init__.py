"""
Copyright 2008-2022 VMware, Inc.  All rights reserved. -- VMware Confidential
"""

__all__ = [ "vim" ]

# Put in initialization list
for name in __all__:
   __import__(name, globals(), locals(), [], 1)
