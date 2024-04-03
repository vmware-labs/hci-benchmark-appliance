#!/usr/bin/python -u
""" Speed test """

from __future__ import print_function

import sys
from pyVmomi import Vim, Vmodl
from pyVim.connect import Connect, Disconnect
from pyVim.helpers import Log
from contrib.threadPool import ThreadPool
import atexit
import time

threadPool = None

def CreatePCFilter(pc, objType, objs):
   """ Create property collector filter for obj """
   # First create the object specification as the task object.
   objspecs = [Vmodl.Query.PropertyCollector.ObjectSpec(obj=obj)
                                                         for obj in objs]

   # Next, create the property specification as the state.
   propspec = Vmodl.Query.PropertyCollector.PropertySpec(
                                          type=objType, pathSet=[], all=True)

   # Create a filter spec with the specified object and property spec.
   filterspec = Vmodl.Query.PropertyCollector.FilterSpec()
   filterspec.objectSet = objspecs
   filterspec.propSet = [propspec]

   # Create the filter
   return pc.CreateFilter(filterspec, True)


def WaitPC(id, pc, objType, objs, numWaitUpdate, waitSec):
   filter = None
   try:
      Log("%s: Begin " % id)
      filter = CreatePCFilter(pc, objType, objs)
      waitOptions = Vmodl.Query.PropertyCollector.WaitOptions(
                                                         maxWaitSeconds=waitSec)
      version = None
      for trial in xrange(0, numWaitUpdate):
         Log("%s: WaitForUpdatesEx %d ..." % (id, trial))
         update = pc.WaitForUpdatesEx(version, waitOptions)
         if update:
            version = update.version
         else:
            break
      Log("%s: Done " % id)
   finally:
      if filter:
         filter.Destroy()


def TestConnectionLimit(si, objType, objs, options):
   # Just in case, raise the fd limit if not enough
   workers = options.workers
   try:
      import resource
      noFds = resource.getrlimit(resource.RLIMIT_NOFILE)
      if noFds < workers:
         resource.setrlimit(resource.RLIMIT_NOFILE, workers)
   except ImportError:
      pass

   pc = si.content.propertyCollector
   numWaitUpdate, waitSec = options.numWaitUpdate, options.waitSec
   works = [(WaitPC, (id, pc, objType, objs, numWaitUpdate, waitSec))
                                                   for id in range(0, workers)]
   workResults = threadPool.QueueWorksAndWait(works)
   for status, result in workResults:
      if not status:
         raise Exception("Connection limit test failed")


## Parse arguments
#
def ParseArguments(argv):
   """ Parse arguments """

   from optparse import OptionParser, make_option

   testHelp = """ """

   # Internal cmds supported by this handler
   _CMD_OPTIONS_LIST = [
      make_option("-h", "--host", dest="host", default="localhost",
                  help="ESX host name"),
      make_option("-o", "--port", dest="port", default=443, help="Port"),
      make_option("-u", "--user", dest="user", default="root",
                  help="Host User name"),
      make_option("-p", "--pwd", dest="pwd", default="",
                  help="Host Password"),
      make_option("-k", "--key", dest="keyFile", default=None,
                  help="Key file path"),
      make_option("-c", "--cert", dest="certFile", default=None,
                  help="Cert file path"),
      make_option("-w", "--workers", dest="workers", type="int",
                  default=8, help="Num of workers"),
      make_option("-s", "--waitSec", dest="waitSec", type="int",
                  default=8, help="Num of sec to wait"),
      make_option("-n", "--numPCUpdates", dest="numWaitUpdate", type="int",
                  default=2, help="Num of pc wait for updates"),
      make_option("-v", "--verbose", action="store_true", dest="verbose_stats",
                  default=False, help="Enable verbose stats"),
      make_option("-?", "--help", action="store_true", help="Help"),
   ]
   _STR_USAGE = "%prog [options]"

   # Get command line options
   cmdParser = OptionParser(option_list=_CMD_OPTIONS_LIST,
                            usage=_STR_USAGE,
                            add_help_option=False)
   cmdParser.allow_interspersed_args = False
   usage = cmdParser.format_help()

   # Parse arguments
   (options, remainingOptions) = cmdParser.parse_args(argv)
   try:
      # optparser does not have a destroy() method in older python
      cmdParser.destroy()
   except Exception:
      pass
   del cmdParser

   # Print usage
   if options.help:
      print(usage)
      print(testHelp)
      sys.exit(0)

   return (options, remainingOptions)


## Main
#
def main():
   global options
   global si
   options, remainingOptions = ParseArguments(sys.argv[1:])

   # Connect
   try:
      si = Connect(host=options.host, port=int(options.port),
                   user=options.user, pwd=options.pwd,
                   keyFile=options.keyFile, certFile=options.certFile)
   except Exception as err:
      print("Login failed: " + str(err))
      return
   atexit.register(Disconnect, si)

   status = "PASS"

   # Parallel or serialize operations
   global threadPool
   threadPool = ThreadPool(maxWorkers=options.workers)

   startTime = None
   endTime = None
   try:
      # si content
      content = si.RetrieveContent()

      startTime = time.time()

      # Connection limit Test
      TestConnectionLimit(si, Vim.Folder, [content.rootFolder], options)

      endTime = time.time()
   except Exception as err:
      Log("Failed test due to exception: " + str(err))
      import traceback
      stackTrace = " ".join(traceback.format_exception(
                            sys.exc_type, sys.exc_value, sys.exc_traceback))
      Log(stackTrace)
      status = "FAIL"

   if threadPool:
      threadPool.Shutdown()

   if startTime and endTime:
      Log("Total test time: %f secs" % (endTime - startTime))
   Log("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
   main()
