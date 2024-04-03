#!/usr/bin/python

###
### Test description:
###
### Pick a vm specified by an index on the command line and make 100000 getconfig calls
### to it in rapid succession.
###
from __future__ import print_function

import sys
from pyVmomi import Vim
from pyVmomi import VmomiSupport
from pyVim.connect import Connect, Disconnect
from pyVim import folder
import time
import atexit

def getdata(vm):
    i = 0
    while i < 1000:
	  config = vm.GetConfig()
	  summary = vm.GetSummary()
	  i = i + 1
	  #print("Iteration: %s" % i)

def main():
    # Process command line
    vmNum = 0
    host = "jairam-esx"
    start = time.time()
    if len(sys.argv) > 1:
       host = sys.argv[1]
       if len(sys.argv) > 2:
          vmNum = int(sys.argv[2])

    # Connect
    si = Connect(host)
    atexit.register(Disconnect, si)

    # Get vms
    vmList = folder.GetAll()
    getdata(vmList[vmNum])

    print("Total time: %s" % (time.time() - start))


# Start program
if __name__ == "__main__":
    main()
