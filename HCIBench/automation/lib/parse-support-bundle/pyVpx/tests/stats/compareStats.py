#!/usr/bin/python

###
###  Simple script for comparing the perf counters in host simulator and
###  the real host. If they are the same, the test is successful; Otherwise,
###  the test should be failure.
###

import sys
import atexit
import time
import threading
from pyVmomi import vim, Hostd
from optparse import OptionParser
from pyVim import vm, host, folder, vmconfig, invt
from pyVim.task import WaitForTask
from pyVim.connect import Connect, Disconnect, GetStub
from pyVim.helpers import Log

counterInfoDict = {}
counterSem = threading.Semaphore()

def GetOptions():
    # Supports the command-line arguments listed below
    parser = OptionParser()
    parser.add_option("-H", "--host",
                      default="localhost",
                      help="Host to connect to.")
    parser.add_option("-u", "--user",
                      default="root",
                      help="User name to use when connecting to host.")
    parser.add_option("-p", "--password",
                      default="",
                      help="Password to use when connecting to host.")
    parser.add_option("-S", "--simHost",
                      default="localhost",
                      help="Simulator to connect to.")
    parser.add_option("-U", "--simUser",
                      default="root",
                      help="User name to use when connecting to simulator.")
    parser.add_option("-P", "--simPassword",
                      default="ca$hc0w",
                      help="Password to use when connecting to simulator.")
    parser.add_option("-R", "--enableReg",
                      default="false",
                      help="Enable or disable registry stats.")
    parser.add_option("-d", "--ds",
                      default="datastore1",
                      help="Datastore name for host.")
    parser.add_option("-D", "--simDs",
                      default="DS1",
                      help="Datastore name for simulator.")
    parser.add_option("-v", "--verbose",
                      default=False, action="store_true",
                      help="Log verbose")

    (options, _) = parser.parse_args()
    return options

def GetValidStatsFromEntity(entity):
   # Check the validity of the values of entity metrics
   stats = set()
   for metric in entity:
      for value in metric.value:
         idx = len(value.value) - 1;
         val = value.value[idx]
         if val == -1:
            Log("ERROR: Stat with counterId:%d and instance:'%s' for entity '%s' is still disabled" % \
                  (value.id.counterId, value.id.instance, metric.entity))
            Log("ERROR: Wrong last value - expected value different from -1 for time-stamp:'%s'" % \
                  (metric.sampleInfo[idx].timestamp))
         else:
            stats.add(value.id.counterId)
   return stats

def GetRegistryStats(perfManager, hostSystem):
   # Query registry stats
   cntrlblCntrs = perfManager.QueryPerfCounterInt()
   if cntrlblCntrs is None:
      Log("ERROR: Failed to get perfCounterInt through vim.PerformanceManager.QueryPerfCounterInt")
      exit(1)

   stub = GetStub()
   registry = Hostd.StatsRegistryManager('ha-internalsvc-statsregistrymgr', stub)
   if registry is None:
      Log("ERROR: Failed to get stats registry object")
      exit(1)
   statsRegistryStats = registry.QueryStatList()
   cntrlblCntrsIds = []
   metricIds = []

   # prepare a list of all controllable counters
   for cntr in cntrlblCntrs:
      cntrlblCntrsIds.append(cntr.key)
      metricId = vim.PerformanceManager.MetricId()
      metricId.counterId = cntr.key
      metricId.instance = "*"
      metricIds.append(metricId)

   querySpec = vim.PerformanceManager.QuerySpec()
   querySpec.entity = hostSystem
   querySpec.format = vim.PerformanceManager.Format.normal
   querySpec.metricId = metricIds;

   perfManager.EnableStat(cntrlblCntrsIds)
   # We should be able to obtain some data for all controllable counters
   # after 20 seconds, which is the default collection interval
   time.sleep(20 + 2)
   result = perfManager.QueryStats([querySpec])
   return GetValidStatsFromEntity(result)

def GetDepotStats(perfManager, entity):
   # Query depot stats for the entity (host, vm, etc.)
   querySpecs = []
   querySpec = vim.PerformanceManager.QuerySpec()
   querySpec.format = vim.PerformanceManager.Format.normal
   querySpec.entity = entity
   querySpec.metricId = perfManager.QueryAvailableMetric(entity)
   querySpec.intervalId = 20
   querySpecs.append(querySpec)
   result = perfManager.QueryStats(querySpecs)
   return GetValidStatsFromEntity(result)

def CreateTestVm(si, dsName):
   # Create a VM for testing
   vmName = "TestStatsVm1"

   # Destroy old VMs
   for vm1 in si.content.rootFolder.childEntity[0].vmFolder.childEntity:
      if vm1.name == vmName:
         if vm1.runtime.powerState != vim.VirtualMachine.PowerState.poweredOff:
            vm.PowerOff(vm1)
         vm1.Destroy()

   spec = vm.CreateQuickDummySpec(vmName, nic=1, memory=32, datastoreName=dsName)
   resPool = invt.GetResourcePool(si=si)
   vmFolder = invt.GetVmFolder(si=si)
   t = vmFolder.CreateVm(spec, pool=resPool)
   WaitForTask(t)
   vm1 = t.info.result

   Log("Created VM %s on %s" % (vm1.name, resPool.owner.host[0].name))

   devices = vmconfig.CheckDevice(vm1.GetConfig(), vim.vm.Device.VirtualEthernetCard)
   if len(devices) < 1:
      raise Exception("Failed to find nic")

   # Reconfigure to add network
   cspec = vim.vm.ConfigSpec()
   devices[0].GetConnectable().SetStartConnected(True)
   devices[0].GetConnectable().SetConnected(True)
   vmconfig.AddDeviceToSpec(cspec, devices[0],
                            vim.vm.Device.VirtualDeviceSpec.Operation.edit)
   vm.Reconfigure(vm1, cspec)
   vm.PowerOn(vm1)
   return vm1

def GetParams(hostName, userName, password):
   try:
      siHost = Connect(host=hostName, user=userName, pwd=password,
                       version="vim.version.version9")
   except vim.fault.HostConnectFault:
      Log("Failed to connect to %s" % hostName)
      raise

   atexit.register(Disconnect, siHost)
   perfManager = siHost.RetrieveContent().perfManager
   hostSystem = host.GetHostSystem(siHost)
   hbrManager = siHost.RetrieveInternalContent().hbrManager
   return siHost, perfManager, hostSystem, hbrManager

def EnableReplication(hbrManager,
                      vmname,
                      destination="127.0.0.1",
                      port=1234,
                      rpo=10,
                      quiesce = False):
   # Enable replication for the specified virtual machine
   repVmInfo = vim.vm.ReplicationConfigSpec()

   repVmInfo.SetVmReplicationId(vmname.GetConfig().GetUuid())
   repVmInfo.SetDestination(destination)
   repVmInfo.SetPort(port)
   repVmInfo.SetRpo(long(rpo))
   repVmInfo.SetQuiesceGuestEnabled(quiesce)
   repVmInfo.SetOppUpdatesEnabled(False)

   disks = []
   for device in vmname.GetConfig().GetHardware().GetDevice():
      if isinstance(device, vim.vm.Device.VirtualDisk):
         repDiskInfo = vim.vm.ReplicationConfigSpec.DiskSettings()
         repDiskInfo.SetKey(device.GetKey())
         repDiskInfo.SetDiskReplicationId(str(device.GetKey()))

         disks.append(repDiskInfo)

   repVmInfo.SetDisk(disks)

   WaitForTask(hbrManager.EnableReplication(vmname, repVmInfo))

class StatData():
   def __init__(self, host, user, password, datastore, enableReg=False, sim=False):
      self.host = host
      self.user = user
      self.password = password
      self.sim = sim
      self.datastore = datastore
      self.enableReg = enableReg

      self.vm = None
      self.vmDepotStats = None
      self.hostDepotStats = None
      self.regStats = None

def CollectStats(statData):
   si, perfManager, hostSystem, hbrManager = GetParams(statData.host,
                                                       statData.user,
                                                       statData.password)
   global counterInfoDict
   global counterSem
   # Add depot stats counter / name pairs
   counterSem.acquire()
   for info in perfManager.perfCounter:
      counterInfoDict[info.key] = "%s.%s.%s" % (info.groupInfo.key,
                                                info.nameInfo.key,
                                                info.rollupType)
   counterSem.release()

   statData.hostDepotStats = GetDepotStats(perfManager, hostSystem)

   statData.vm = CreateTestVm(si, statData.datastore)

   # Enable hbr replication for real host, don't need to do this for simulator
   if hbrManager is not None and not statData.sim:
      EnableReplication(hbrManager, statData.vm)
   elif not statData.sim:
      Log("Warning: hbrManager is None!");

   if statData.enableReg:
      # Add registry stats counter / name pairs
      counterInfo = perfManager.QueryPerfCounterInt()
      counterSem.acquire()
      for info in counterInfo:
         counterInfoDict[info.key] = "%s.%s.%s" % (info.groupInfo.key,
                                                   info.nameInfo.key,
                                                   info.rollupType)
      counterSem.release()
      statData.regStats = GetRegistryStats(perfManager, hostSystem)

   time.sleep(40) # Sleep to let stats populate

   statData.vmDepotStats = GetDepotStats(perfManager, statData.vm)
   vm.PowerOff(statData.vm)
   WaitForTask(statData.vm.Destroy())


def Main():
   global counterInfoDict
   # Process command line
   options = GetOptions()
   enableReg = True if options.enableReg == "true" else False

   realStatData = StatData(options.host,
                          options.user,
                          options.password,
                          options.ds,
                          enableReg)
   simStatData = StatData(options.simHost,
                          options.simUser,
                          options.simPassword,
                          options.simDs,
                          enableReg,
                          sim=True)

   thread = []
   thread.append(threading.Thread(target=CollectStats, args=(realStatData,)))
   thread.append(threading.Thread(target=CollectStats, args=(simStatData,)))

   for t in thread:
      t.start()
   for t in thread:
      t.join()

   status = "PASS"

   if enableReg:
      Log("Compare registry stats in real host and simulator")
      Log("--------------------------------------------------------------------")
      Log("Registry stat counters in host - total: %s" % len(realStatData.regStats))
      Log("Registry stat counters in simulator - total: %s" % len(simStatData.regStats))
      Log("   ")
      Log("Registry stats in host but not in simulator:")
      Log("--------------------------------------------------------------------")
      diffRegStats = False
      for key in realStatData.regStats:
         if key not in simStatData.regStats:
            Log("   %s : %s " % (key, counterInfoDict[key]))
            status = "FAIL"
            diffRegStats = True
      if not diffRegStats:
         Log("   NONE   ")
      Log("   ")

   Log("Compare host stats in real host and simulator")
   Log("--------------------------------------------------------------------")
   Log("Host depot stat counters in real host - total: %s" % len(realStatData.hostDepotStats))
   Log("Host depot stat counters in simulator - total: %s" % len(simStatData.hostDepotStats))
   Log("   ")
   Log("Host depot stats in host but not in simulator:")
   Log("--------------------------------------------------------------------")
   diffHostDepot = False
   for key in realStatData.hostDepotStats:
      if key not in simStatData.hostDepotStats:
         Log("   %s : %s " % (key, counterInfoDict[key]))
         status = "FAIL"
         diffHostDepot = True
   if not diffHostDepot:
      Log("   NONE   ")
   Log("   ")

   Log("Compare vm stats in real host and simulator")
   Log("--------------------------------------------------------------------")
   Log("Vm depot stat counters in real host - total: %s" % len(realStatData.vmDepotStats))
   Log("Vm depot stat counters in simulator - total: %s" % len(simStatData.vmDepotStats))
   Log("   ")
   Log("Vm depot stats in host but not in simulator:")
   Log("--------------------------------------------------------------------")
   diffVmDepot = False
   for key in realStatData.vmDepotStats:
      if key not in simStatData.vmDepotStats:
         Log("   %s : %s " % (key, counterInfoDict[key]))
         status = "FAIL"
         diffVmDepot = True
   if not diffVmDepot:
      Log("   NONE   ")
   Log("   ")

   if options.verbose and \
      len(realStatData.vmDepotStats) != len(simStatData.vmDepotStats):
      vmDepotStats = list(simStatData.vmDepotStats - realStatData.vmDepotStats)
      vmDepotStats.sort()
      for key in vmDepotStats:
         Log("   %s : %s " % (key, counterInfoDict[key]))

   Log("TEST RUN COMPLETE: " + status)
   if status != "PASS":
      return 1
   return 0

# Start program
if __name__ == "__main__":
  sys.exit(Main())
