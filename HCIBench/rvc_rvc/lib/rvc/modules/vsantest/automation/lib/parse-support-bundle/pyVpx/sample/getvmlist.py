#!/usr/bin/python
"""
Python program for listing the vms on a host on which hostd is running

Requirements:
 * pyVmomi, pyVim
 * Needs to be invoked with py.sh rather than regular python executable
 * The target host needs to be running hostd
"""

from optparse import OptionParser
from pyVim.connect import Connect, Disconnect
from pyVim import folder
import atexit


def GetOptions():
    """
   Supports the command-line arguments listed below.
   """

    parser = OptionParser()
    parser.add_option("--host", help="remote host to connect to")
    parser.add_option("-o", "--port", default=443, help="Port"),
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

    summary = vm.summary
    print "Name       : ", summary.config.name
    print "Path       : ", summary.config.vmPathName
    print "Guest      : ", summary.config.guestFullName
    annotation = summary.config.annotation
    if annotation != None and annotation != "":
        print "Annotation : ", annotation
    print "State      : ", summary.runtime.powerState
    if summary.guest != None:
        ip = summary.guest.ipAddress
    if ip != None and ip != "":
        print "IP         : ", ip
    if summary.runtime.question != None:
        print "Question  : ", summary.runtime.question.text
    print ""


def main():
    """
   Simple command-line program for listing the virtual machines on a
   system managed by hostd.
   """

    options = GetOptions()

    si = Connect(host=options.host,
                 user=options.user,
                 pwd=options.password,
                 port=int(options.port),
                 namespace="vim25/5.5")
    atexit.register(Disconnect, si)

    for vm in folder.FindPrefix(options.vmprefix):
        PrintVmInfo(vm)


# Start program
if __name__ == "__main__":
    main()
