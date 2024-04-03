#!/usr/bin/python -u
""" Speed test """

from __future__ import print_function

import sys
from pyVmomi import Vim, Vmodl
from pyVmomi import VmomiSupport
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTasks, WaitForTask
from pyVim.vm import CreateQuickDummySpec
from pyVim import vmconfig
from pyVim.invt import GetEnv
from contrib.threadPool import ThreadPool
from datetime import datetime
import atexit
import time
import os
import threading
import subprocess
import copy
import ssl

from multiprocessing import Process, Manager


import uuid

try:
   from com.vmware.cis_client import Session
   from com.vmware.vapi.std.errors_client import (AlreadyInDesiredState,
        NotAllowedInCurrentState, NotFound)
   from com.vmware.vcenter_client import (VM, Datastore, Folder)
   from com.vmware.vcenter.vm_client import (GuestOS, Power)
   from com.vmware.vcenter.vm.hardware_client import (Cpu, Memory,Disk,
        Ethernet,ScsiAddressSpec, SataAddressSpec, IdeAddressSpec)
   from com.vmware.vcenter.vm.hardware.adapter_client import Sata, Scsi

   from lib.datastore import GetDatastoreRef
   from vmware.vapi.lib.connect import get_connector
   from vmware.vapi.security.session import create_session_security_context
   from vmware.vapi.security.user_password import create_user_password_security_context
   from vmware.vapi.stdlib.client.factories import StubConfigurationFactory
except ImportError:
   print("No vAPI support. Build pyVpx and set TESTVPX_PYTHON to get it.")

options = None
si = None
threadPool = None

# Global variables for the concurrent workflow of vm operations test
fd = None
invtOpts = []
vmConfigs = []
vm_svc = None
power_svc = None
datastore_svc = None


def create_disk_create_spec(hba_type, bus_number, unit_number):
    create_spec = None
    if Disk.HostBusAdapterType.IDE == hba_type:
        primary = (bus_number == 0)
        master = (unit_number == 0)
        ide_address_spec = IdeAddressSpec(primary=primary, master=master)
        create_spec = Disk.CreateSpec(type=Disk.HostBusAdapterType.IDE, ide=ide_address_spec)
    elif Disk.HostBusAdapterType.SCSI == hba_type:
        scsi_address_spec = ScsiAddressSpec(bus=bus_number, unit=unit_number)
        create_spec = Disk.CreateSpec(type=Disk.HostBusAdapterType.SCSI, scsi=scsi_address_spec)
    elif Disk.HostBusAdapterType.SATA == hba_type:
        sata_address_spec = SataAddressSpec(bus=bus_number, unit=unit_number)
        create_spec = Disk.CreateSpec(type=Disk.HostBusAdapterType.SATA, sata=sata_address_spec)

    return create_spec


def create_ethernet_create_spec(emulation_type=None,
                                upt_compatibility_enabled=None,
                                mac_type=None,
                                mac_address=None,
                                pci=None,
                                wake_on_lan_enabled=None,
                                backing=None,
                                start_connected=None,
                                allow_guest_control=None,
                                cr=None):
    '''
    Create a Ethernet.CreateSpec to be used to create a NIC
    '''
    ethernet_backing=backing;
    if ethernet_backing is None:
        network = cr.GetNetwork()[0]

        ethernet_backing=Ethernet.BackingSpec(type=Ethernet.BackingType.STANDARD_PORTGROUP,
                                              network=network._moId)
    return Ethernet.CreateSpec(emulation_type, upt_compatibility_enabled,
                               mac_type, mac_address,
                               pci, wake_on_lan_enabled, ethernet_backing,
                               start_connected, allow_guest_control)


#
# Log method is same as pyVim.helpers Log method with an option to
# print stats in the file. This is useful when multiple speedtests
# are executed concurrently from a wrapper code
#
def Log(msg):
   """
   Prints a formatted log message to stdout.

   @type  msg   : str
   @param msg   : Message to log
   @rtype       : None
   """
   global fd

   pMsg = "[ " + str(datetime.now()) + " ]" + msg
   print(pMsg)

   if options.verbose_stats and fd:
      fd.write("%s\n" % pMsg)

def MinAveMaxSd(numbers):
   """ Return (min, avg, max) from a list of numbers """
   min_, avg, max_ = 0, 0, 0
   if len(numbers) > 0:
      min_ = min(numbers)
      avg  = sum(numbers) / len(numbers)
      max_ = max(numbers)
      sd = (sum([(num - avg) ** 2 for num in numbers]) / len(numbers)) ** .5
   return min_, avg, max_, sd


def TasksStat(taskInfos):
   """ Returns a list of (queue time, task process time) """
   stats = []
   for taskInfo in taskInfos:
      queueTime = taskInfo.queueTime
      startTime = taskInfo.startTime
      completeTime = taskInfo.completeTime
      stats.append( (queueTime, startTime, completeTime) )
   return stats


def LogTasksStat(msg, taskInfos):
   """ Log tasks stat """
   Log(msg + " stat")
   stats = TasksStat(taskInfos)

   queueTime = []
   processTime = []
   totalTime = []
   for queue, start, complete in stats:
      if start > queue:
         delta = start - queue
      else:
         delta = start - start
      wait = float(delta.seconds) + float(delta.microseconds)/1000000
      queueTime.append(wait)
      if complete > start:
         delta = complete - start
      else:
         delta = complete - complete
      process = float(delta.seconds) + float(delta.microseconds)/1000000
      processTime.append(process)
      total = wait+process
      totalTime.append(total)
      Log(" %s %s %s ; %f %f %f" % (queue.time(), start.time(), complete.time(),
                                 wait, process, total))
   Log(msg + " queue (min %f secs avg %f secs max %f secs sd %f secs)" % \
                                                      MinAveMaxSd(queueTime))
   Log(msg + " process (min %f secs avg %f secs max %f secs sd %f secs)" % \
                                                      MinAveMaxSd(processTime))
   Log(msg + " total (min %f secs avg %f secs max %f secs sd %f secs)" % \
                                                      MinAveMaxSd(totalTime))


def DoWorksNoWait(works):
   """
   Do works, but don't wait for the result to come back.
   Either in parallel or in series
   """
   global threadPool
   if threadPool:
      results = [threadPool.QueueWork(fn, *args, **kwargs)
                     for fn, args, kwargs in ThreadPool.NormalizeWorks(works)]
   else:
      results = [fn(*args, **kwargs) for fn, args, kwargs
                                          in ThreadPool.NormalizeWorks(works)]
   return results


def JoinWorks(groupRetValues):
   """
   Join works
   groupRetValues is in the form of (retVal, [childRetValues])
   - For threaded works, the childRetValues is expected to be an array of
     child workitems. JoinWorks will recursive call Join() on the child
     workitems to gather all child returns value
     The return value of child workItems Join() is expected to be a
     groupRetValues
   - For non-threaded works, the childRetValues is expected to be an array of
     child return value
   """
   retVal, childRetValues = groupRetValues
   retValues = [retVal]
   if childRetValues:
      global threadPool
      if threadPool:
         childRetValues = [workItem.Join() for workItem in childRetValues]
      for ret in childRetValues:
         retValues.extend(JoinWorks(ret))
   return retValues


class AutoWaitTasks:
   """
   Helper class to call WaitForTasks when time expire. Mainly to get around
   hostd task retention timeout limit. To gather tasks result before they
   disappear
   """
   def __init__(self, numTasks, collectTimeS):
      """ AutoWaitTasks constructor """
      global si
      self.tasks = []
      self.numTasks = numTasks
      self.collectTimeS = collectTimeS
      self.startTime = time.time()
      self.si = si
      self.pc = self.si.content.propertyCollector
      self.lock = threading.Lock()

   def DoWork(self, fn, args, kwargs):
      """ Do work, and call Done when done """
      try:
         ret = fn(*args, **kwargs)
         return self.Done(ret)
      except:
         self.Done()
         raise

   def Done(self, ret=None):
      """
      Done work. If result is a task, issue WaitForTasks if it is the last
      task or collect time expired
      """
      tasks = None

      self.lock.acquire()
      try:
         self.numTasks -= 1
         if ret and isinstance(ret, Vim.Task):
            # Accumulate tasks
            self.tasks.append(ret)

         currTime = time.time()
         if self.numTasks == 0 or (currTime - self.startTime) > self.collectTimeS:
            # Restart timer
            self.startTime = currTime

            tasks = self.tasks
            self.tasks = []
      finally:
         self.lock.release()

      if tasks:
         # Do wait tasks
         WaitForTasks(tasks, raiseOnError=False, si=self.si, pc=self.pc)

      return ret


def DoWorks(works):
   """ Do works, either in parallel or in series """
   # Wrap works in auto wait tasks
   collectTimeS = 6*60
   autoWaitTasks = AutoWaitTasks(numTasks=len(works), collectTimeS=collectTimeS)
   realWorks = [lambda fn=fn, args=args, kwargs=kwargs:
                                       autoWaitTasks.DoWork(fn, args, kwargs)
                for fn, args, kwargs in ThreadPool.NormalizeWorks(works)]

   # Dispatch works
   global threadPool
   if threadPool:
      workResults = threadPool.QueueWorksAndWait(realWorks)
      results = [task for status, task in workResults if status]
   else:
      results = [fn(*args, **kwargs) for fn, args, kwargs
                                      in ThreadPool.NormalizeWorks(realWorks)]
   return results


def GetTaskInfo(task):
   """ Get task.info, eat task missing exception """
   try:
      return task.info
   except Vmodl.Fault.ManagedObjectNotFound:
      pass


def GenericTasks(msg, works, preCreatedTasks = None):
   """ Generic Tasks """
   tasks = []
   try:
      Log("%s generating tasks..." % (msg))
      startTime = time.time()
      if preCreatedTasks:
         WaitForTasks(preCreatedTasks, raiseOnError=False)
         tasks = preCreatedTasks
      else:
         tasks = DoWorks(works)
      endTime = time.time()
      elapsed = endTime - startTime

      # Wait for each task to complete
      realTask = True
      numTasks = len(tasks)
      Log("Done generating %d tasks for %s." % (numTasks, msg))

      if numTasks > 0:
         Log("%s %d tasks took %f secs, average %f secs" % (msg, numTasks,
                                                            elapsed,
                                                            elapsed / numTasks))
         if not isinstance(tasks[0], Vim.Task):
            realTask = False

      # Get task info
      if realTask:
         allTaskInfos = DoWorks([(GetTaskInfo, (task,)) for task in tasks])
         taskInfos = [info for info in allTaskInfos if info]

      if numTasks > 0:
         if realTask and options.verbose_stats:
            LogTasksStat(msg, taskInfos)

      # Return task result
      if realTask:
         return [taskInfo.result for taskInfo in taskInfos \
                              if taskInfo.state == Vim.TaskInfo.State.success]
      else:
         return tasks
   except Exception as err:
      Log("%s failed: %s" % (msg, err))
      import traceback
      exc_type, exc_value, exc_traceback = sys.exc_info()
      stackTrace = " ".join(traceback.format_exception(
                            exc_type, exc_value, exc_traceback))
      Log(stackTrace)
      sys.exc_clear()
   return tasks


def CreatePoolsArgs(args):
   """ Parse create pools parameters """
   numChildren = 0
   numGeneration = 1
   for arg in args:
      if not arg:
         continue
      key, value = arg.strip().split("=", 1)
      if key == "child":
         # Num of children of each generation
         numChildren = max(0, int(value))
      elif key == "gen" or key == "generation":
         # Num of generations of this rp
         # min level is 1
         numGeneration = max(1, int(value))

   return numGeneration, numChildren


def CreatePool(rp, name, spec, numGeneration, numChildren):
   """ Create resource pools, and child if needed """
   global options
   if options.verbose_stats:
      Log("Create rp %s in %s" % (name, str(rp)))
   newRp = rp.CreateResourcePool(name, spec)
   if numGeneration > 0:
      ret = CreateChildPools(newRp, name, spec, numGeneration - 1, numChildren)
   else:
      ret = (newRp, None)
   return ret


def CreateChildPools(rp, namePrefix, spec, numGeneration, numChildren):
   """ Create child resource pools """
   works = [(CreatePool, (rp, namePrefix + "_" + str(child), spec,
               numGeneration, numChildren)) for child in range(0, numChildren)]
   childRps = DoWorksNoWait(works)
   return (rp, childRps)


def CreateResourcePools(rp, namePrefix, poolRange, numGeneration, numChildren):
   """ Create resource pools """
   spec = Vim.ResourceConfigSpec()
   cpuAllocation = Vim.ResourceAllocationInfo()
   cpuAllocation.shares = Vim.SharesInfo(level="normal", shares=1000)
   spec.cpuAllocation = cpuAllocation
   memAllocation = Vim.ResourceAllocationInfo()
   memAllocation.shares = Vim.SharesInfo(level="normal", shares=1000)
   spec.memoryAllocation = memAllocation

   # Create children pool
   works = [(CreatePool, (rp, namePrefix + "_" + str(child), spec,
               numGeneration, numChildren)) for child in poolRange]
   childRps = DoWorksNoWait(works)
   rps = [childRp for childRp in JoinWorks((rp, childRps)) if childRp != rp]
   return rps


def UpdatePoolConfig(pool, spec):
   spec.entity = pool
   pool.UpdateConfig(None, spec)


def UpdateVmResourceConfig(parent, vms, spec):
   specList = []
   for vm in vms:
      currSpec = copy.copy(spec)
      currSpec.entity = vm
      specList.append(currSpec)
   retVal = parent.UpdateChildResourceConfiguration(specList)
   return retVal


def DestroyPools(resourcePool, namePrefix):
   """ Delete resource pools """
   # Found pools to destroy
   Log("Finding pools to destroy...")
   pools = []
   for pool in resourcePool.resourcePool:
      if pool.name.startswith(namePrefix):
         pools.append(pool)
   Log("Found %s pools to destroy" % len(pools))

   works = [(pool.Destroy,) for pool in pools]
   GenericTasks("Delete resource pool", works)


def UpdatePoolsArgs(args):
   """ Parse update pools parameters """
   cpuShares = 1000
   memShares = 1000
   for arg in args:
      if not arg:
         continue
      key, value = arg.strip().split("=", 1)
      if key == "cpu":
         # Cpu shares
         cpuShares = int(value)
      elif key == "mem" or key == "memory":
         memShares = int(value)

   return cpuShares, memShares


def UpdatePools(resourcePool, pools, cpuShares, memShares):
   """ Update resource pools """
   spec = Vim.ResourceConfigSpec()

   cpuAllocation = Vim.ResourceAllocationInfo()
   cpuAllocation.shares = Vim.SharesInfo(level="custom", shares=cpuShares)
   spec.cpuAllocation = cpuAllocation
   memAllocation = Vim.ResourceAllocationInfo()
   memAllocation.shares = Vim.SharesInfo(level="custom", shares=memShares)
   spec.memoryAllocation = memAllocation

   works = [(UpdatePoolConfig, (pool, spec)) for pool in pools]
   GenericTasks("Update resource pool", works)


def TestResourcePools(resourcePool, namePrefix, poolRange,
                      cleanup=True, ops="", profile=""):
   """ Test resource pools related stuff """
   global options

   Log("Resource pools test")

   if profile == None:
      profileOps = []
   else:
      profileOps = profile.lower().split(":")

   # Default operations
   if not ops:
      ops = "create:update:destroy"

   rps = []

   try:
      for op in ops.split(":"):
         opsAndArgs = op.split()
         if len(opsAndArgs) > 1:
            args = opsAndArgs[1].split(";")
         else:
            args = []
         op = opsAndArgs[0]

         ExecuteOperationCmd(options.preOperationCmd, op)
         StartProfile(op, profileOps)

         if op == "destroy":
            works = [(pool.Destroy,) for pool in rps]
            GenericTasks("Delete resource pool", works)
            rps = []
         elif op == "create":
            numGeneration, numChildren = CreatePoolsArgs(args)
            work = [(CreateResourcePools, (resourcePool, namePrefix, poolRange,
                                           numGeneration, numChildren))]
            rps = GenericTasks("Create resource pool", work)[0]
            Log("Created %d resource pools with %d generations (each with %d " \
                "children). A total of %d resource pools" % \
                     (len(poolRange), numGeneration, numChildren, len(rps)))
         elif op == "update":
            # Reconfigure pools
            cpuShares, memShares = UpdatePoolsArgs(args)
            UpdatePools(resourcePool, rps, cpuShares, memShares)
         else:
            Log("Unknown pools operation: %s" % (op))

         EndProfile(op.split()[0], profileOps)
         ExecuteOperationCmd(options.postOperationCmd, op.split()[0])
   finally:
      if cleanup:
         # Cleanup
         DestroyPools(resourcePool, namePrefix)


def GetTestDatastores(hostSystem, dsNames):
   """
   Verify datastore names, or pick a test datastore if names not specified
   """
   result = []
   maxFreeSpace = -1
   datastores = hostSystem.datastore
   for datastore in datastores:
      summary = datastore.summary
      if not dsNames: # Pick the biggest VMFS datastores
         if summary.type.lower() == "vmfs" and summary.accessible:
            if maxFreeSpace < 0:
               maxFreeSpace = summary.freeSpace
               result.append((datastore, summary.name))
            else:
               if summary.freeSpace > maxFreeSpace:
                  maxFreeSpace = summary.freeSpace
                  result[0] = (datastore, summary.name)
      elif summary.name in dsNames:
         # Make sure datastore name exists
         result.append((datastore, summary.name))
   if len(result) == 0:
      suffix = ""
      if dsNames:
         suffix = " with names %s" % dsNames
      Log("Found no datastore %s" % suffix)
   return result


def GetDatastore(dsInfos, numCreateVMs):
   """ Generator to get ds names """
   totalVMs = 0
   countedDS = []
   uncountedDS = []
   for dsName, numVMs in dsInfos:
      if numVMs > 0:
         totalVMs += numVMs
         countedDS.append((dsName, numVMs))
      else:
         uncountedDS.append(dsName)

   if totalVMs > numCreateVMs:
      Log("Warning! Creating %d VMs, less than %d VMs specified in ds "
          "parametersSome datastores will have less VMs than specified" %
                                                   (numCreateVMs, totalVMs))
   elif totalVMs < numCreateVMs and len(uncountedDS) == 0:
      Log("Error! Creating %d VMs, more than %d VMs specified in ds "
          "parameters" % (numCreateVMs, totalVMs))
      raise Exception()

   for dsName, numVM in countedDS:
      while numVM > 0:
         numVM -= 1
         yield dsName
   if uncountedDS:
      idx = 0
      while True:
         dsName = uncountedDS[idx]
         idx = (idx + 1) % len(uncountedDS)
         yield dsName

def GetParentDatacenter(object):
   """ Find the parent datacenter of the specified object """
   dc = object
   while dc and not isinstance(dc, Vim.Datacenter):
      dc = dc.parent
   return dc
# end GetParentDatacenter

def CreateVMConfig(vmFolder, resourcePool, hostSystem, namePrefix, vmRange, dsInfos, dvsName, dvsPgName):
   """ Generate config spec for creating VMs """
   # Create VM config
   Log("Getting datastores...")
   dsNames = [dsName for dsName, numVM in dsInfos]
   datastores = GetTestDatastores(hostSystem, dsNames)
   if len(datastores) <= 0:
      Log("No datastores found")
      return []
   else:
      Log("Creating VMs in datastores %s" % [dsName for ds, dsName in datastores])

   if not dsInfos:
      dsInfos = [(dsName, 0) for ds, dsName in datastores]
   else:
      dsNames = set()
      for ds, dsName in datastores:
         dsNames.add(dsName)
      dsInfos = [(dsName, numVM) for dsName, numVM in dsInfos if dsName in dsNames]

   datastoreIter = GetDatastore(dsInfos, len(vmRange))

   envBrowser = hostSystem.parent.GetEnvironmentBrowser()
   cfgOption = envBrowser.QueryConfigOption(None, None)
   cfgTarget = envBrowser.QueryConfigTarget(None)
   configs = []

   if dvsName and dvsPgName:
      nics = 0
      dvs = FindDvsByName(dvsName)
      dvsPg = FindDvsPortGroupByName(dvs, dvsPgName)
   else:
      nics = 2

   Log("Generating %d vm spec" % (len(vmRange)))
   for vmIdx in vmRange:
      vmName = namePrefix + str(vmIdx).zfill(4)
      dsName = datastoreIter.next()
      cfgSpec = CreateQuickDummySpec(vmName, memory=32,
                                     numScsiDisks=2, diskSizeInMB=1,
                                     nic=nics,
                                     envBrowser=envBrowser,
                                     cfgOption=cfgOption,
                                     cfgTarget=cfgTarget,
                                     datastoreName=dsName)
      configs.append(cfgSpec)

   # DVS backing
   if dvsName and dvsPgName:
      result = DoWorks([(vmconfig.AddDvPortBacking,
                        (cfgSpec, "", dvs.uuid),
                        {"portgroupKey":dvsPg.key}) for cfgSpec in configs])

   return configs
#end

def VapiCreateVMConfig(vmFolderId, resourcePoolId, hostSystem, namePrefix, vmRange, dsInfos, dvsName, dvsPgName):
   """ Generate config spec for creating VMs """
   # Create VM config
   Log("Getting datastores...")
   dsNames = [dsName for dsName, numVM in dsInfos]
   datastores = GetTestDatastores(hostSystem, dsNames)
   if len(datastores) <= 0:
      Log("No datastores found")
      return []
   else:
      Log("Create VMs in datastores %s" % [dsName for ds, dsName in datastores])

   if not dsInfos:
      dsInfos = [(dsName, 0) for ds, dsName in datastores]
   else:
      dsNames = set()
      for ds, dsName in datastores:
         dsNames.add(dsName)
      dsInfos = [(dsName, numVM) for dsName, numVM in dsInfos if dsName in dsNames]

   datastoreIter = GetDatastore(dsInfos, len(vmRange))

   configs = []

   Log("Generating %d vm spec" % (len(vmRange)))
   for vmIdx in vmRange:
      vmName = namePrefix + str(vmIdx).zfill(4)
      dsName = datastoreIter.next()
      ds = GetDatastoreRef(hostSystem, dsName)

      create_spec = VM.CreateSpec(name=vmName, guest_os=GuestOS.OTHER_LINUX)

      # Create placement spec
      placement_spec = VM.PlacementSpec(folder=vmFolderId,
                                        resource_pool=resourcePoolId,
                                        datastore=ds._moId)
      create_spec.placement = placement_spec
      create_spec.memory = Memory.UpdateSpec(size_mib=32)
      disk_create_spec1 = create_disk_create_spec(Disk.HostBusAdapterType.SCSI, 0, 0)
      disk_create_spec1.new_vmdk = Disk.VmdkCreateSpec(name='disk1', capacity=1024*1024)
      disk_create_spec2 = create_disk_create_spec(Disk.HostBusAdapterType.SCSI, 0, 1)
      disk_create_spec2.new_vmdk = Disk.VmdkCreateSpec(name='disk2', capacity=1024*1024)
      create_spec.disk = [disk_create_spec1, disk_create_spec2]

      if dvsPgName:
        dvs = FindDvsByName(dvsName)
        dvsPg = FindDvsPortGroupByName(dvs, dvsPgName)
        ethernet_create_spec = create_ethernet_create_spec(
                                backing=Ethernet.BackingSpec(
                                  type=Ethernet.BackingType.DISTRIBUTED_PORTGROUP,
                                  network=dvsPg._moId))
        create_spec.nics = [ethernet_create_spec]
      else:
        ethernet_create_spec1 = create_ethernet_create_spec(emulation_type=Ethernet.EmulationType.E1000,
                                                            cr=hostSystem)
        ethernet_create_spec2 = create_ethernet_create_spec(emulation_type=Ethernet.EmulationType.E1000,
                                                            cr=hostSystem)
        create_spec.nics = [ethernet_create_spec1, ethernet_create_spec2]

      configs.append(create_spec)

   return configs
#end

def CreateVMs(vmFolder, resourcePool, hostSystem, namePrefix, vmRange, dsInfos, dvs, dvsPortgroup):
   """ Create VMs """
   configs = CreateVMConfig(vmFolder, resourcePool, hostSystem, namePrefix, vmRange, dsInfos, dvs, dvsPortgroup)
   if len(configs) < 1:
      return []

   # Create VMs
   works = [(vmFolder.CreateVm,
                  (config, resourcePool, hostSystem)) for config in configs]
   return GenericTasks("Create VMs", works)


def VapiCreateVMs(vmFolderId, resourcePoolId, hostSystem, namePrefix, vmRange, dsInfos=[], dvs=None, dvsPortgroup=None):
   """ Create VMs """
   configs = VapiCreateVMConfig(vmFolderId, resourcePoolId, hostSystem,
                                namePrefix, vmRange, dsInfos, dvs, dvsPortgroup)
   if len(configs) < 1:
      return []

   # Create VMs
   global vm_svc
   works = [(vm_svc.create, (config,)) for config in configs]
   return DoWorksNoWait(works)


def CloneVMsArgs(op):
   op, opArgs = ParseOperation(op)
   srcVm = None
   linked = True
   for (argId, argVal) in opArgs:
      if argId == "srcvm":
         srcVm = argVal
      if argId == "linked":
         linked = int(argVal) != 0
   return (srcVm, linked)

def CloneVMs(vmFolder, resourcePool, hostSystem, namePrefix, vmRange, op):
   """ Create VM clones """
   dsInfos, dvs, dvsPortgroup = CreateVMsArgs(op[len("clone"):].split(";"))
   userSpecifiedSrcVm, linked = CloneVMsArgs(op)

   # myVM is the base VM for the clone operation. If a user does not specify the
   # the srcVm, we create a new one and destroy it after the clone operation is done.
   # Otherwise, we use the specified one.
   myVm = None

   if userSpecifiedSrcVm is not None:
      #Find and use the source vm
      Log("Clone: Finding source vm %s..." % userSpecifiedSrcVm)
      vms = GetObjectsFromContainer(vmFolder, Vim.VirtualMachine, name=userSpecifiedSrcVm)
      if len(vms) >= 1:
         Log("Clone: Found %d source vm with name %s" % \
                                                (len(vms), userSpecifiedSrcVm))
         myVm = vms[userSpecifiedSrcVm]
      else:
         Log("Clone: Cannot find source vm %s" % userSpecifiedSrcVm)
         return []
   else:
      #First create a source VM, snapshot it and then clone it required number of times
      configs = CreateVMConfig(vmFolder, resourcePool, hostSystem, namePrefix+"-src", [0], dsInfos, dvs, dvsPortgroup)

      Log("Clone: Creating source vm")
      task = vmFolder.CreateVm(configs[0], resourcePool, hostSystem)
      WaitForTask(task)
      myVm = task.info.result

   if linked:
      if myVm.snapshot is None:
         Log("Clone: Snapshotting source VM")
         task = myVm.CreateSnapshot('snap-0', "", False, False)
         WaitForTask(task)

      diskMoveType = Vim.Vm.RelocateSpec.DiskMoveOptions.createNewChildDiskBacking
      locspec = Vim.Vm.RelocateSpec(host=hostSystem,
                                    pool=resourcePool,
                                    diskMoveType=diskMoveType)
      cspec = Vim.Vm.CloneSpec(location=locspec,
                               powerOn=False,
                               template=False,
                               snapshot=myVm.snapshot.currentSnapshot)
   else:
      locspec = Vim.Vm.RelocateSpec(host=hostSystem, pool=resourcePool)
      cspec = Vim.Vm.CloneSpec(location=locspec,
                               powerOn=False,
                               template=False)

   # Create clones
   Log("Clone: Cloning vms...")
   works = [(myVm.Clone,
               (vmFolder, namePrefix+str(vmIdx).zfill(4), cspec)) for vmIdx in vmRange]
   clones = GenericTasks("Clone VMs", works)

   if userSpecifiedSrcVm is None:
      # Clean-up: Delete the created source VM
      Log("Clone: Deleting source vm")
      WaitForTask(myVm.Destroy())

   return clones


def ToInt(numStr):
   """
   Convert str to dec num. Unlike int(strNum), will stop if it see any non
   numeric char (int(strNum) will throw instead)
   """
   s = 0
   for c in numStr:
      if c.isalnum():
         s = s*10 + int(c)
      else:
         break
   return s


def IncludeVM(name, namePrefix, vmRange):
   """ Filter VM """
   prefixLen = len(namePrefix)
   return name.startswith(namePrefix) and ToInt(name[prefixLen:]) in vmRange


def FilterVMs(vms, namePrefix, vmRange):
   """ Filter vms base on prefix and range """
   Log("Filtering vms (prefix %s)..." % (namePrefix))
   # Equivalent to the follow, only running much faster
   #vms = [vm for vm in vms if vm.name.startswith(namePrefix)]
   names = DoWorks([lambda vm=vm: vm.name for vm in vms])
   result = [vm for name, vm in zip(names, vms)
                                 if IncludeVM(name, namePrefix, vmRange)]
   Log("%d vms (prefix %s)" % (len(result), namePrefix))
   return result


def FindVMs(vmContainer, namePrefix, vmRange):
   """ Find vms matching prefix """
   allVmsMap = GetObjectsFromContainer(vmContainer, Vim.VirtualMachine)
   vms = FilterVMsFromMap(allVmsMap, namePrefix, vmRange)
   return vms


def DestroyVM(vm):
   """ Destroy VM. Return destroy task """
   if vm.runtime.powerState == Vim.VirtualMachine.PowerState.poweredOn:
      WaitForTasks([vm.PowerOff()], raiseOnError=False)
   return vm.Destroy()


def DestroyVMs(vmFolder, namePrefix, vmRange):
   """ Destroy VMs """
   # Find vms to delete
   vms = FindVMs(vmFolder, namePrefix, vmRange)
   if len(vms) > 0:
      works = [(DestroyVM, (vm,)) for vm in vms]
      GenericTasks("Destroy VMs", works)


def VapiDestroyVM(vm_id):
   """ Destroy VM"""
   global vm_svc
   global power_svc
   Log("Destroying VM: %s" % vm_id)
   if power_svc.get(vm_id).state == Power.State.POWERED_ON:
       power_svc.stop()
   vm_svc.delete(vm_id)

def VapiDestroyVMs(vmFolderId, namePrefix, vmRange):
   """ Destroy VMs. Returns destroy task """
   # Find vms to delete
   global vm_svc
   filter_spec = VM.FilterSpec(folders=set([vmFolderId]))
   all_vms = [summary.vm for summary in vm_svc.list(filter_spec)]
   Log("Filtering VMs (prefix '%s' ; vmRange '%s')... " % (namePrefix, vmRange))
   vm_ids = [vm_id for (vm_id, vm_name) in all_vms if IncludeVM(vm_name, namePrefix, vmRange)]
   Log("Found VMs: %s"%(str(vm_ids)))
   if len(vm_ids) > 0:
      works = [(VapiDestroyVM, (vm,)) for vm in vm_ids]
      return DoWorksNoWait(works)
   return []


def FindFiles(datastore, pattern):
   """ Find files in datastore with specified pattern """
   browser = datastore.browser
   searchSpec = Vim.Host.DatastoreBrowser.SearchSpec()
   searchSpec.matchPattern = pattern
   task = browser.SearchSubFolders("[%s] /" % datastore.summary.name,
                                              searchSpec)
   WaitForTasks([task])
   paths = []
   for result in task.info.result:
      for filename in result.file:
         paths.append(result.folderPath + "/" + filename.path)
   return paths


def CreateVMsArgs(args):
   """ Parse Create VM parameters """
   dsInfos = []
   dvs = ""
   dvsPortgroup = ""
   for arg in args:
      if not arg:
         continue
      key, value = arg.strip().split("=", 1)
      if key == "ds":
         values = value.split("#")
         if len(values) > 1:
            numVMs = max(int(values[1]), 0)
         else:
            numVMs = 0
         dsInfos.append((values[0], numVMs))
      elif key == "dvsname":
         dvs = value
      elif key == "dvspgname":
         dvsPortgroup = value

   if (not dvs) or (not dvsPortgroup):
      dvs = ""
      dvsPortgroup = ""
   return (dsInfos, dvs, dvsPortgroup)


def RegisterVMsArgs(args):
   """ Parse Register VM parameters """
   dsNames = []
   for arg in args:
      if not arg:
         continue
      key, value = arg.strip().split("=", 1)
      if key == "ds":
         dsNames.append(value)
   return dsNames


def ReconfigureVMsArgs(args):
   """ Parse Register VM parameters """
   dsName = None
   for arg in args:
      key, value = arg.strip().split("=", 1)
      if key == "ds":
         dsName = value
   return dsName


def UpdateVMsArgs(args):
   """ Parse Update VM parameters """
   batchSize = 1
   newVal = 5000
   for arg in args:
      if not arg:
         continue
      key, value = arg.strip().split("=", 1)
      if key == "batchSize":
         batchSize = int(value)
      if key == "newVal":
         newVal = int(value)
   return batchSize, newVal


def EditVMs(op, vms, vmFolder):
   """ Modifies the configuration of the  """
   op, opArgs = ParseOperation(op)
   targetNetwork = None
   dc = GetParentDatacenter(vmFolder)
   works = []
   for (argId, argVal) in opArgs:
      if argId == "network":
         # Connect all nics of the VM to the specified network
         for network in dc.network:
            if network.name == argVal:
               targetNetwork = network
               break
         if not network:
            Log("Warning! Network %s not found in datacenter %s" % (argVal, dc.name))
            continue
         if isinstance(network, Vim.Dvs.DistributedVirtualPortgroup):
            # The nic backing will be the DVS
            backing = Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
            backing.port = Vim.Dvs.PortConnection()
            backing.port.switchUuid = network.config.distributedVirtualSwitch.uuid
            backing.port.portgroupKey = network.key
         else:
            backing = Vim.Vm.Device.VirtualEthernetCard.NetworkBackingInfo()
            backing.deviceName = argVal
         for vm in vms:
            configSpec = Vim.Vm.ConfigSpec()
            for device in vm.config.hardware.device:
               if isinstance(device, Vim.Vm.Device.VirtualEthernetCard):
                  deviceChange = Vim.Vm.Device.VirtualDeviceSpec()
                  deviceChange.device = device
                  deviceChange.device.backing = backing
                  deviceChange.operation = "edit"
                  configSpec.deviceChange.append(deviceChange)
            works.append((vm.Reconfigure, (configSpec,)))
      elif argId == "nics":
         configSpec = Vim.Vm.ConfigSpec()
         # Add nics to the VMs
         for i in range(int(argVal)):
            vmconfig.AddNic(configSpec)
         works = [(vm.Reconfigure, (configSpec,)) for vm in vms]
   GenericTasks("Edit VMs", works)
# end EditVMs

def ReserveVmCpu(op, vms):
   op, opArgs = ParseOperation(op)
   ONE_MHZ = 1
   reservation = ONE_MHZ # By default, we use 1 MHz
   for (argId, argVal) in opArgs:
      if argId == "reservation":
         reservation = int(argVal)
   configSpec = Vim.Vm.ConfigSpec()
   cpuAlloc = Vim.ResourceAllocationInfo()
   cpuAlloc.SetReservation(reservation)
   configSpec.SetCpuAllocation(cpuAlloc)
   works = [(vm.Reconfigure, (configSpec,)) for vm in vms]
   GenericTasks("VM reserve CPU", works)


def AddVmDisk(op, hostSystem, vms):
   op, opArgs = ParseOperation(op)
   configSpec = Vim.Vm.ConfigSpec()
   dsName = None
   for (argId, argVal) in opArgs:
      if argId == "ds":
         dsName = argVal
   if dsName is None:
      datastores = GetTestDatastores(hostSystem, None)
      if datastores:
         dsName = datastores[0][1]
   Log("VM add disk: Adding disk on datastore %s" % dsName)

   envBrowser = hostSystem.parent.environmentBrowser
   cfgOption = envBrowser.QueryConfigOption(None, None)
   cfgTarget = envBrowser.QueryConfigTarget(None)
   vmconfig.AddScsiCtlr(configSpec, cfgOption=cfgOption, cfgTarget=cfgTarget)
   vmconfig.AddScsiDisk(configSpec, cfgOption=cfgOption, cfgTarget=cfgTarget, datastorename=dsName)
   # Reconfigure
   works = [(vm.Reconfigure, (configSpec,)) for vm in vms]
   GenericTasks("VM add disk", works)


def ChangeVmNetwork(op, vms, vmFolder):
   op, opArgs = ParseOperation(op)
   targetNetworkMo = None
   targetNetworkName = None
   dc = GetParentDatacenter(vmFolder)
   works = []
   for (argId, argVal) in opArgs:
      if argId == "network":
         for network in dc.network:
            if network.name == argVal:
               targetNetworkMo = network
               targetNetworkName = argVal
               break
         if targetNetworkMo is None:
            Log("Warning! Network %s not found in datacenter %s" % (argVal, dc.name))
            return

   if targetNetworkMo is None:
      return

   # Connect all nics of the VM to the specified network
   if isinstance(targetNetworkMo, Vim.Dvs.DistributedVirtualPortgroup):
      # The nic backing will be the DVS
      backing = Vim.Vm.Device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
      backing.port = Vim.Dvs.PortConnection()
      backing.port.switchUuid = targetNetworkMo.config.distributedVirtualSwitch.uuid
      backing.port.portgroupKey = targetNetworkMo.key
   else:
      backing = Vim.Vm.Device.VirtualEthernetCard.NetworkBackingInfo()
      backing.deviceName = targetNetworkName
   for vm in vms:
      configSpec = Vim.Vm.ConfigSpec()
      for device in vm.config.hardware.device:
         if isinstance(device, Vim.Vm.Device.VirtualEthernetCard):
            deviceChange = Vim.Vm.Device.VirtualDeviceSpec()
            deviceChange.device = device
            deviceChange.device.backing = backing
            deviceChange.operation = "edit"
            configSpec.deviceChange.append(deviceChange)
      works.append((vm.Reconfigure, (configSpec,)))
   GenericTasks("VM change network", works)


def RunLocalCommand(cmdLine):
   """
   Executes a local shell command
   """
   p = subprocess.Popen(cmdLine, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
   outdata, errdata = p.communicate()
   if errdata:
      Log("Error output from local/remote command (%s):\n%s" % (cmdLine,errdata))
   return outdata


def RunRemoteCommand(cmd):
   """
   Assumes you've got password less login already setup.
   """
   return RunLocalCommand("ssh %s@%s 'sh -lc \"%s\"'" % (options.user, options.host, cmd))


def ExecuteOperationCmd(cmdTemplate, operation):
   """
   Replaces the operation name in the command template and executes the resulting command
   """

   if not cmdTemplate:
      return
   import re
   matcher = re.compile(r"\{opName\}")
   cmdProcessed = matcher.sub(operation, cmdTemplate)
   RunLocalCommand(cmdProcessed)


def FindHostByName(name):
   """ Finds a host specified by its name """
   global si
   idx = si.content.searchIndex
   host = idx.FindByIp(None, name, False) or idx.FindByDnsName(None, name, False)

   if not host:
      from socket import gethostbyaddr, herror
      try:
         hostName = gethostbyaddr(name)[0]
         host = idx.FindByDnsName(None, hostName, False)
      except herror as err:
         Log("Cannot find host %s" % name)
         host = None

   return host
# end

def StartProfile(currentOp, profileList):
   """
   logs into esx server and starts up the userworld profiler
   """

   if currentOp not in profileList:
      return
   blocking =""
   if options.profileBlockedTime:
      blocking = "-b"
   Log("Gathering %s profile data for %s" % (blocking, currentOp))
   RunRemoteCommand("%s/support/scripts/uw-perf/startVmkStats %s -p %s" \
                    % (GetBoraPath(), blocking, options.agentToProfile))


def EndProfile(currentOp, profileList):
   """
   logs into esx server and dumps profile data
   """
   if currentOp not in profileList:
      return
   opStr = currentOp and "-o " + currentOp or ""
   buildTypeStr = GetBuildType() and "-b " + GetBuildType() or ""
   imageLocationsStr = options.imageLocations and "-i " + options.imageLocations or ""
   Log("Dumping profile data for %s" % currentOp)
   RunRemoteCommand("%s/support/scripts/uw-perf/stopVmkStats -v %s %s -s %s %s %s" \
                    % (GetBoraPath(), GetBoraPath(), buildTypeStr, options.statsDir, imageLocationsStr, opStr))


def GuestOp(vm, op, opPreCond):
   """
   Do guest op
   """
   if vm.guest is not None:
      toolsStatus = vm.guest.toolsStatus
      if toolsStatus == "toolsOk" or toolsStatus == "toolsOld":
         try:
            if opPreCond(vm):
               op()
            else:
               Log("Guest op: %s pre cond failed" % (vm.name))
         except Exception as err:
            Log("Guest op: %s fault (%s)" % (vm.name, err))
      else:
         Log("Guest op: %s %s" % (vm.name, toolsStatus))
   else:
      Log("Guest op: %s guest not present" % vm.name)


def CreateVMsPCFilterSpec(vms, pathSet):
   """
   Create vms property collector filter spec
   """
   # First create the object specification as the task object.
   objspecs = [Vmodl.Query.PropertyCollector.ObjectSpec(obj=vm)
                                                            for vm in vms]

   # Next, create the property specification as the state.
   if len(pathSet) > 0:
      all = False
   else:
      all = True
   propspec = Vmodl.Query.PropertyCollector.PropertySpec(
                 type=Vim.VirtualMachine,
                 pathSet=pathSet,
                 all=all)

   # Create a filter spec with the specified object and property spec.
   filterSpec = Vmodl.Query.PropertyCollector.FilterSpec(propSet=[propspec],
                                                         objectSet=objspecs)
   return filterSpec


def WaitForEndCond(vms, filterSpec, fnEndCond):
   """
   Wait for guests to meet end condition
   """
   # Create the filter
   pc = si.content.propertyCollector
   filter = pc.CreateFilter(filterSpec, partialUpdates=True)

   waitOptions = Vmodl.Query.PropertyCollector.WaitOptions()
   waitOptions.maxWaitSeconds = 30

   try:
      version = None
      vmsCopy = copy.copy(vms)
      vmLensLast = len(vmsCopy)
      startTime = time.time()
      lastTime = startTime
      printVmListCnt = 0

      while len(vmsCopy) > 0:
         update = pc.WaitForUpdatesEx(version, waitOptions)
         if update:
            currTime = time.time()
            for filterSet in update.filterSet:
               for objSet in filterSet.objectSet:
                  vm = objSet.obj
                  #print(vm)
                  try:
                     vmIdx = vmsCopy.index(vm)
                  except:
                     continue

                  if fnEndCond(objSet.kind, objSet.changeSet):
                     vmsCopy.pop(vmIdx)
                     if options.verbose_stats:
                        Log(" %s done: %f secs" % (vm.name, currTime - startTime))

            version = update.version

         currTime = time.time()
         if (currTime - lastTime) > waitOptions.maxWaitSeconds:
            deltaStartTime = currTime - startTime
            numVms = len(vmsCopy)
            if vmLensLast > numVms:
               # Still making progress. Only print pending vms count
               Log("Pending %d vms after %f secs" % (numVms, deltaStartTime))
               printVmListCnt = 0
            elif numVms > 0:
               # Not making progress...
               if (printVmListCnt % 32) != 0:
                  Log("Pending %d vms after %f secs" % (numVms, deltaStartTime))
               else:
                  Log("Pending %d vms after %f secs: %s" % \
                      (numVms, deltaStartTime, [vm.name for vm in vmsCopy]))
               printVmListCnt += 1
            vmLensLast = numVms
            lastTime = currTime
   finally:
      if filter:
         filter.Destroy()

#
# Logic for testing concurrent workflow of VM operations on a single
# using VC
#
class VMWorkflow:
   """
      Class encapsulating a single workflow information
   """

   def __init__(self, namePrefix, id, opList):
      self.wfOps = opList
      self.nextOp = 0
      self.vmName = namePrefix + str(id).zfill(4)
      self.vmIdx = id
      self.vmPrefix = namePrefix
      self.vmMoId = None
      self.opQueueTime = []
      self.opStartTime = []
      self.opEndTime = []
      self.opTaskState = []
      self.opTaskIds = []
      self.isFinished = False

   def GetNextOp(self):
      opIdx = self.nextOp
      self.nextOp = self.nextOp + 1
      if (opIdx >= len(self.wfOps)):
         return None

      opName = self.wfOps[opIdx]
      return opName

   def FinishWorkflow(self):
      # Finish the workflow operations
      self.isFinished = True

#
# Queue a workflow task
#
def QueueWorkflowTask(wfTaskQueue, op, vmName):
   wfTaskQueue.put([vmName, op])

#
# Execute a workflow task
# Runs in the main thread and coordinates with the property collector
# thread to determine if all the workflows have finished execution
# Continuously checks the queue for new tasks and picks up the first
# available task. Submits the task to the threadpool's worker and
# updates the VMworkflow instance with the returned task key
#
def ExecuteWorkflowTask(wfItemDict, wfTaskQueue, wfFinishEvent, taskDict):
   Log("Executing workflow tasks")

   # Main loop
   while True:
      # finish event is set from the property collector thread
      if wfFinishEvent.is_set():
         break

      # pick up the next op from queue
      if wfTaskQueue.empty():
         continue

      opInfo = wfTaskQueue.get_nowait()
      wfItem = wfItemDict[opInfo[0]]

      if opInfo[1] != 'create' and wfItem.vmMoId == None:
         Log("MoId for VM '%s' None for op '%s'" % (wfItem.vmName, opInfo[1]))
         continue

      #
      # TODO: Need to move the operations into its own methods
      # that will return the task key
      #
      if opInfo[1] == 'create':
         vmFolder = invtOpts[0]
         vmConfig = vmConfigs[wfItem.vmIdx-1]
         vmRP = invtOpts[1]
         vmHS = invtOpts[2]
         works = [(vmFolder.CreateVM_Task, (vmConfig, vmRP, vmHS))]
      elif opInfo[1] == 'on':
         vmMor = Vim.VirtualMachine(wfItem.vmMoId, si._stub)
         works = [(vmMor.PowerOnVM_Task,)]
      elif opInfo[1] == 'off':
         vmMor = Vim.VirtualMachine(wfItem.vmMoId, si._stub)
         works = [(vmMor.PowerOffVM_Task,)]
      elif opInfo[1] == 'reset':
         vmMor = Vim.VirtualMachine(wfItem.vmMoId, si._stub)
         works = [(vmMor.ResetVM_Task,)]
      elif opInfo[1] == 'destroy':
         vmMor = Vim.VirtualMachine(wfItem.vmMoId, si._stub)
         works = [(vmMor.Destroy_Task,)]

      # Queue the work item to the thread pool
      global threadPool
      workResults = threadPool.QueueWorksAndWait(works)

      # Keep track of the task id in the workflow instance
      wfItem.opTaskIds.append(workResults)

      # Update the task dictionary that the property collector uses
      taskDict[workResults[0][1].info.key] = wfItem.vmName
      #---- END OF WHILE

   Log("Finished executing workflow tasks")


#
# Creating a list view for the task.info property
#
def CreatePCFilter(pcContent):
   pc = pcContent.GetPropertyCollector()
   viewMgr = pcContent.GetViewManager()

   # Create the object specification as the task-manager object
   listView = viewMgr.CreateListView([])
   viewobjspec = Vmodl.Query.PropertyCollector.ObjectSpec(
      obj = listView,
      selectSet = [
         Vmodl.Query.PropertyCollector.TraversalSpec(
            type = Vim.View.ListView,
            path = "view",
            name = "traverseTasks"
         )
      ]
   )

   # Create the property specification for the task information
   propspec = Vmodl.Query.PropertyCollector.PropertySpec(
      type = Vim.Task,
      pathSet = ["info"]
   )

   # Create the filter specification
   filterspec = Vmodl.Query.PropertyCollector.FilterSpec(
      objectSet = [viewobjspec],
      propSet = [propspec]
   )

   return (listView, pc.CreateFilter(filterspec, True))

#
# Check if all the workflows have finished
#
def HasPendingWfItems(finishDict, wfItemDict):
   if len(wfItemDict) > len(finishDict):
      return True
   else:
      return False

#
# Main Property Collector thread (runs in a separate thread). Checks if
# there are any updates and processes them. Also checks if all the
# workflows have finished and raises a finish event for the main thread
#
def PCWaitForUpdates(wfItemDict, wfTaskQueue, wfFinishEvent, taskDict):
   Log("Starting PC WaitForUpdates")
   taskSeenDict = {}
   finishDict = {}

   pcSi = Connect(host=options.vc, port=int(options.port),
                  user=options.vcuser, pwd=options.vcpwd)

   pcContent = pcSi.RetrieveContent()
   pc = pcContent.GetPropertyCollector()
   (listView, taskFilter) = CreatePCFilter(pcContent)
   lastVersion = None
   waitOptions = Vmodl.Query.PropertyCollector.WaitOptions(
      maxWaitSeconds = 1
   )

   while True:
      update = pc.WaitForUpdatesEx(lastVersion, waitOptions)
      try:
         if not update:
            if (HasPendingWfItems(finishDict, wfItemDict)):
               Log("Handling no updates")
               HandlePCUpdates(pcSi, None, wfItemDict, wfTaskQueue, taskDict, taskSeenDict, finishDict, listView)
               continue
            else:
               break

         if not update.GetTruncated():
            lastVersion = update.GetVersion()
         for fu in update.filterSet:
            HandlePCUpdates(pcSi, fu.objectSet, wfItemDict, wfTaskQueue, taskDict, taskSeenDict, finishDict, listView)

         if (not HasPendingWfItems(finishDict, wfItemDict)):
            break

      except (KeyboardInterrupt, SystemExit):
         break

   # Set event indicating that workflow operations are completed
   wfFinishEvent.set()
   taskFilter.Destroy()
   Log("Exiting PC WaitForUpdates")

#
# Handles Property Collector updates, adds tasks that were created
# to the ListView for further monitoring and removes tasks that have
# finished from the list view
#
def HandlePCUpdates(pcSi, objUpdates, wfItemDict, wfTaskQueue, taskDict, taskSeenDict, finishDict, listView):
   viewAddList = []
   viewRemoveList = []

   #
   # New tasks are added to taskSeenDict. For tasks getting modify
   # update, changes are recorded
   #
   if objUpdates:
      for o in objUpdates:
         # Handle enter updates
         # For the new tasks created, keep track in taskseen dict
         # for processing the changes later on in the thread
         if o.kind == 'enter':
            for change in o.changeSet:
               if change.op == 'assign' and change.name == 'info':
                  taskInfo = change.val
                  taskSeenDict[str(o.obj)] = [taskInfo.key]
                  taskSeenDict[str(o.obj)].append([o.changeSet])
         # Handle modify updates
         # Update the taskseen dict for existing tasks for processing
         # the changes later on in the thread
         if o.kind == 'modify':
            for change in o.changeSet:
               try:
                  taskSeenDict[str(o.obj)][1].append(o.changeSet)
               except KeyError as e:
                  Log("task not found for %s" % e)

   #
   # Updates the view with the new task entries
   # TODO: currently we are updating listview with all the tasks
   # (even the ones that are already monitored by listview. We can
   # optimize to just add new tasks
   #
   for taskKey in taskDict.keys():
      wfTask = Vim.Task(taskKey, pcSi._stub)
      viewAddList.append(wfTask)

   try:
      listView.Modify(viewAddList, [])
   except Exception as e:
      Log("Exception while modifying viewAddList %s" % e)

   #
   # Identify which tasks have finished. Relies on the taskDict updated
   # updated by ExecuteWorkflowTask to identify the vm name for which the
   # corresponding task was created
   #
   taskSeenKeys = taskSeenDict.keys()
   for key in taskSeenKeys:
      taskKey = taskSeenDict[key][0]
      taskChangeSets = taskSeenDict[key][1]

      if taskKey not in taskDict:
         continue

      taskFinishFlag = False
      vmName = taskDict[taskKey]
      wfItem = wfItemDict[vmName]
      for changeSet in taskChangeSets:
         for change in changeSet:

            #
            # For cases where task started and completed in same update
            #
            if change.op == 'assign' and change.name =='info':
               taskInfo = change.val
               wfItem.opQueueTime.append(taskInfo.queueTime)
               if taskInfo.state != 'queued':
                  wfItem.opStartTime.append(taskInfo.startTime)

               #
               # task has finished, track it so that we can remove it
               # from list view
               #
               if taskInfo.completeTime:
                  wfItem.opEndTime.append(taskInfo.completeTime)
                  # If it is create vm task, we get the moid from the result
                  # we need to update the workflow instance to contain this
                  # moid so that we can execute the next workflow operation
                  if wfItem.vmMoId == None:
                     if taskInfo.result:
                        wfItem.vmMoId = taskInfo.result._GetMoId()
                        Log("VmMoId is - %s, %s - enter" % (vmName,wfItem.vmMoId))

                  taskFinishFlag = True

            #
            # For cases where the task was in progress for quite a while
            # and it just completed
            #
            if change.op == 'assign':
               if change.name == 'info.startTime':
                  if wfItem.opStartTime.count(change.val) == 0:
                     wfItem.opStartTime.append(change.val)
               if change.name == 'info.completeTime':
                  if wfItem.opEndTime.count(change.val) == 0:
                     wfItem.opEndTime.append(change.val)
                  taskFinishFlag = True
               if change.name == 'info.state':
                  Log("Task state for VM %s is %s" % (vmName,change.val))
               if change.name == 'info.result':
                  # If it is create vm task, we get the moid from the result
                  # we need to update the workflow instance to contain this
                  # moid so that we can execute the next workflow operation
                  if wfItem.vmMoId == None:
                     wfItem.vmMoId = change.val._GetMoId()
                     Log("VmMoId is - %s, %s - modify" % (vmName,wfItem.vmMoId))

      #
      # For finished tasks, prepare the remove list to remove them from
      # ListView
      #
      taskSeenDict[key][1] = []
      wfItemDict[vmName] = wfItem
      if taskFinishFlag:
         Log("Task finished for %s %s" % (vmName, taskKey))
         taskDict.pop(taskKey)
         taskSeenDict.pop(key)
         wfTask = Vim.Task(taskKey, pcSi._stub)
         viewRemoveList.append(wfTask)
         nextOp = wfItem.GetNextOp()
         wfItemDict[vmName] = wfItem
         # Queue the next operation for the workflow
         if nextOp != None:
            QueueWorkflowTask(wfTaskQueue, nextOp, vmName)
         else:
            Log("Workflow finished for vmName %s" % vmName)
            finishDict[vmName] = "Finished"

   #
   # Remove finished tasks from the property collector updates
   #
   try:
      listView.Modify([], viewRemoveList)
   except Exception as e:
      Log("Exception while modifying viewRemoveList %s" % e)


#
# Calculate the stats for the workflows executed
#
def GetTimeStat(queue, start, complete):
   if start > queue:
      delta = start - queue
   else:
      delta = start - start
   wait = float(delta.seconds) + float(delta.microseconds)/1000000
   if complete > start:
      delta = complete - start
   else:
      delta = complete - complete
   process = float(delta.seconds) + float(delta.microseconds)/1000000
   total = wait + process

   return (wait, process, total)

def GetClientWaitTime(complete, nextQueue):
   delta = nextQueue - complete
   clientWait = float(delta.seconds) + float(delta.microseconds)/1000000
   return clientWait

def FixWorkflowTimeStats(opIdx, wfItem):
    from datetime import datetime
    currTime = datetime.now()
    if opIdx > len(wfItem.opQueueTime) - 1:
       wfItem.opQueueTime.append(currTime)
    if opIdx > len(wfItem.opStartTime) - 1:
       wfItem.opStartTime.append(currTime)
    if opIdx > len(wfItem.opEndTime) - 1:
       wfItem.opEndTime.append(currTime)

def LogWorkflowStats(wfItemDict):
   # Log the workflow stats

   Log("Logging workflow stats")
   wfStats = {}
   opStats = {}
   wfQueueTime = []
   wfTotalTime = []
   wfProcessTime = []
   wfClientWaitTime = []

   for wfItemKey in wfItemDict.keys():
      wfItem = wfItemDict[wfItemKey]
      wfStats[wfItem.vmName] = {'clientwait': [], 'queueoptime': [],
                                'processoptime': [], 'totaloptime': []}
      if len(opStats) == 0:
         for op in wfItem.wfOps:
            opStats[op] = {'queue': [], 'process': [], 'total': []}

      opRange = range(len(wfItem.wfOps))
      # Capture stats for each workflow
      for opIdx in opRange:
         opName = wfItem.wfOps[opIdx]
         FixWorkflowTimeStats(opIdx, wfItem)
         (wait, process, total) = GetTimeStat(wfItem.opQueueTime[opIdx],
                                              wfItem.opStartTime[opIdx],
                                              wfItem.opEndTime[opIdx])
         Log("Workflow: Op:%s VM:%s %s %s %s ; %f %f %f" %
               (opName, wfItem.vmName, wfItem.opQueueTime[opIdx].time(),
               wfItem.opStartTime[opIdx].time(),
               wfItem.opEndTime[opIdx].time(),
               wait, process, total))
         opStats[opName]['queue'].append(wait)
         opStats[opName]['process'].append(process)
         opStats[opName]['total'].append(total)

         if opIdx < len(wfItem.wfOps)-1:
            clientWait = GetClientWaitTime(wfItem.opEndTime[opIdx], wfItem.opQueueTime[opIdx+1])
            wfStats[wfItem.vmName]['clientwait'].append(clientWait)
         wfStats[wfItem.vmName]['queueoptime'].append(wait)
         wfStats[wfItem.vmName]['processoptime'].append(process)
         wfStats[wfItem.vmName]['totaloptime'].append(total)

      # Aggregate individual op stats for the workflow
      wfStats[wfItem.vmName]['totaltime'] = sum(wfStats[wfItem.vmName]['totaloptime']) +\
                                            sum(wfStats[wfItem.vmName]['clientwait'])
      wfStats[wfItem.vmName]['totalqueuetime'] = sum(wfStats[wfItem.vmName]['queueoptime'])
      wfStats[wfItem.vmName]['totalprocesstime'] = sum(wfStats[wfItem.vmName]['processoptime'])
      wfStats[wfItem.vmName]['totalclientwaittime'] = sum(wfStats[wfItem.vmName]['clientwait'])
      Log("Workflow: VM:%s clientwait (%f secs)" % (wfItem.vmName, wfStats[wfItem.vmName]['totalclientwaittime']))
      Log("Workflow: VM:%s queue (%f secs)" % (wfItem.vmName, wfStats[wfItem.vmName]['totalqueuetime']))
      Log("Workflow: VM:%s process (%f secs)" % (wfItem.vmName, wfStats[wfItem.vmName]['totalprocesstime']))
      Log("Workflow: VM:%s total (%f secs)" % (wfItem.vmName, wfStats[wfItem.vmName]['totaltime']))
      wfQueueTime.append(wfStats[wfItem.vmName]['totalqueuetime'])
      wfProcessTime.append(wfStats[wfItem.vmName]['totalprocesstime'])
      wfTotalTime.append(wfStats[wfItem.vmName]['totaltime'])
      wfClientWaitTime.append(wfStats[wfItem.vmName]['totalclientwaittime'])

   for opName in opStats.keys():
      opStr = "Op:%s " % opName
      Log(opStr + "queue (min %f secs avg %f secs max %f secs sd %f secs)" % \
            MinAveMaxSd(opStats[opName]['queue']))
      Log(opStr + "process (min %f secs avg %f secs max %f secs sd %f secs)" % \
            MinAveMaxSd(opStats[opName]['process']))
      Log(opStr + "total (min %f secs avg %f secs max %f secs sd %f secs)" % \
            MinAveMaxSd(opStats[opName]['total']))

   Log("Workflow: clientwaittime (min %f secs avg %f secs max %f secs sd %f secs)" % \
         MinAveMaxSd(wfClientWaitTime))
   Log("Workflow: queue (min %f secs avg %f secs max %f secs sd %f secs)" % \
         MinAveMaxSd(wfQueueTime))
   Log("Workflow: process (min %f secs avg %f secs max %f secs sd %f secs)" % \
         MinAveMaxSd(wfProcessTime))
   Log("Workflow: total (min %f secs avg %f secs max %f secs sd %f secs)" % \
         MinAveMaxSd(wfTotalTime))

   Log("End of workflow stats")


#
# Concurrent VM Workflows test
#
def TestVMWorkflows(vmFolder, resourcePool, hostSystem,
                    namePrefix, wfRange, cleanup=True, tag="vc",
                    ops="", profile=""):
   """ Test VM workflows """
   global options

   Log("VM Workflow test")

   manager = Manager()
   wfItemDict = manager.dict()
   wfTaskQueue = manager.Queue()
   wfFinishEvent = manager.Event()
   taskDict = manager.dict()

   # -- TODO: implement profiling for workflows
   if profile == None:
      profileOps = []
   else:
      profileOps = profile.lower().split(":")

   wfOpList = []
   if tag == "vc":
      wfOpList = ["create", "on", "off", "destroy"]

   dsInfos = []
   dvs = ""
   dvsPortgroup = ""
   if ops:
      op = ops.split(':')[0]
      dsInfos, dvs, dvsPortgroup = CreateVMsArgs(op[len("create"):].split(";"))

   #
   # TODO: Add logic here to get the vm moids if the vms are already
   # created and the first operation of the workflow is not a create
   #
   configs = CreateVMConfig(vmFolder, resourcePool, hostSystem, namePrefix, wfRange, dsInfos, dvs, dvsPortgroup)
   vmConfigs.extend(configs)

   invtOpts.append(vmFolder)
   invtOpts.append(resourcePool)
   invtOpts.append(hostSystem)

   # Create a list of workflows
   wfList = []
   for idx in wfRange:
      wfItem = VMWorkflow(namePrefix, idx, wfOpList)
      wfList.append(wfItem)
      vmName = namePrefix + str(idx).zfill(4)
      wfItemDict[vmName] = wfItem

   # Create a Producer/Consumer Queue
   # Create a dict of wf VM Names and wfItem mapping
   # Populate the queue with op from wfItems
   for wfItem in wfList:
      nextOp = wfItem.GetNextOp()
      wfItemDict[wfItem.vmName] = wfItem
      QueueWorkflowTask(wfTaskQueue, nextOp, wfItem.vmName)

   # Start PC WaitForUpdates thread, listnening for task updates
   pcProcess = Process(target=PCWaitForUpdates, args=(wfItemDict, wfTaskQueue, wfFinishEvent,taskDict))
   pcProcess.name = "%s PC" % namePrefix
   pcProcess.start()

   # Bootstrap the process, by letting worker threads pick up the wfItem from the
   # queue and queue it
   ExecuteWorkflowTask(wfItemDict, wfTaskQueue, wfFinishEvent,taskDict)

   pcProcess.join()

   # Log workflow stats
   LogWorkflowStats(wfItemDict)

   Log("End VM Workflow test")
   ###---- DONE WorkFlowTest


def GenericWaitFor(msg, vms, filterSpec, fnEndCond):
   startTime = time.time()
   Log("Waiting %s for %d vms" % (msg, len(vms)))
   WaitForEndCond(vms, filterSpec, fnEndCond)
   endTime = time.time()
   elapsed = endTime - startTime
   Log("Done %s for %d vms took %f secs, average %f secs" %
                                   (msg, len(vms), elapsed, elapsed / len(vms)))


def WaitForGuestOn(vms):
   """
   Wait for guests to power on
   """
   def CheckToolsRunningStatus(kind, changeSet):
      """ Guest tools running status end condition cb """
      for change in changeSet:
         if change.name == "guest.toolsRunningStatus" and \
            change.val == "guestToolsRunning":
            return True
      else:
         return False

   # Other possible pathSet
   #
   # "runtime.powerState" -> vm power state, not guest
   # "guestHeartbeatStatus" -> "green" Too slow. Take very long time
   # "guest.guestState" -> "running". On too early
   # "guest.guestOperationsReady" -> Again, too early
   # "guest.interactiveGuestOperationsReady" -> Not set for esx
   # "guest.guestFamily" / "guest.guestId" -> Set after toolsRunningStatus
   #           executed script. Seems to be good. Won't work for unknown guest?
   filterSpec = CreateVMsPCFilterSpec(vms, ["guest.toolsRunningStatus",])

   msg = "guest power on"
   GenericWaitFor(msg, vms, filterSpec, CheckToolsRunningStatus)


def WaitForGuestState(vms, guestState):
   """
   Wait for specific guest state
   """
   # only support on for now
   if guestState == "on":
      # Wait for guest to start
      # Note: Must have guest tools installed
      WaitForGuestOn(vms)
   else:
      Log("Invalid guest state (%s)" % guestState)


def WaitForVmPowerState(vms, state):
   """
   Wait for specific vm state
   """

   # Validate state
   if state.lower() == "on":
      state = "poweredOn"
   elif state.lower() == "off":
      state = "poweredOff"
   elif state.lower() in ("suspended", "suspend"):
      state = "suspended"
   else:
      Log("Invalid vm state (%s)" % state)
      return

   def CheckVmPowerState(kind, changeSet):
      """ Vm power state end condition cb """
      for change in changeSet:
         if change.name == "runtime.powerState" and change.val == state:
            return True
      else:
         return False

   filterSpec = CreateVMsPCFilterSpec(vms, ["runtime.powerState",])

   msg = "power state -> %s" % state
   GenericWaitFor(msg, vms, filterSpec, CheckVmPowerState)


def TestVMs(vmFolder, resourcePool, hostSystem,
            namePrefix, vmRange, cleanup=True, ops="", profile="",
            checkmax=True):
   """ Test VMs related stuff """
   global options

   Log("VMs test")

   if profile == None:
      profileOps = []
   else:
      profileOps = profile.lower().split(":")

   # Default operations
   if not ops:
      ops = "clean:create:on:reset:snap:suspend:on:update-shares:update-OL:off:reconfig:unreg:reg"

   try:
      vms = []

      for op in ops.split(":"):
         ExecuteOperationCmd(options.preOperationCmd, op.split()[0])
         StartProfile(op.split()[0], profileOps)
         if op == "destroy":
            # Remove vms
            works = [(DestroyVM, (vm,)) for vm in vms]
            GenericTasks("Destroy VMs", works)
            vms = []
         elif op.startswith("clean"):
            # Remove old vms
            DestroyVMs(vmFolder, namePrefix, vmRange)
            vms = []
         elif op.startswith("create"):
            # Create VMs
            dsInfos, dvs, dvsPortgroup = CreateVMsArgs(op[len("create"):].split(";"))
            vms = CreateVMs(vmFolder, resourcePool, hostSystem,
                            namePrefix, vmRange, dsInfos, dvs, dvsPortgroup)
         elif op.startswith("clone"):
            # Clone VMs
            vms = CloneVMs(vmFolder, resourcePool, hostSystem,
                           namePrefix, vmRange, op)
         elif op.startswith("find"):
            # Find registered VM
            localHost = None
            opName, opArgs = ParseOperation(op)
            for (argId, argVal) in opArgs:
               if argId == "hostOnly" and int(argVal) != 0:
                  vmFolder = hostSystem   # Only find the VMs from the host under test
            # Find registered VM
            vms = FindVMs(vmFolder, namePrefix, vmRange)
         elif op.startswith("unreg"):
            # Unregister test
            Log("VMs unregister")
            works = [(vm.Unregister,) for vm in vms]
            GenericTasks("VM unregister", works)
            vms = []
         elif op.startswith("reg"):
            # Register test
            Log("VMs register")
            # Search all vmx files
            dsNames = None
            args = op.split(" ", 1)
            if len(args) > 1:
               dsNames = RegisterVMsArgs(args[1].split(";"))
            datastores = GetTestDatastores(hostSystem, dsNames)
            result = DoWorks([(FindFiles, (datastore, namePrefix + "*.vmx")) for
                                       datastore, datastoreName in datastores])
            #for datastore, datastoreName in datastores:
            #   paths.extend(FindFiles(datastore, namePrefix + "*.vmx"))
            paths = []
            for files in result:
               for name in files:
                  if IncludeVM(name[name.rfind("/") + 1: - len(".vmx")],
                               namePrefix, vmRange):
                     paths.append(name)
            Log("Found %d vm config files with prefix %s" % (len(paths),
                                                             namePrefix))
            asTemplate = False
            works = [(vmFolder.RegisterVm,
                        (path, None, asTemplate, resourcePool, hostSystem))
                                                            for path in paths]
            vms = GenericTasks("Register VMs", works)
         elif op.startswith("reconfig"):
            configSpec = Vim.Vm.ConfigSpec()
            # Increase memory size
            configSpec.memoryMB = 64
            # Add scsi disk
            dsName = None
            args = op.split(" ", 1)
            if len(args) > 1:
               dsName = ReconfigureVMsArgs(args[1].split(";"))
            else:
               datastores = GetTestDatastores(hostSystem, None)
               if datastores:
                  dsName = datastores[0][1]
            Log("Reconfig: Adding disk on datastore %s" % dsName)
            vmconfig.AddScsiCtlr(configSpec)
            vmconfig.AddScsiDisk(configSpec, datastorename=dsName)
            # Add NIC
            vmconfig.AddNic(configSpec)
            # Reconfigure
            works = [(vm.Reconfigure, (configSpec,)) for vm in vms]
            GenericTasks("VM reconfigure", works)
         elif op.startswith("edit"):
            # Edit the configuration of the virtual machines
            EditVMs(op, vms, vmFolder)
         elif op.startswith("reservecpu"):
            ReserveVmCpu(op, vms)
         elif op.startswith("addvmdisk"):
            AddVmDisk(op, hostSystem, vms)
         elif op.startswith("changenetwork"):
            ChangeVmNetwork(op, vms, vmFolder)
         elif op.startswith("update-shares"):

            batchSize, newVal = UpdateVMsArgs(op[len("update-shares"):].split(";"))

            spec = Vim.ResourceConfigSpec()
            cpuAllocation = Vim.ResourceAllocationInfo()
            cpuAllocation.shares = Vim.SharesInfo(level="custom", shares=newVal)
            spec.cpuAllocation = cpuAllocation
            memAllocation = Vim.ResourceAllocationInfo()
            memAllocation.shares = Vim.SharesInfo(level="custom", shares=newVal)
            spec.memoryAllocation = memAllocation
            works = [(UpdateVmResourceConfig, (resourcePool, vms[i:i+batchSize], spec))
                           for i in range(0, len(vms), batchSize) ]
            GenericTasks("VM share update", works)
         elif op.startswith("update-OL"):

            batchSize, newVal = UpdateVMsArgs(op[len("update-OL"):].split(";"))

            spec = Vim.ResourceConfigSpec()
            cpuAllocation = Vim.ResourceAllocationInfo()
            spec.cpuAllocation = cpuAllocation
            memAllocation = Vim.ResourceAllocationInfo()
            memAllocation.overheadLimit = newVal
            spec.memoryAllocation = memAllocation
            works = [(UpdateVmResourceConfig, (resourcePool, vms[i:i+batchSize], spec))
                           for i in range(0, len(vms), batchSize) ]
            GenericTasks("VM overheadLimit update", works)
         elif op == "on":
            # Sometimes, we don't want to check the # of supported VMs.
            # Use "checkmax" to opt out.
            if checkmax:
               result = RunRemoteCommand("vsish -e get /system/supportedVMs")
               supportedVms = result != None and int(result) or -1
               if supportedVms > 0:
                  Log("Host can support a maximum of %d powered-on VMs" % supportedVms);
                  if len(vms) > supportedVms:
                     raise Exception("Not enough resources to power on %d VMs on this host" % len(vms))
            works = [(vm.PowerOn,) for vm in vms]
            GenericTasks("VM power on", works)
         elif op == "groupon":
            dc = vmFolder.parent
            gpoWork = [(dc.PowerOnVm, (vms, ))]
            gpoTaskResult = GenericTasks("Group placement for Vms", gpoWork)[0]
            if gpoTaskResult.notAttempted:
               Log("%d out of %d VMs are not placed" % (len(gpoTaskResult.notAttempted), len(vms)))
            vmTasks = [x.GetTask() for x in gpoTaskResult.attempted]

            if len(vmTasks) == 0 : # No placement suceeded
               raise Exception("None of the %d vms could be placed" % len(vms))

            GenericTasks("VM power on", works = None, preCreatedTasks = vmTasks)

         elif op == "off":
            works = [(vm.PowerOff,) for vm in vms]
            GenericTasks("VM power off", works)
         elif op == "reset":
            works = [(vm.Reset,) for vm in vms]
            GenericTasks("VM reset", works)
         elif op == "suspend":
            Log("VMs power ops: on -> suspend")
            works = [(vm.Suspend,) for vm in vms]
            GenericTasks("VM suspend", works)
         elif op.startswith("snap"):
            # Take snapshot
            works = [(vm.CreateSnapshot, (),
                {"name":"snap", "memory":False, "quiesce":False}) for vm in vms]
            GenericTasks("VM create snapshot", works)
         elif op.startswith("rallsnap") or op.startswith("removeallsnap"):
            # Remove all snapshots
            works = [(vm.RemoveAllSnapshots,) for vm in vms]
            GenericTasks("VM remove all snapshots", works)
         elif op.startswith("rcurrsnap") or op.startswith("revertcurrentsnap"):
            # Revert to current snapshot
            works = [(vm.RevertToCurrentSnapshot,) for vm in vms]
            GenericTasks("VM revert to current snapshot", works)
         elif op.startswith("migrate"):
            # Migrate to another host (vMotion)
            op, opArgs = ParseOperation(op)
            targetHost = None
            for (argId, argVal) in opArgs:
               if argId == "host":
                  targetHost = FindHostByName(argVal)
            targetPool = (targetHost or hostSystem).parent.resourcePool
            works = [(vm.Migrate, (targetPool, None, "defaultPriority", None)) for vm in vms]
            GenericTasks("Migrate VM", works)
         elif op == "shutdownguest":
            works = [(GuestOp,
                      (vm,
                       vm.ShutdownGuest,
                       lambda vm: \
                         vm.guest.toolsRunningStatus != "guestToolsNotRunning" \
                         and (vm.guest.guestState == "running" or \
                              vm.guest.guestState == "standby")
                      )) for vm in vms]
            GenericTasks("VM guest shutdown", works)
         elif op == "rebootguest":
            works = [(GuestOp,
                      (vm,
                       vm.RebootGuest,
                       lambda vm: \
                         vm.guest.toolsRunningStatus != "guestToolsNotRunning" \
                         and (vm.guest.guestState == "running" or \
                              vm.guest.guestState == "standby" or \
                              vm.guest.guestState == "unknown")
                      )) for vm in vms]
            GenericTasks("VM guest reboot", works)
         elif op == "standbyguest":
            works = [(GuestOp,
                      (vm,
                       vm.StandbyGuest,
                       lambda vm: \
                         vm.guest.toolsRunningStatus != "guestToolsNotRunning" \
                         and vm.guest.guestState == "running"
                      )) for vm in vms]
            GenericTasks("VM guest standby", works)
         elif op.startswith("wait"):
            waitSec = -1
            vmState = None
            guestState = None
            op, opArgs = ParseOperation(op)
            for (argId, argVal) in opArgs:
               if argId == "time":
                  waitSec = int(argVal)
               elif argId == "power":
                  vmState = argVal
               elif argId == "guest":
                  guestState = argVal
            if waitSec != -1:
               Log("Sleep for %d seconds..." % waitSec)
               time.sleep(waitSec)
            elif vmState is not None:
               WaitForVmPowerState(vms, vmState)
            elif guestState is not None:
               # Note: Must have guest tools installed
               WaitForGuestState(vms, guestState)
            else:
               raw_input("Paused. Press Enter to continue...")
         elif op == "profileon":
            StartProfile("", "")
         elif op == "profileoff":
            EndProfile("", "")
         else:
            Log("Unknown vm operation: %s" % (op))
         EndProfile(op.split()[0], profileOps)
         ExecuteOperationCmd(options.postOperationCmd, op.split()[0])
   finally:
      if cleanup:
         # Cleanup
         DestroyVMs(vmFolder, namePrefix, vmRange)


def VapiTimedCreateVM(config):
   """ Create and calculate time taken """
   global vm_svc
   start = time.time()
   vm_id = vm_svc.create(config)
   return (vm_id, time.time() - start)


def VapiTimedPowerOnVM(vm_id):
   """ Power on VM and calculate time taken"""
   global power_svc
   start = time.time()
   power_svc.start(vm_id)
   return time.time() - start


def VapiTimedPowerOffVM(vm_id):
   """ Power on VM and calculate time taken"""
   global power_svc
   start = time.time()
   power_svc.stop(vm_id)
   return time.time() - start


def VapiTimedDestroyVM(vm_id):
   """ Destroy VM and calculate time taken"""
   global vm_svc
   global power_svc
   start = time.time()
   if power_svc.get(vm_id).state == Power.State.POWERED_ON:
       power_svc.stop(vm_id)
   vm_svc.delete(vm_id)
   return time.time() - start


def VapiTestVMs(vmFolderId, resourcePoolId, hostSystem,
            namePrefix, vmRange, cleanup=True, ops="", profile="",
            checkmax=True):
   """ Test VMs related stuff """
   global options

   Log("vAPI VMs test")

   if profile == None:
      profileOps = []
   else:
      profileOps = profile.lower().split(":")

   # Default operations
   if not ops:
      ops = "clean:create:on:off:destroy"

   try:
      vm_ids = []

      for op in ops.split(":"):
         ExecuteOperationCmd(options.preOperationCmd, op.split()[0])
         StartProfile(op.split()[0], profileOps)

         if op.startswith("find"):
            # Find registered VM
            filter_spec = VM.FilterSpec(folders=set([vmFolderId]))
            all_vms = [(summary.vm, summary.name) for summary in vm_svc.list(filter_spec)]
            Log("Filtering VMs (prefix '%s' ; vmRange '%s')... " % (namePrefix, vmRange))
            vm_ids = [vm_id for (vm_id, vm_name) in all_vms if IncludeVM(vm_name, namePrefix, vmRange)]
         elif op.startswith("create"):
            # Create VMs
            dsInfos = []
            dvs = ""
            dvsPortgroup = ""
            dsInfos, dvs, dvsPortgroup = CreateVMsArgs(op[len("create"):].split(";"))
            configs = VapiCreateVMConfig(vmFolderId, resourcePoolId, hostSystem,
                                namePrefix, vmRange, dsInfos, dvs, dvsPortgroup)
            works = [(VapiTimedCreateVM, (config,)) for config in configs]
            results = DoWorksNoWait(works)
            total = []
            for result in results:
               (vm_id, time_taken) = result.Join()
               vm_ids.append(vm_id)
               total.append(time_taken)
            Log("Created VMs: %s"%(str(vm_ids)))
            Log("Create VMs total (min %f secs avg %f secs max %f secs sd %f secs)" % \
                                                               MinAveMaxSd(total))
         elif op == "on":
            # Sometimes, we don't want to check the # of supported VMs.
            # Use "checkmax" to opt out.
            if checkmax:
               result = RunRemoteCommand("vsish -e get /system/supportedVMs")
               supportedVms = result != None and int(result) or -1
               if supportedVms > 0:
                  Log("Host can support a maximum of %d powered-on VMs" % supportedVms);
                  if len(vm_ids) > supportedVms:
                     raise Exception("Not enough resources to power on %d VMs on this host" % len(vm_ids))
            Log("Powering on VMs: %s"%(str(vm_ids)))
            works = [(VapiTimedPowerOnVM, (vm,)) for vm in vm_ids]
            results = DoWorksNoWait(works)
            total = [result.Join() for result in results]
            Log("VM power on total (min %f secs avg %f secs max %f secs sd %f secs)" % \
                                                               MinAveMaxSd(total))
         elif op == "off":
            Log("Powering off VMs: %s"%(str(vm_ids)))
            works = [(VapiTimedPowerOffVM, (vm,)) for vm in vm_ids]
            results = DoWorksNoWait(works)
            total = [result.Join() for result in results]
            Log("VM power off total (min %f secs avg %f secs max %f secs sd %f secs)" % \
                                                               MinAveMaxSd(total))
         elif op == "destroy":
            # Remove vms
            Log("Destroying VMs: %s"%(str(vm_ids)))
            works = [(VapiTimedDestroyVM, (vm,)) for vm in vm_ids]
            results = DoWorksNoWait(works)
            total = [result.Join() for result in results]
            Log("Destroy VMs total (min %f secs avg %f secs max %f secs sd %f secs)" % \
                                                               MinAveMaxSd(total))
            vm_ids = []

         elif op.startswith("clean"):
            # Remove old vms
            Log("Cleaning up VMs %s"%(str(vm_ids)))
            results = VapiDestroyVMs(vmFolderId, namePrefix, vmRange)
            for result in results:
              result.Join()
            vm_ids = []
         else:
            Log("Unknown vm operation: %s" % (op))
         EndProfile(op.split()[0], profileOps)
         ExecuteOperationCmd(options.postOperationCmd, op.split()[0])
   finally:
      if cleanup:
         # Cleanup
         Log("Finally, cleaning up VMs %s"%(str(vm_ids)))
         results = VapiDestroyVMs(vmFolderId, namePrefix, vmRange)
         for result in results:
          result.Join()
         vm_ids = []


def GetObjects(objType, name = None):
   """ Get list of inventory objects of a specified type and (optionally) name """
   global si
   objView = si.content.viewManager.CreateContainerView(si.content.rootFolder, [objType], True)
   objList = objView.GetView()
   retList = []
   if name != None:
      # XXX: Use PropertyCollector filters
      retList = filter(lambda x: x.name == name, objList)
   else:
      retList = objList
   objView.Destroy()
   return retList
# end GetObjects


def FilterVMsFromMap(vmsMap, namePrefix, vmRange):
   """ Filter vms from the map based on prefix and range """
   Log("Filtering vms (prefix %s)..." % (namePrefix))
   vmRefList = []
   for vmName, vmRef in vmsMap.iteritems():
      if IncludeVM(vmName, namePrefix, vmRange):
         vmRefList.append(vmRef)

   Log("%d vms (prefix %s)" % (len(vmRefList), namePrefix))
   return vmRefList


def GetObjectsFromContainer(objContainer, objType, name = None):
   """
   Get map of inventory objects of a specified type and (optionally) name
   starting with the root as objContainer. The map is keyed by the name and
   the value is the ref of the object
   """
   global si
   objView = si.content.viewManager.CreateContainerView(objContainer, [objType], True)
   propColl = si.content.GetPropertyCollector()

   # Set up traversal spec
   tSpec = Vmodl.Query.PropertyCollector.TraversalSpec()
   tSpec.name = "traverseEntities"
   tSpec.path = "view"
   tSpec.skip = False
   tSpec.type = Vim.view.ContainerView

   # Set up objSpec
   objSpec = Vmodl.Query.PropertyCollector.ObjectSpec()
   objSpec.obj = objView
   objSpec.skip = True
   objSpec.selectSet.append(tSpec)

   # Set up property spec
   propSpec = Vmodl.Query.PropertyCollector.PropertySpec()
   propSpec.type = objType
   propSpec.pathSet.append("name")

   # Set up filter spec
   filterSpec = Vmodl.Query.PropertyCollector.FilterSpec(propSet=[propSpec], objectSet=[objSpec])
   retrieveOpt = Vmodl.Query.PropertyCollector.RetrieveOptions()

   retrieveRes = propColl.RetrievePropertiesEx([filterSpec], retrieveOpt)
   if retrieveRes:
      ocList = retrieveRes.objects
      token = retrieveRes.token
   else:
      token = None
      ocList = []
   while token:
      retrieveRes = propColl.ContinueRetrievePropertiesEx(token)
      tempOcList = retrieveRes.objects
      token = retrieveRes.token
      ocList.extend(tempOcList)

   retMap = {}
   for objContent in ocList:
      objName = objContent.propSet[0].val
      objRef = objContent.obj
      if name != None and objName != name:
         continue
      retMap[objName] = objRef

   objView.Destroy()
   return retMap
# end GetObjectsFromContainer


def ParseOperation(op):
   """ Splits an operation into an operation id and a list of operation argument key-value pairs)  """
   # XXX TODO: Use this function everywhere to parse the operations strings
   (opId, sep, rest) = op.partition(' ')
   opParams = []

   if rest:
      for param in rest.split(';'):
         (paramKey, sep, paramValue) = param.partition('=')
         if sep:
            paramKey = paramKey.strip()
            paramValue = paramValue.strip()

         if paramKey and paramValue:
            opParams.append((paramKey, paramValue))
         else:
            Log("Warning! Invalid operation argument: " + param)

   return (opId, opParams)
# end ParseOperation


def TestDatacenter(rootFolder, dataCenter, ops="", profile=""):
   """ Test Datacenter related stuff """
   global options

   Log("Datacenter test")

   if profile == None:
      profileOps = []
   else:
      profileOps = profile.lower().split(":")

   # Default operations
   if not ops:
      ops = "add:remove"

   try:
      for opandArg in ops.split(":"):
         (op, opArgs) =  ParseOperation(opandArg)

         opargs = dict(opArgs)

         ExecuteOperationCmd(options.preOperationCmd, op)
         StartProfile(op, profileOps)
         if op == "add":
            Log("Add a datacenter")

            # datacenter name
            dname = opargs.get("name", "speedTest-DC-0")

            # create datacenter
            works = [(rootFolder.CreateDatacenter, (dname, ))]
            dataCenter = GenericTasks("Create datacenter", works)
         elif op == "remove":
            Log("Remove a datacenter")
            GenericTasks("Remove datacenter", [(dataCenter.Destroy, ())])
         else:
            Log("Unknown datacenter operation: %s" % (op))
         EndProfile(op, profileOps)
         ExecuteOperationCmd(options.postOperationCmd, op)
   finally:
      pass
#end


def TestCluster(hostFolder, clusterComputeResource, ops="", profile=""):
   """ Test Cluster related stuff """
   global options

   Log("Cluster test")

   if profile == None:
      profileOps = []
   else:
      profileOps = profile.lower().split(":")

   # Default operations
   if not ops:
      ops = "add:reconfig:remove"

   try:
      for opandArg in ops.split(":"):
         (op, opArgs) =  ParseOperation(opandArg)

         opargs = dict(opArgs)

         ExecuteOperationCmd(options.preOperationCmd, op)
         StartProfile(op, profileOps)
         if op == "add":
            # cluster config spec
            cspec = Vim.Cluster.ConfigSpecEx()

            # cluster name
            cname = opargs.get("name", "speedTest-cluster-0")

            works = [(hostFolder.CreateClusterEx, (cname, cspec))]
            clusterComputeResource = GenericTasks("Add Cluster", works)
         elif op == "reconfig":
            # cluster config sped
            cspec = Vim.Cluster.ConfigSpecEx()

            # HA
            if "ha" in opargs:
               cspec.dasConfig = Vim.cluster.DasConfigInfo (
                                    enabled = (opargs["ha"] == "1"),
                                    admissionControlEnabled = False
                                 )

            # DRS
            if "drs" in opargs:
               cspec.drsConfig = Vim.cluster.DrsConfigInfo (
                                    enabled = (opargs["drs"] == "1")
                                 )

            # Reconfig cluster
            works = [(clusterComputeResource.ReconfigureEx, (cspec, False))]
            GenericTasks("Reconfigure Cluster", works)
         elif op == "remove":
            GenericTasks("Remove cluster", [(clusterComputeResource.Destroy, ())])
         else:
            Log("Unknown cluster operation: %s" % (op))
         EndProfile(op, profileOps)
         ExecuteOperationCmd(options.postOperationCmd, op)
   finally:
      pass
#end


def AddHost(dataCenter, host, user, pwd, opargs):
   """ Add host """
   ssltp = None
   try:
      dataCenter.QueryConnectionInfo(host, 443, user, pwd)
   except Vim.Fault.SSLVerifyFault as svf:
      Log("AddHost: Auto-accepting host's SSL certificate")
      ssltp = svf.thumbprint

   cspec = Vim.Host.ConnectSpec(
      force = True,
      hostName = host,
      userName = user,
      password = pwd,
      sslThumbprint = ssltp)

   cluster = None
   if "cluster" in opargs :
      cObjs = GetObjects(Vim.ClusterComputeResource, opargs["cluster"])
      if len(cObjs) == 0:
         Log("AddHost: Cluster %s not found, adding to DC" % opargs["cluster"])
      else:
         cluster = cObjs[0]

   if cluster != None:
      works = [(cluster.AddHost, (cspec, True, None, None))]
   else:
      works = [(dataCenter.hostFolder.AddStandaloneHost, (cspec, None, True, None))]
   crs = GenericTasks("Add host", works)
   if cluster != None:
      return crs[0]
   else:
      return crs[0].host[0]
#end


def TestHost(hostFolder, hostSystem, ops="", profile=""):
   """ Test Host related stuff """
   global options

   Log("Host test")

   if profile == None:
      profileOps = []
   else:
      profileOps = profile.lower().split(":")

   # Default operations
   if not ops:
      ops = "add:enterMM:exitMM:disconnect:reconnect:remove"

   try:
      for opandArg in ops.split(":"):
         (op, opArgs) =  ParseOperation(opandArg)

         opargs = dict(opArgs)

         ExecuteOperationCmd(options.preOperationCmd, op)
         StartProfile(op, profileOps)

         if op == "add":
            if hostFolder is not None:
               dataCenter = hostFolder.parent
            else:
               dc = opargs.get("dc")
               objs = GetObjects(Vim.Datacenter, dc)
               if len(objs) == 0:
                  Log("AddHost: data center %s not found" % dc)
                  continue
               else:
                  dataCenter = objs[0]
            hostSystem = AddHost(dataCenter, options.host,
               options.user, options.pwd, opargs)
         elif op == "remove" or op == "removeHost":
            if isinstance(hostSystem.parent, Vim.ClusterComputeResource):
               t = hostSystem.Destroy
            else:
               t = hostSystem.parent.Destroy
            GenericTasks("Remove host", [(t, ())])
         elif op == "enterMM":
            if "to" in opargs:
               timeout = int(opargs["to"])
            else:
               timeout = 0
            GenericTasks("Enter maintenance mode", [ \
               (hostSystem.EnterMaintenanceMode, (timeout, True))])
         elif op == "exitMM":
            if "to" in opargs:
               timeout = int(opargs["to"])
            else:
               timeout =  0
            GenericTasks("Exit maintenance mode", [ \
               (hostSystem.ExitMaintenanceMode, (timeout,))])
         elif op == "disconnect":
            GenericTasks("Disconnect Host", [ \
               (hostSystem.Disconnect, ())])
         elif op == "reconnect":
            GenericTasks("Reconnect Host", [ \
               (hostSystem.Reconnect, ())])
         elif op == "shutdown":
            GenericTasks("Shutdown Host", [ \
               (hostSystem.Shutdown, (True,))])
         else:
            Log("Unknown host operation: %s" % (op))
         EndProfile(op, profileOps)
         ExecuteOperationCmd(options.postOperationCmd, op)
   finally:
      pass
#end


def AddNasDatastore(hostSystem, opargs):
   """ Add a NAS datastore """
   # host datastore system
   hostDatastoreSystem = hostSystem.configManager.datastoreSystem

   # Build the Nas spec
   hostNasVolSpec = Vim.Host.NasVolume.Specification()

   hostNasVolSpec.accessMode = opargs.get("mode", "readWrite")

   if not "name" in opargs:
      raise Exception("Need to specify name of the datastore")
   else:
      hostNasVolSpec.localPath = opargs["name"]

   if not "remoteHost" in opargs:
      raise Exception("Need to specify the remote host")
   else:
      hostNasVolSpec.remoteHost = opargs["remoteHost"]

   if not "remotePath" in opargs:
      raise Exception("Need to specify the remote path")
   else:
      hostNasVolSpec.remotePath = opargs["remotePath"]

   # create the NAS datastore
   works = [(hostDatastoreSystem.CreateNasDatastore, (hostNasVolSpec, ))]
   datastores = GenericTasks("Create a NAS datastore", works)
   return datastores
#end


def TestDatastore(hostFolder, hostSystem, ops="", profile=""):
   """ Test Datastore related stuff """
   global options

   Log("Datastore test")

   if profile == None:
      profileOps = []
   else:
      profileOps = profile.lower().split(":")

   # Default operations
   if not ops:
      ops = "add:remove"

   try:
      for opandArg in ops.split(":"):
         (op, opArgs) =  ParseOperation(opandArg)

         opargs = dict(opArgs)

         ExecuteOperationCmd(options.preOperationCmd, op)
         StartProfile(op, profileOps)
         if op == "add":
            datastores = AddNasDatastore(hostSystem, opargs)
         elif op == "remove":
            Log("Remove a datastore")
            if not "name" in opargs:
               raise Exception("Need to specify name of the datastore")

            # host datastore system
            hostDatastoreSystem = hostSystem.configManager.datastoreSystem
            datastores = hostDatastoreSystem.datastore
            foundAndRemoved = False
            dsName = opargs["name"]
            for ds in datastores:
               if ds.summary.name == dsName:
                  works = [(hostDatastoreSystem.RemoveDatastore, (ds, ))]
                  GenericTasks("Remove a datastore", works)
                  foundAndRemoved = True
                  break

            if not foundAndRemoved:
               Log("Could not find/remove the specified datastore")
         else:
            Log("Unknown datastore operation: %s" % (op))
         EndProfile(op, profileOps)
         ExecuteOperationCmd(options.postOperationCmd, op)
   finally:
      pass
#end


def CreateVSwitches(host, names, ports):
   """
   Creates one or more legacy virtual switches on the specified host
      host - the target host managed object
      names - a list of the names of the switches to add
      ports - the number of ports for the switches
   """
   netSys = host.GetConfigManager().GetNetworkSystem()
   spec = Vim.Host.VirtualSwitch.Specification()
   spec.numPorts = ports
   works = [(netSys.AddVirtualSwitch, (name, spec)) for name in names]
   return GenericTasks("Create Virtual Switch", works)
# end CreateVSwitch()

def RemoveVSwitches(host, names):
   """
   Removes one or more legacy virtual switches from the specified host
      host - the target host managed object
      names - a list of the names of the switches to remove
   """
   netSys = host.GetConfigManager().GetNetworkSystem()
   works = [(netSys.RemoveVirtualSwitch, (name,)) for name in names]
   return GenericTasks("Remove Virtual Switch", works)
# end RemoveVSwitches()

def UpdateVSwitches(host, names, ports):
   """
   Modifies the number of ports for one or more legacy virtual switches
      host - the managed object of the host on which the switches are
      names - a list of the names of the switches to modify
      ports - the new number of ports for the switches
   """
   netSys = host.GetConfigManager().GetNetworkSystem()
   spec = Vim.Host.VirtualSwitch.Specification()
   spec.numPorts = ports
   works = [(netSys.UpdateVirtualSwitch, (name, spec)) for name in names]
   return GenericTasks("Edit Virtual Switch", works)
# end UpdateVSwitches()

def TestVSwitch(hostSystem, ops="", profile=""):
   """ Test Virtual Switch related stuff """
   global options

   if profile == None:
      profileOps = []
   else:
      profileOps = profile.lower().split(":")

   # Default operations
   if not ops:
      ops = "create:edit:remove"

   createdSwitches = []

   try:
      for opandArg in ops.split(":"):
         (op, opArgs) =  ParseOperation(opandArg)

         ExecuteOperationCmd(options.preOperationCmd, op)
         StartProfile(op, profileOps)

         # Collect operation arguments
         host = None
         ports = None
         names = []

         for (argId, argVal) in opArgs:

            if argId == "host":
               if host:
                  Log("Warning! Duplicate host option for virtual switch %s operation." % (op))
               host = FindHostByName(argVal)
            elif argId == "name":
               names.append(argVal)
            elif argId == "ports" and op != "remove":
               if ports:
                  Log("Warning! Duplicate ports option for virtual switch %s operation." % (op))
               ports = int(argVal)
            else:
               Log("Warning! Unknown option for virtual switch %s operation: %s" % (op, argId))

         # Perform create operation
         if op == "create":
            CreateVSwitches(host or hostSystem, names or ["speedTest-vswitch"], ports or 120)
            createdSwitches.extend(names)

         # Perform remove operation
         elif op == "remove":
            RemoveVSwitches(host or hostSystem, names or createdSwitches)
            createdSwitches = []

         # Perform edit operation
         elif op == "edit":
            UpdateVSwitches(host or hostSystem, names or createdSwitches, ports or 248)
         else:
            Log("Unknown vSwitch operation: %s" % (op))

         EndProfile(op, profileOps)
         ExecuteOperationCmd(options.postOperationCmd, op)
   finally:
      pass
#end TestVSwitch

def CreateDVS(dataCenter, name):
   """ Creates a new dvs with the specified name on the specified datacenter """
   # Prepare the create spec
   spec = Vim.DistributedVirtualSwitch.CreateSpec()
   spec.configSpec = Vim.DistributedVirtualSwitch.ConfigSpec()
   spec.configSpec.name = name

   works = [(dataCenter.networkFolder.CreateDistributedVirtualSwitch, (spec,))]
   tasks = GenericTasks("Create Distributed Virtual Switch", works)

   if tasks:
      return tasks[0]
   else:
      return None
# end CreateDVS()

def RemoveDVS(dvs):
   """ Removes the specified DVS """
   # Prepare the create spec
   works = [(dvs.Destroy, ())]
   GenericTasks("Remove Distributed Virtual Switch", works)
# end RemoveDVS()

def AddDvsPortGroup(dvs, name, portType, portsCount):
   """ Adds a  port group to the specified DVS """
   portSpec = Vim.Dvs.DistributedVirtualPortgroup.ConfigSpec()
   portSpec.name = name

   if portType == "static":
      portSpec.type = "earlyBinding"
   elif portType == "dynamic":
      portSpec.type = "lateBinding"
   elif portType == "ephemeral":
      portSpec.type = "ephemeral"
   elif portType:
      Log("Warnig! Invalid DVS port type (%s) - port type ignored. Valid types are static, dynamic and ephemeral" % portType)

   if portsCount and portType != "ephemeral":
      portSpec.numPorts = portsCount

   works = [(dvs.AddPortgroups, ([portSpec],))]
   tasks = GenericTasks("Add Portgroup to Distributed Virtual Switch", works)

   if tasks:
      return tasks[0]
   else:
      return None
# end AddDvsPortGroup()

def RemoveDvsPortGroup(portGroup):
   """ Removes a port group """
   works = [(portGroup.Destroy, ())]
   tasks = GenericTasks("Remove Portgroup from a Distributed Virtual Switch", works)
# end RemoveDvsPortGroup()

def AddHostToDvs(dvs, host, pnicNames, scPortGroup, maxProxyPorts):
   """
   Adds a host to the dvs by reconfiguring the host. The reconfiguration is performed
   using a single call to the HostNetworkSystem.UpgradeNetworkConfig method to avoid losing
   connectivity to the host.
   """
   hostNetwork = host.configManager.networkSystem

   oldNetworkConfig = hostNetwork.networkConfig
   newNetworkConfig = Vim.Host.NetworkConfig()

   # If the host is already added to a DVS through some of the specified uplink, we ignore
   # this uplink
   pnicsToUse = pnicNames
   for proxySwitch in oldNetworkConfig.proxySwitch:
      for pnic in [pnicSpec.pnicDevice for pnicSpec in proxySwitch.spec.backing.pnicSpec]:
         while pnic in pnicsToUse:
            Log("Warning! Physical nic %s is already used by dvs %s - won't use it." % (pnic, proxySwitch.uuid) )
            pnicsToUse.remove(pnic)
   if not pnicsToUse:
      Log("Warning! No physical nics available to connect this host to the DVS - network problems possible.")

   # Create a proxy switch for the dvs
   newNetworkConfig.proxySwitch = []
   proxySwitch = Vim.Host.HostProxySwitch.Config()
   proxySwitch.changeOperation = "add"
   proxySwitch.uuid = dvs.uuid
   proxySwitch.spec = Vim.Host.HostProxySwitch.Specification()
   proxySwitch.spec.backing = Vim.Dvs.HostMember.PnicBacking()
   proxySwitch.spec.backing.pnicSpec = []
   for pnic in pnicsToUse:
      pnicSpec = Vim.Dvs.HostMember.PnicSpec()
      pnicSpec.pnicDevice = pnic
      proxySwitch.spec.backing.pnicSpec.append(pnicSpec)
      newNetworkConfig.proxySwitch.append(proxySwitch)

   # If there are virtual switches that use some of the physical nics that will be
   # allocated to the dvs, remove these nics from their backing
   disconnectedSwitches = []
   newNetworkConfig.vswitch = []
   if pnicsToUse:
      for vSwitch in oldNetworkConfig.vswitch:
         if isinstance(vSwitch.spec.bridge, Vim.Host.VirtualSwitch.SimpleBridge):
            if vSwitch.spec.bridge.nicDevice in pnicsToUse:
               vSwitch.changeOperation = "edit"
               vSwitch.spec.bridge = None
               newNetworkConfig.vswitch.append(vSwitch)
               disconnectedSwitches.append(vSwitch.name)
         elif isinstance(vSwitch.spec.bridge, Vim.Host.VirtualSwitch.BondBridge):
            nicDevice = []
            for pnic in vSwitch.spec.bridge.nicDevice:
               if not pnic in pnicsToUse:
                  nicDevice.append(pnic)
            if len(nicDevice) != len(vSwitch.spec.bridge.nicDevice):
               vSwitch.changeOperation = "edit"
               if nicDevice:
                  vSwitch.spec.bridge.nicDevice = nicDevice
               else:
                  vSwitch.spec.bridge = None
                  disconnectedSwitches.append(vSwitch.name)
               newNetworkConfig.vswitch.append(vSwitch)
         elif isinstance(vSwitch.spec.bridge, Vim.Host.VirtualSwitch.AutoBridge):
            exclNicDevice = []
            for pnic in pnicsToUse:
               if not pnic in vSwitch.spec.bridge.excludedNicDevice:
                  exclNicDevice.append(pnic)
            if exclNicDevice:
               vSwitch.changeOperation = "edit"
               vSwitch.spec.bridge.excludedNicDevice.extend(exclNicDevice)
               newNetworkConfig.vswitch.append(vSwitch)
               if len(vSwitch.spec.bridge.excludedNicDevice) == len(oldNetworkConfig.pnic):
                  disconnectedSwitches.append(vSwitch.name)

   # If some switches got disconnected, find the affected portgroups
   disconnectedPortgroups = []
   if disconnectedSwitches:
      for portgroup in oldNetworkConfig.portgroup:
         if portgroup.spec.vswitchName in disconnectedSwitches:
            disconnectedPortgroups.append(portgroup.spec.name)

   # If there is a service console that uses one of the physical nics that will be used
   # as uplinks by the dvs, they need to be moved to the dvs
   if disconnectedPortgroups:
      for consoleNic in oldNetworkConfig.consoleVnic:
         # If the console nic is connected to a disconnected portgroup, move it to the new dvs
         if not consoleNic.spec.distributedVirtualPort and \
                        (consoleNic.spec.portgroup in disconnectedPortgroups or \
                         consoleNic.portgroup in disconnectedPortgroups):
            # If there is no portgroup to which to move the disconected service console
            # emit a warning
            if not scPortGroup:
               Log("Warning! Service console %s will be disconnected by this operation" % consoleNic.device)
               continue
            consoleNic.changeOperation = "edit"
            consoleNic.portgroup = ""
            consoleNic.spec.portgroup = None
            consoleNic.spec.distributedVirtualPort = Vim.Dvs.PortConnection()
            consoleNic.spec.distributedVirtualPort.switchUuid = dvs.uuid
            consoleNic.spec.distributedVirtualPort.portgroupKey = scPortGroup.key
            newNetworkConfig.consoleVnic.append(consoleNic)

   # We also need to reconfigure the DVS to add the host to it
   dvsConfig = Vim.DistributedVirtualSwitch.ConfigSpec()
   dvsConfig.configVersion = dvs.config.configVersion
   hostMemberConfig = Vim.Dvs.HostMember.ConfigSpec()
   hostMemberConfig.operation = "add"
   hostMemberConfig.host = host
   if maxProxyPorts:
      hostMemberConfig.maxProxySwitchPorts = maxProxyPorts
   hostMemberConfig.backing = Vim.Dvs.HostMember.PnicBacking()
   hostMemberConfig.backing.pnicSpec = []
   for pnic in pnicsToUse:
      pnicSpec = Vim.Dvs.HostMember.PnicSpec()
      pnicSpec.pnicDevice = pnic
      hostMemberConfig.backing.pnicSpec.append(pnicSpec)
   dvsConfig.host.append(hostMemberConfig)

   works = [(hostNetwork.UpdateNetworkConfig, (newNetworkConfig, "modify")),
            (dvs.Reconfigure, (dvsConfig, ))]
   GenericTasks("Add a Host to a Distributed Virtual Switch", works)
# end AddHostToDvs()

def RemoveHostFromDvs(dvs, host):
   """
   Removes a host from the dvs by reconfiguring the host. The reconfiguration is performed
   using a single call to the HostNetworkSystem.UpgradeNetworkConfig method to avoid losing
   connectivity to the host.
   """
   hostNetwork = host.configManager.networkSystem

   oldNetworkConfig = hostNetwork.networkConfig
   newNetworkConfig = Vim.Host.NetworkConfig()

   # These nics will have to be moved from the dvs to local vSwitches to preserve connectivity
   pnicsToMove = []

   # Remove all proxy switches associated with this dvs
   newNetworkConfig.proxySwitch = []
   for proxySwitch in oldNetworkConfig.proxySwitch:
      if proxySwitch.uuid == dvs.uuid:
         # The physical NICs of the removed proxy switches will need to be moved
         pnicsToMove.extend([pnicSpec.pnicDevice for pnicSpec in proxySwitch.spec.backing.pnicSpec])
         proxySwitch.changeOperation = "remove"
         proxySwitch.spec = None
         newNetworkConfig.proxySwitch.append(proxySwitch)

   # Add a new vSwitch (with a simple bridge) and a single portgtoup for every physical
   # nic which needs to be moved
   if pnicsToMove:
      vSwitchNum = 0;
      portgroupNum = 0;
      usedSwitchNames = [vSwitch.name for vSwitch in oldNetworkConfig.vswitch]
      usedPGroupNames = [portgroup.spec.name for portgroup in oldNetworkConfig.portgroup]

      for pnic in pnicsToMove:
         # Specify a vSwitch bridged to the physical nic
         vSwitch = Vim.Host.VirtualSwitch.Config()
         vSwitch.changeOperation = "add"
         vSwitch.spec = Vim.Host.VirtualSwitch.Specification()
         vSwitch.spec.numPorts = 120
         vSwitch.spec.bridge = Vim.Host.VirtualSwitch.BondBridge()
         vSwitch.spec.bridge.nicDevice = [pnic]
         # Generate a unique name for the vSwitch
         while (True):
            name = "vSwitch%d" % vSwitchNum
            vSwitchNum += 1
            if not name in usedSwitchNames:
               vSwitch.name = name
               break
         # Add the new switch to the list
         newNetworkConfig.vswitch.append(vSwitch)
         # Add a portgroup that uses the vSwitch
         portgroup = Vim.Host.PortGroup.Config()
         portgroup.changeOperation = "add"
         portgroup.spec = Vim.Host.PortGroup.Specification()
         portgroup.spec.policy = Vim.Host.NetworkPolicy()
         portgroup.spec.vswitchName = vSwitch.name
         portgroup.spec.vlanId = 0
         # Generate a unique name for the portgroup
         while (True):
            name = "Network %d" % portgroupNum
            portgroupNum += 1
            if not name in usedPGroupNames:
               portgroup.spec.name = name
               break
         newNetworkConfig.portgroup.append(portgroup)

   # If a service console vNic uses the DVS it will need to be moved to a legacy virtual switch
   for consoleNic in oldNetworkConfig.consoleVnic:
      # If the console nic is in this DVS, move it
      if consoleNic.spec.distributedVirtualPort and \
                     consoleNic.spec.distributedVirtualPort.switchUuid == dvs.uuid:
         vNic = Vim.Host.VirtualNic.Config()
         vNic.changeOperation = "edit"
         vNic.device = consoleNic.device
         vNic.portgroup = newNetworkConfig.portgroup[0].spec.name
         vNic.spec = Vim.Host.VirtualNic.Specification()
         vNic.spec.mac = consoleNic.spec.mac
         newNetworkConfig.consoleVnic.append(vNic)

   # We also need to reconfigure the DVS to remove the host from it
   dvsConfig = Vim.DistributedVirtualSwitch.ConfigSpec()
   dvsConfig.configVersion = dvs.config.configVersion
   hostMemberConfig = Vim.Dvs.HostMember.ConfigSpec()
   hostMemberConfig.operation = "remove"
   hostMemberConfig.host = host
   dvsConfig.host.append(hostMemberConfig)


   works = [(hostNetwork.UpdateNetworkConfig, (newNetworkConfig, "modify")),
            (dvs.Reconfigure, (dvsConfig, ))]
   tasks = GenericTasks("Remove A Host from a Distributed Virtual Switch", works)

   if tasks:
      return tasks[0]
   else:
      return None
# end RemoveHostFromDvs()

def FindDvsByName(name):
   """ Finds the DVS with the provided name. """
   dvs = GetObjects(Vim.DistributedVirtualSwitch, name)

   if dvs:
      return dvs[0]
   else:
      return None
# end FindDvsByName

def FindDvsPortGroupByName(dvs, name):
   """
   Finds the portgroup associated with the DVS that has the specified name.
   """
   for portGroup in dvs.portgroup:
      if portGroup.config.name == name:
         return portGroup
   return None
# end FindDvsPortGroupByName

def TestDVS(dataCenter, hostSystem, ops="", profile=""):
   """ Test DVS related stuff """
   global options

   if not options.vc:
      Log("Warnig! No VC server specified - DVS operations ignored.")

   else:
      if profile == None:
         profileOps = []
      else:
         profileOps = profile.lower().split(":")

      # Default operations
      if not ops:
         ops = "create:edit:remove"

      dvs = None
      portGroup = None

      try:
         for opandArg in ops.split(":"):
            (op, opArgs) =  ParseOperation(opandArg)

            ExecuteOperationCmd(options.preOperationCmd, op)
            StartProfile(op, profileOps)

            # Collect operation arguments
            host = None
            ports = None
            dvsName = None
            maxProxyPorts = None
            pgName = None
            pgType = None
            pnicNames = []

            for (argId, argVal) in opArgs:

               if argId == "host":
                  if host:
                     Log("Warning! Duplicate host option for DVS %s operation." % (op))
                  hostSystem = FindHostByName(argVal)
                  if not hostSystem:
                     Log("Warning! Could not find host %s" % (argVal))
               elif argId == "dvsname":
                  if dvsName:
                     Log("Warning! Duplicate dvsName option for DVS %s operation." % (op))
                  dvsName = argVal
                  if op != "create":
                     dvs = FindDvsByName(dvsName)
                     if not dvs:
                        if dvsName:
                           Log("Warning! No DVS named %s was found. Operation %s ignored." % (dvsName, op))
               elif argId == "ports":
                  if ports:
                      Log("Warning! Duplicate ports option for DVS %s operation." % (op))
                  ports = int(argVal)
               elif argId == "maxProxyPorts":
                  maxProxyPorts = int(argVal)
               elif argId == "pgname":
                  if pgName:
                      Log("Warning! Duplicate portgroup name option for DVS %s operation." % (op))
                  pgName = argVal
               elif argId == "pgtype":
                  if pgName:
                      Log("Warning! Duplicate portgroup type option for DVS %s operation." % (op))
                  pgType = argVal
               elif argId == "pnic":
                  pnicNames.append(argVal)
               else:
                  Log("Warning! Unknown option for virtual switch %s operation: %s" % (op, argId))

            if not dvs and op != "create":
               Log("Warning! No DVS specified. Operation %s ignored" % (op))
               continue

            # Process operation
            # -----------------

            # Perform create operation
            if op == "create":
               dvs = CreateDVS(dataCenter, dvsName or "speedTest-DVS")
            # Perform remove operation
            elif op == "remove":
               RemoveDVS(dvs)
               dvs = None
            # Perform add portgroup operation
            elif op == "addportgroup":
               portGroup = AddDvsPortGroup(dvs, pgName or "speedTest-PortGroup", pgType or "dynamic", ports or 500)
            elif op == "rmportgroup":
               if pgName:
                  portGroup = FindDvsPortGroupByName(dvs, pgName)
               if portGroup:
                  RemoveDvsPortGroup(portGroup)
                  portGroup = None
            elif op == "addhost":
               if pgName:
                  portGroup = FindDvsPortGroupByName(dvs, pgName)
                  if not portGroup:
                     Log("Warning! Could not find port group %s" % (pgName))
               AddHostToDvs(dvs, hostSystem, pnicNames, portGroup, maxProxyPorts)
            elif op == "rmhost":
               RemoveHostFromDvs(dvs, hostSystem)
            else:
               Log("Unknown DVS operation: %s" % (op))

            EndProfile(op, profileOps)
            ExecuteOperationCmd(options.postOperationCmd, op)
      finally:
         pass
#end TestDVS

def ParseRange(rangeStr):
   """
   Parse a range of numbers with format start[-end][;*]
   e.g. 0-9;15;20-30
   """
   ranges = rangeStr.split(";")
   rangeSet = set()
   for _range in ranges:
      tokens = _range.split("-")
      if len(tokens) == 1:
         rangeSet.add(ToInt(tokens[0]))
      else:
         for num in xrange(ToInt(tokens[0]), ToInt(tokens[1])+1):
            rangeSet.add(num)
   return rangeSet


## Parse arguments
#
def ParseArguments(argv):
   """ Parse arguments """

   from optparse import OptionParser, make_option

   testHelp = """
The following tests are available:
  Resource pool: rp[,prefix={prefix}][,r={ranges}][,cleanup={0|1}][,ops={op}[:op]*]
    prefix - Test name prefix
    cleanup - Cleanup when done
    ranges - Test ranges {begin}-{end}[{begin}-{end}]* (e.g. r=1-10;12-14)
    ops - Resource ops {create|update|destroy}
      Some operations accept additional parameters in key/value form:
        {op} [key=value][;key=value]*

      - find:
        hostOnly=0|1
          If 0, find the VMs from the whole inventory. This is the default behavior.
          Else, find the VMs registered on the host under test.

      - create:
        gen={num of generations}
          Num of descendants generation
        child={num of children}
          Num of children for each generation
        e.g. 'create gen=1;child=4'

      - update:
        cpu={cpu shares}
        mem={memory shares}
        e.g. 'update cpu=5000;mem=4000'

  Datacenter: datacenter[,profile={op}[:op]*][,ops={op}[:op]*]
     profile - Datacenter ops to profile
     ops - Datacenter ops {add/remove}
      Some operations accept additional paramaeters in key/value form:
        {op} [key=value][;key=value]*

      - add:
        name={Datacenter Name}
          Then name of the datacenter to be created. If not specified the name
          "dc-0" is chosen for the newly created datacenter.

  Cluster: cluster[,profile={op}[:op]*][,ops={op}[:op]*]
     profile - Cluster ops to profile
     ops - Cluster ops {add/reconfig/remove}
      Some operations accept additional parameters in key/value form:
        {op} [key=value][;key=value]*

      - add:
        name={clusterName}
          The name of the cluster to be added. If not specified, the name
          "cluster-0" is chosen for the newly added cluster.
          e.g. 'add name=myCluster'
      - reconfig:
        ha={1/0};drs={1/0}
          The configuration of this cluster. If HA needs to be configured then
          ha=1 else ha=1. Similarly, if DRS needs to be configured then drs=1
          else drs=0.
          e.g. 'reconfig ha=1;drs=1'

  Host: host[,profile={op}[:op]*][,ops={op}[:op]*]
     profile - Host ops to profile
     ops - Host ops {add/enterMM/exitMM/disconnect/reconnect/remove/shutdown}
      Some operations accept additional parameters in key/value form:
        {op} [key=value][;key=value]*

      - add:
        name={clusterName}
          The cluster to add the host to. If it's a standalone host this value
          is None
          e.g. 'add cluster=myCluster'

      - enterMM, exitMM:
        to={timeout}
          Time-out, in seconds, to wait for the operation to complete. Default
          is no time-out

  VM: vm[,prefix={prefix}][,r={range}][,cleanup={0|1}][,profile={op}[:op]*][,ops={op}[:op]*]
    prefix - Test name prefix
    cleanup - Cleanup when done
    ranges - Test ranges {begin}-{end}[{begin}-{end}]* (e.g. r=1-10;12-14)
    profile - VM ops to profile
    ops - VM ops {clean|create|find|on|groupon|update-shares|update-OL|off|suspend|
                  reset|unreg|reg|reconfig|edit|snap|
                  removeallsnap|revertcurrentsnap|
                  destroy|migrate}
      Some operations accept additional parameters in key/value form:
        {op} [key=value][;key=value]*

      - find:
        hostOnly=0|1
          If 0, find the VMs from the whole inventory. This is the default behavior.
          Else, find the VMs registered on the host under test.

      - create:
        ds={datastore}[#{num VMs}
          The datastore to create vm, optionally follows by the number of VMs
          e.g. 'create ds=ds1#20;ds=ds2;ds=ds3'
               Create the first 20 vm in ds1, then eventually distribute the
               rest in ds2 and ds3
          If no datastore is specified, will create VMs in the largest vmfs vol
        dvsname={distributed virtual switch name}
          If set, specifies the dvs to be used as a backing for the VM nics.
          Also requires the dvspgname parameter.
        dvspgname={distributed port group}
          If set, specifies the dvs to be used as a backing for the VM nics.
          Also requires the dvspgname parameter.

      - migrate:
        host={host name}
          The host to which to migrate the virtual machines. If not provided,
          the host provided by the --host command line argument will be used.

      - clone:
        ds={datastore}
          The datastore to create the source VM and its linked clones
          e.g. 'clone ds=ds1'
        If no datastore is specified, will create VMs in the largest vmfs vol

        srcvm={vm name}
          If set, use the specified VM as the source VM.
          Otherwise, create a new source VM.

        linked=1|0
          If 1 (default), do linked clone. Otherwise, full clone.

      - reg:
        ds={datastore}
          The datastore to search for vm
          e.g. 'reg ds=ds1'

      - reconfig:
        ds={datastore}
          The datastore where a SCSI disk should be added during reconfigure.
          e.g. 'reconfig ds=ds1'

      - edit:
        network={network name}
          If provided, the nics backing will be moved to the specified
          network. When the network is backed by a DVS switch, and the user
          wants to move the dv ports from one pg to another, simply use the
          target pg name as the argument.
        nics={number}
          If provided, so many number of nics would be added the the VM.

      - reservecpu:
        reservation={reservation in MHz}
          Change the CPU reservation, by default is 1 MHz.

      - addvmdisk
        ds={datastore name}
          If provided, add a virtual disk using the specified datastore.
          Otherwise, use the first available datastore on the host.

      - changenetwork
        network={network name}
          If provided, the nics backing will be moved to the specified
          network. When the network is backed by a DVS switch, and the user
          wants to move the dv ports from one pg to another, simply use the
          target pg name as the argument.
          Otherwise, no operation will be done.

      - update-shares, update-OL:
        batchSize={size}
          The batch size for the update operation
        newVal={val}
          The new value for the update (new shares for update-shares,
          new overheadLimit for update-OL'
          e.g. 'batchSize=1;newVal=5000'

      - shutdownguest:
      - rebootguest:
      - standbyguest:
         Misc. guest OS operations

      - wait:
        Wait for a specfic condition
        time={time in sec}
          Time to wait, in seconds.

        power={on|off|suspended}
          vm power state

        guest={on}
          Guest power state. MUST have vm guest tool installed
          i.e. Don't work on vm with no OS, e.g. dummy vms, ...

  Datastore: datastore [,profile={op}[:op]*][,ops={op}[:op]*]
     profile - Datastore ops to profile
     ops - Datastore ops {add/remove}
      Some operations accept additional parameters in key/value form:
      {op} [key=value][;key=value]*

     - add:
       name={name};remoteHost={remotePath};remotePath={remotePath}
          The configuration of the NAS datastore to be added.
     - remove:
       name={datastore Name}
          The name of the datastore that needs to be removed.

  Virtual switch: vswitch[,profile={op}[:op]*][,ops={op}[:op]*]
    ops - Switch operations {create|remove|edit}
      Some operations accept additional parameters in key/value form:
        {op} [key=value][;key=value]*

      - create:
        host={host name}
          The host on which to create the virtual switch if connected to VC.
          If not provided, the host provided by the --host command line
          argument will be used.
        name={switch name}
          The name of the new switch. If no name is specified,
          "speedTest-vswitch" will be used
        ports={count}
          The number of ports for this switch. 120 by default.

      - remove:
        host={host name}
          The host on which to create the virtual switch if connected to VC.
          If not provided, the host provided by the --host command line
          argument will be used.
        name={switch name}
          The name of the switch to be removed. If no name is provided, removes
          all switches added by the create operation.

      - edit:
        host={host name}
          The host on which to create the virtual switch if connected to VC.
          If not provided, the host provided by the --host command line
          argument will be used.
        name={switch name}
          The name of the switch to be reconfigured. If no name is provided,
          reconfigures all switches added by the create operation
        ports={count}
          The number of ports for this switch. 248 by default.

  Distributed virtual switch: dvs[,profile={op}[:op]*][,ops={op}[:op]*]
    ops - Switch operations {create|remove|addportgroup|rmportgroup|addhost|rmhost}
      Some operations accept additional parameters in key/value form:
        {op} [key=value][;key=value]*

      - create:
        dvsname={DVS name}
          The name of the DVS to create. If no name is provided, the dvs will
          be named "speedTest-DVS".

      - remove:
        dvsname={DVS name}
          The name of the DVS to remove. If no name is provided, the last dvs
          specified in a previous DVS test will be used.

      - addportgroup:
        dvsname={DVS name}
          The name of the DVS to add the portgroup to. If no name is provided,
          the last dvs specified in a previous DVS test will be used.
        pgname={port group name}
          The name of the portgroup to create. If not specified the new port
          group will be called "speedTest-PortGroup".
        pgtype={static|dynamic|ephemeral}
          If not provided, a dynamic portgroup will be created
        ports={count}
          The number of ports for this portgroup. 500 by default.

      - rmportgroup:
        dvsname={DVS name}
          The name of the DVS to which portgroup belongs. If no name is
          provided, the last dvs specified in a previous DVS test will be used.
        pgname={port group name}
          The name of the portgroup to remove. If not specified the last
          created port group will be removed.

      - addhost:
        dvsname={DVS name}
          The name of the DVS to add the host to. If no name is provided, the
          last dvs specified in a previous DVS test will be used.
        host={host name}
          The host to add to the DVS. If not provided, the host provided by the
          --host command line argument will be used.
        maxProxyPorts = {maximum number of proxy ports}
           The maximum number of ports allowed to be created in the proxy
           switch.
        pnic={physical nic name}
          The name of a physical nic to use as an uplink. This argument can be
          provided multiple times and all specified nics will be used.
          WARNING: This option does not work yet.
        pgname={portgroup name}
          If one or more service consol virtual nics would get disconnected by
          this operation, they will be connected to this portgroup to avoid
          losing connectivity to the host.
          WARNING: This option does not work yet.

      - rmhost:
        dvsname={DVS name}
          The name of the DVS to which the host is connected. If no name is
          provided, the last dvs specified in a previous DVS test will be used.
        host={host name}
          The host to remove from the DVS. If not provided, the host specified
          by a previous DVS test will be used. If this is the first DVS test
          that specifies a host, the host provided by the --host command line
          argument will be used.


  Running custom commands before and after each batch of identical operations:
    --preOperationCmd, --postOperationCmd:
      These options supply a command that will be executed before or after each
      set of identical VM operations. If the command contains the "{opName}"
      string, all of its occurences will be replaced by the name of the
      operation that is to be performed or has been performed, respectively.
      Example:
        --preOperationCmd="xperf -on latency -SetProfInt 2000 -stackwalk Profile"
        --postOperationCmd="xperf -d .\Output\{opName}Profile.etl"
"""

   # Internal cmds supported by this handler
   _CMD_OPTIONS_LIST = [
      make_option("-s", "--vc", dest="vc", default=None,
                  help="VC server"),
      make_option("-h", "--host", dest="host", default="localhost",
                  help="ESX host name"),
      make_option("-o", "--port", dest="port", default=443, help="Port"),
      make_option("-u", "--user", dest="user", default="root",
                  help="Host User name"),
      make_option("-p", "--pwd", dest="pwd", default="",
                  help="Host Password"),
      make_option("--vcuser", dest="vcuser", default="Administrator",
                  help="VC User name"),
      make_option("--vcpwd", dest="vcpwd", default="ca\$hc0w",
                  help="VC Password"),
      make_option("-w", "--workers", dest="workers", type="int",
                  default=8, help="Num of workers. 1 => serialize operation"),
      make_option("-t", "--test", dest="tests", action="append", default=[],
                  help="Tests to run (e.g. -t rp,r=1-50 -t vm,r=1-10;12-24)."),
      make_option("-v", "--verbose", action="store_true", dest="verbose_stats",
                  default=False, help="Enable verbose stats"),
      make_option("-b", "--profileBlockedTime", action="store_true",
                  dest="profileBlockedTime", default=False, help="Count blocked time in profile"),
      make_option("-a", "--agentToProfile", dest="agentToProfile",
                  default="vmware-hostd", help="Agent to profile - e.g. vmware-hostd or vmware-vpxa"),
      make_option("-d", "--statsDir", dest="statsDir",
                  default="/tmp", help="Stats root directory"),
      make_option("-i", "--imageLocations", dest="imageLocations", default=None,
                  help="Locations of images to extract symbol information from in the form: image1:pathToImage1;image2:pathToImage2"),
      make_option("", "--preOperationCmd", dest="preOperationCmd", default=None,
                  help="A command to be executed before each set of identical VM operations. Each occurance of {opName} in the command string will be replaced with the name of the operation to be performed"),
      make_option("", "--postOperationCmd", dest="postOperationCmd", default=None,
                  help="A command to be executed after each operation set of identical VM operations. Each occurance of {opName} in the command string will be replaced with the name of the operation that was performed"),
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

def GetBoraPath():
   try:
      vmtree = os.environ["VMTREE"]
      if not vmtree:
         raise KeyError("VMTREE")
   except KeyError as err:
      boraPath = "/bora"
      cwd = os.getcwd()
      idx = cwd.rfind(boraPath)
      if idx > 0:
         vmtree = cwd[:idx + len(boraPath)]
      else:
         print("Must set VMTREE")
         raise err

   return vmtree

def GetBuildType():
   bldType = os.environ.get("VMBLD", "")
   if not bldType:
      bldType = os.environ.get("BLDTYPE", "")
   return bldType

## Main
#
def main():
   global options
   global si
   options, remainingOptions = ParseArguments(sys.argv[1:])
   req_ver_ssl = (2,7,9)

   if sys.version_info >= req_ver_ssl:
      context = ssl.create_default_context()
      context.check_hostname = False
      context.verify_mode = ssl.CERT_NONE
   else:
      context = None

   # Connect
   try:
      if options.vc:
         si = Connect(host=options.vc, port=int(options.port),
                      user=options.vcuser, pwd=options.vcpwd,
                      sslContext=context)
      else:
         si = Connect(host=options.host, port=int(options.port),
                      user=options.user, pwd=options.pwd, sslContext=context)
   except Exception as err:
      print("Login failed: " + str(err))
      return
   atexit.register(Disconnect, si)

   status = "PASS"

   # Parallel or serialize operations
   global threadPool
   if options.tests and options.workers > 1:
      threadPool = ThreadPool(maxWorkers=options.workers)
      stub = si._GetStub()
      if hasattr(stub, "poolSize"):
         stub.poolSize = options.workers

   startTime = None
   endTime = None
   try:
      # si content
      content = si.RetrieveContent()

      # init managed objects
      dataCenter = None
      computeResource = None
      resourcePool = None
      hostSystem = None
      clusterComputeResource = None
      vmFolder  = None
      hostFolder = None

      # hostSystem
      hostSystem = FindHostByName(options.host)

      if hostSystem:
         # compute resources
         crObjs = GetObjects(Vim.ComputeResource)
         crObj = filter(lambda x: hostSystem in x.host, crObjs)[0]
         computeResource = crObj

         # Clustered host
         if isinstance(crObj, Vim.ClusterComputeResource):
            clusterComputeResource = computeResource

         # resource pool
         resourcePool = computeResource.resourcePool

         dataCenter = GetParentDatacenter(hostSystem)
         # vmFolder
         vmFolder = dataCenter.vmFolder
         # hostFolder
         hostFolder = dataCenter.hostFolder

      startTime = time.time()

      for test in options.tests:
         args = test.split(",")
         opt = {}
         for arg in args[1:]:
            key, value = arg.split("=", 1)
            opt[key] = value
         if args[0] == "rp" or args[0] == "resourcepool":
            # Test resource pool
            if hostSystem == None:
               Log("No host for operation")
               return
            TestResourcePools(resourcePool,
                              namePrefix=opt.get("prefix",
                                                 "speed-test-resource-pool"),
                              poolRange=ParseRange(opt.get("r", "0-99")),
                              cleanup=bool(int(opt.get("cleanup",1))),
                              ops=opt.get("ops",""),
                              profile=opt.get("profile"))
         elif args[0] == "datacenter":
            # Test cluster operations
            TestDatacenter(content.rootFolder, dataCenter,
                          ops=opt.get("ops",""), profile=opt.get("profile"))
         elif args[0] == "cluster":
            # Test cluster operations
            TestCluster(hostFolder, clusterComputeResource,
                        ops=opt.get("ops",""), profile=opt.get("profile"))
         elif args[0] == "host":
            # Test host operations
            TestHost(hostFolder, hostSystem,
                     ops=opt.get("ops",""), profile=opt.get("profile"))
         elif args[0] == "vm":
            if hostSystem == None:
               Log("No host for operation")
               return
            # Test VMs
            TestVMs(vmFolder, resourcePool, hostSystem,
                    namePrefix=opt.get("prefix", "speed-test-vms"),
                    vmRange=ParseRange(opt.get("r", "0-4")),
                    cleanup=bool(int(opt.get("cleanup",1))),
                    ops=opt.get("ops",""), profile=opt.get("profile"),
                    checkmax=bool(int(opt.get("checkmax",1))))
         elif args[0] == "vapivm":
            if hostSystem == None:
               Log("No host for operation")
               return

            endpoint_url = 'https://%s/api' % options.vc
            connector = get_connector('http', 'json', url=endpoint_url)
            user_password_security_context = create_user_password_security_context(
                options.vcuser, options.vcpwd)
            connector.set_security_context(user_password_security_context)
            stub_config = StubConfigurationFactory.new_std_configuration(connector)
            session_svc = Session(stub_config)
            session_id = session_svc.create()
            session_security_context = create_session_security_context(session_id)
            connector.set_security_context(session_security_context)
            global vm_svc
            global power_svc
            global datastore_svc
            vm_svc = VM(stub_config)
            power_svc = Power(stub_config)
            datastore_svc = Datastore(stub_config)

            # Test VMs
            VapiTestVMs(vmFolder._moId, resourcePool._moId, hostSystem,
                    namePrefix=opt.get("prefix", "speed-test-vms"),
                    vmRange=ParseRange(opt.get("r", "0-4")),
                    cleanup=bool(int(opt.get("cleanup",1))),
                    ops=opt.get("ops",""), profile=opt.get("profile"),
                    checkmax=bool(int(opt.get("checkmax",1))))

            session_svc.delete()

         elif args[0] == "datastore":
            if hostSystem == None:
               Log("No host for datastore operation")
               return
            # Test cluster operations
            TestDatastore(hostFolder, hostSystem,
                          ops=opt.get("ops",""), profile=opt.get("profile"))
         elif args[0] == "vswitch":
            # Test virtual switch operations
            TestVSwitch(hostSystem, ops=opt.get("ops",""), profile=opt.get("profile"))
         elif args[0] == "dvs":
            # Test DVS operations
            TestDVS(dataCenter, hostSystem, ops=opt.get("ops",""), profile=opt.get("profile"))
         elif args[0] == "vmwf":
            # Test concurrent workflow of VM operatons on a single host
            if options.vc == None:
               Log("Workflow test only supported for VC currently")
            if hostSystem == None:
               Log("No host for operation")
               return
            if options.verbose_stats:
               global fd
               fd = open("%s/%s" % (options.statsDir,
                                    opt.get("prefix", "speed-test-vms")), "w")
            # Test VMs
            TestVMWorkflows(vmFolder, resourcePool, hostSystem,
                            namePrefix=opt.get("prefix", "speed-test-vms"),
                            wfRange=ParseRange(opt.get("r", "0-4")),
                            cleanup=bool(int(opt.get("cleanup",1))),
                            tag=opt.get("tag","vc"),
                            ops=opt.get("ops",""), profile=opt.get("profile"))
         else:
            # Unknown test
            print("Skip unknown test: %s" % args[0])
      endTime = time.time()
   except Exception as err:
      Log("Failed test due to exception: " + str(err))
      import traceback
      exc_type, exc_value, exc_traceback = sys.exc_info()
      stackTrace = " ".join(traceback.format_exception(
                            exc_type, exc_value, exc_traceback))
      Log(stackTrace)
      sys.exc_clear()
      status = "FAIL"

   if threadPool:
      threadPool.Shutdown()

   if startTime and endTime:
      Log("Total test time: %f secs" % (endTime - startTime))
   Log("TEST RUN COMPLETE: " + status)

   if options.verbose_stats and fd:
      fd.close()


# Start program
if __name__ == "__main__":
   main()
