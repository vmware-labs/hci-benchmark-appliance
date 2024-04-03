#!/usr/bin/env python

"""
Copyright 2009-2021 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is YATP (Yet another thread pool)
- Please update and run the threadPool unit test after each modification
"""
__author__ = "VMware, Inc"
import sys
import time
import threading
import sys
if sys.version_info[0] >= 3:
   from queue import Queue, Empty
else:
   from Queue import Queue, Empty

## Work item
#
class WorkItem:
   def __init__(self, fn, *args, **kwargs):
      """ Work item constructor """
      self.fn = fn
      self.args = args
      self.kwargs = kwargs
      self.ret = None
      self.err = None
      self.event = threading.Event()

   def Join(self, timeout=None):
      """ Wait for work item is done """
      # Wait until work is done
      self.event.wait(timeout)

      # Throw exception if error occured
      if self.err:
         raise self.err
      return self.ret

   def Done(self):
      """ Signal work item is done """
      self.event.set()

   def __enter__(self):
      """ with statement enter """
      return self

   def __exit__(self, type, value, traceback):
      """ with statement exit """
      self.Join()
      del self.event, self.fn, self.args, self.kwargs

## Thread pool
#
class ThreadPool:
   def __init__(self, minWorkers=0, maxWorkers=8,
                      idleTimeout=5*60, logger=None):
      """ Thread pool constructor """
      assert(minWorkers >= 0)
      assert(minWorkers <= maxWorkers)
      self.minWorkers = minWorkers
      self.maxWorkers = maxWorkers
      self.idleTimeout = idleTimeout
      self.workers = {}
      self.workItems = Queue(0)
      self.lock = threading.Lock()
      self.shutdown = False
      self.logger = logger
      for worker in range(0, self.minWorkers):
         self._AddWorker()

   def _Log(self, msg):
      """ Log message """
      if self.logger:
         self.logger.info(msg)
      else:
         print(msg)

   def _Worker(self):
      """ Thread pool worker """
      thdName = threading.currentThread().getName()
      while not self.shutdown:
         try:
            # Wait for request
            try:
               workItem = self.workItems.get(timeout=self.idleTimeout)
            except Empty:
               workItem = None

            if not workItem:
               # Worker idle timeout. Retire thread if needed
               with self.lock:
                  doneThread = len(self.workers) > self.minWorkers
                  if doneThread:
                     self._RemoveWorker(thdName)
                     break
                  else:
                     continue
            elif self.shutdown:
               # Put the work item back to queue
               self.workItems.put(workItem)
               break

            # Start work
            workItem.ret = workItem.fn(*workItem.args, **workItem.kwargs)
         except:
            if sys:
               import traceback
               errtype, errvalue, trace = sys.exc_info()
               stackTrace = " ".join(traceback.format_exception(
                                errtype, errvalue, trace))
               self._Log("\n".join([thdName + " caught exception: " + str(errtype),
                        stackTrace]))
               if workItem:
                  workItem.err = errvalue
               #
               # NOTE: See the Python documentation for sys.exc_info for a warning
               # about an inefficiency in garbage collection and the need to
               # delete the local variable to which stacktrace is assigned
               try:
                  del trace
               except:
                  pass
            else:
               # System is dying and likely to be in undefined state.
               # sys (and other imported modules) could be unloaded and set
               # to None when we get here. Must quit as quickly as possible
               return

         # Signal done on workItem
         workItem.Done()

      # One less worker
      with self.lock:
         self._RemoveWorker(thdName)

   def _RemoveWorker(self, thdName):
      """ Remove a worker. Assume locked """
      self.workers.pop(thdName, None)

   def _AddWorker(self):
      """ Add a worker. Assume locked """
      if len(self.workers) < self.maxWorkers:
         thd = threading.Thread(target=self._Worker)
         thd.setDaemon(True)
         thd.start()
         self.workers[thd.getName()] = thd

   def QueueWork(self, fn, *args, **kwargs):
      """
      Queue work
      Returns a WorkItem when work is queued to work queue
      The work will start when a ready worker is available to process the work
      User could call {WorkItem}.Join() to wait for the work item to finish
      """
      if self.shutdown:
         return None

      # Add worker if needed
      with self.lock:
         self._AddWorker()

      workItem = WorkItem(fn, *args, **kwargs)
      self.workItems.put(workItem)
      return workItem

   @staticmethod
   def NormalizeWorks(works):
      """ Generator to return work in normalize form: (fn, args, kwargs) """
      for work in works:
         args = ()
         kwargs = {}
         if callable(work):
            fn = work
         elif len(work) >= 3:
            fn, args, kwargs = work
         elif len(work) == 2:
            fn, args = work
         else:
            fn = work[0]
         yield (fn, args, kwargs)

   def QueueWorksAndWait(self, works):
      """
      Queue a brunch of works and wait until all works are completed / error
      out
      Pass in a list of works: fn / (fn, args) / (fn, args, kwargs)
      Returns a list of (True, return val) / (False, exception) when done
      """
      workItems = [self.QueueWork(fn, *args, **kwargs)
                           for fn, args, kwargs in self.NormalizeWorks(works)]
      results = []
      for work in workItems:
         if work:
            try:
               ret = work.Join()
               results.append((True, ret))
            except:
               results.append((False, sys.exc_info()[0]))
         else:
            # No work queued
            results.append((False, None))

      return results

   def QueueWorkAndWait(self, fn, *args, **kwargs):
      """
      Queue a work and wait until the work is completed / error out
      Returns (True, return val) / (False, exception) when work is done
      """
      return self.QueueWorksAndWait([(fn, args, kwargs)])[0]

   def Shutdown(self, noWait=False):
      """
      Shuthdown this thread pool
      Returns immediately without waiting for all workers to quit if noWait
      is set to True
      """
      # Set myself as shutting down.
      if self.shutdown:
         return
      self.shutdown = True

      # Queue a fake work item
      workItem = object()
      self.workItems.put(workItem)

      # Wait until all workers quit
      if not noWait:
         self._Log("Shutdown: Waiting for workers to quit...")
         while True:
            with self.lock:
               numWorkers = len(self.workers)

            # Done if no worker left or not making progress
            if numWorkers == 0:
               break

            time.sleep(0.1)
         self._Log("Shutdown: All workers quit")

   def __del__(self):
      """ Destructor """
      self.Shutdown()

   def __enter__(self):
      """ with statment enter """
      return self

   def __exit__(self, type, value, traceback):
      """ with statment exit """
      self.Shutdown()
