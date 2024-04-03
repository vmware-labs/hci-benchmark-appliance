#!/usr/bin/env python
'''
Python stress testing framework

This module contains the abstraction that forms the basis of stress tests
(ToggleOp) and test driver classes (LoopIndependent, LoopConflict and
the generic LoopDriver). Other classes to represent loop limits (LoopLimit),
client arguments (ClientArg) and a thread barrier (Barrier) are also provided.
'''
import sys
import types
import traceback
import time
import threading

##############################################################################
# Exported classes and functions
##############################################################################
__all__ = ['ToggleOp', 'LoopDriver', 'LoopConflict', 'LoopIndependent'
           , 'LoopLimit', 'DefLoopLimit', 'ClientArg', 'Barrier']
class ToggleOp:
   """
   Abstraction to represent a repeatable operation

   This abstraction needs be derived for the operations that are stressed via
   the drivers
   """
   def __init__(self, args=None):
      """
      args represents the arguments that this operation needs. This can be
      anything, but if your operation needs multiple arguments, you may want
      it to take a dictionary, list or specific class.
      """
      self.args = args
      self.clientId = "0"
   def __del__(self): pass
   def on(self):
      """
      The first step in a repeatable operation.
      Typically sets a state that the 'off' method should un-set
      """
      pass
   def off(self):
      """
      This is the third step in a repeatable operation.
      Typically un-sets the state set in the 'on' method.
      """
      pass
   def onVerify(self):
      """
      This the second step in a repeatable operation. Returns a boolean.
      If the return value is not 'True', the loop processing terminates.
      Otherwise, the loop processing continues. Typically used to verify the
      'on' step. Returns True by default.
      """
      return True
   def offVerify(self):
      """
      This the final (fourth) step in a repeatable operation.
      Returns a boolean. If the return value is not 'True', the loop
      processing terminates. Otherwise, loop processing continues. Typically
      used to verify the 'off' step. Returns True by default.
      """      
      return True
   def getClientId(self):
      """
      Returns the identifier for the client corresponding to the current thread
      """
      return self.clientId
   def syncPreWait(self, barrier):
      """
      This method is called when clients enter the synchronization barrier.
      Use 'barrier.data' to store information that can be checked in the
      'syncPreWait' calls of other clients or the 'syncPreOpen' call that the
      final client will make. Only called when synchronization is enabled for
      the client.
      """
      pass
   def syncPreOpen(self, barrier):
      """
      This method is called when the last client reaches the synchronization
      barrier and is about to 'open' the barrier for all clients to leave.
      Synchronization validation can be performed here.'barrier.data' is the
      shared data that can be checked. Only called when synchronization is
      enabled for the client.
      """      
      return True
   def syncPreLeave(self, barrier):
      """
      This method is called when the client is about to leave the barrier.
      Only called when synchronization is enabled for the client.
      """
      pass
class LoopLimit:
   """
   Represents the limit for looping.
   """
   def __init__(self, iters=1, time=None):
      """
      'iters' represents the maximum number of iterations that the loop
      should run. 'time' represents the amount of time that the loop should
      run.
      Advisory: If both values are set, loop execution should terminate when
      either limit is reached. Note that time checking is typically done at the
      end of loop, that is, clients are not terminated in the middle of loops
      even if the loop run time is exceeded.
      """
      self.iters = iters
      self.time = time

DefLoopLimit = LoopLimit()

class ClientArg:
   """
   Stores the parameters for a client that will be run concurrently.
   """
   def __init__(self, op, args=[], limit=DefLoopLimit, sync=True):
      """
      'op' represents the operation that the client performs. 'op' should
      inherit from 'ToggleOp'). 'args' represent the argument that will be
      sent to the constructor of 'op'. 'limit' represents the loop limit for
      this client and 'sync' indicates whether this client should synchronize
      with other clients in its group.
      """
      self.op = op
      self.args = args
      self.limit = limit
      self.sync = sync
class Barrier:
   """
   Provides a mechanism for synchronization of multiple threads. This can be
   used to ensure that all threads reach a barrier before they can proceed.
   """
   def __init__(self, length=1, data=None):
      """
      'length' denotes the number of threads a barrier should hold. 'data' is
      anything that the clients intend to share (and check).
      """
      self.length = length
      self.data = data
      self.cond = threading.Condition()
      self.numPresent = 0
   def enter(self):
      """
      This method should be called when a thread reaches a barrier.
      """
      if self.numPresent > self.length:
         raise Exception("Invalid barrier use: thread limit ("
                         + str(self.length) + ") already reached")
      self.cond.acquire()
      self.numPresent += 1
   def isFull(self):
      """
      Indicates whether the barrier is full to its limit
      """      
      return self.numPresent == self.length
   def wait(self):
      """
      This methods should be called if the thread intends to wait on the
      barrier,
      """
      self.cond.wait()
   def open(self, syncOk=True):
      """
      This method should be called if the thread intends to notify all
      waiting clients. The 'syncOk' argument is returned in the 'leave' method
      and can be used by threads to verify if the barrier synchronization
      happened as expected
      """
      self.syncOk = syncOk
      self.cond.notifyAll()
   def leave(self):
      """
      This method should be called if the thread intends to leave the barrier.
      """
      self.numPresent -= 1
      cond = self.cond
      if self.numPresent == 0:
         self.cond = threading.Condition()
      cond.release()
      return self.syncOk

class LoopOp(threading.Thread):
   PASS = 0
   ERROR = 1
   FAIL = 2
   VERIFY_FAIL = 3
   SYNC_FAIL = 4
   def __init__(self, id, op, args, limit=DefLoopLimit, syncInfo=None):
      threading.Thread.__init__(self)
      self.id = id
      self.op = op
      self.args = args
      self.limit = limit
      self.syncInfo = syncInfo
      self.status = self.PASS
      self.totalOps = 0
      self.totalRunTime = 0.0
      self.currentLoopNum = 0
      self.startTime = 0.0
   def setSync(self, doSync):
         self.doSync = doSync
   def loopInit(self):
      self.startTime = time.time()
   def loopNext(self):
      proceed = False
      if self.limit.iters is not None:
         if self.currentLoopNum < self.limit.iters: proceed = True
      if self.limit.time is not None:
         if (time.time() - self.startTime) < self.limit.time: proceed = True
      self.currentLoopNum += 1      
      return proceed
   def runLoop(self):
      self.loopInit()
      while self.loopNext():
         self.obj.on()
         if self.obj.onVerify() is not True:
            self.status = self.VERIFY_FAIL
            break
         if not self.sync():
            self.status = self.SYNC_FAIL
            break
         self.obj.off()
         if self.obj.offVerify() is not True:
            self.status = self.VERIFY_FAIL
            break
         if not self.sync():
            self.status = self.SYNC_FAIL
            break
         print (self.obj.getClientId()
                + " completed loop number "
                + str(self.currentLoopNum))
   def sync(self):
      if self.syncInfo == None:
         return True
      barrier = self.syncInfo
      barrier.enter()
      if not barrier.isFull():
         self.obj.syncPreWait(barrier)
         barrier.wait()
         self.obj.syncPreLeave(barrier)            
      else:
         syncOk = self.obj.syncPreOpen(barrier)
         barrier.open(syncOk) 
         self.obj.syncPreLeave(barrier)
      return barrier.leave()
   def run(self):
      self.obj = None
      try:
         self.obj = self.op(self.args)
         self.obj.clientId = self.id
         self.runLoop()
      except:
         traceback.print_exc()
         self.status = self.ERROR
      self.totalOps = self.currentLoopNum - 1
      self.totalRunTime = time.time() - self.startTime

class LoopDriver:
   """
   A driver that can launch multiple clients that loop on 'ToggleOp's
   Important concepts are 'client' and 'group':
   clients represent an individual thread that loops on a ToggleOp
   group represents a set of clients, some of which may synchronize on
   a barrier after each 'onVerify' and 'offVerify' step.
   """
   def __init__(self, args):
      """
      'args' must be a 2-dimensional list of ClientArg. Each "row" of args
      represents a group of clients that can synchronize with each other.
      For example:
      To  launch 3 independent clients that loop 10 times on Op1, args can be:
      [
         [ClientArg(Op1, arg1, Limit(10), False)],
         [ClientArg(Op1, arg2, Limit(10), False)],
         [ClientArg(Op1, arg3, Limit(10), False)]
      ]
      The last argument to ClientArg is false since only one client is present
      in a group so synchronization (and the corresponding overhead) is not
      needed.

      To launch 3 groups of synchronizing clients that loop 10 times on Op2,
      args can be:
      [
         [
            ClientArg(Op2, arg1_1, Limit(10)),
            ClientArg(Op2, arg1_2, Limit(10))
         ],
         [
            ClientArg(Op2, arg2_1, Limit(10)),
            ClientArg(Op2, arg2_2, Limit(10))
         ],
         [
            ClientArg(Op2, arg3_1, Limit(10)),
            ClientArg(Op2, arg3_2, Limit(10))
         ]

      ]

      To launch 3 groups of clients for Op1, Op2 and Op3, args can be:
      [
         [
            ClientArg(Op1, arg1_1, Limit(10)),
            ClientArg(Op1, arg1_2, Limit(10))
         ],
         [
            ClientArg(Op2, arg2_1, Limit(10)),
            ClientArg(Op2, arg2_2, Limit(10))
         ],
         [
            ClientArg(Op3, arg3_1, Limit(10), False),
            ClientArg(Op3, arg3_2, Limit(10), False)
         ]

      ]
      Note that the last group of clients in the above won't synchronize.

      
      Ops in a particular group can be different. Also, you can choose to
      only require a few clients in a group to synchronize. Further, there
      can be different number of clients in each group. Example:
      [
         [
            ClientArg(Op1, arg1_1, Limit(10), False),
            ClientArg(Op2, arg1_2, Limit(10)),
            ClientArg(Op2, arg1_3, Limit(10))            
         ],
         [
            ClientArg(Op3, arg2_1, Limit(10)),
            ClientArg(Op4, arg2_2, Limit(10))
         ],
         [
            ClientArg(Op5, arg3_1, Limit(10), False),
            ClientArg(Op6, arg3_2, Limit(10), False),
            ClientArg(Op6, arg3_3, Limit(10), False),
            ClientArg(Op6, arg3_4, Limit(10), False),
            ClientArg(Op6, arg3_5, Limit(10), False)            
         ]

      ]
      Each client in the above loops on a different op. Note that
      in the first group, only the second and third client will synchronize.
      The last group has 5 clients in it.
      """
      self.groupList = []
      for groupArgs in args:
         threadGroup = []
         syncInfo = None
         barrierLen = 0
         for clientArg in groupArgs:
            if clientArg.sync == True:
               barrierLen += 1
         if barrierLen > 0:
            syncInfo = Barrier(barrierLen)
         for clientArg in groupArgs:
            id = str(len(self.groupList)) + ":" + str(len(threadGroup))
            threadGroup.append(LoopOp(id
                                      , clientArg.op
                                      , clientArg.args
                                      , clientArg.limit
                                      , syncInfo))
         self.groupList.append(threadGroup)
   def run(self):
      """
      Make the driver launch the clients
      """
      for threadGroup in self.groupList:
         for thread in threadGroup:
            thread.start()
               
      self.status, self.totalOps, self.totalRunTimes = [], [], []
            
      for threadGroup in self.groupList:
         for thread in threadGroup:
            thread.join()
            self.status.append(thread.status)
            self.totalOps.append(thread.totalOps)
            self.totalRunTimes.append(thread.totalRunTime)
         
   def printResults(self):
      """
      Print information about the client runs
      """
      # very basic information is printed for now.
      # can be made more comprehensive:
      # - print individual thread info
      # - conflict group info
      print "Number of groups: " + str(len(self.groupList))
      
      totalNumOps = 0
      for totalOpIter in self.totalOps: totalNumOps += totalOpIter
      totalNumClients = 0
      for group in self.groupList: totalNumClients += len(group)
      print "Total number of clients: " + str(totalNumClients)
      print "Average number of loops: " + str(totalNumOps
                                              * 1.0 / len(self.totalOps))
      
      totalTime = 0
      for totalTimeIter in self.totalRunTimes: totalTime += totalTimeIter
      print "Average run time:" + str(totalTime / len(self.groupList))
      
class LoopIndependent(LoopDriver):
   """
   Driver to launch independent clients
   """
   def __init__(self, op, args, limit=DefLoopLimit):
      """
      'op' must be of the type ToggleOp. All clients will perform this op.
      'args' must be a list. Number of clients launched equals the size of
      this list. Each element of the list will be passed to the initializer
      of the 'op' object of a client.
      """
      if type(args) is not types.ListType:
         raise ValueError("args must be a list")
      convArgs = [[ClientArg(op, arg, limit, False)] for arg in args]
      LoopDriver.__init__(self, convArgs)

class LoopConflict(LoopDriver):
   """
   Driver to launch groups of clients. Clients within groups can synchronize.
   """
   def __init__(self, ops, args, limit=DefLoopLimit, sync=True):
      """
      Each element of 'ops' must be a ToggleOp; each element will be executed
      by one client in every group.
      'args' must be a list. Number of groups of clients launched equals
      the size of this list. Each element of this list will be passed to
      the initializer of the 'op' object of a client in every group.
      Therefore, total number of clients launched will be len(ops) * len(args)
      'sync' indicates whether the clients of a group synchronize.
      Example:
      To launch 3 groups of synchronizing clients that loop 10 times on Op2,
      call as follows:
      LoopConflict([Op2]*3, argList, Limit(10), True)
      where len(argList) is 10
      """      
      if type(ops) is not types.ListType:
         raise ValueError("ops must be a list")      
      if type(args) is not types.ListType:
         raise ValueError("args must be a list")
      convArgs=[[ClientArg(op, arg, limit, sync) for op in ops]
                for arg in args]
      LoopDriver.__init__(self, convArgs)

