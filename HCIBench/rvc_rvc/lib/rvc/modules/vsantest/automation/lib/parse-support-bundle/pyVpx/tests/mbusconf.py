#!/usr/bin/python

#
# Basic tests for Vim::Host::MessageBusProxy
#

from __future__ import print_function

import sys
import getopt
import time
import array
import util
from pyVmomi import Vim, Vmodl
from pyVim.connect import SmartConnect
from pyVim.helpers import Log
from pyVim import folder
from pyVim import vm
from pyVim import host
from pyVim import task
from pyVim import connect
from optparse import OptionParser

def get_options():
   parser = OptionParser()
   parser.add_option("-t", "--test",
                     default="Configure",
                     help="API to test")
   parser.add_option("-H", "--host",
                     default="zhangv-esx",
                     help="remote host to connect to")
   parser.add_option("-u", "--user",
                     default="root",
                     help="User name to use when connecting to hostd")
   parser.add_option("-p", "--password",
                     default="",
                     help="Password to use when connecting to hostd")
   parser.add_option("-U", "--guestuser",
                     default="root",
                     help="Guest username")
   parser.add_option("-P", "--guestpassword",
                     default="vmw@re",
                     help="Guest password")
   parser.add_option("-v", "--vmname",
                     default="pitlib-rhel-6-0-server-ga-i386-en",
                     help="Name of the virtual machine")
   parser.add_option("-V", "--vmxpath",
                     default="[datastore0] pitlib-rhel-6-0-server-ga-i386-en/pitlib-rhel-6-0-server-ga-i386-en.vmx",
                     help="Datastore path to the virtual machine")
   (options, _) = parser.parse_args()
   return options

def get_options_2():
   parser = OptionParser()
   parser.add_option("-H", "--host",
                     default="10.114.182.227",
                     help="remote host to connect to")
   parser.add_option("-u", "--user",
                     default="root",
                     help="User name to use when connecting to hostd")
   parser.add_option("-p", "--password",
                     default="vmware",
                     help="Password to use when connecting to hostd")
   parser.add_option("-U", "--guestuser",
                     default="root",
                     help="Guest username")
   parser.add_option("-P", "--guestpassword",
                     default="vmw@re",
                     help="Guest password")
   parser.add_option("-v", "--vmname",
                     default="pitlib-rhel-6-0-server-ga-i386-en",
                     help="Name of the virtual machine")
   parser.add_option("-V", "--vmxpath",
                     default="[datastore0] pitlib-rhel-6-0-server-ga-i386-en/pitlib-rhel-6-0-server-ga-i386-en.vmx",
                     help="Datastore path to the virtual machine")
   (options, _) = parser.parse_args()
   return options

def init(hostname, user, passwd, vmname, vmxpath, guestuser, guestpwd):
   # Connect.  Use latest available version.
   global si
   si = SmartConnect(host=hostname, user=user, pwd=passwd)

def FindHostByName(name):
   """ Finds a host specified by its name """
   global si
   idx = si.content.searchIndex
   host = idx.FindByIp(None, name, False) or idx.FindByDnsName(None, name, False)

   if not host:
      from socket import gethostbyaddr, herror
      try:
         hostName = gethostbyaddr(name)[0]
         host = idx.FindByDnsName(None, hostName, False)
      except herror as err:
         Log("Cannot find host %s" % name)
         host = None

   return host
# end

def main():

   # Process command line
   options = get_options()

   init(options.host, options.user,
		options.password, options.vmname, options.vmxpath,
		options.guestuser, options.guestpassword)

   hostSystem = host.GetHostSystem(si)
#   hostSystem = FindHostByName("10.20.87.28")
   messageBus = hostSystem.configManager.messageBusProxy

   configSpec = Vim.MessageBusProxy.MessageBusProxyConfigSpec()
#   configSpec.brokerURI.append("amqp://localhost")
   configSpec.brokerURI.append("amqps://localhost")

#   util.interrogate(configSpec)

   if (options.test == "Configure") :
      print("Configure")
      messageBus.Configure(configSpec)
   elif (options.test == "Unconfigure") :
      print("Unconfigure")
      messageBus.Unconfigure()
   elif (options.test == "RetrieveInfo") :
      print(messageBus.RetrieveInfo())
   elif (options.test == "Start") :
      print("Start")
      messageBus.Start()
   elif (options.test == "Stop") :
      print("Stop")
      messageBus.Stop()
   elif (options.test == "Reload") :
      print("Reload")
      messageBus.Reload()
   else:
      print("Unknown")

# Start program
if __name__ == "__main__":
   main()
   Log("mbusconf test completed")
