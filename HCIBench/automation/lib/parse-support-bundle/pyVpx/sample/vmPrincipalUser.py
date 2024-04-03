#!/usr/bin/python
"""
Simple command-line program for getting/setting the vmPrincipalUser
"""

from pyVim.connect import Connect
from pyVim import host
from optparse import OptionParser


def GetOptionsAndArgs():
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
    (options, args) = parser.parse_args()
    return (options, args)


def main():
    """
   Simple command-line program for getting/setting the vmPrincipalUser
   """

    (options, args) = GetOptionsAndArgs()

    serviceInstance = Connect(host=options.host,
                              user=options.user,
                              pwd=options.password)

    hostSystem = host.GetHostSystem(serviceInstance)
    hostConfig = hostSystem.GetConfig()
    hostConfigManager = hostSystem.GetConfigManager()
    datastoreSystem = hostConfigManager.GetDatastoreSystem()

    vmPrincipalUser = hostConfig.datastorePrincipal
    print "vmPrincipalUser is \"%s\"" % vmPrincipalUser

    if len(args) == 1:
        newVmPrincipalUser = args[0]
        print "Changing vmPrincipalUser to \"%s\"" % newVmPrincipalUser
        datastoreSystem.ConfigureDatastorePrincipal(
            userName=newVmPrincipalUser)


# Start program
if __name__ == "__main__":
    main()
