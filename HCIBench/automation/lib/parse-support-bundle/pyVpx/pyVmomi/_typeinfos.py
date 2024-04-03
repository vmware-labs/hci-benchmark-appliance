# **********************************************************
# Copyright 2005-2022 VMware, Inc.  All rights reserved.
# -- VMware Confidential
# **********************************************************

import sys
from . import _import_typeinfo

# Keep the list in alphabetical order
typeinfos = [
    'ciscm',
    'ciscommon',
    'cisdata',
    'ciskvlocal',
    'cislicense',
    'core',
    'csi',
    'dataservice',
    'dodo',
    'dp',
    'eam',
    'ehp',
    'hbr',
    'hmsdrs',
    'hostd',
    'idp',
    'imagebuilder',
    'imagefactory',
    'infra',
    'integrity',
    'legacylicense',
    'lookup',
    'nfc',
    'pbm',
    'phonehome',
    'query',
    'rbd',
    'reflect',
    'sca',
    'sms',
    'sps',
    'sso',
    'sysimage',
    'test',
    'vasa',
    'vcint',
    'vim',
    'vmomitest',
    'vorb',
    'vpx',
    'vpxapi',
    'vslm',
    'vsm',
]

pyVmomi = sys.modules['pyVmomi']
setattr(pyVmomi, 'LoadVsanTypeinfo', lambda: _import_typeinfo('vsanhealth'))
