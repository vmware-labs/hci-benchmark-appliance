from __future__ import print_function

import getopt
import vc
import connect
import invt
import sys
import atexit

"""
Same script to add a host to virtual center. Checks to see if a datacenter
already exists: if not, it creates one, and adds the host to it.
"""

def Usage(msg="Unknown error"):
   print("Error: " + msg)
   print("Usage: addHost [-d datacenter] [-u user] [-p passwd] <hostName>")
   sys.exit(1)

def main():
   user="Administrator"
   pwd="ca$hc0w"
   dataCenter = None

   try:
      opts,args = getopt.getopt(sys.argv[1:], "d:u:p:")
   except getopt.GetoptError:
      Usage("Unknown arguments")

   if len(args) == 0:
      Usage("Host not specified")
   host = args[0]

   for a,v in opts:
      if a=="-d":
         dataCenter = v
      if a=="-u":
         user = v
      if a=="-p":
         pwd = v

   si = connect.Connect(user=user, pwd=pwd)
   atexit.register(connect.Disconnect, si)

   dataCenterName = dataCenter is None and "pyDatacenter" or dataCenter
   if invt.GetDatacenter(dataCenter) is None:
      # No datacenter is specified, or the datacenter specified does not exist.
      print("Creating a new datacenter " + dataCenterName)
      vc.CreateDatacenter(dataCenterName)

   print("Adding host " + host + "...", end='')
   vc.AddHost(host=host, dataCenter=dataCenterName)
   print("Done!")


if __name__ == "__main__":
   main()

