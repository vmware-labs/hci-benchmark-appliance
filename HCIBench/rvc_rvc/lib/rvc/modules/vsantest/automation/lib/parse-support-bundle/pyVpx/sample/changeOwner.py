#!/usr/bin/python
"""
Python program for changing ownership of a file using
ChangeOwner VMODL call.

Requirements:
 * pyVmomi, pyVim
 * The target host needs to be running hostd
"""

from optparse import OptionParser
from pyVim.connect import Connect
from pyVim import fm, vimhost


def GetOptions():
    """
   Supports the command-line arguments listed below.
   Returns tuple with options, owner, and filename.
   """

    parser = OptionParser(usage="%prog [options] {owner} {filename}")
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
    (options, args) = parser.parse_args()
    if len(args) != 2:
        parser.error("incorrect number of arguments")
    return (options, args[0], args[1])


def main():
    """
   Simple command-line program for listing the virtual machines on a
   system managed by hostd.
   """

    (options, owner, filename) = GetOptions()

    host = vimhost.Host(hostname=options.host,
                        login=options.user,
                        passwd=options.password)

    fm.ChangeOwner(host=host,
                   srcDatacenter=None,
                   srcFile=filename,
                   owner=owner)


# Start program
if __name__ == "__main__":
    main()
