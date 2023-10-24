#!/usr/bin/python
"""
Python program for interacting with the services on an ESX server

Requirements:
 * pyVmomi, pyVim
 * Needs to be invoked with py.sh rather than regular python executable
 * The target host needs to be running hostd
"""

from optparse import OptionParser
from pyVmomi import Vim
from pyVim.connect import SmartConnect
from pyVim.host import GetHostConfigManager

parser = OptionParser()
parser.add_option("--host", help="remote host to connect to")
parser.add_option("-u",
                  "--user",
                  default="root",
                  help="User name to use when connecting to hostd")
parser.add_option("-p",
                  "--password",
                  default="",
                  help="Password to use when connecting to hostd")
parser.add_option('--list',
                  dest='list',
                  default=False,
                  action='store_true',
                  help='List the available services')
parser.add_option("--start", default=None, help="Start the specified service")
parser.add_option("--stop", default=None, help="Start the specified service")
parser.add_option("--restart",
                  default=None,
                  help="Start the specified service")
(options, args) = parser.parse_args()

serviceInstance = SmartConnect(host=options.host,
                               user=options.user,
                               pwd=options.password,
                               preferredApiVersions=['vim.version.version9'])
serviceSystem = GetHostConfigManager(serviceInstance).serviceSystem


def ListServices(serviceSystem):
    maxLabelWidth = max(
        [len(s.label) for s in serviceSystem.serviceInfo.service])
    maxKeyWidth = max([len(s.key) for s in serviceSystem.serviceInfo.service])
    print('%-*s %-*s %s' %
          (maxLabelWidth, 'Label', maxKeyWidth, 'Key', ' Status '))
    print('%-*s %-*s %s' %
          (maxLabelWidth, '-----', maxKeyWidth, '---', ' ------ '))
    for service in serviceSystem.serviceInfo.service:
        print('%-*s %-*s %s' %
              (maxLabelWidth, service.label, maxKeyWidth, service.key,
               service.running and 'Running' or 'Stopped'))


if options.list:
    ListServices(serviceSystem)
elif options.start:
    serviceSystem.Start(options.start)
elif options.stop:
    serviceSystem.Stop(options.stop)
elif options.restart:
    serviceSystem.Restart(options.restart)
else:
    ListServices(serviceSystem)
