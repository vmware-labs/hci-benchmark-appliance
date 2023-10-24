#!/usr/bin/python
"""
Python program for getting list of files not owned by a vm using
QueryUnownedFiles VMODL call.

Requirements:
 * pyVmomi, pyVim
 * The target host needs to be running hostd
"""

from optparse import OptionParser
from pyVim.connect import Connect
from pyVim import folder


def GetOptions():
    """
   Supports the command-line arguments listed below.
   """

    parser = OptionParser()
    parser.add_option("--host", help="remote host to connect to")
    parser.add_option("-u",
                      "--user",
                      default="root",
                      help="User name to use when connecting to hostd")
    parser.add_option("-p",
                      "--password",
                      "--pwd",
                      default="ca$hc0w",
                      help="Password to use when connecting to hostd")
    parser.add_option("-v",
                      "--vmprefix",
                      default="",
                      help="Prefix for virtual machine")
    (options, _) = parser.parse_args()
    return options


def PrintVmInfo(vm):
    """
   Print information for a particular virtual machine.
   """

    summary = vm.GetSummary()
    print "Name       : %s" % summary.GetConfig().GetName()
    files = vm.QueryUnownedFiles()
    print "Files      : %s" % files


def main():
    """
   Simple command-line program for listing the virtual machines on a
   system managed by hostd.
   """

    options = GetOptions()

    Connect(host=options.host, user=options.user, pwd=options.password)

    for vm in folder.FindPrefix(options.vmprefix):
        PrintVmInfo(vm)


# Start program
if __name__ == "__main__":
    main()
