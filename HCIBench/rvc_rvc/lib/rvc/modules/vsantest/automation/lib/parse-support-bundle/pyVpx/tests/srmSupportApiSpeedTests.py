#!/usr/bin/python

#
# Performance stats as of 08/30/2011
# ----------------------------------
#
# Serial Execution on 500 VM's on 10 hosts:
# -----------------------------------------
# API:                                  Registered              Unregistered
# RetrieveVmRecoveryInfo                9.57790327072           180.124495983
# RetrieveLastVmMigrationStatus         8.38376021385           198.177805185
# DeleteVmExceptDisks                   701.943456173           761.298356771
#
#
# Parallel Execution (10 threads) on 500 VM's on 10 hosts:
# --------------------------------------------------------
# API:                                  Registered              Unregistered
# RetrieveVmRecoveryInfo                1.28990244865           24.1904430389
# RetrieveLastVmMigrationStatus         0.73449492454           24.1831030846
# DeleteVmExceptDisks                   93.3442976475           109.573899031
#

from optparse import OptionParser
import os
import sys
from pyVmomi import Vim, Vmodl
from pyVim import folder, host, path, vm, vmconfig
from pyVim.connect import Connect, Disconnect, GetSi, SmartConnect, SetSi
from pyVim.task import WaitForTask
from pyVim.helpers import Log, StopWatch
from pyVim.invt import GetDatacenter
import time
import atexit
import socket
import subprocess
import logging
from contrib.threadPool import ThreadPool, WorkItem

NUM_THREADS=20

testVMPrefix = "SrmSupportAPISpeedTestVM_"
threadPool = ThreadPool(minWorkers=NUM_THREADS,
                        maxWorkers=NUM_THREADS,
                        logger=logging)

def Cleanup(vmName, sessions, doCleanup):
   for hostName, si in sessions.iteritems():
      SetSi(si)
      oldVms = folder.FindPrefix(vmName)
      if oldVms:
         if doCleanup:
            Log("Cleaning up old vms with name: " + vmName)
            for oldVm in oldVms:
               if oldVm.GetRuntime().GetPowerState() == Vim.VirtualMachine.PowerState.poweredOn:
                  vm.PowerOff(oldVm)
               oldVm.Destroy()

def CurrentVmCount(vmName, sessions):
   vmCount = []
   for hostName, si in sessions.iteritems():
      SetSi(si)
      vmCount.append(len(folder.FindPrefix(vmName)))
   return vmCount

def RunLocalCommand(cmdLine):
   """
   Executes a local shell command
   """
   p = subprocess.Popen(cmdLine, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
   outdata, errdata = p.communicate()
   if errdata:
      Log("Error output from local/remote command (%s):\n%s" % (cmdLine,errdata))
   return outdata

def RunRemoteCommand(host, cmd):
   """
   Assumes you've got password less login already setup.
   """
   return RunLocalCommand("ssh %s@%s 'sh -lc \"%s\"'" % ("root", host, cmd))

def CreateVm(si, hostName, vmname):
   return (hostName, vm.CreateQuickDummy(vmname=vmname, numScsiDisks=1, si=si))

def CreateVms(numvms, vmname, unregister=False):
   vmsperhost = numvms/len(hostSystems)
   vms = {}
   workItems = []

   hostIndex = 0
   for hostName, hostSystem in hostSystems.iteritems():
      vmIndex = 0
      vms.setdefault(hostName, [])
      while vmIndex < vmsperhost:
         si = sessions[hostName]
         newVmname = "%s%s" % (vmname, str(hostIndex * vmsperhost + vmIndex))
         workItems.append( (CreateVm, (si, hostName, newVmname,)) )
         vmIndex += 1

   results = threadPool.QueueWorksAndWait(workItems)
   for result in results:
      status, methResult = result
      if status:
         hostName, vmRef = methResult
         vms[hostName].append(vmRef.GetConfig())
         if unregister:
            vmRef.Unregister()

   return vms

def Execute(method, vmPath, si, isTask):
   result = method(vmPath)
   if isTask:
      WaitForTask(task=result, si=si)

def TimeApi(vms, func, isTask=False, parallel=False):
   totalTime = 0
   workItems = []

   for hostName, llpm in llpms.iteritems():
      vmRefs = vms[hostName]
      workItemsPerHost = []
      for vmRef in vmRefs:
         vmPath = vmRef.GetFiles().GetVmPathName()
         method = getattr(llpm, func)
         t1 = time.time()
         if parallel:
            workItemsPerHost.append( (Execute, (method, vmPath, sessions[hostName], isTask, )) )
         else:
            Execute(method, vmPath, sessions[hostName], isTask)
         t2 = time.time()
         totalTime += (t2 - t1)
      workItems.append(workItemsPerHost)

   if workItems:
      workItems = zip(*workItems)
      workItems = [item for subWorkItems in workItems for item in subWorkItems]
      t1 = time.time()
      threadPool.QueueWorksAndWait(workItems)
      t2 = time.time()
      totalTime += (t2 - t1)

   return totalTime

def CleanUpHosts(vms):
   Log("Cleaning up left over files from DeleteVmExceptDisks method")
   for hostName, vmRefs in vms.iteritems():
      for vmRef in vmRefs:
         vmPath = vmRef.GetFiles().GetVmPathName()
         datastore = vmPath.split("]")[0].split("[")[1]
         vmDir = vmPath.split("/")[0].split(" ")[-1]
         RunRemoteCommand(hostName, "rm -rf \"/vmfs/volumes/%s/%s\"" % (datastore, vmDir))

def RunTests(argv):
   global options

   # Can't use built-in help option because -h is used for hostname
   parser = OptionParser(add_help_option=False)

   parser.add_option('-h', '--host', dest='hostFile', help='ESX Host name', default='localhost')
   parser.add_option('-i', '--numvms', dest='numvms', help='Number of VMs',
                     default=1, type='int')
   parser.add_option('-p', '--parallel', dest='parallel', help='Execute Parallely',
                     default=False, action='store_true')
   parser.add_option('-c', '--cleanup', dest='cleanup',
                     help='Try to clean up test VMs from previous runs',
                     default=False, action='store_true')
   parser.add_option('-?', '--help', '--usage', action='help', help='Usage information')

   (options, args) = parser.parse_args(argv)

   hosts = []
   with open(options.hostFile, "r") as hostData:
      for hostName in hostData:
         hosts.append(hostName.strip())

   # Connect
   global sessions
   global hostSystems
   global llpms
   sessions = {}
   hostSystems = {}
   llpms = {}
   for hostName in hosts:
      Log("Adding %s" % hostName)
      si = SmartConnect(host=hostName, port=443)
      atexit.register(Disconnect, si)
      sessions[hostName] = si
      hostSystem = host.GetHostSystem(si)
      internalCfgMgr = hostSystem.RetrieveInternalConfigManager()
      hostSystems[hostName] = hostSystem
      llpms[hostName] = internalCfgMgr.llProvisioningManager

   resultsArray = []
   # Do cleanup if requested
   Cleanup(testVMPrefix, sessions, options.cleanup)

   # Invoke API's on registered vm's and record time
   vmName = testVMPrefix
   Log("Creating %s vms on %s hosts" %(options.numvms, len(hosts)))
   vms = CreateVms(options.numvms, vmName)
   result = TimeApi(vms, "RetrieveVmRecoveryInfo", False, options.parallel)
   Log("Recovery Info of %s registered vm's on %s hosts took %s" %(options.numvms, len(hosts), result))

   result = TimeApi(vms, "RetrieveLastVmMigrationStatus", False, options.parallel)
   Log("Migration status of %s registered vm's on %s hosts took %s" %(options.numvms, len(hosts), result))

   result = TimeApi(vms, "DeleteVmExceptDisks", True, options.parallel)
   Log("Deleting %s registered vm's except disks on %s hosts took %s" %(options.numvms, len(hosts), result))

   CleanUpHosts(vms)

   # Invoke API's on unregistered vm's and record time
   Log("Creating %s vms on %s hosts" %(options.numvms, len(hosts)))
   vms = CreateVms(options.numvms, vmName, True)

   result = TimeApi(vms, "RetrieveVmRecoveryInfo", False, options.parallel)
   Log("Recovery Info of %s unregistered vm's on %s hosts took %s" %(options.numvms, len(hosts), result))

   result = TimeApi(vms, "RetrieveLastVmMigrationStatus", False, options.parallel)
   Log("Migration status of %s unregistered vm's on %s hosts took %s" %(options.numvms, len(hosts), result))

   result = TimeApi(vms, "DeleteVmExceptDisks", True, options.parallel)
   Log("Deleting %s unregistered vm's except disks on %s hosts took %s" %(options.numvms, len(hosts), result))

   CleanUpHosts(vms)

   return

# Start program
if __name__ == "__main__":
   RunTests(sys.argv[1:])
