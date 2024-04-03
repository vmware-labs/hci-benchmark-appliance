#!/usr/bin/env python

"""
Script to validate hostLog does not allow reconfiguring to a non-host log
valid path.
"""

from pyVim.connect import SmartConnect
from pyVim.vm import CreateQuickDummy
from pyVim.vmconfig import CheckDevice
from pyVim.task import WaitForTask
from pyVim.arguments import Arguments
from pyVmomi import vim, vmodl

import sys

def main():
   supportedArgs = [ (["s:", "host="], "localhost", "host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd")
                   ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information",
                          "usage")]

   args = Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage"):
      args.Usage()
      sys.exit(0)

   si = SmartConnect(host=args.GetKeyValue('host'),
                     user=args.GetKeyValue('user'),
                     pwd=args.GetKeyValue('pwd'))

   vm = CreateQuickDummy('vm-for-hostlog', numScsiDisks=1)
   try:
      disk = CheckDevice(vm.config, vim.vm.device.VirtualDisk)[0]
      diskName = disk.backing.fileName
      for dsUrl in vm.config.datastoreUrl:
         diskName = diskName.replace('[%s] ' % dsUrl.name, dsUrl.url + '/')
      hostlogOption = vim.option.OptionValue(key='migrate.hostlog',
                                             value=diskName)
      spec = vim.vm.ConfigSpec(extraConfig=[hostlogOption])
      WaitForTask(vm.Reconfigure(spec))
   except vmodl.fault.InvalidArgument as e:
      print("Hit %s as expected" % e)
   else:
      raise Exception("Failed to hit Reconfigure error changing hostlog")
   finally:
      WaitForTask(vm.Destroy())

if __name__ == "__main__":
   main()

