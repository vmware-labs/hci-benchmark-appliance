# Copyright 2016 VMware, Inc.  All rights reserved.

import os
import sys

# This module is both used as a package and a binary, which causes
# python 3 to complain about the following syntax:
# from .foo import bar
#
# This path modification allows us to not use the new
# relative import syntax of python 3 by always having the file
# in that directory in our path.
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
