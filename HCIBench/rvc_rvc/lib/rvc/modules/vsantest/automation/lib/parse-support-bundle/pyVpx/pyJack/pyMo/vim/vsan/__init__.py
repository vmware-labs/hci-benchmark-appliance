#!/usr/bin/env python

# This file is directly borrowed from vsphere-2015-vsanhealth branch

import os
import sys

if "VSAN_PYMO_SKIP_VC_CONN" not in os.environ:
   vsanPath = '/usr/lib/vmware/vsan/perfsvc/'
   if vsanPath not in sys.path:
      sys.path.append(vsanPath)

"""
Set this flag so that VSAN will hide any fileds that are defined
by VSAN Vmodl versions, since hostd cannot recognize Vsan's
Vmodl version.
"""
os.environ['HIDE_VSAN_VMODL_VERSION'] = 'True'

__all__ = ["VsanAsyncSystem", "VsanAsyncSystemImpl", "VsanSystemEx"]

# Import __all__
for name in __all__:
   __import__(name, globals(), locals(), [])
