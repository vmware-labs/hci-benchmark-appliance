#!/usr/bin/python

from __future__ import print_function

import sys
import atexit
import time
from pyVmomi import Vim, Hostd
from pyVmomi import VmomiSupport
from pyVim.connect import SmartConnect, Disconnect, GetStub
from optparse import OptionParser

def GetOptions():
    """
    Supports the command-line arguments listed below
    """
    parser = OptionParser()
    parser.add_option("-H", "--host",
                      default="localhost",
                      help="Remote host to connect to.")
    parser.add_option("-u", "--user",
                      default="root",
                      help="User name to use when connecting to hostd.")
    parser.add_option("-p", "--password",
                      default="",
                      help="Password to use when connecting to hostd.")
    (options, _) = parser.parse_args()
    return options

def Main():
   # Process command line
   options = GetOptions()

   si = SmartConnect(host=options.host,
                     user=options.user,
                     pwd=options.password)
   atexit.register(Disconnect, si)

   content = si.RetrieveContent()
   rootFolder = content.GetRootFolder()
   dataCenter = rootFolder.GetChildEntity()[0]
   hostFolder = dataCenter.GetHostFolder()
   compResrce = hostFolder.GetChildEntity()[0]
   localHost = compResrce.GetHost()[0]
   prfrmncMngr = content.perfManager

   cntrlblCntrs = prfrmncMngr.GetPerfCounterInt()

   if cntrlblCntrs is None:
      print("ERROR: Failed to get perfCounterInt through vim.PerformanceManager.GetCounterInfoInt")
      exit(1)

   namedCntrlblCntrs = {}
   for cntr in cntrlblCntrs:
      name = cntr.groupInfo.key + "." + cntr.nameInfo.key
      namedCntrlblCntrs[name] = cntr

   stub = GetStub()
   registry = Hostd.StatsRegistryManager('ha-internalsvc-statsregistrymgr', stub)
   if registry is None:
      print("ERROR: Failed to get stats registry object")
      exit(1)

   statsRegistryStats = registry.QueryStatList()

   #
   # Check whether all valid StatsRegistry stats are in perfCounterInt property
   #
   checked = {}
   for srStat in statsRegistryStats:
      attribs = srStat.statDef.attribute
      if len(attribs) <= 1 or (len(attribs) == 2 and (attribs[0].type == "vm" or attribs[0].type == "resPool")):
         name = srStat.statDef.name
         found = namedCntrlblCntrs[name]
         if found is None:
            print("ERROR: StatsRegistry stat %s is not present in vim.PerformanceManager" % name)
            exit(1)
         if name in checked:
            continue
         checked[name] = name
         if srStat.statDef.unit != found.unitInfo.key:
            print("ERROR: StatsRegistry stat %s is different in vim.PerformanceManager" % name)
            print(" INFO: Wrong unit - expected '%s', but got '%s'"
                  % (srStat.statDef.unit, found.unitInfo.key))
            exit(1)
         # -2147483648 == 0x80000000 in int32 type
         expectedCounterId = srStat.id - 2147483648
         if expectedCounterId != found.key:
            print("ERROR: StatsRegistry stat %s is different in vim.PerformanceManager" % name)
            print(" INFO: Wrong id - expected '%s', but got '%s'" % (expectedCounterId, found.key))
            exit(1)

   cntrlblCntrsIds = []
   metricIds = []

   # prepare a list of our controllable counters
   for cntr in cntrlblCntrs:
      cntrlblCntrsIds.append(cntr.key)
      metricId = Vim.PerformanceManager.MetricId()
      metricId.counterId = cntr.key
      metricId.instance = "*"
      metricIds.append(metricId)

   querySpec = Vim.PerformanceManager.QuerySpec()
   querySpec.entity = localHost
   querySpec.maxSample = 1
   querySpec.intervalId = 20
   querySpec.format = Vim.PerformanceManager.Format.normal
   querySpec.metricId = metricIds;

   #
   # Enable all possible counters
   #
   prfrmncMngr.EnableStat(cntrlblCntrsIds)

   #
   # We should be able to obtain some data for all controllable counters
   # after 20 seconds, which is the default collection interval
   #
   time.sleep(20 + 2)
   result = prfrmncMngr.QueryStats([querySpec])

   for metric in result:
      for value in metric.value:
         idx = len(value.value) - 1;
         val = value.value[idx]
         if val == -1:
            print("ERROR: Stat with counterId:%d and instance:'%s' "
                  "for entity '%s' is still disabled"
                  % (value.id.counterId, value.id.instance, metric.entity))
            print(" INFO: Wrong last value - expected value different from -1 "
                  "for time-stamp:'%s'" % (metric.sampleInfo[idx].timestamp))
            exit(1)

   #
   # Disable all possible counters
   #
   prfrmncMngr.DisableStat(cntrlblCntrsIds)

   #
   # The controllable counters should be disabled now and after 20 more
   # seconds we should see empty samples (-1s)
   #
   time.sleep(20 + 2)
   result = prfrmncMngr.QueryStats([querySpec])

   for metric in result:
      for value in metric.value:
         idx = len(value.value) - 1;
         val = value.value[idx]
         if val != -1:
            print("ERROR: Stat with counterId:%d and instance:'%s' "
                  "for entity '%s' is still enabled" %
                  (value.id.counterId, value.id.instance, metric.entity))
            print("INFO: Wrong last value - expected -1, but got %d "
                  "for time-stamp:'%s'"
                  % (val, metric.sampleInfo[idx].timestamp))
            exit(1)

   print("SUCCESS!")


# Start program
if __name__ == "__main__":
    Main()
