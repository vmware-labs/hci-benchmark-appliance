#!/usr/bin/python

#
# Example -
#  $VMTREE/vim/py/py.sh  $VMTREE/vim/py/tests/vslm/vStorageObjectManager.py -h "10.160.49.74" -u "root" -p "" -d "dsName"
#


import sys
import random

import pyVmomi
from pyVmomi import Vim, Vmodl, VmomiSupport, SoapStubAdapter
from pyVmomi import Vmodl
from pyVim.connect import SmartConnect, Disconnect
from pyVim.helpers import Log,StopWatch
from pyVim import arguments
from pyVim import host
import atexit
import vslmUtil

supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                  (["u:", "user="], "root", "User name", "user"),
                  (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                  (["d:", "dsName="], "datastore-1", "Datastore Name", "dsName")]

supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage") ]

args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
if args.GetKeyValue("usage") == True:
   args.Usage()
   sys.exit(0)

# Connect
si = SmartConnect(host=args.GetKeyValue("host"),
                  user=args.GetKeyValue("user"),
                  pwd=args.GetKeyValue("pwd"))
atexit.register(Disconnect, si)

dsName = args.GetKeyValue("dsName")

vsomgr = si.RetrieveContent().vStorageObjectManager
if not vsomgr:
    raise Exception("FCD feature is disabled")

def GetDatastore(si, dsName):
    hs = host.GetHostSystem(si)
    datastores = hs.GetDatastore()
    for ds in datastores:
        if ds.name == dsName:
           return ds
    raise Exception("Error looking up datastore: %s" % dsName)

# Main
def main():
   datastore = GetDatastore(si, dsName)

   vslmUtil.Run(vsomgr, None, datastore)

   Log("All tests passed")

# Start program
if __name__ == "__main__":
    main()

