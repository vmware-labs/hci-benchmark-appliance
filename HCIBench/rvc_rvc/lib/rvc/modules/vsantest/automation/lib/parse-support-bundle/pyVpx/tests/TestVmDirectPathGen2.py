#!/usr/bin/python

from __future__ import print_function

import sys
from pyVmomi import Vim
from pyVim.connect import Connect, Disconnect
from optparse import OptionParser
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm, host
from pyVim import invt
from pyVim import vmconfig
from pyVim import vimutil
from pyVim import arguments
from pyVim.helpers import StopWatch
import time
import atexit
import operator

#
# Just some code to automate looking as passthrough state for a host
#
#

def get_options():
    """
    Supports the command-line arguments listed below
    """

    parser = OptionParser()
    parser.add_option("-H", "--host",
                      default="10.20.112.66",
                      help="remote host to connect to")
    parser.add_option("-u", "--user",
                      default="Administrator",
                      help="User name to use when connecting to hostd")
    parser.add_option("-p", "--password",
                      default="ca$hc0w",
                      help="Password to use when connecting to hostd")
    (options, _) = parser.parse_args()

    return options

def main():
    """
    Test does the following.
    - Print out host vmDirectPathGen2 capability
    - Print out pNIC vmDirectPathGen2 capability
    - Iterate VMs, and show deviceRuntimeState for vmDirectPathGen2

    """
    options = get_options()

    try:
       si = Connect(host=options.host,
                    user=options.user,
                    version="vim.version.version9",
                    pwd=options.password)
    except Vim.Fault.InvalidLogin:
       print("Failed initial login with VC default credentials, "
             "trying again with host defaults")
       options.user = "root"
       options.password = ""
       si = Connect(host=options.host,
                    user=options.user,
                    version="vim.version.version9",
                    pwd=options.password)
    atexit.register(Disconnect, si)

    content = si.content
    capability = si.capability
    if capability.multiHostSupported:
       print("Detected that this is a VC, not an ESX")

    datacenters =  host.GetRootFolder(si).childEntity

    for d in datacenters:
       hostfolder = d.hostFolder
       hosts = hostfolder.childEntity
       for h in hosts:
          print("Host %s" % h.name)
          # Why does a single host have an array of hostsystems?
          hostsystems = h.host
          for hs in hostsystems:
             HostCapability = hs.GetCapability()
             print("Host hardware is %scompatible with vmDirectPathGen2"
                   % ["NOT ", ""][HostCapability.vmDirectPathGen2Supported])
             if HostCapability.vmDirectPathGen2Supported:
               assert not HostCapability.vmDirectPathGen2UnsupportedReason
             else:
                print("VmDirectPathGen2SupportedReason: ",
                      HostCapability.vmDirectPathGen2UnsupportedReason)
             cm = hs.GetConfigManager()
             networkSystem = cm.networkSystem

             networkInfo = networkSystem.networkInfo
             pnic = networkInfo.pnic

             numsupportedpnics = 0
             for p in pnic:
                if p.vmDirectPathGen2Supported:
                   assert p.vmDirectPathGen2SupportedMode == "upt"
                   print("Device %s supports vmDirectPathGen2" % p.device)
                   numsupportedpnics += 1
                else:
                   print("Device %s does NOT support vmDirectPathGen2" % p.device)

             if not numsupportedpnics:
                print("No pNICs are compatible with vmDirectPath on this host")

             vms = host.GetHostSystem(si).vm
             for v in vms:
                devices = v.runtime.device
                print("VM %s [%s]:" % (v.name, v))
                for d in devices:
                   runtimeState = d.runtimeState
                   print("\tDevice %s" % d.key)
                   print("\t\tVmDirectPathGen2Active:", runtimeState.vmDirectPathGen2Active)
                   if runtimeState.vmDirectPathGen2InactiveReasonVm:
                      print("\t\tVmDirectPathGen2InactiveReasonVm: %s" %
                            str(runtimeState.vmDirectPathGen2InactiveReasonVm).replace("\n", "\n\t\t"))
                   if runtimeState.vmDirectPathGen2InactiveReasonOther:
                      print("\t\tVmDirectPathGen2InactiveReasonOther: %s" %
                            str(runtimeState.vmDirectPathGen2InactiveReasonOther).replace("\n", "\n\t\t"))
                   if runtimeState.vmDirectPathGen2InactiveReasonExtended:
                      print("\t\tVmDirectPathGen2InactiveReasonExtended: %s" %
                            str(runtimeState.vmDirectPathGen2InactiveReasonExtended).replace("\n", "\n\t\t"))
    return 0

# Start program
if __name__ == "__main__":
    sys.exit(main())
