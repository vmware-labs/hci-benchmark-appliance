#!/usr/bin/python

import sys
from pyVmomi import Vim
from pyVmomi import VmomiSupport
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import atexit

def main():
    # Process command line
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage") ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Connect
   si = Connect(host=args.GetKeyValue("host"),
                user=args.GetKeyValue("user"),
                pwd=args.GetKeyValue("pwd"))
   atexit.register(Disconnect, si)

   # Connect
   status = "PASS"
   try:
      content = si.RetrieveContent()

      # Gee, getting to hostSystem require quit a bit of works
      dataCenter = content.GetRootFolder().GetChildEntity()[0]
      hostFolder = dataCenter.GetHostFolder()
      computeResource = hostFolder.GetChildEntity()[0]
      hostSystem = computeResource.GetHost()[0]

      # Performance manager
      perfManager = content.GetPerfManager()
      querySpecs = []

      querySpec = Vim.PerformanceManager.QuerySpec()
      querySpec.entity = hostSystem
      querySpecs.append(querySpec)
      for i in range(0,4):
         # Query stats
         entityMetrics = perfManager.QueryStats(querySpecs)

         # Query composite stats
         metricIds = perfManager.QueryAvailableMetric(hostSystem)
         querySpec.metricId = metricIds
         entityMetrics = perfManager.QueryCompositeStats(querySpecs[0])
   except Exception as e:
      Log("Failed test due to exception: " + str(e))
      status = "FAIL"
   finally:
      pass
   Log("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()

