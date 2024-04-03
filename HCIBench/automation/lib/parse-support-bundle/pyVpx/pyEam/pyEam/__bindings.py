# **********************************************************
# Copyright 2005-2022 VMware, Inc.  All rights reserved.
# -- VMware Confidential
# **********************************************************

# Keep the list in alphabetical order
knownBindings = [
    '_typeinfo_ciscm',
    '_typeinfo_ciscommon.py',
    '_typeinfo_cisdata',
    '_typeinfo_ciskvlocal.py',
    '_typeinfo_cislicense',
    '_typeinfo_core',
    '_typeinfo_csi',
    '_typeinfo_dataservice',
    '_typeinfo_dodo',
    '_typeinfo_dp',
    '_typeinfo_eam',
    '_typeinfo_ehp.py',
    '_typeinfo_hbr',
    '_typeinfo_hmsdrs',
    '_typeinfo_hostd',
    '_typeinfo_idp.py',
    '_typeinfo_imagebuilder',
    '_typeinfo_imagefactory',
    '_typeinfo_infra',
    '_typeinfo_integrity',
    '_typeinfo_legacylicense',
    '_typeinfo_lookup',
    '_typeinfo_nfc',
    '_typeinfo_pbm',
    '_typeinfo_phonehome',
    '_typeinfo_query',
    '_typeinfo_rbd',
    '_typeinfo_reflect',
    '_typeinfo_sca.py',
    '_typeinfo_sms',
    '_typeinfo_sps',
    '_typeinfo_sso',
    '_typeinfo_sysimage',
    '_typeinfo_test',
    '_typeinfo_vasa',
    '_typeinfo_vcint',
    '_typeinfo_vim',
    '_typeinfo_vmomitest',
    '_typeinfo_vorb',
    '_typeinfo_vpx',
    '_typeinfo_vpxapi',
    '_typeinfo_vsan.py',
    '_typeinfo_vslm',
    '_typeinfo_vsm',
]

for binding in knownBindings:
    try:
        __import__(binding, globals(), level=1)
    except ImportError:
        pass
