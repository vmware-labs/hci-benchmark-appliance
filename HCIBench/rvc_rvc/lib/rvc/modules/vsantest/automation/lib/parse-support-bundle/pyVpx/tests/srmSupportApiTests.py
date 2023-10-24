#!/usr/bin/python

from __future__ import print_function

from optparse import OptionParser
import os
import sys
from pyVmomi import Vim, Vmodl
from pyVim import folder, host, path, vm, vmconfig
from pyVim.connect import Disconnect, GetSi, SmartConnect
from pyVim.task import WaitForTask
from pyVim.helpers import Log, StopWatch
from pyVim.invt import GetDatacenter
import time
import atexit
import socket
import subprocess

testVMPrefix = "SrmSupportAPIUnitTestVM_"
isMockup = False

class Phase:
   def __init__(self):
      self.phaseNumber = 0
      self.phaseClock = StopWatch()

   def SetPhase(self, msg):
      Log("Phase " + str(self.phaseNumber) + ": " + msg + " completed")
      self.phaseClock.finish("phase " + str(self.phaseNumber))
      self.phaseClock = StopWatch()
      self.phaseNumber = self.phaseNumber + 1

def Cleanup(vmName, doCleanup):
   if options.vcHost:
      return

   oldVms = folder.FindPrefix(vmName)
   if oldVms:
      if doCleanup:
         Log("Cleaning up old vms with name: " + vmName)
         for oldVm in oldVms:
            if oldVm.GetRuntime().GetPowerState() == Vim.VirtualMachine.PowerState.poweredOn:
               vm.PowerOff(oldVm)
            oldVm.Destroy()
      else:
         Log("Please cleanup unit test vms from previous runs")
         sys.exit(-1)

def GetHostSystem(hostname):
   if options.vcHost:
      dcRef = GetDatacenter(options.dcName)
      searchIndex = si.content.searchIndex
      hostSystem = searchIndex.FindByIp(dcRef, hostname, False) or \
      searchIndex.FindByDnsName(dcRef, hostname, False)
   else:
      hostSystem = host.GetHostSystem(si)
   return hostSystem

def GetLLPM(hostSystem):
   internalCfgMgr = hostSystem.RetrieveInternalConfigManager()
   return internalCfgMgr.llProvisioningManager

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

def BrowseDir(hostSystem, path, search='*'):
   browse = hostSystem.GetDatastoreBrowser()

   searchSpec = Vim.Host.DatastoreBrowser.SearchSpec()
   searchSpec.matchPattern = search

   task = browse.Search(path, searchSpec)
   WaitForTask(task)
   result = []
   for file in task.info.result.file:
      result.append(file)
   return result

def BasicRetrieveTests(host, newName):
   Log("Retrieve tests on dummy VM's")
   Log("Creating VM on Source Host")

   hostSystem = GetHostSystem(host)
   testVm = vm.CreateQuickDummy(newName, 1, host=hostSystem, datastoreName=options.datastore)
   llpm = GetLLPM(hostSystem)

   config = testVm.GetConfig()
   vmPathName = config.GetFiles().GetVmPathName()
   Log("Registered VM %s" % vmPathName)
   task = llpm.RetrieveVmRecoveryInfo(vmPathName)
   WaitForTask(task)
   Log(str(task.info.result))
   task = llpm.RetrieveLastVmMigrationStatus(vmPathName)
   WaitForTask(task)
   Log(str(task.info.result))

   Log("Unregistered VM %s" % vmPathName)
   testVm.Unregister()
   task = llpm.RetrieveVmRecoveryInfo(vmPathName)
   WaitForTask(task)
   Log(str(task.info.result))
   task = llpm.RetrieveLastVmMigrationStatus(vmPathName)
   WaitForTask(task)
   Log(str(task.info.result))

   Log("Retrieve using file which is not present")
   try:
      task = llpm.RetrieveVmRecoveryInfo(vmPathName + "!@#!@!@!#")
      WaitForTask(task)
      Log(str(task.info.result))
      raise Exception("Did not throw exception with invalid file")
   except Exception as e:
      print(e)

   Log("Retrieve using file which is not present")
   try:
      task = llpm.RetrieveLastVmMigrationStatus(vmPathName + "!@#!@!@!#")
      WaitForTask(task)
      Log(str(task.info.result))
      raise Exception("Did not throw exception with invalid file")
   except Exception as e:
      print(e)

   task = llpm.DeleteVm(config)
   WaitForTask(task)

# Search for all vmx files in the datastore and call Retrieve*
# on all of them
def RetrieveTests(host):
   hostSystem = GetHostSystem(host)
   llpm = GetLLPM(hostSystem)

   vmxFilePaths = []
   folders = BrowseDir(hostSystem, "[%s]" % options.datastore)
   for folder in folders:
      vmxFiles = BrowseDir(hostSystem, "[%s] %s" % (options.datastore, folder.path), "*.vmx")
      vmxFilePaths.extend(["[%s] %s/%s" % (options.datastore, folder.path, vmxFile.path)
                          for vmxFile in vmxFiles])

   for vmxFilePath in vmxFilePaths:
      Log("Invoking RetrieveVmRecoveryInfo on %s" % vmxFilePath)
      task = llpm.RetrieveVmRecoveryInfo(vmxFilePath)
      WaitForTask(task)
      Log(str(task.info.result))
      Log("Invoking RetrieveLastVmMigrationStatus on %s" % vmxFilePath)
      task = llpm.RetrieveLastVmMigrationStatus(vmxFilePath)
      WaitForTask(task)
      Log(str(task.info.result))

def DeleteVmExceptDisks(host, llpm, vmPathName):
   vmName = vmPathName.split(" ")[1].split("/")[0]

   filesBefore = RunRemoteCommand(host, "ls /vmfs/volumes/%s/%s" % (options.datastore,vmName))
   Log("Files before: \n" + filesBefore)
   task = llpm.DeleteVmExceptDisks(vmPathName)
   WaitForTask(task)
   filesAfter = RunRemoteCommand(host, "ls /vmfs/volumes/%s/%s" % (options.datastore,vmName))
   Log("Files after: \n" + filesAfter)

   filesLeft = RunRemoteCommand(host, "ls /vmfs/volumes/%s/%s | grep -v vmdk" % (options.datastore,vmName))
   if filesLeft:
      raise Exception("Delete did not happen cleanly")

   RunRemoteCommand(host, "rm -rf /vmfs/volumes/%s/%s | grep -v vmdk" % (options.datastore,vmName))

def DeleteVmExceptDisksTests(host, newName):
   # If we delete a registered VM using llpm, VC does not do cleanup
   # Changing the name of test VM so other tests can run
   if options.vcHost:
      newName = newName + "delTest"

   hostSystem = GetHostSystem(host)
   llpm = GetLLPM(hostSystem)

   Log("Delete Registered VM")
   testVm = vm.CreateQuickDummy(newName, 1, host=hostSystem, datastoreName=options.datastore)
   vmPathName = testVm.GetConfig().GetFiles().GetVmPathName()
   DeleteVmExceptDisks(host, llpm, vmPathName)

   Log("Delete Unregistered VM")
   testVm = vm.CreateQuickDummy(newName + "1", 1, host=hostSystem, datastoreName=options.datastore)
   vmPathName = testVm.GetConfig().GetFiles().GetVmPathName()
   testVm.Unregister()
   DeleteVmExceptDisks(host, llpm, vmPathName)

def PoweroffSuspendedVMTests(host, vmName, datastore):
   hostSystem = GetHostSystem(host)
   Log("Poweroff Suspended VM")
   testVm = vm.CreateQuickDummy(vmName, 1, datastoreName=datastore)
   tmpName = vmName + str(1)
   testVm1 = vm.CreateQuickDummy(tmpName, 1, datastoreName=datastore)

   # Poweron a VM, then suspend it.
   task = testVm.PowerOn()
   WaitForTask(task)

   task = testVm.Suspend()
   WaitForTask(task)

   # Now try powering off the VM
   task = testVm.PowerOff()
   WaitForTask(task)

   Log("Successfully powered of Suspended VM")

   Log("Doing Maintenance mode sanity checking")

   task = hostSystem.EnterMaintenanceMode(0)
   WaitForTask(task)

   Log("Entered Maintenance mode")

   task = hostSystem.ExitMaintenanceMode(0)
   WaitForTask(task)

   task = testVm.PowerOn()
   WaitForTask(task)
   task = testVm.Suspend()
   WaitForTask(task)

   Log("Powering off a suspended VM in maintenance mode")

   task = hostSystem.EnterMaintenanceMode(0)
   WaitForTask(task)

   try:
      task = testVm.PowerOff()
      WaitForTask(task)
   except Vim.Fault.InvalidState:
      print("Received InvalidState exception")

   task = hostSystem.ExitMaintenanceMode(0)
   WaitForTask(task)

   Log("Check maintenance mode ref count test 1")

   task = testVm.PowerOn()
   WaitForTask(task)
   task = testVm.Suspend()
   WaitForTask(task)

   Log("Power on 2nd VM")
   task = testVm1.PowerOn()
   WaitForTask(task)

   hostSystem.EnterMaintenanceMode(15)

   Log("Power off 2nd VM, host should go in maintenance mode now.")
   task = testVm1.PowerOff()
   WaitForTask(task)

   time.sleep(3)

   task = hostSystem.ExitMaintenanceMode(0)
   WaitForTask(task)

   Log("Check maintenance mode ref count test 2")

   task = testVm.PowerOff()
   WaitForTask(task)

   Log("Power on 2nd VM")
   task = testVm1.PowerOn()
   WaitForTask(task)

   hostSystem.EnterMaintenanceMode(15)

   Log("Power off 2nd VM, host should go in maintenance mode now.")
   task = testVm1.PowerOff()
   WaitForTask(task)

   time.sleep(3)

   task = hostSystem.ExitMaintenanceMode(0)
   WaitForTask(task)

   # Destroy the test VM.
   vm.Destroy(testVm)
   vm.Destroy(testVm1)

def RunTests(argv):
   global isMockup
   global options

   # Can't use built-in help option because -h is used for hostname
   parser = OptionParser(add_help_option=False)

   parser.add_option('-v', '--vc', dest='vcHost', help='VC Host name')
   parser.add_option('-d', '--dc', dest='dcName', help='Datacenter name')
   parser.add_option('-h', '--host', dest='host', help='ESX Host name', default='localhost')
   parser.add_option('-u', '--user', dest='user', help='User name', default='root')
   parser.add_option('-p', '--pwd', dest='pwd', help='Password', default="")
   parser.add_option('-o', '--port', dest='port', help='Port',
                     default=443, type='int')
   parser.add_option('-i', '--numiter', dest='iter', help='Iterations',
                     default=1, type='int')
   parser.add_option('-t', '--datastore', dest='datastore', help='Datastore')
   parser.add_option('-l', '--volume', dest='volume', help='VMFS volume')
   parser.add_option('-c', '--cleanup', dest='cleanup',
                     help='Try to clean up test VMs from previous runs',
                     default=False, action='store_true')
   parser.add_option('-?', '--help', '--usage', action='help', help='Usage information')

   (options, args) = parser.parse_args(argv)

   # Connect
   global si
   if options.vcHost:
      si = SmartConnect(host=options.vcHost,
                        user="Administrator",
                        pwd="ca$hc0w")
   else:
      si = SmartConnect(host=options.host,
                        user=options.user,
                        pwd=options.pwd,
                        port=options.port)
   atexit.register(Disconnect, si)

   isMockup = host.IsHostMockup(si)
   status = "PASS"

   # Determine the datastore name
   if options.datastore and options.volume:
      Log("Cannot specify both datastore and volume")
      sys.exit(-1)
   elif options.datastore:
      datastore = options.datastore
      Log("Using specified datastore: '%s'" % datastore)
   elif options.volume:
      # Convert absolute volume path to (dsName, relPath) tuple to get dsName
      Log("Trying to determine datastore name for volume: '%s'" % options.volume)
      try:
         datastore = path.FsPathToTuple(options.volume)[0]
         Log("Using datastore: '%s'" % datastore)
      except path.FilePathError:
         Log("Could not determine datastore name for volume: '%s'" % options.volume)
         sys.exit(-1)
   else:
      Log("No datastore or volume specified, test will choose one")
      datastore = None

   resultsArray = []
   # Do cleanup if requested
   Cleanup(testVMPrefix, options.cleanup)

   for i in range(options.iter):
      bigClock = StopWatch()
      try:
         try:
            # Find the vm without tools
            newName = testVMPrefix + str(i)
            ph = Phase()
            # Retrieve Vm Recovery Info Tests
            BasicRetrieveTests(options.host, newName)
            ph.SetPhase("Basic retrieve recovery and migration info on " + newName)

            RetrieveTests(options.host)
            ph.SetPhase("Retrieve recovery and migration info on all VM's in a datastore")

            # Delete Vm except disks tests
            DeleteVmExceptDisksTests(options.host, newName)
            ph.SetPhase("Delete vm except disks on " + newName)

            # Power off suspended VM test.
            PoweroffSuspendedVMTests(options.host, newName, datastore)
            ph.SetPhase("Powered Off Suspended VM " + newName)

            status = "PASS"

         finally:
            bigClock.finish("iteration " + str(i))

      except Exception as e:
         Log("Caught exception : " + str(e))
         status = "FAIL"

      Log("TEST RUN COMPLETE: " + status)
      resultsArray.append(status)

   return_code = 0
   Log("Results for each iteration: ")
   for i in range(len(resultsArray)):
      if resultsArray[i] == "FAIL":
         return_code = -1
      Log("Iteration " + str(i) + ": " + resultsArray[i])

   return return_code

# Start program
if __name__ == "__main__":
    sys.exit(RunTests(sys.argv[1:]))
