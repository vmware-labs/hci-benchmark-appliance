#!/usr/bin/python

import copy

import sys
import atexit
import time
from datetime import datetime, timedelta, tzinfo

import pyVmomi
import pyVim
from pyVim import connect
from pyVim.connect import Connect, Disconnect, GetStub
from optparse import OptionParser

# This is needed in order to work with Puthon versions before 3
ZERO = timedelta(0)
class UTC(tzinfo):
    def utcoffset(self, dt):
        return ZERO
    def tzname(self, dt):
        return "UTC"
    def dst(self, dt):
        return ZERO
utc = UTC()

# In seconds:
SUMMARY_INTERVAL   = 20 * 60
SUMMARY_INTERVALID =  5 * 60
QUERY_INTERVAL     = 20


''' These are all currently (2015/02/12) available stats from Vigor.
    However, below we are querying for all "guest.*" stats just in case.
STATS_TO_QUERY = [
   # These are common ("common/*"):
   "guest.memTotal",
   "guest.memFree",
   "guest.memNeeded"
   "guest.pageSize",
   "guest.hugePageSize",
   "guest.pageInRate",
   "guest.pageOutRate",
   "guest.pageSwapInRate",
   "guest.pageSwapOutRate",
   "guest.contextSwapRate",
   "guest.processCreationRate",
   "guest.threadCreationRate",
   # These are Linux specific ("linux/*"):
   "guest.pageFaultRate",
   "guest.pageMajorFaultRate",
   "guest.pageFreeRate",
   "guest.pageStealRate",
   "guest.pageSwapScanRate",
   "guest.pageDirectScanRate",
   "guest.swappiness",
   "guest.lowWaterMark",
   "guest.memAvailable",
   "guest.memActiveFile",
   "guest.memInactiveFile",
   "guest.memSlabReclaim",
   "guest.hugePagesTotal",
   "guest.hugePagesFree",
   "guest.memBuffers",
   "guest.memCached",
   "guest.memInactive",
   "guest.memPinned",
   "guest.memSwapTotal",
   "guest.memSwapFree",
   "guest.memSwapCached",
   "guest.memDirty",
   "guest.memCommitted",
   # These are Windows specific ("windows/*"):
   "guest.systemCache",
   "guest.standbyCore",
   "guest.standbyNormal",
   "guest.standbyReserve",
   "guest.mmAvailable",
   "guest.modifiedPageList",
   "guest.pageFileTotal",
   "guest.pageFileUsage",
   "guest.pagedPoolResident",
   "guest.systemCodeResident",
   "guest.systemDriverResident",
   "guest.nonpagedPool",
   "guest.cacheBytes",
   "guest.freeSystemPtes",
   "guest.commitLimit",
   "guest.committed",
   "guest.privateWorkingSet",
   "guest.diskReadRate",
   "guest.diskWriteRate"
]
'''

def GetOptions():
    """
    Supports the command-line arguments listed below
    """
    parser = OptionParser()
    parser.add_option("-H", "--host",
                      default="sof-23244-srv",
                      help="Remote host to connect to.")
    parser.add_option("-u", "--user",
                      default="root",
                      help="User name to use when connecting to hostd.")
    parser.add_option("-p", "--password",
                      default="",
                      help="Password to use when connecting to hostd.")
    (options, _) = parser.parse_args()
    return options

def main():
   # Process command line
   options = GetOptions()

   serviceInstance = Connect(host = options.host,
                             user = options.user,
#                             namespace = "vim25/dev2",
                             pwd = options.password)
   atexit.register(Disconnect, serviceInstance)

   content = serviceInstance.RetrieveContent()
   isESX = content.GetAbout().GetApiType() == "HostAgent"
   perfMgr = content.perfManager

   rootFolder = content.GetRootFolder()

   metricIds = []
   idToNameMap = {}
   nameToIdMap = {}
   countersToEnable = []

   # Just in case - take all available counters on the server
   perfCounters = perfMgr.perfCounter
   try:
      perfCounters += perfMgr.QueryPerfCounterInt();
      print "Counters available on the host (%d):" % (len(perfCounters))
      for cntr in perfCounters:
         print "%d -> %s.%s [%s]" % (cntr.key, cntr.groupInfo.key, cntr.nameInfo.key, cntr.unitInfo.key)
   except: pass

   STATS_TO_QUERY =[]
   for cntrInfo in perfCounters:
      statGroup = cntrInfo.groupInfo.key
      statName = statGroup + "." + cntrInfo.nameInfo.key
      enabled = True if cntrInfo.key >= 0 else cntrInfo.enabled
      idToNameMap[cntrInfo.key] = (statName, enabled, cntrInfo.unitInfo.label)
      nameToIdMap[statName] = cntrInfo.key
      #if statGroup == 'cpu':
      if cntrInfo.key < 0:
         STATS_TO_QUERY.append(statName)

   for statToQuery in STATS_TO_QUERY:
      if statToQuery in nameToIdMap:
         counterId = nameToIdMap[statToQuery]
         metricId = pyVmomi.Vim.PerformanceManager.MetricId()
         metricId.counterId = counterId
         metricId.instance = "*"
         metricIds.append(metricId)
         enabled = idToNameMap[counterId][1]
         print "Requesting counterID=%12d ('%40s') which %s" % (counterId, statToQuery, "is already enabled" if enabled else "must be enabled")
         if not isESX or not enabled:
            countersToEnable.append(counterId);

   # TODO: perfMgr.EnableStat should be used only against HostD.
   #       Different mechanism is needed for VpxD.
   if len(countersToEnable) > 0:
      print "Enabling counters '%s'..." % (countersToEnable)
      if not isESX:
         newLevelMappings = []
         for counterToEnable in countersToEnable:
            currentLevelMapping = pyVmomi.Vim.PerformanceManager.CounterLevelMapping()
            currentLevelMapping.counterId = counterToEnable
            currentLevelMapping.aggregateLevel = 1
            newLevelMappings.append(currentLevelMapping)
         perfMgr.UpdateCounterLevelMapping(newLevelMappings)
      else:
         perfMgr.EnableStat(countersToEnable);
      print "...will be available shortly - HostD needs some time to start collecting these!"


   summarySpecs = []
   hostsNames = {}
   switchesNames = {}
   virtualMachines = {}
   #
   # Create queries for all VMs from all available data-centers
   # This is working against both: HostD and VpxD
   #
   dataCenters = rootFolder.GetChildEntity()
   for dataCenter in dataCenters:
      dataCenterName = dataCenter.GetName()
      vmsFolder = dataCenter.GetVmFolder()
      vms = vmsFolder.GetChildEntity()

      if vms:
         for virtualMachine in vms:
            if isinstance(virtualMachine, pyVmomi.vim.VirtualMachine):
               virtualMachineName = virtualMachine.GetName()
               virtualMachines[virtualMachine] = virtualMachineName
               print "Requesting for %s ('%s') from %s ('%s')" % (virtualMachine, virtualMachineName, dataCenter, dataCenterName)
               vmQuerySpec = pyVmomi.Vim.PerformanceManager.QuerySpec()
               vmQuerySpec.entity = virtualMachine
               vmQuerySpec.intervalId = SUMMARY_INTERVALID
               vmQuerySpec.format = pyVmomi.Vim.PerformanceManager.Format.csv
               vmQuerySpec.metricId = metricIds
               summarySpecs.append(vmQuerySpec)
      else:
         print "No VMs found for %s ('%s')!" % (dataCenter, dataCenterName)

      hostsFolder = dataCenter.GetHostFolder()
      computeResources = hostsFolder.GetChildEntity()
      for computeResource in computeResources:
         hosts = computeResource.GetHost()
         for host in hosts:
            hostName = host.GetName()
            hostsNames[host] = hostName
            print "Requesting for %s ('%s') from %s in %s ('%s')" % (host, hostName, computeResource, dataCenter, dataCenterName)
            hostQuerySpec = pyVmomi.Vim.PerformanceManager.QuerySpec()
            hostQuerySpec.entity = host
            hostQuerySpec.intervalId = SUMMARY_INTERVALID
            hostQuerySpec.format = pyVmomi.Vim.PerformanceManager.Format.csv
            hostQuerySpec.metricId = metricIds
            summarySpecs.append(hostQuerySpec)

      networkFolder = dataCenter.GetNetworkFolder()
      networks = networkFolder.GetChildEntity()
      for network in networks:
         if type(network) is pyVmomi.vim.dvs.VmwareDistributedVirtualSwitch:
            switchName = network.GetName()
            switchesNames[network] = switchName
            print "Requesting for %s ('%s') in %s ('%s')" % (network, switchName, dataCenter, dataCenterName)
            dvsQuerySpec = pyVmomi.Vim.PerformanceManager.QuerySpec()
            dvsQuerySpec.entity = network
            dvsQuerySpec.intervalId = SUMMARY_INTERVALID
            dvsQuerySpec.format = pyVmomi.Vim.PerformanceManager.Format.csv
            dvsQuerySpec.metricId = metricIds
            summarySpecs.append(dvsQuerySpec)
            
            
   querySpecs = copy.deepcopy(summarySpecs)
   for spec in querySpecs:
      # real-time interval
      spec.intervalId = 20
      # we need only one sample - the last one
      spec.maxSample = 1
      # Request Format.normal - we don't want to convert string to int64
      spec.format = pyVmomi.Vim.PerformanceManager.Format.normal

   lastSummarized = 0
   summaryIteration = 1
   queryIteration = 1
   prevTime = None
   while True:
      print "=" * 80

      # Query current value of the stats on every QUERY_INTERVAL seconds...
      queryResult = perfMgr.QueryStats(querySpecs)
      print "Last samples (iteration=%d):" % (queryIteration)
      for entityMetric in queryResult:
         for series in entityMetric.value:
            counterId = series.id.counterId
            instanceStr = series.id.instance
            statName = idToNameMap[counterId][0]
            entity = entityMetric.entity
            if isinstance(entity, pyVmomi.vim.VirtualMachine):
               entityName = virtualMachines[entity]
            elif isinstance(entity, pyVmomi.vim.dvs.VmwareDistributedVirtualSwitch):
               entityName = switchesNames[entity]
            else:
               entityName = hostsNames[entity]
            unit = idToNameMap[counterId][2]
            # Last sample
            statValue = series.value[-1]
            # -1 is special value returned by vim.PerformanceManager indicating unavailable stat
            if statValue > -1:
               if unit == '%':
                  # Percent is returned as a 100ths of percent in integer value (e.g. 56.78% == 5678)
                  print "%12d -> %40s('%s', '%s') = %.2f %s" % (counterId, statName, entityName, instanceStr, statValue / 100.0, unit)
               else:
                  # All other values are always positive
                  print "%12d -> %40s('%s', '%s') = %d %s" % (counterId, statName, entityName, instanceStr, statValue, unit)
            else:
               print "%12d -> %40s('%s', '%s') = N/A" % (counterId, statName, entityName, instanceStr)

      if isESX:
         # ...and summarize them on every SUMMARY_INTERVAL seconds.
         if lastSummarized == 0:
            # Always take the server local time (this is very important for VpxD connection)
            nowOnServer = serviceInstance.CurrentTime().replace(tzinfo=utc)
            startTime = (nowOnServer - timedelta(seconds=SUMMARY_INTERVAL)) if not prevTime else prevTime
            endTime = nowOnServer
            for spec in summarySpecs:
               spec.startTime = startTime
               spec.endTime = endTime
            prevTime = endTime
            summaryResult = perfMgr.SummarizeStats(summarySpecs)
            print "Summarized stats (iteration=%d) from '%s' to '%s'" % (summaryIteration, startTime, endTime)
            #print summaryResult
            summaryIteration = summaryIteration + 1

      time.sleep(QUERY_INTERVAL)
      queryIteration = queryIteration + 1
      lastSummarized = lastSummarized + QUERY_INTERVAL
      if lastSummarized >= SUMMARY_INTERVAL:
         lastSummarized = 0

# Start program
if __name__ == "__main__":
   main()
