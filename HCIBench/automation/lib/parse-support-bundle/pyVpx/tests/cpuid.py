#!/usr/bin/python

###
### Test description:
###
### Check cpuid read/write
###
from __future__ import print_function

import sys
from pyVmomi import *
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm
import atexit

def main():
    # Process command line
    host = "jairam-esx"
    if len(sys.argv) > 1:
       host = sys.argv[1]

    try:
       si = Connect(host)
       atexit.register(Disconnect, si)
       vm.CreateQuickDummy("CpuIdTest")
       v1 = folder.Find("CpuIdTest")
       print("Created a dummy")

       # Print current.
       print(v1.GetConfig().GetCpuFeatureMask())

       # Change level 0 and level 80
       config = Vim.Vm.ConfigSpec()

       lvl0 = Vim.Vm.ConfigSpec.CpuIdInfoSpec()
       info = Vim.Host.CpuIdInfo()
       info.SetLevel(0)
       info.SetEax("XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX")
       info.SetEbx("XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX")
       info.SetEcx("XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX")
       info.SetEdx("XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX")
       lvl0.SetOperation("add")
       lvl0.SetInfo(info)

       lvl1 = Vim.Vm.ConfigSpec.CpuIdInfoSpec()
       info2 = Vim.Host.CpuIdInfo()
       info2.SetLevel(1)
       info2.SetVendor("amd")
       info2.SetEax("XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX")
       info2.SetEdx("XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX")
       lvl1.SetOperation("add")
       lvl1.SetInfo(info2)

       config.SetCpuFeatureMask([lvl0, lvl1])
       print("Assigned features")

       task = v1.Reconfigure(config)
       if WaitForTask(task) == "error":
          raise task.GetInfo().GetError()
       vm.Destroy(v1)
    except Exception as e:
       print("Failed test due to exception: %s" % e)
       raise


# Start program
if __name__ == "__main__":
    main()
