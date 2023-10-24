#!/usr/bin/python

# **********************************************************
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential
# **********************************************************

import getopt
import os
import sys
from pyVmomi import types, Vmodl, Vim, SoapStubAdapter
#from pyVmomi.SoapAdapter import Serialize
from pyVmomi import VmomiSupport
from pyVim import configSerialize


def MakeConfigDefSpec():
    optionDef = Vim.Option.OptionDef()
    optionDef.key = "security.host.ruissl"
    optionDef.label = "security.host.ruissl"
    optionDef.summary = "Require SSL to be used when communicating with the host over port 902."

    optionDef.optionType = Vim.Option.BoolOption()
    optionDef.optionType.valueIsReadonly = False
    optionDef.optionType.defaultValue = True
    optionDef.optionType.supported = True

    configOptionDefs = [optionDef]

    return Vim.Option.OptionDef.Array(configOptionDefs)


def MakeSettingsDefSpec():
    optionDef = Vim.Option.OptionDef()
    optionDef.key = "guest.commands.sharedPolicyRefCount"
    optionDef.label = "guest.commands.sharedPolicyRefCount"
    optionDef.summary = "Reference count to enable guest operations."

    optionDef.optionType = Vim.Option.IntOption()
    optionDef.optionType.valueIsReadonly = False
    optionDef.optionType.defaultValue = 0
    optionDef.optionType.min = 0
    optionDef.optionType.max = 0x7fffffff

    return Vim.Option.OptionDef.Array([optionDef])


def main():
    print "-------------------- Config Definitions --------------------"
    configDef = MakeConfigDefSpec()
    print configSerialize.SerializeToConfig(configDef)
    print "------------------------------------------------------------"

    print "-------------------- Setting Definitions --------------------"
    settingsDef = MakeSettingsDefSpec()
    print configSerialize.SerializeToConfig(settingsDef)
    print "------------------------------------------------------------"


# Start program
if __name__ == "__main__":
    main()
