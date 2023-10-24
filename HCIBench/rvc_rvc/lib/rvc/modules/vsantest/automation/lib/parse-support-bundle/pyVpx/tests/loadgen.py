#!/usr/bin/python

"""
Script to generate concurrent task load against a VC server.
"""
from __future__ import print_function

from pyVmomi import Vim, Vmodl, SoapStubAdapter, Vpx
from pyVmomi.VmomiSupport import newestVersions
from pyVim import connect, invt, task, vm
import sys, os, time, threading, optparse, datetime, popen2, copy
from time import mktime, strptime
import httplib

_SCRIPT_NAME = os.path.basename(os.path.splitext(__file__)[0])
_USAGE="%s <logfile> [options]" % _SCRIPT_NAME

global _log, _proflog
_log = None
_proflog = None

def Log(prefix, x):
   prefix = "[%s: %s] " % (prefix, datetime.datetime.now().isoformat(' '))
   str = "%s %s" % (prefix, x)
   #print(str)
   _log.write("%s\n" % str)
   _log.flush()

def ConvertToSeconds(timestamp):
   return mktime(strptime(timestamp.split('.')[0], "%Y-%m-%dT%H:%M:%S"))

def GetContainerObjects(container, types, recursive):
   viewMgr = connect.GetSi().GetContent().GetViewManager()
   view = viewMgr.CreateContainerView(container, types, recursive)
   objects = view.GetView()
   view.Destroy()
   return objects

class StatsThread(threading.Thread):
   def __init__(self, hostName, hostPort, userName, password):
      threading.Thread.__init__(self)
      connect.ThreadConnect(host=hostName, user=userName, pwd=password,
                            port=hostPort, namespace=newestVersions.GetWireId('vpx'))
      internalSi = Vpx.ServiceInstance('VpxdInternalServiceInstance',
                                       connect.GetStub())
      self.canceled = False
      self.profiler = internalSi.GetProfiler()
      self.registry = self.profiler.GetPerfCounterRegistry()
      self.registry.ClearAll()
      self.query = self.registry.CreateRegexQuery(
         '/LockStats/*|/ActivationStats/*|/HostSyncStats/*', False)

   def Log(self, x):
      prefix = "[Profiler: %s] " % datetime.datetime.now().isoformat(' ')
      str = "%s %s" % (prefix, x)
      _proflog.write("%s\n" % str)
      _proflog.flush()

   def run(self):
      while not self.canceled:
         # Print profiler logs
         self.Log("Start retrieving profiler logs")
         result = self.query.Execute()
         for i in result:
            self.Log("%s %s" % (i.metadata.name, i.value))

         scores = self.profiler.GetObjectScores()
         for s in scores.split('\n'):
            if not s.startswith('/SystemStats'):
               continue
            self.Log("%s" % s)
         # Sleep 30 seconds
         startTime = mktime(datetime.datetime.now().timetuple())
         currTime = startTime
         while (currTime - startTime) < 30:
            time.sleep(5)
            currTime = mktime(datetime.datetime.now().timetuple())

   def Cancel(self):
      self.canceled = True

class PCThread(threading.Thread):
   def __init__(self):
      threading.Thread.__init__(self)
      si = connect.GetSi()
      self.sc = si.RetrieveContent()
      self.pc = self.sc.GetPropertyCollector()
      tm = self.sc.GetTaskManager()

      # Create a blank filter spec.
      filterSpec = Vmodl.Query.PropertyCollector.FilterSpec()
      objectSet = []
      propSet = []

      # Set TaskManager as the root object for the filter.
      objectSpec = Vmodl.Query.PropertyCollector.ObjectSpec()
      objectSpec.SetObj(tm)
      objectSpec.SetSkip(True)
      objectSet.append(objectSpec)

      # Tasks are listed by the "recentTask" array property of TaskManager.
      travSpec = Vmodl.Query.PropertyCollector.TraversalSpec()
      travSpec.SetName("traverseTasks")
      travSpec.SetPath("recentTask")
      travSpec.SetSkip(False)
      travSpec.SetType(tm.__class__)
      objectSpec.SetSelectSet([travSpec])

      # In a Task, we are interested in the info property.
      propSpec = Vmodl.Query.PropertyCollector.PropertySpec()
      propSpec.SetType(Vim.Task)
      propSpec.SetPathSet(["info"])
      propSet.append(propSpec)

      filterSpec.SetObjectSet(objectSet)
      filterSpec.SetPropSet(propSet)

      # Create the task filter
      self.taskFilter = self.pc.CreateFilter(filterSpec, True)

      # Create a dictionary of known task IDs to states
      self.taskMap = {}
      self.mapLock = threading.Lock()

   def Log(self, x):
      print("[PC: %s] %s" % (datetime.datetime.now().isoformat(' '), x))

   def run(self):
      version = None
      while True:
         #self.Log("Waiting for updates")
         try:
            updates = self.pc.WaitForUpdates(version)
         except Vmodl.MethodFault:
            break
         except Exception as e:
            self.Log("WaitForUpdates got exception: %s" % str(e))
            raise
         #self.Log("Got updates")
         version = updates.GetVersion()
         for fu in updates.GetFilterSet():
            filter = fu.GetFilter()
            objectSet = fu.GetObjectSet()
            if filter._GetMoId() == self.taskFilter._GetMoId():
               self.ProcessTaskFilterUpdate(objectSet)
            else:
               self.Log("Unknown filter %s:" % filter._GetMoId())
               raise Exception("Unknown filter %s" % filter._GetMoId())
      self.Log("Exiting")

   def ProcessTaskFilterUpdate(self, objectSet):
      self.mapLock.acquire()
      try:
         for ou in objectSet:
            if not isinstance(ou.GetObj(), Vim.Task):
               self.Log("Not a task")
               continue
            taskId = ou.GetObj()._GetMoId()
            taskInfo = None
            if ou.GetKind() is Vmodl.Query.PropertyCollector.ObjectUpdate.Kind.enter:
               taskInfo = ou.GetChangeSet()[0].GetVal()
               if not self.taskMap.has_key(taskId):
                  taskData = { 'info':taskInfo, 'condition':threading.Condition() }
                  taskData['condition'].acquire()
                  self.taskMap[taskId] = taskData
               else:
                  taskData = self.taskMap[taskId]
                  taskData['condition'].acquire()
                  taskData['info'] = taskInfo

               #self.Log("Task %s appeared, state = %s" %\
               #         (taskId, taskData['state']))
               if (taskData['info'].completeTime != None and
                   (taskData['info'].state == Vim.TaskInfo.State.success or\
                    taskData['info'].state == Vim.TaskInfo.State.error)):
                  taskData['condition'].notifyAll()
               taskData['condition'].release()
               continue
            if ou.GetKind() is Vmodl.Query.PropertyCollector.ObjectUpdate.Kind.leave:
               # self.Log("Task %s disappeared" % taskId)
               #if self.taskMap.has_key(taskId):
               #   del self.taskMap[taskId]
               continue
            if ou.GetKind() is Vmodl.Query.PropertyCollector.ObjectUpdate.Kind.modify:
               taskData = self.taskMap[taskId]
               taskData['condition'].acquire()
               for change in ou.GetChangeSet():
                  type = change.GetName()
                  val = change.GetVal()
                  #self.Log("Change for path %s" % type)
                  if type == "info":
                     taskData['info'] = val
                  elif type == "info.state":
                     taskData['info'].state = val
                  elif type == "info.error":
                     taskData['info'].error = val
                  elif type == "info.result":
                     taskData['info'].result = val
                  elif type == "info.queueTime":
                     taskData['info'].queueTime = val
                  elif type == "info.completeTime":
                     taskData['info'].completeTime = val
                  elif type == "info.startTime":
                     taskData['info'].startTime = val
               #self.Log("Task %s changed, state = %s" % \
               #   (taskId, taskData['state']))
               if (taskData['info'].completeTime != None and
                   (taskData['info'].state == Vim.TaskInfo.State.success or \
                    taskData['info'].state == Vim.TaskInfo.State.error)):
                  taskData['condition'].notifyAll()
               taskData['condition'].release()
      except:
         self.mapLock.release()
         raise
      self.mapLock.release()

   def Cancel(self):
      self.pc.CancelWaitForUpdates()

   def WaitForTaskUpdate(self, theTask):
      taskId = theTask._GetMoId()
      taskData = None
      self.mapLock.acquire()
      if self.taskMap.has_key(taskId):
         taskData = self.taskMap[taskId]
      else:
         taskData = { 'condition': threading.Condition() }
         self.taskMap[taskId] = taskData
      self.mapLock.release()
      taskData['condition'].acquire()
      while not taskData.has_key('info') or \
                (taskData['info'].state != Vim.TaskInfo.State.success and \
                 taskData['info'].state != Vim.TaskInfo.State.error):
         taskData['condition'].wait()

      taskInfo = copy.copy(taskData['info'])
      taskData['condition'].release()
      return taskInfo


class TestThread(threading.Thread):
   def __init__(self, pcThread, id, dc, vms=None):
      threading.Thread.__init__(self)
      self.pcThread = pcThread
      self.id = id
      self.dc = dc
      self.vms = vms
      self.tasks = []

   def GetTasks(self):
      return self.tasks

   def Log(self, x):
      Log("Thread %d" % self.id, x)

   def WaitForTasks(self):
      for t in self.tasks:
         taskInfo = self.pcThread.WaitForTaskUpdate(t)
         if taskInfo.queueTime == None or taskInfo.startTime == None or \
            taskInfo.completeTime == None:
            if taskInfo.state == Vim.TaskInfo.State.success:
               self.Log("-- %s -- %s -- %s -- %s %s %s %s" % \
                        (taskInfo.key, taskInfo.entity, taskInfo.descriptionId,
                         taskInfo.state, taskInfo.queueTime, taskInfo.startTime,
                         taskInfo.completeTime))
            else:
               self.Log("-- %s -- %s -- %s -- %s(%s) %s %s %s" % \
                        (taskInfo.key, taskInfo.entity, taskInfo.descriptionId,
                         taskInfo.state, taskInfo.error.__class__.__name__,
                         taskInfo.queueTime, taskInfo.startTime,
                         taskInfo.completeTime))
         else:
            t1 = ConvertToSeconds(taskInfo.queueTime)
            t2 = ConvertToSeconds(taskInfo.startTime)
            t3 = ConvertToSeconds(taskInfo.completeTime)
            if taskInfo.state == Vim.TaskInfo.State.success:
               self.Log("-- %s -- %s -- %s -- %s %s %d %d" %
                        (taskInfo.key, taskInfo.entity, taskInfo.descriptionId, \
                         taskInfo.state, taskInfo.queueTime, (t2 - t1), (t3 - t2)))
            else:
               self.Log("-- %s -- %s -- %s -- %s(%s) %s %d %d" %
                        (taskInfo.key, taskInfo.entity, taskInfo.descriptionId,
                         taskInfo.state, taskInfo.error.__class__.__name__,
                         taskInfo.queueTime, (t2 - t1), (t3 - t2)))

   def run(self):
      pass


class CreateVMThread(TestThread):
   def __init__(self, pcThread, id, dc, hosts, numVmsPerHost):
      TestThread.__init__(self, pcThread, id, dc)
      self.hosts = hosts
      self.numVmsPerHost= numVmsPerHost

   def run(self):
      numHosts = len(self.hosts)
      self.Log("Creating %d VMs on %d hosts in DC %s" % \
               ((self.numVmsPerHost * numHosts), numHosts, self.dc.name))
      for host in self.hosts:
         self.CreateVMOnHost(host, self.numVmsPerHost)

   def CreateVMOnHost(self, host, numVms):
      dcName = self.dc.name
      hostName = host.name
      vmName = "testvm_" + hostName
      compRes = host.GetParent()
      resPool = compRes.GetResourcePool()
      envBrowser = compRes.GetEnvironmentBrowser()
      configSpec = vm.CreateQuickDummySpec(vmName, envBrowser=envBrowser)
      vmFolder = self.dc.GetVmFolder()
      for i in range(0, numVms):
         vmName = "testvm_" + hostName + "_%d" % i
         configSpec.SetName(vmName)

         self.Log("Creating VM %s on host %s in DC %s started" % \
                  (vmName, hostName, dcName))
         t = vmFolder.CreateVm(configSpec, resPool, host)
         self.Log("Creating VM %s on host %s in DC %s done: %s" % \
                  (vmName, hostName, dcName, t))

         self.tasks.append(t)


class PowerOnThread(TestThread):
   def __init__(self, pcThread, id, dc, vms, groupPowerOn):
      TestThread.__init__(self, pcThread, id, dc, vms)
      self.groupPowerOn = groupPowerOn

   def run(self):
      dcName = self.dc.name
      self.Log("Powering on %s VMs in DC %s" % (len(self.vms), self.dc.name))
      if self.groupPowerOn:
         t1 = self.dc.PowerOnVm(self.vms)
         info = self.pcThread.WaitForTaskUpdate(t1)
         for x in info.result.attempted:
            self.tasks.append(x.task)
      else:
         for v in self.vms:
            self.Log("Powering on %s in DC %s started" % (v.name, dcName))
            t = v.PowerOn()
            self.Log("Powering on %s in DC %s done: %s" % (v.name, dcName, t))
            self.tasks.append(t)


class PowerOffThread(TestThread):
   def __init__(self, pcThread, id, dc, vms):
      TestThread.__init__(self, pcThread, id, dc, vms)

   def run(self):
      dcName = self.dc.name
      self.Log("Powering off %s VMs in DC %s" % (len(self.vms), dcName))
      for v in self.vms:
         self.Log("Powering off %s in DC %s started" % (v.name, dcName))
         t = v.PowerOff()
         self.Log("Powering off %s in DC %s done: %s" % (v.name, dcName, t))
         self.tasks.append(t)

class CloneThread(TestThread):
   def __init__(self, pcThread, id, dc, vms):
      TestThread.__init__(self, pcThread, id, dc, vms)

   def run(self):
      dcName = self.dc.name
      for v in self.vms:
         cloneSpec = Vim.Vm.CloneSpec(location=Vim.Vm.RelocateSpec(),
                                      template = False, powerOn = False)
         srcname = v.name
         dstname = srcname + "-clone"
         self.Log("Cloning %s to %s in DC %s started" % (srcname, dstname, dcName))
         t = v.Clone(v.GetParent(), dstname, cloneSpec)
         self.Log("Cloning %s to %s in DC %s done: %s" % (srcname, dstname, dcName, t))
         self.tasks.append(t)

class DestroyVMThread(TestThread):
   def __init__(self, pcThread, id, dc, vms):
      TestThread.__init__(self, pcThread, id, dc, vms)

   def run(self):
      dcName = self.dc.name
      for v in self.vms:
         self.Log("Destroying %s in DC %s started" % (v.name, dcName))
         t = v.Destroy()
         self.Log("Destroying %s in DC %s done: %s" % (v.name, dcName, t))
         self.tasks.append(t)

def WaitForThreads(threads):
   startTime = time.time()
   for t in threads:
      if t.isAlive():
         t.join()
   Log("main", "Time for task initializtion is %d" % (time.time() - startTime))

   for t in threads:
      t.WaitForTasks()

def CleanupTestVMs(pcThread):
   content = connect.GetSi().GetContent()
   viewMgr = content.GetViewManager()
   vmView = viewMgr.CreateContainerView(content.rootFolder, [Vim.VirtualMachine], True)
   tasks = []
   vms = vmView.GetView()
   Log("main", "Cleanup %d test VMs" % len(vms))
   for v in vms:
      if vm.IsPoweredOn(v):
         tasks.append(v.PowerOff())

   # Wait for all PowerOff tasks
   for t in tasks:
      pcThread.WaitForTaskUpdate(t)

   # Destroy all test VMs
   tasks = []
   for v in vms:
      tasks.append(v.Destroy())

   # Wait for all Destroy tasks
   for t in tasks:
      pcThread.WaitForTaskUpdate(t)


def Main(hostName, hostPort, userName, password, numHosts, numVmsPerHost,
         createVms, groupPowerOn, cloneVms, destroyVms):
   Log("main", "Test started: %s Hosts, %s VMs per host " % \
       (numHosts, numVmsPerHost))
   Log("main", "Connecting to %s:%d" % (hostName, hostPort))

   try:
      si = connect.ThreadConnect(host=hostName, user=userName, pwd=password,
                                 port=hostPort, namespace="vim25/5.5")
   except Exception as e:
      Log("main", "Failed to connect to VC server %s, %s" % (hostName, e))
      exit()

   Log("main", "Connected")

   # Start property collector thread
   Log("main", "Starting property collector thread")
   pcThread = PCThread()
   pcThread.setDaemon(True)
   pcThread.start()

   # Find All Datacenters
   dcs = GetContainerObjects(si.content.rootFolder, [Vim.Datacenter], False)
   numDcs = len(dcs)
   numHostsPerDc = (numHosts / numDcs)
   if numHosts % numDcs != 0:
      numHostsPerDc = numHostsPerDc + 1
      Log("main", "Found %d datacenters, %d hosts per DC" % (numDcs, numHostsPerDc))

   if createVms:
      # Cleanup the inventory
      CleanupTestVMs(pcThread)

   Log("main", "Starting profiler stats thread")
   statsThread = StatsThread(hostName, hostPort, userName, password)
   statsThread.start()

   if createVms:
      # Build a DC-Hosts map before issuing CreateVM tasks
      total = 0
      hostlist = {}
      for dc in dcs:
         count = min(numHosts - total, numHostsPerDc)
         if count == 0:
            break;
         hosts = GetContainerObjects(dc, [Vim.HostSystem], True)
         if len(hosts) < count:
            Log("main", "No enough hosts in DC %s, required %d but only %d found"
               % (dc.name, count, len(hosts)))
            exit()
         hostlist[dc] = hosts[0 : count]
         total = total + count

      # Create VMs
      Log("main", "Starting CreateVm Test")
      startTime = time.time()
      threads = []
      for dc,hosts in hostlist.items():
         thr = CreateVMThread(pcThread, len(threads), dc, hosts, numVmsPerHost)
         thr.start()
         threads.append(thr)
      WaitForThreads(threads)
      Log("main", "Total time for CreateVM is %d" % (time.time() - startTime))


   # Build a DC-VMs map before issuing PowerOn/PowerOff tasks
   vmlist = {}
   for dc in dcs:
      objects = GetContainerObjects(dc, [Vim.VirtualMachine], True)
      vms = []
      for o in objects:
         vms.append(o)
      if len(vms) > 0:
         vmlist[dc] = vms

   # PowerOn VMs
   Log("main", "Starting PowerOn Test")
   startTime = time.time()
   threads = []
   for dc,vms in vmlist.items():
      thr = PowerOnThread(pcThread, len(threads), dc, vms, groupPowerOn)
      thr.start()
      threads.append(thr)
   WaitForThreads(threads)
   Log("main", "Total time for PowerOn is %d" % (time.time() - startTime))

   # Sleep 30 seconds for pending host syncs
   time.sleep(30)

   # PowerOff VMs
   Log("main", "Starting PowerOff Test")
   startTime = time.time()
   threads = []
   for dc,vms in vmlist.items():
      thr = PowerOffThread(pcThread, len(threads), dc, vms)
      thr.start()
      threads.append(thr)
   WaitForThreads(threads)
   Log("main", "Total time for PowerOff is %d" % (time.time() - startTime))

   if cloneVms:
      # Clone VMs
      Log("main", "Starting CloneVM Test")
      startTime = time.time()
      threads = []
      for dc,vms in vmlist.items():
         thr = CloneThread(pcThread, len(threads), dc, vms)
         thr.start()
         threads.append(thr)
      WaitForThreads(threads)
      Log("main", "Total time for CloneVM is %d" % (time.time() - startTime))

      # Update vmlist to include newly cloned VMs
      vmlist = {}
      for dc in dcs:
         vmlist[dc] = GetContainerObjects(dc, [Vim.VirtualMachine], True)

   if destroyVms:
      # Destroy VMs
      Log("main", "Starting DestroyVM Test")
      startTime = time.time()
      threads = []
      for dc,vms in vmlist.items():
         thr = DestroyVMThread(pcThread, len(threads), dc, vms)
         thr.start()
         threads.append(thr)
      WaitForThreads(threads)
      Log("main", "Total time for DestroyVM is %d" % (time.time() - startTime))

   Log("main", "Test Complete")

   Log("main", "Logging out")
   pcThread.Cancel()
   statsThread.Cancel()
   si.content.sessionManager.Logout()

   Log("main", "Done")
   sys.stdout.flush()
   os.close(sys.stdout.fileno())

if __name__ == "__main__":
   parser = optparse.OptionParser(
      usage=_USAGE,
      prog=_SCRIPT_NAME,
      description=__doc__.strip())
   parser.add_option('-s', '--server', action='store',
                     type='string', dest='hostName',
                     help='VIM server to connect to (default localhost)')
   parser.add_option('-o', '--port', action='store',
                     type='int', dest='hostPort',
                     help='Connection port')
   parser.add_option('-u', '--user', action='store',
                     type='string', dest='userName',
                     help='User name to connect as')
   parser.add_option('-p', '--password', action='store',
                     type='string', dest='password',
                     help='User password')
   parser.add_option('-n', '--numhosts', action='store',
                     type='int', dest='numHosts',
                     help='Number of Hosts')
   parser.add_option('-m', '--numvms', action='store',
                     type='int', dest='numVmsPerHost',
                     help='Number of VMs per host')
   parser.add_option('-c', '--createvms', action='store_true',
                     dest='createVms',
                     help='Create and destroy VMs')
   parser.add_option('-g', '--grouppoweron', action='store_true',
                     dest='groupPowerOn',
                     help='Use group powerOn')

   parser.set_defaults(hostName="localhost",
                       hostPort=443,
                       userName="root",
                       password="ca$hc0w",
                       numVmsPerHost=16,
                       numHosts=64,
                       createVms=False,
                       groupPowerOn=False)
   options, args = parser.parse_args(sys.argv)

   if len(args) != 2:
      parser.print_help()
      exit()

   logfile = args[1]
   if os.path.exists(logfile):
      print("Warning, file \"%s\" exists, appending" % logfile)
   else:
      print("Logging to file \"%s\"" % logfile)
   _log = file(logfile, 'a', 0)

   strs = logfile.rsplit('.', 1)
   if (len(strs) < 2):
      proflogfile = "%s-profiler.log" % logfile
   else:
      proflogfile = "%s-profiler.%s" % (strs[0], strs[1])

   if os.path.exists(proflogfile):
      print("Warning, file \"%s\" exists, appending" % proflogfile)
   else:
      print("Logging profiler stats to file \"%s\"" % proflogfile)
   _proflog = file(proflogfile, 'a', 0)

   Main(options.hostName, options.hostPort, options.userName, options.password,
        options.numHosts, options.numVmsPerHost, options.createVms,
        options.groupPowerOn, False, False)
