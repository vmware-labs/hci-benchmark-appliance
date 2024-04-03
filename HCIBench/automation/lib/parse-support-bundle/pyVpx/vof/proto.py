#!/usr/bin/python

import getopt
from pyVmomi import Vmodl, Vim
import os
import sys

import vom.object
import vom.service
#import time


# Prototype for VMware Orchestration Framework
#
# Base set of VOM Objects and VOM Services
#
# 1. GetAllVMs | VMtoVirtualDisk
# 2. GetAllVMs | FilterBy(powerStatus == "poweredOn") | VMtoVirtualCdrom | disconnect
# 3. GetAllVMs | VMtoVirtualEthernetAdapter | FilterBy(oneof Ethernet*.networkName == "<network>") | rename "new_name"
# 
#
# To do:


def usage():
   print "Usage: vimdump <options>\n"
   print "Options:"
   print "  -h            help"
   print "  -H <host>     host to connect. default is 'localhost'"
   print "  -O <port>     port to connect. default is 902 for VMDB adapter."
   print "  -U <user>     user to connect as. default is logged in user."
   print "  -P <password> password to login."
   print "  -A <adapter>  adapter type.  Either 'VMDB' or 'SOAP'. default is 'VMDB'"


def PrintIdArray(array):
   i = 1
   print "["
   for a in array:
      print "   %d. %s" % (i, a.ToIdString())
      i = i + 1
   print "]"

def PrintArray(array):
   i = 1
   print "["
   for a in array:
      print "   %d. %s" % (i, str(a))
      i = i + 1
   print "]"

def PrintVmomiArray(array):
   i = 1
   print "["
   for a in array:
      print "   %d. %s" % (i, a)
      i = i + 1
   print "]"

def main():
   try:
      opts, args = getopt.getopt(sys.argv[1:], "hH:O:U:P:A:",
                                 ["help",
                                  "host=",
                                  "port=",
                                  "user=",
                                  "password=",
                                  "adapter="])
   except getopt.GetoptError:
      # print help information and exit:
      usage()
      sys.exit(1)

   host = None
   port = None
   user = None
   password = None
   adapter = None

   for o, a in opts:
      if o in ("-H", "--host"):
         host = a
      if o in ("-O", "--port"):
         port = int(a)
      if o in ("-U", "--user"):
         user = a
      if o in ("-P", "--password"):
         password = a
      if o in ("-A", "--adapter"):
         adapter = a
      if o in ("-h", "--help"):
         usage()
         sys.exit()

   instanceProps = {}
   instanceProps["host"] = host
   instanceProps["port"] = port
   instanceProps["user"] = user
   instanceProps["password"] = password
   instanceProps["adapter"] = adapter

   print "Getting VirtualMachines"
   stream = vom.service.GetAllVMs(instanceProps)
   print "Got %d VirtualMachines." % len(stream)
   PrintIdArray(stream)

   print "Transmuting to VirtualDisks"
   stream = vom.service.VMtoVirtualDisk(stream, instanceProps)
   print "Got %d VirtualDisks." % len(stream)
   PrintIdArray(stream)

#   print "Transmuting to VirtualCdrom"
#   stream = vom.service.VMtoVirtualCdrom(stream, instanceProps)
#   print "Got %d VirtualCdrom." % len(stream)
#   PrintIdArray(stream)

#   stream = vom.service.ToProperty(stream, "capacityInKB")
   stream = vom.service.ToProperty(stream, "backing")
   PrintVmomiArray(stream)


if __name__ == "__main__":
   main()

