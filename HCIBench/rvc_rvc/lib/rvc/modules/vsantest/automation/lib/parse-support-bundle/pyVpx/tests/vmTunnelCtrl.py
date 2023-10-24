#!/usr/bin/python

from __future__ import print_function

#import util
from pyVim import connect, vm, folder, vmconfig
from pyVim.task import WaitForTask
from pyVmomi import Vim
from optparse import OptionParser

def get_options():
   parser = OptionParser()
   parser.add_option("-t", "--task",
                     default="enable",
                     help="enable | disable")
   parser.add_option("-H", "--host",
                     default="localhost",
                     help="remote host to connect to")
   parser.add_option("-u", "--user",
                     default="root",
                     help="username to use when connecting to host")
   parser.add_option("-p", "--password",
                     default="",
                     help="Password to use when connecting to host")
   parser.add_option("-v", "--vmname",
                     default="winxp32",
                     help="Name of the virtual machine")
   (options, _) = parser.parse_args()
   return options

def main():
    # command line
    options = get_options()

    si = connect.SmartConnect(host=options.host,
                              pwd=options.password)
    print("Connected %s" % options.host)

    vmHandle = folder.Find(options.vmname)

    cspec = Vim.Vm.ConfigSpec()
    cspec.messageBusTunnelEnabled = (options.task.lower() == 'enable')
    task = vmHandle.Reconfigure(cspec)
    WaitForTask(task)

    # util.interrogate(vmHandle.config)

    print("messageBusTunnelEnabled: %s" % vmHandle.config.messageBusTunnelEnabled)

if __name__ == '__main__':
    main()
