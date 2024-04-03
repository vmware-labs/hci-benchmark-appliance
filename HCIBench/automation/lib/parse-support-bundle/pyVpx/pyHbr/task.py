#
# task.py
#
# Helpers for handling hbrsrv task objects.
#
# Much of this is just reworked from pyVim's task calls but with changes
# to deal with how hbrsrv tasks differ from Vim tasks.
#

import logging

from pyVmomi import Vmodl
from pyVmomi import Hbr

logger = logging.getLogger('pyHbr.task')


def TaskUpdatesVerbose(task, progress, multi):
   """
   Verbose information about task progress
   """
   if isinstance(task.info.progress, int):
      info = task.info
      if not isinstance(progress, str):
         progress = '%d%% (%s)' % (info.progress, info.state)

      if multi :
         logger.info('%s %s - %s' % (task._GetMoId(), info.operation, progress))
      else:
         logger.info(progress)


def WaitForTask(task,
                raiseOnError=True,
                si=None,
                pc=None,
                onProgressUpdate=None,
                verbose=False):
   """
   Wait for task to complete.

   @type  raiseOnError      : bool
   @param raiseOnError      : Any exception thrown is thrown up to the caller
                              if raiseOnError is set to true.
   @type  si                : ManagedObjectReference to the manager that has
                              the task.
   @param si                : Service instance that has the task.
   @type  pc                : ManagedObjectReference to a PropertyCollector.
   @param pc                : Property collector to use. If None, get it from
                              the ServiceInstance.
   @type  onProgressUpdate  : callable
   @param onProgressUpdate  : Callable to call with task progress updates.
   """

   if si is None:
      raise RuntimeError("Trying to wait for task with no service instance.")

   if pc is None:
      pc = si.propertyCollector

   progressUpdater = ProgressUpdater(task, onProgressUpdate, verbose, False)
   progressUpdater.Update('Created %s task' % task.info.operation)

   filter = CreateFilter(pc, task)

   version, state = None, None
   # Loop looking for updates till the state moves to a completed state.
   while state not in (Hbr.Replica.TaskInfo.State.success,
                       Hbr.Replica.TaskInfo.State.error):
      try:
         version, state = GetTaskStatus(task, version, pc)
         progressUpdater.UpdateIfNeeded()
      except Vmodl.Fault.ManagedObjectNotFound:
         logger.warning('Task object has been deleted')
         break

   filter.Destroy()

   if state == "error":
      progressUpdater.Update('Error: %s' % str(task.info.error))
      if raiseOnError:
         raise task.info.error
      else:
         logger.error('Task reported error: ' + str(task.info.error))
   else:
      progressUpdater.Update('Completed %s task' % task.info.operation)

   return state


def WaitForTasks(tasks,
                 raiseOnError=True,
                 si=None,
                 pc=None,
                 onProgressUpdate=None,
                 verbose=False,
                 results=None):
   """
   Wait for mulitiple tasks to complete. Much faster than calling WaitForTask
   N times
   """

   if not tasks:
      return

   if si is None:
      raise RuntimeError("Trying to wait for task with no service instance.")

   if pc is None:
      pc = si.propertyCollector

   if results is None:  results = []

   progressUpdaters = {}
   for task in tasks:
      progressUpdater = ProgressUpdater(task, onProgressUpdate, verbose, True)
      progressUpdater.Update('Created %s task %s' % (task.info.operation,
                                                     task._GetMoId()))
      progressUpdaters[str(task)] = progressUpdater

   filter = CreateTasksFilter(pc, tasks)

   try:
      version, state = None, None

      # Loop looking for updates till the state moves to a completed state.
      while len(progressUpdaters):
         update = pc.WaitForUpdates(version)
         for filterSet in update.filterSet:
            for objSet in filterSet.objectSet:
               task = objSet.obj
               taskId = str(task)
               for change in objSet.changeSet:
                  if change.name == 'info':
                     state = change.val.state
                  elif change.name == 'info.state':
                     state = change.val
                  else:
                     continue

                  progressUpdater = progressUpdaters.get(taskId)
                  if not progressUpdater:
                     continue

                  if state == Hbr.Replica.TaskInfo.State.success:
                     progressUpdater.Update('Completed %s task %s' % \
                                            (task.info.operation,
                                             task._GetMoId()))
                     progressUpdaters.pop(taskId)
                     # cache the results, as task objects could expire if one
                     # of the tasks take a longer time to complete
                     results.append(task.info.result)
                  elif state == Hbr.Replica.TaskInfo.State.error:
                     err = task.info.error
                     progressUpdater.Update('Error: %s' % str(err))
                     if raiseOnError:
                        raise err
                     else:
                        logger.error("Task %s reported error: %s" % (taskId, str(err)))
                        progressUpdaters.pop(taskId)
                  else:
                     if onProgressUpdate:
                        progressUpdater.UpdateIfNeeded()
         # Move to next version
         version = update.version
   finally:
      if filter:
         filter.Destroy()
   return


def GetTaskStatus(task, version, pc, timeout=10):
   waitOptions = Vmodl.Query.PropertyCollector.WaitOptions(maxWaitSeconds=timeout)
   update = pc.WaitForUpdatesEx(version, waitOptions)
   state = task.info.state
   return update.version if update else version, state


def CreateFilter(pc, task):
   """ Create property collector filter for task """
   return CreateTasksFilter(pc, [task])


def CreateTasksFilter(pc, tasks):
   """ Create property collector filter for tasks """
   if not tasks:
      return None

   # First create the object specification as the task object.
   objspecs = [Vmodl.Query.PropertyCollector.ObjectSpec(obj=task)
                                                            for task in tasks]

   # Next, create the property specification as the state.
   propspec = Vmodl.Query.PropertyCollector.PropertySpec(type=Hbr.Replica.Task,
                                                         pathSet=[],
                                                         all=True)

   # Create a filter spec with the specified object and property spec.
   filterspec = Vmodl.Query.PropertyCollector.FilterSpec()
   filterspec.objectSet = objspecs
   filterspec.propSet = [propspec]

   # Create the filter
   return pc.CreateFilter(filterspec, True)


class ProgressUpdater(object):
   """
   Class that keeps track of task percentage complete and calls a
   provided callback when it changes.
   """

   def __init__(self, task, onProgressUpdate=None, verbose=False, multi=False):
      self.task = task
      self.prevProgress = 0
      self.progress = 0
      self.multi = multi

      if verbose:
         self.taskUpdate = TaskUpdatesVerbose
      else:
         self.taskUpdate = onProgressUpdate

   def Update(self, state):
      if self.taskUpdate:
         self.taskUpdate(self.task, state, self.multi)

   def UpdateIfNeeded(self):
      self.progress = self.task.info.progress

      if self.progress != self.prevProgress:
         self.Update(self.progress)

      self.prevProgress = self.progress

