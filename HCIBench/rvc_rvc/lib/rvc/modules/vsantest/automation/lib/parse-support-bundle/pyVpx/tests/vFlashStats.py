#!/usr/bin/python

#
# how to call:
# ./vim/py/py.sh ./vim/py/tests/vFlashStats.py -h <host> -u <user> -p <password> -v <vmname> -d <diskInstance>
# ./vim/py/py.sh ./vim/py/tests/vFlashStats.py -h "10.112.185.87" -u "root" -p "" -v "VM01" -d "scsi0:1"
#

from __future__ import print_function

import sys
import datetime
from pyVmomi import Vim
from pyVmomi import VmomiSupport
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import arguments
from pyVim import vm, folder, invt
from pyVim.helpers import Log,StopWatch
import atexit

# Process command line
supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                  (["u:", "user="], "root", "User name", "user"),
                  (["p:", "pwd="], "", "Password", "pwd"),
                  (["v:", "vmname="], "VM01", "Virtual Machine Name", "vmname"),
                  (["d:", "diskInstance="], "scsi0:1", "Disk Instance", "diskInstance"),
                  (["m:", "moduleInstance="], "vfc", "Module Instance", "moduleInstance"),
                ]

supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage") ]

args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
if args.GetKeyValue("usage") == True:
   args.Usage()
   sys.exit(0)

# Connect
si = Connect(host=args.GetKeyValue("host"),
             user=args.GetKeyValue("user"),
             pwd=args.GetKeyValue("pwd"))
atexit.register(Disconnect, si)

vmname = args.GetKeyValue("vmname")
vm1 = folder.Find(vmname)

content = si.RetrieveContent()
dataCenter = content.GetRootFolder().GetChildEntity()[0]
hostFolder = dataCenter.GetHostFolder()
computeResource = hostFolder.GetChildEntity()[0]
hostSystem = computeResource.GetHost()[0]

diskInstance =  args.GetKeyValue("diskInstance");
moduleInstance = args.GetKeyValue("moduleInstance");

perfManager = content.GetPerfManager()
counterInfos = perfManager.perfCounter

def main():
   # test vFC disk stats
   test1()

   # test vFlashModule stats
   test2()

def test1():
   status = "PASS"
   try:
      counterID1 = "vFlashCacheIops"
      counterID2 = "vFlashCacheLatency"
      counterID3 = "vFlashCacheThroughput"

      # check if VFlash Cache counter ID is present
      idx1 = -1;
      idx2 = -1;
      idx3 = -1;

      for i in range(0, len(counterInfos) - 1):
         #print(counterInfos[i])
         if (counterInfos[i].nameInfo.key == counterID1):
            print(counterInfos[i])
            print("Found %s\n" % counterID1)
            idx1 = i
         elif (counterInfos[i].nameInfo.key == counterID2):
            print(counterInfos[i])
            print("Found %s\n" % counterID2)
            idx2 = i
         elif (counterInfos[i].nameInfo.key == counterID3):
            print(counterInfos[i])
            print("Found %s\n" % counterID3)
            idx3 = i

      if idx1 == -1 or idx2 == -1 or idx3 == -1:
         raise ValueError("Invalid counter index")

      # Query stats
      currTime = datetime.datetime.now()
      thirtyMins = datetime.timedelta(minutes = 30)
      sixHours = datetime.timedelta(hours = 6)

      querySpecs = []

      querySpec1 = Vim.PerformanceManager.QuerySpec()
      querySpec2 = Vim.PerformanceManager.QuerySpec()
      querySpec3 = Vim.PerformanceManager.QuerySpec()

      querySpec1.entity = vm1
      querySpec2.entity = vm1
      querySpec3.entity = vm1

      metricId1 = Vim.PerformanceManager.MetricId()
      metricId1.counterId = counterInfos[idx1].key
      metricId1.instance  = diskInstance
      querySpec1.metricId.append(metricId1)

      metricId2 = Vim.PerformanceManager.MetricId()
      metricId2.counterId = counterInfos[idx2].key
      metricId2.instance  = diskInstance
      querySpec2.metricId.append(metricId2)

      metricId3 = Vim.PerformanceManager.MetricId()
      metricId3.counterId = counterInfos[idx3].key
      metricId3.instance  = diskInstance
      querySpec3.metricId.append(metricId3)

      querySpec1.intervalId = 20
      querySpec2.intervalId = 20
      querySpec3.intervalId = 20

      querySpecs.append(querySpec1)
      querySpecs.append(querySpec2)
      querySpecs.append(querySpec3)

      # Query stats
      entityMetrics = perfManager.QueryStats(querySpecs)
      if len(entityMetrics) == 0:
         print("No stats found from querySpec %s!!" % querySpecs)
         status = "FAIL"
      else:
         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[0].value]

         print('\n\nCounter Name: %s' % counterInfos[idx1].nameInfo.key)
         print('\n'.join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[1].value]

         print('\n\nCounter Name: %s' % counterInfos[idx2].nameInfo.key)
         print('\n' . join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[2].value]

         print('\n\nCounter Name: %s' % counterInfos[idx3].nameInfo.key)
         print('\n'.join(res))

   except Exception as e:
      raise
      print("\tFailed test due to exception: " + str(e))
      status = "FAIL"
   finally:
      pass
   print("TEST 1 COMPLETE: " + status)



def test2():
   print("\n\nTEST 2 START")
   status = "PASS"
   try:
      counterID1 = "numActiveVMDKs"

      idx1 = -1

      for i in range(0, len(counterInfos)):
         #print(counterInfos[i])
         if (counterInfos[i].nameInfo.key == counterID1):
            print(counterInfos[i])
            print("Found %s" % counterID1)
            idx1 = i

      if idx1 == -1:
         raise ValueError("Invalid counter index")

      # Query stats
      currTime = datetime.datetime.now()
      thirtyMins = datetime.timedelta(minutes = 30)
      sixHours = datetime.timedelta(hours = 6)

      querySpecs = []

      querySpec1 = Vim.PerformanceManager.QuerySpec()

      querySpec1.entity = hostSystem

      metricId1 = Vim.PerformanceManager.MetricId()
      metricId1.counterId = counterInfos[idx1].key
      metricId1.instance  = moduleInstance
      querySpec1.metricId.append(metricId1)

      querySpec1.intervalId = 20

      querySpecs.append(querySpec1)

      # Query stats
      entityMetrics = perfManager.QueryStats(querySpecs)
      if len(entityMetrics) == 0:
         print("No stats found from querySpec %s!!" % querySpecs)
         status = "FAIL"
      else:
         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[0].value]

         print('\n\nCounter Name: %s' % counterInfos[idx1].nameInfo.key)
         print('\n'.join(res))

   except Exception as e:
      raise
      print("\tFailed test due to exception: " + str(e))
      status = "FAIL"
   finally:
      pass
   print("TEST 2 COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()
