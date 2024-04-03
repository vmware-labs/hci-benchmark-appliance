#!/usr/bin/env python

"""
Copyright 2009-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is used to test thread pool
"""

from __future__ import with_statement
from contrib.threadPool import ThreadPool
import unittest
import logging
import sys
import time
import threading

def GetName():
   return threading.currentThread().getName()

def FnSleep(seconds):
   print GetName() + ": Sleeping for " + str(seconds)
   time.sleep(seconds)
   print GetName() + ": Done sleeping"

def FnWithoutArguments():
   print GetName() + ": FnWithoutArguments()"
   return 1

def FnArguments(a, *args, **kwargs):
   print GetName() + ": FnArguments(", a, args, kwargs, ")"
   return 1

def FnRaiseStringException():
   print GetName() + ": raise str"
   raise "Exception"

def FnRaiseException():
   print GetName() + ": raise Exception()"
   raise Exception("exception")

## Simple testing
#
class TestSoapHandler(unittest.TestCase):
   ## Setup
   #
   def setUp(self):
      logging.basicConfig(level=logging.INFO)

      self.minWorkers = 2
      self.maxWorkers = 4
      self.idleTimeout = 1
      self.logger = logging.info

   ## tearDown
   #
   def tearDown(self):
      pass

   def CreateDefThreadPool(self):
      return ThreadPool(minWorkers=self.minWorkers, maxWorkers=self.maxWorkers,
                        idleTimeout=self.idleTimeout, logger=logging)

   ## Invoke work
   #
   def test_QueueWorkAndWait(self):
      self.logger("Testing QueueWorkAndWait...")
      with self.CreateDefThreadPool() as threadPool:
         threadPool.QueueWorkAndWait(FnWithoutArguments)
         threadPool.QueueWorkAndWait(FnArguments, 1, c=4)
         threadPool.QueueWorkAndWait(FnArguments, 1, 2, c=4)
         threadPool.QueueWorkAndWait(FnArguments, 1, 2, 3, c=4)

   ## Invoke works
   #
   def test_QueueWorksAndWait(self):
      self.logger("Testing QueueWorksAndWait...")
      with self.CreateDefThreadPool() as threadPool:
         works = [(FnWithoutArguments, ),
                  FnWithoutArguments,
                  (FnArguments, (1,)),
                  (FnArguments, (1,2)),
                  (FnArguments, (), {'a':3, 'b':2, 'c':1})]
         results = threadPool.QueueWorksAndWait(works)
         for status, result in results:
            self.failUnless(status == True and result == 1)

   ## Invoke works with exception
   #
   def test_QueueWorksAndWaitWithException(self):
      self.logger("Testing QueueWorksAndWait with exception...")
      with self.CreateDefThreadPool() as threadPool:
         works = [(FnRaiseStringException, ),
                  (FnWithoutArguments, ),
                  (FnRaiseException, ),
                  (FnArguments, (1,)),
                  (FnArguments, (1,2)),
                  (FnArguments, (), {'a':3, 'b':2, 'c':1})]
         results = threadPool.QueueWorksAndWait(works)
         for status, result in results:
            if status == True:
               self.failUnless(result == 1)
            else:
               self.failUnless(isinstance(result, str) or
                               issubclass(result, Exception))

   ## Queue work
   #
   def test_QueueWork(self):
      self.logger("Testing QueueWork...")
      with self.CreateDefThreadPool() as threadPool:
         workItems = [threadPool.QueueWork(FnWithoutArguments),
                      threadPool.QueueWork(FnArguments, 1, c=4),
                      threadPool.QueueWork(FnArguments, 1, 2, c=4),
                      threadPool.QueueWork(FnArguments, 1, 2, 3, c=4)]
         for workItem in workItems:
            workItem.Join()

   ## Workers control
   #
   def test_WorkersControl(self):
      threadPool = self.CreateDefThreadPool()
      self.logger("Testing max workers limits...")
      workItems = []
      for worker in range(0, self.maxWorkers + 2):
         workItems.append(threadPool.QueueWork(time.sleep, 1))
         self.failUnless(len(threadPool.workers) <= self.maxWorkers)
      self.failUnless(len(workItems) > self.maxWorkers)
      for workItem in workItems:
         workItem.Join()

      # Make sure idle workers quit
      self.logger("Testing idle workers quit...")
      time.sleep(self.idleTimeout + .5)
      self.failUnless(len(threadPool.workers) == self.minWorkers)

      # Make sure shutdown ok
      self.logger("Testing shutdown...")
      threadPool.Shutdown()
      self.failUnless(len(threadPool.workers) == 0)

   ## with statement support
   #
   def test_WithStatementSupport(self):
      if sys.hexversion >= 0x02050000:
         # Additional testing for RAII
         self.logger("Testing thread pool RAII...")
         with self.CreateDefThreadPool() as threadPool:
            workItems = []
            for worker in range(0, self.maxWorkers * 2):
               workItems.append(threadPool.QueueWork(FnSleep, 1))
            # Note: No join. See if shutdown ok

         self.logger("Testing workItem RAII...")
         with self.CreateDefThreadPool() as threadPool:
            for worker in range(0, self.maxWorkers + 2):
               with threadPool.QueueWork(FnWithoutArguments) as workItem:
                  pass
      else:
         pass

   ## Shutdown no wait
   #
   def test_ShutdownNoWait(self):
      self.logger("Testing shutdown no wait...")
      threadPool = self.CreateDefThreadPool()
      threadPool.Shutdown(noWait=True)
      self.failUnless(len(threadPool.workers) == self.minWorkers)

## Test main
#
if __name__ == "__main__":
   unittest.main()
