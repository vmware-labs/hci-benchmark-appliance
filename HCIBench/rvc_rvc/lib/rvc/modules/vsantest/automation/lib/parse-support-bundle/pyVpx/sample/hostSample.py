#!/usr/bin/python
"""
Simple command-line program for dumping the host config.
"""

from pyVim.connect import Connect
from pyVim import host
from optparse import OptionParser


def GetOptions():
    """
   Supports the command-line arguments listed below.
   """

    parser = OptionParser()
    parser.add_option("--host",
                      default="localhost",
                      help="remote host to connect to")
    parser.add_option("-u",
                      "--user",
                      default="root",
                      help="User name to use when connecting to hostd")
    parser.add_option("-p",
                      "--password",
                      "--pwd",
                      default="ca$hc0w",
                      help="Password to use when connecting to hostd")
    (options, _) = parser.parse_args()
    return options


def main():
    """
   Simple command-line program for dumping the host config.
   """

    options = GetOptions()

    serviceInstance = Connect(host=options.host,
                              user=options.user,
                              pwd=options.password)

    host.DumpHostConfig(serviceInstance)


# Start program
if __name__ == "__main__":
    main()
