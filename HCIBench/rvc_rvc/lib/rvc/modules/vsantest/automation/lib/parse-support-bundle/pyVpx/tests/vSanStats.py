#!/usr/bin/python

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
                  (["d:", "domInstance="], "xxx", "DOM Object instance", "domInstance"),
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

content = si.RetrieveContent()
dataCenter = content.GetRootFolder().GetChildEntity()[0]
hostFolder = dataCenter.GetHostFolder()
computeResource = hostFolder.GetChildEntity()[0]
hostSystem = computeResource.GetHost()[0]

domInstance = args.GetKeyValue("domInstance");

perfManager = content.GetPerfManager()
counterInfos = perfManager.perfCounter

def main():
   # test VSAN DOM Object stats
   test1()
   test2()
   test3()

def test1():
   status = "PASS"
   try:
      counterID1 = "readIops"
      counterID2 = "readThroughput"
      counterID3 = "readAvgLatency"
      counterID4 = "readMaxLatency"
      counterID5 = "readCacheHitRate"
      counterID6 = "readCongestion"

      # check if VSan counter ID is present
      idx1 = -1;
      idx2 = -1;
      idx3 = -1;
      idx4 = -1;
      idx5 = -1;
      idx6 = -1;

      for i in range(0, len(counterInfos)):
         if (counterInfos[i].nameInfo.key == counterID1):
            #print(counterInfos[i])
            print("Found %s\n" % counterID1)
            idx1 = i
         elif (counterInfos[i].nameInfo.key == counterID2):
            #print(counterInfos[i])
            print("Found %s\n" % counterID2)
            idx2 = i
         elif (counterInfos[i].nameInfo.key == counterID3):
            #print(counterInfos[i])
            print("Found %s\n" % counterID3)
            idx3 = i
         elif (counterInfos[i].nameInfo.key == counterID4):
            #print(counterInfos[i])
            print("Found %s\n" % counterID4)
            idx4 = i
         elif (counterInfos[i].nameInfo.key == counterID5):
            #print counterInfos[i]
            print("Found %s\n" % counterID5)
            idx5 = i
         elif (counterInfos[i].nameInfo.key == counterID6):
            #print(counterInfos[i])
            print("Found %s\n" % counterID6)
            idx6 = i

      if idx1 == -1 or idx2 == -1 or idx3 == -1 or idx4 == -1 or idx5 == -1 or idx6 == -1:
         raise ValueError("Invalid counter index")

      # Query stats
      querySpecs = []

      querySpec1 = Vim.PerformanceManager.QuerySpec()
      metricId1 = Vim.PerformanceManager.MetricId()
      metricId1.counterId = counterInfos[idx1].key
      metricId1.instance  = domInstance;
      querySpec1.metricId.append(metricId1)
      querySpec1.intervalId = 20
      querySpec1.entity = hostSystem

      querySpec2 = Vim.PerformanceManager.QuerySpec()
      metricId2 = Vim.PerformanceManager.MetricId()
      metricId2.counterId = counterInfos[idx2].key
      metricId2.instance  = domInstance;
      querySpec2.metricId.append(metricId2)
      querySpec2.intervalId = 20
      querySpec2.entity = hostSystem

      querySpec3 = Vim.PerformanceManager.QuerySpec()
      metricId3 = Vim.PerformanceManager.MetricId()
      metricId3.instance  = domInstance;
      metricId3.counterId = counterInfos[idx3].key
      querySpec3.metricId.append(metricId3)
      querySpec3.intervalId = 20
      querySpec3.entity = hostSystem

      querySpec4 = Vim.PerformanceManager.QuerySpec()
      metricId4 = Vim.PerformanceManager.MetricId()
      metricId4.instance  = domInstance;
      metricId4.counterId = counterInfos[idx4].key
      querySpec4.metricId.append(metricId4)
      querySpec4.intervalId = 20
      querySpec4.entity = hostSystem

      querySpec5 = Vim.PerformanceManager.QuerySpec()
      metricId5 = Vim.PerformanceManager.MetricId()
      metricId5.instance  = domInstance;
      metricId5.counterId = counterInfos[idx5].key
      querySpec5.metricId.append(metricId5)
      querySpec5.intervalId = 20
      querySpec5.entity = hostSystem

      querySpec6 = Vim.PerformanceManager.QuerySpec()
      metricId6 = Vim.PerformanceManager.MetricId()
      metricId6.instance  = domInstance;
      metricId6.counterId = counterInfos[idx6].key
      querySpec6.metricId.append(metricId6)
      querySpec6.intervalId = 20
      querySpec6.entity = hostSystem

      querySpecs.append(querySpec1)
      querySpecs.append(querySpec2)
      querySpecs.append(querySpec3)
      querySpecs.append(querySpec4)
      querySpecs.append(querySpec5)
      querySpecs.append(querySpec6)

      # Query stats
      entityMetrics = perfManager.QueryStats(querySpecs)
      if len(entityMetrics) == 0:
         print("No stats found from querySpec %s!!" % querySpecs)
         status = "FAIL"
      else:
         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[0].value]

         print('\n\nCounter Name:', counterInfos[idx1].nameInfo.key)
         print('\n'.join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[1].value]

         print('\n\nCounter Name:', counterInfos[idx2].nameInfo.key)
         print('\n' . join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[2].value]

         print('\n\nCounter Name:', counterInfos[idx3].nameInfo.key)
         print('\n'.join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[3].value]

         print('\n\nCounter Name:', counterInfos[idx4].nameInfo.key)
         print('\n'.join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[4].value]

         print('\n\nCounter Name:', counterInfos[idx5].nameInfo.key)
         print('\n'.join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[5].value]

         print('\n\nCounter Name:', counterInfos[idx6].nameInfo.key)
         print('\n'.join(res))

   except Exception as e:
      raise
      print("\tFailed test due to exception: " + str(e))
      status = "FAIL"
   finally:
      pass
   print("TEST 1 COMPLETE: " + status)


def test2():
   status = "PASS"
   try:
      counterID1 = "writeIops"
      counterID2 = "writeThroughput"
      counterID3 = "writeAvgLatency"
      counterID4 = "writeMaxLatency"
      counterID5 = "writeCongestion"

      # check if VSan counter ID is present
      idx1 = -1;
      idx2 = -1;
      idx3 = -1;
      idx4 = -1;
      idx5 = -1;

      for i in range(0, len(counterInfos)):
         if (counterInfos[i].nameInfo.key == counterID1):
            print("Found %s\n" % counterID1)
            idx1 = i
         elif (counterInfos[i].nameInfo.key == counterID2):
            print("Found %s\n" % counterID2)
            idx2 = i
         elif (counterInfos[i].nameInfo.key == counterID3):
            print("Found %s\n" % counterID3)
            idx3 = i
         elif (counterInfos[i].nameInfo.key == counterID4):
            print("Found %s\n" % counterID4)
            idx4 = i
         elif (counterInfos[i].nameInfo.key == counterID5):
            print("Found %s\n" % counterID5)
            idx5 = i

      if idx1 == -1 or idx2 == -1 or idx3 == -1 or idx4 == -1 or idx5 == -1:
         raise ValueError("Invalid counter index")

      # Query stats
      querySpecs = []

      querySpec1 = Vim.PerformanceManager.QuerySpec()
      metricId1 = Vim.PerformanceManager.MetricId()
      metricId1.counterId = counterInfos[idx1].key
      metricId1.instance  = domInstance;
      querySpec1.metricId.append(metricId1)
      querySpec1.intervalId = 20
      querySpec1.entity = hostSystem

      querySpec2 = Vim.PerformanceManager.QuerySpec()
      metricId2 = Vim.PerformanceManager.MetricId()
      metricId2.counterId = counterInfos[idx2].key
      metricId2.instance  = domInstance;
      querySpec2.metricId.append(metricId2)
      querySpec2.intervalId = 20
      querySpec2.entity = hostSystem

      querySpec3 = Vim.PerformanceManager.QuerySpec()
      metricId3 = Vim.PerformanceManager.MetricId()
      metricId3.instance  = domInstance;
      metricId3.counterId = counterInfos[idx3].key
      querySpec3.metricId.append(metricId3)
      querySpec3.intervalId = 20
      querySpec3.entity = hostSystem

      querySpec4 = Vim.PerformanceManager.QuerySpec()
      metricId4 = Vim.PerformanceManager.MetricId()
      metricId4.instance  = domInstance;
      metricId4.counterId = counterInfos[idx4].key
      querySpec4.metricId.append(metricId4)
      querySpec4.intervalId = 20
      querySpec4.entity = hostSystem

      querySpec5 = Vim.PerformanceManager.QuerySpec()
      metricId5 = Vim.PerformanceManager.MetricId()
      metricId5.instance  = domInstance;
      metricId5.counterId = counterInfos[idx5].key
      querySpec5.metricId.append(metricId5)
      querySpec5.intervalId = 20
      querySpec5.entity = hostSystem

      querySpecs.append(querySpec1)
      querySpecs.append(querySpec2)
      querySpecs.append(querySpec3)
      querySpecs.append(querySpec4)
      querySpecs.append(querySpec5)

      # Query stats
      entityMetrics = perfManager.QueryStats(querySpecs)
      if len(entityMetrics) == 0:
         print("No stats found from querySpec %s!!" % querySpecs)
         status = "FAIL"
      else:
         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[0].value]

         print('\n\nCounter Name:', counterInfos[idx1].nameInfo.key)
         print('\n'.join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[1].value]

         print('\n\nCounter Name:', counterInfos[idx2].nameInfo.key)
         print('\n' . join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[2].value]

         print('\n\nCounter Name:', counterInfos[idx3].nameInfo.key)
         print('\n'.join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[3].value]

         print('\n\nCounter Name:', counterInfos[idx4].nameInfo.key)
         print('\n'.join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[4].value]

         print('\n\nCounter Name:', counterInfos[idx5].nameInfo.key)
         print('\n'.join(res))

   except Exception as e:
      raise
      print("\tFailed test due to exception: " + str(e))
      status = "FAIL"
   finally:
      pass
   print("TEST 2 COMPLETE: " + status)


def test3():
   status = "PASS"
   try:
      counterID1 = "recoveryWriteIops"
      counterID2 = "recoveryWriteThroughput"
      counterID3 = "recoveryWriteAvgLatency"
      counterID4 = "recoveryWriteMaxLatency"
      counterID5 = "recoveryWriteCongestion"

      # check if VSan counter ID is present
      idx1 = -1;
      idx2 = -1;
      idx3 = -1;
      idx4 = -1;
      idx5 = -1;

      for i in range(0, len(counterInfos)):
         if (counterInfos[i].nameInfo.key == counterID1):
            print("Found %s\n" % counterID1)
            idx1 = i
         elif (counterInfos[i].nameInfo.key == counterID2):
            print("Found %s\n" % counterID2)
            idx2 = i
         elif (counterInfos[i].nameInfo.key == counterID3):
            print("Found %s\n" % counterID3)
            idx3 = i
         elif (counterInfos[i].nameInfo.key == counterID4):
            print("Found %s\n" % counterID4)
            idx4 = i
         elif (counterInfos[i].nameInfo.key == counterID5):
            print("Found %s\n" % counterID5)
            idx5 = i

      if idx1 == -1 or idx2 == -1 or idx3 == -1 or idx4 == -1 or idx5 == -1:
         raise ValueError("Invalid counter index")

      # Query stats
      querySpecs = []

      querySpec1 = Vim.PerformanceManager.QuerySpec()
      metricId1 = Vim.PerformanceManager.MetricId()
      metricId1.counterId = counterInfos[idx1].key
      metricId1.instance  = domInstance;
      querySpec1.metricId.append(metricId1)
      querySpec1.intervalId = 20
      querySpec1.entity = hostSystem

      querySpec2 = Vim.PerformanceManager.QuerySpec()
      metricId2 = Vim.PerformanceManager.MetricId()
      metricId2.counterId = counterInfos[idx2].key
      metricId2.instance  = domInstance;
      querySpec2.metricId.append(metricId2)
      querySpec2.intervalId = 20
      querySpec2.entity = hostSystem

      querySpec3 = Vim.PerformanceManager.QuerySpec()
      metricId3 = Vim.PerformanceManager.MetricId()
      metricId3.instance  = domInstance;
      metricId3.counterId = counterInfos[idx3].key
      querySpec3.metricId.append(metricId3)
      querySpec3.intervalId = 20
      querySpec3.entity = hostSystem

      querySpec4 = Vim.PerformanceManager.QuerySpec()
      metricId4 = Vim.PerformanceManager.MetricId()
      metricId4.instance  = domInstance;
      metricId4.counterId = counterInfos[idx4].key
      querySpec4.metricId.append(metricId4)
      querySpec4.intervalId = 20
      querySpec4.entity = hostSystem

      querySpec5 = Vim.PerformanceManager.QuerySpec()
      metricId5 = Vim.PerformanceManager.MetricId()
      metricId5.instance  = domInstance;
      metricId5.counterId = counterInfos[idx5].key
      querySpec5.metricId.append(metricId5)
      querySpec5.intervalId = 20
      querySpec5.entity = hostSystem

      querySpecs.append(querySpec1)
      querySpecs.append(querySpec2)
      querySpecs.append(querySpec3)
      querySpecs.append(querySpec4)
      querySpecs.append(querySpec5)

      # Query stats
      entityMetrics = perfManager.QueryStats(querySpecs)
      if len(entityMetrics) == 0:
         print("No stats found from querySpec %s!!" % querySpecs)
         status = "FAIL"
      else:
         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[0].value]

         print('\n\nCounter Name:', counterInfos[idx1].nameInfo.key)
         print('\n'.join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[1].value]

         print('\n\nCounter Name:', counterInfos[idx2].nameInfo.key)
         print('\n' . join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[2].value]

         print('\n\nCounter Name:', counterInfos[idx3].nameInfo.key)
         print('\n'.join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[3].value]

         print('\n\nCounter Name:', counterInfos[idx4].nameInfo.key)
         print('\n'.join(res))

         res = ["Counter Id  : %d\nInstance    : %s\n%s" % (v.id.counterId, v.id.instance,
               ' ' . join(["%d " % val for val in v.value]))
                        for v in entityMetrics[4].value]

         print('\n\nCounter Name:', counterInfos[idx5].nameInfo.key)
         print('\n'.join(res))

   except Exception as e:
      raise
      print("\tFailed test due to exception: " + str(e))
      status = "FAIL"
   finally:
      pass
   print("TEST 3 COMPLETE: " + status)

# Start program
if __name__ == "__main__":
    main()
