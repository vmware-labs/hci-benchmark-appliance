#!/usr/bin/python

#------------------------------------------------------------------------------
#
# Unit test for Virtual Storage Lifecycle Management Plugin Service.
#
#------------------------------------------------------------------------------


# Currently this test runs as a standalone process, not as a test running
# withing a framework.
#
# This test requires the hostd log file from a host running the vslmsvc plugin.
# The log file is obtained from the host provided in the command line useing
# the supplied user id and password.  If the host has been running for too long
# the log file may have rolled over and the required information will not be
# found in the log file.  In this case the hostd process should be restarted.
#
# ToDo: 1) Automatically launch a host if one isn't provided.
#       2) Try restarting the host if the init entry is not found in the log.
#       3) Incorporate this test into a test framework.

from __future__ import print_function

import sys
import atexit
import subprocess
import time
import re

from pyVim.connect import SmartConnect, Disconnect
from pyVim import arguments
from pyVim import host
from pyVim.helpers import Log

#
# Define command line options
#
                  # [argvals], default, help, name
supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                  (["u:", "user="], "root", "User name", "user"),
                  (["p:", "pwd="], "", "Password", "pwd") ]

supportedToggles = [ (["usage", "help"],
                      False, "Show usage information", "usage"),
                     (["v", "verbose"],
                      False, "Verbose output", "verbose") ]

#
# Parse command line parameters and process usage.
#
args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
if args.GetKeyValue("usage") == True:
   args.Usage()
   sys.exit(0)

#
# Define a connection with the host.
#
si = SmartConnect(host=args.GetKeyValue("host"),
                  user=args.GetKeyValue("user"),
                  pwd=args.GetKeyValue("pwd"))
atexit.register(Disconnect, si)

def main():
   #
   # Open connection with host
   #
   hs = host.GetHostSystem(si)
   verbose = (args.GetKeyValue("verbose") == True)

   #
   # Run plugin tests.
   #
   vslmsvcPlugginTest = VslmsvcPlugginTests(verbose);
   vslmsvcPlugginTest.runTests()

   #
   # Report test results.
   #
   if (verbose):
      Log(" tests = " + str(vslmsvcPlugginTest.testCount()))
      Log(" failures = " + str(vslmsvcPlugginTest.testFailureCount()))
   if (vslmsvcPlugginTest.testFailureCount()):
      resultsMessage = str(vslmsvcPlugginTest.testFailureCount()) +\
                       " Vslmsvc Pluggin Test Failures:\n"
      for message in vslmsvcPlugginTest.errorMessages:
         resultsMessage += message + "\n"
   else:
      resultsMessage = "All tests passed."

   if(verbose):
      Log(resultsMessage)
   else:
      raise Exception(resultsMessage)

#
# Tester Class for vslmsvc pluggin
#
class VslmsvcPlugginTests:

   #---------------------------------------------------------------------------
   #
   # Subclass to find log entries.
   #
   #---------------------------------------------------------------------------
   class SearchRecord:

      #
      # Initialize class attributes
      #
      def __init__(self, data):
         self.data = data
         self.dataLen = len(data)
         self.startSrchIndex = 0
         self.stopSrchIndex = self.dataLen
         self.lastMsg = ""
         self.lastMsgDateStr = ""
         self.lastMsgTimeStr = ""
         self.lastMsgTime = 0
         self.lastMsgIndex = 0

      #
      # Search for a timestamp and the given pattern in the given data.
      # On success record the timestamp, the pattern just found, the index
      # into the data of the pattern, and the index into the data from which
      # to continue the next serach.
      #
      # Returns: True on success; False otherwise
      #
      def grep(self,pat):
         pattern = re.compile("^([-0-9]{10})T([:.0-9]{12})Z.+"+pat,re.M)
         match = pattern.search(self.data,
                                self.startSrchIndex, self.stopSrchIndex)
         if match:
            self.lastMsg = pat
            self.lastMsgIndex = match.start()
            self.startSrchIndex = match.end()
            self._storeMsgTime(match.group(1),match.group(2))
         return match;

      #
      # Store the given timestamp both as a string and as seconds
      # since the epoch.
      #
      # Returns: Timestamp as seconds since the epoch.
      # Throws: ValueError if given strings cannot be converted.
      #
      def _storeMsgTime(self,dateStr,timeStr):
            self.lastMsgDateStr = dateStr
            self.lastMsgTimeStr = timeStr
            dateTimeStr = dateStr+' '+timeStr+"000"
            #try:
            timeTuple = time.strptime(dateTimeStr,
                                      "%Y-%m-%d %H:%M:%S.%f")
            #except ValueError:
            #   print("ValueError excption generated by time.striptime("%s)
            #         % dateTimeStr)
            self.lastMsgTime = time.mktime(timeTuple)
            return self.lastMsgTime
   #---------------------------------------------------------------------------


   #
   # Initialize class attributes
   #
   def __init__(self,verbosity):
      pipe = subprocess.Popen(['ssh',
                               "root@" + args.GetKeyValue("host")
                                       , " cat /var/run/log/hostd.log"],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
      self.verbose = verbosity
      self.tests = self.failures = 0
      self.startKey = "Vslmsvc plugin started"
      self.initKey  = "Vslmsvc plugin initialized"
      self.stopKey  = "Vslmsvc plugin stopped"
      self.data = pipe.communicate()[0]
      self.errorMessages = []

      self.initTime = 0
      self.initIndex = 0
      self.startTime = 0
      self.startIndex = 0
      self.stopTime = 0
      self.stopIndex = 0
      self.searchRecord = self.SearchRecord(self.data)

   #
   # A private method to test and record a condition.
   # Returns: Value of given condition.
   #
   def _assert(self,value):
      self.tests += 1
      if (not value):
         self.failures += 1
      return value;

   #
   # Accessor for number of tests performed.
   # Returns the number of tests performed.
   #
   def testCount(self):
      return self.tests

   #
   # Accessor for number of tests failed.
   # Returns the number of tests failed.
   #
   def testFailureCount(self):
      return self.failures

   #
   # Public interface to initiate testing.
   #
   def runTests(self):
      self._initTest()
      self._startTest()
      self._waitStopTest()
      self._fcdProphylacticaTaskSchedulingTest()

   #
   # Test log for presence of plugin initialization message.
   #
   def _initTest(self):
      if(self._assert(self.searchRecord.grep(self.initKey))):
         self.initTime = self.searchRecord.lastMsgTime
         self.initIndex = self.searchRecord.lastMsgIndex
         return
      self.errorMessages.append('"' + self.initKey + '"'
                                    + " not found in hostd.log.")

   #
   # Test log for presence of plugin started message.
   #
   def _startTest(self):
      if (self._assert(self.searchRecord.grep(self.startKey)) and
                       self.initTime):
         # startTime > initTime is implicit b/c of progressive search
         self.startTime = self.searchRecord.lastMsgTime
         self.startIndex = self.searchRecord.lastMsgIndex
         return
      self.errorMessages.append('"' + self.startKey + '"' +
                                " not found (following init) in hostd.log.")

   #
   # Test log for presence of plugin stopped message.
   #
   def _waitStopTest(self):
      if (self._assert(self.searchRecord.grep(self.stopKey)) and
                       self.startTime):
         self.stopTime = self.searchRecord.lastMsgTime
         self.stopIndex = self.searchRecord.lastMsgIndex
         return
      self.errorMessages.append('"' + self.stopKey + '"' +
                                " not found (following start) in hostd.log.")

   #
   # Test log for presence of log messages indicating the scheduling of a
   # periodic task as well as messages indicating the execution of that tasks
   # according to the expected repitition interval.
   #
   def _fcdProphylacticaTaskSchedulingTest(self):

      expectedSchInterval = 30 # seconds
      keys = ["Vslmsvc::invokeAndRescheduleFCDProphylacticaTask invoked.",
              "FCDLIB: fcd-catalog: Catalog::Prophylactica."]

      for keyIndex in [0,1]:
         # reset begin/end of search
         self.searchRecord.startSrchIndex\
                           = self.startIndex if (self.startIndex) else 0
         self.searchRecord.stopSrchIndex\
                           = self.stopIndex if (self.stopIndex)\
                                            else self.searchRecord.dataLen
         key = keys[keyIndex]
         if self.verbose:
            print('Examining times between "%s"' % key)

         match = self.searchRecord.grep(key)
         if self._assert(match):
            comparisons = 0
            lastSchMsgTime = self.searchRecord.lastMsgTime
            lastSchMsgIndex = self.searchRecord.lastMsgIndex
            lastSchMsgDateStr = self.searchRecord.lastMsgDateStr
            lastSchMsgTimeStr = self.searchRecord.lastMsgTimeStr
            while(1):
               match = self.searchRecord.grep(key) # no assert for these finds
               if not match:
                  break
               comparisons += 1
               timeDiff = (self.searchRecord.lastMsgTime - lastSchMsgTime)
               if not self._assert(timeDiff <= expectedSchInterval + 1 and
                                 timeDiff >= expectedSchInterval - 1):
                  self.errorMessages.append('Improper interval between "' + key
                                   + '"' + " at " + lastSchMsgDateStr + " "
                                   + lastSchMsgTimeStr + " and "
                                   + self.searchRecord.lastMsgDateStr + " and "
                                   + self.searchRecord.lastMsgTimeStr
                                   + " in hostd.log.")
               lastSchMsgTime = self.searchRecord.lastMsgTime
               lastSchMsgIndex = self.searchRecord.lastMsgIndex
               lastSchMsgDateStr = self.searchRecord.lastMsgDateStr
               lastSchMsgTimeStr = self.searchRecord.lastMsgTimeStr

            if not self._assert(comparisons > 0):
               self.errorMessages.append('"' + key + '"' + " only found once "
                                  + "(between start and stop) in hostd.log.")
         else:
            self.errorMessages.append('"' + key + '"' + " not found (between "
                                      + "start and stop) in hostd.log.")


#
# Start program
#
if __name__ == "__main__":
    main()
