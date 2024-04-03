#!/usr/bin/python

from __future__ import print_function

import sys
import time
import getopt
from pyVmomi import Vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm, folder
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import atexit

# Import different test modules
from testFirmware import mainTestFirmware
from testMulticore import mainTestMulticore

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter"),
                     (["t:", "test="], "", "Speciffic test to run", "test")
                   ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage"),
                        (["runall", "r"], True, "Run all the tests", "runall"),
                        (["nodelete"], False, "Dont delete vm on completion", "nodelete") ]

   allTests = {
                'firmware':  mainTestFirmware,
                'multicore': mainTestMulticore
              }

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()

      print("\nTests available:")
      for k in allTests.keys():
         print("\t" + k)

      sys.exit(0)

   # Connect
   si = SmartConnect(host=args.GetKeyValue("host"),
                     user=args.GetKeyValue("user"),
                     pwd=args.GetKeyValue("pwd"))
   atexit.register(Disconnect, si)


   # Process command line
   numiter = int(args.GetKeyValue("iter"))
   runall = args.GetKeyValue("runall")
   noDelete = args.GetKeyValue("nodelete")
   test = args.GetKeyValue("test")
   status = "PASS"

   for i in range(numiter):
       bigClock = StopWatch()

       partialStatus = "PASS"

       if test == "":
          for k in allTests.keys():
             partialStatus = allTests[k]()
       else:
          if test in allTests.keys():
             partialStatus = allTests[test]()
          else:
             Log("Test '"+ test +"' not found. Check usage for list of tests.")

       if partialStatus == "FAIL":
          status = "FAIL"

       Log("Tests completed.")
       bigClock.finish("iteration " + str(i))

   Log("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()

