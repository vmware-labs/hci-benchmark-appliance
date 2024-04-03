#!/usr/bin/env python

"""
Copyright (c) 2015-2024 Broadcom. All Rights Reserved.
Broadcom Confidential. The term "Broadcom" refers to Broadcom Inc.
and/or its subsidiaries.

"""

import logging
# add null handler to not print the logging exception which invoke by import
logging.getLogger().addHandler(logging.NullHandler())

import sys
import os
import ssl
import configparser

try:
   onEsx = (os.uname()[0].lower() == 'vmkernel')
except Exception:
   onEsx =  False
if not onEsx:
   sys.path.append('%s/pyVpx' % os.path.dirname(__file__))

import pyVmomi
from pyVmomi import vim, vmodl
import datetime
import time
import subprocess

if onEsx:
   import vsanPerfPyMo
   import cliutils
   from VsanHealthHelpers import SoapStubAdapterForLocalhost
   from VsanHealthUtil import ConnectToLocalHostd
   from VsanHealthUtil import IsVsanEsaEnabledInHost

   from VsanHostHelper import isWitnessHost, isVsanPerfWitnessMetricsEnabled, isVsanPerfHighResolutionEnabled, \
                              HOST_ENTITY_TYPES, OBJECT_ENTITY_TYPES, LONG_RETENTION_STATS_ENTITY_TYPES, \
                              QUERY_TIME_RANGE_1_HOUR, QUERY_TIME_RANGE_12_HOURS, \
                              isVsanPnicPrivStatsMonitorEnabled
else:
   os.environ['VSAN_PYMO_SKIP_VC_CONN'] = '1'
   import vsanmgmtObjects

from argparse import ArgumentParser, RawTextHelpFormatter
try:
   from VsanConfigUtil import DATA_PROTECTION_ENABLED, isVsan2ResyncEtaMonitorEnabled
except:
   DATA_PROTECTION_ENABLED = False


def commandsDescription(msg=None):
   msg = '''<svc_info|perf_stats_with_dump|perf_stats_with_dump_extended|perf_stats|perf_stats_extended|perf_stats_diag|perf_stats_with_dump_diag|perf_stats_vmdk|perf_stats_with_dump_vmdk|perf_stats_ioinsight|perf_stats_with_dump_ioinsight'''

   msg += "|vsandirect_stats|vsandirect_stats_with_dump"

   if isVsanPerfHighResolutionEnabled():
      msg += "|perf_stats_high_resolution|perf_stats_with_dump_high_resolution"

   msg += \
'''>
svc_info                                     Print vSAN performance service information.
perf_stats_with_dump [days|hours]            Dump vSAN performance service stats in SOAP format, argument is number of days, by default dump 2 days.
perf_stats_with_dump_extended [days|hours]   Dump vSAN performance service extended stats in SOAP format, argument is number of days, by default dump 2 days.
perf_stats_with_dump_diag  [days|hours]      Dump vSAN diagnostic stats in SOAP format, argument is number of days, by default print 2 days.
perf_stats_with_dump_vmdk  [days|hours]      Dump vSAN virtual SCSI, virtual disk, virtual machine stats in SOAP format, argument is number of days, by default print 2 days.
perf_stats  [days|hours]                     Print vSAN performance service stats, argument is number of days, by default print 2 days.
perf_stats_extended  [days|hours]            Print vSAN performance service extended stats, argument is number of days, by default print 2 days.
perf_stats_diag  [days|hours]                Print vSAN diagnostic stats, argument is number of days, by default print 2 days.
perf_stats_vmdk  [days|hours]                Print vSAN virtual SCSI, virtual disk, virtual machine stats, argument is number of days, by default print 2 days.
perf_stats_ioinsight  [days|hours]           Print vSAN I/O Insight stats, argument is number of days, by default print 2 days.
perf_stats_with_dump_ioinsight  [days|hours] Print vSAN I/O Insight stats in SOAP format, argument is number of days, by default print 2 hours.
selective_with_dump                          Print vSAN performance service selective stats, in this command, starttime and endtime must be passed. The format of stattime and endtime is Unix epoch time.'''

   msg += \
'''
vsandirect_stats  [days|hours]                 Print vSAN Direct stats, argument is number of days, by default print 2 days.
vsandirect_stats_with_dump  [days|hours]       Print vSAN Direct stats in SOAP format, argument is number of days, by default print 2 days.'''

   if isVsanPerfHighResolutionEnabled():
      msg += \
'''
perf_stats_high_resolution  [hours]     Print performance service stats with small interval, argument is number of hours, by default print 1 hour.
perf_stats_with_dump_high_resolution  [hours]     Print performance service stats with small interval in SOAP format, argument is number of hours, by default print 1 hour.'''

   return msg

configFile = '/etc/vmware/vsan/vsanperf.conf'

def ReadConfigFile():
   configs = {}
   try:
      cfParser = configparser.RawConfigParser()
      cfParser.read(configFile)

      for (k,v) in cfParser.items('VSANPERF'):
         configs[k] = v
   except:
      pass
   return configs

default_collectInterval = 300
debugMode = False
longRetentionStatsModeIntervalInMinutes = 7 * 24 * 60
try:
   configs = ReadConfigFile()
   if "interval" in configs:
      collectInterval = int(configs["interval"])
   if 'db_purge_debug_mode' in configs:
      debugMode = configs["db_purge_debug_mode"] == 'True'
   if 'long_retention_stats_mode_interval_in_minutes' in configs:
      longRetentionStatsModeIntervalInMinutes = int(configs["long_retention_stats_mode_interval_in_minutes"])
except:
   pass

def getLongRetentionStatsOptions(debugMode, longRetentionStatsModeIntervalInMinutes):
   # First check the debug mode, then check the customized collection interval
   if debugMode:
      # debug mode only save 4 minutes data
      dumpDuration = 4 * 60
      longRetentionStatsModeInterval = 60
      # page size in minute, for debug mode, the paging size is the duration
      pagingSize = 4
   else:
      if longRetentionStatsModeIntervalInMinutes == 7 * 24 * 60:
         # default value will return 5 years data
         dumpDuration = 5 * 365 * 24 * 60 * 60
         longRetentionStatsModeInterval = longRetentionStatsModeIntervalInMinutes * 60
      else:
         # By default the collect interval is 7 days, and the retention is 5 years.
         # One sharding piece contains 1 year data, so totaly keep 5 pieces.
         # The total number of timestamp points is 260 (52*5).
         # The long_retention_stats_mode_interval_in_minutes is only for testing, if we change the
         # value, we need to make sure the number of entries is less than default total
         # number of timestamp points.
         # so the duration is 260 * interval_in_seconds
         longRetentionStatsModeInterval = longRetentionStatsModeIntervalInMinutes * 60
         dumpDuration = longRetentionStatsModeInterval * 260
      # Split the query time range to 5 pages, unit is minute
      pagingSize = dumpDuration // 60 // 5
   return pagingSize, dumpDuration, longRetentionStatsModeInterval

def checkCommand(command):
   supportCmds = ['svc_info', 'perf_stats', 'perf_stats_with_dump',
                  'perf_stats_extended', 'perf_stats_with_dump_extended', 'selective_with_dump',
                  'perf_stats_diag', 'perf_stats_with_dump_diag', 'perf_stats_vmdk', 'perf_stats_with_dump_vmdk',
                  'perf_stats_ioinsight', 'perf_stats_with_dump_ioinsight']

   if isVsanPerfHighResolutionEnabled():
      supportCmds.extend(['perf_stats_high_resolution', 'perf_stats_with_dump_high_resolution'])

   supportCmds.extend(['vsandirect_stats', 'vsandirect_stats_with_dump'])

   supportCmds.extend(['perf_stats_device_long_retention', 'perf_stats_with_dump_device_long_retention'])

   if command not in supportCmds:
      print('Error: Invalid command, please use -h to get valid command.')
      sys.exit(1)

def checkRange(command, timeRange):
   if command in ['perf_stats', 'perf_stats_with_dump',
                  'perf_stats_extended', 'perf_stats_with_dump_extended',
                  'perf_stats_diag', 'perf_stats_with_dump_diag', 'perf_stats_vmdk', 'perf_stats_with_dump_vmdk',
                  'perf_stats_ioinsight', 'perf_stats_with_dump_ioinsight',
                  'vsandirect_stats', 'vsandirect_stats_with_dump',
                  'perf_stats_high_resolution', 'perf_stats_with_dump_high_resolution']:
      try:
         days2Dump = int(timeRange)
      except:
         print('The days for dump stats should be integer!')
         sys.exit(1)

def checkUnit(unit, command):
   if unit not in ['hour', 'day']:
      print('Invalid option, please use -h to get valid option!')
      sys.exit(1)

def checkDumpHours(hours2Dump, command):
   if hours2Dump > 90 * 24:
      print('Error: The max limit of time range for dumping stats is 90 days (2160 hours)!')
      sys.exit(1)

def checkStartTimeAndEndTime(startTime, endTime):
   if selectedInfo in ['selective_with_dump']:
      if (startTime is None or endTime is None):
         print('Error: The starttime and endtime must be passed in when use "selective_with_dump" command')
         sys.exit(1)
      try:
         startTime = int(startTime)
         endTime = int(endTime)
      except:
         print('The starttime and endtime should be integer!')
         sys.exit(1)
      if startTime > endTime:
         print('Error: The starttime should not more than endtime!')
         sys.exit(1)

def checkHost(hostname):
   if hostname is None:
      print('Error: The hostname must be passed in!')
      sys.exit(1)

def checkUsernameAndPassword(username, password):
   if username is None or password is None:
      print('Error: The username and password must be passed in!')
      sys.exit(1)

parser = ArgumentParser(formatter_class=RawTextHelpFormatter)
parser.add_argument("command", help=commandsDescription())
parser.add_argument("time2Dump", help="Time range to dump",
                   type=int, nargs='?', default=2)
parser.add_argument("-u", "--unit", help="unit of dump time range, value is hour|day, default value is day",
                  dest="unit",
                  default="day")
parser.add_argument("-st", "--starttime", help="start timestamp of query", type=int, dest="startTime")
parser.add_argument("-et", "--endtime", help="end timestamp of query", type=int, dest="endTime")
parser.add_argument("-host", "--hostname", help="ESXi host to connect", dest="hostname")
parser.add_argument("-n", "--username", help="ESXi host username", dest="username")
parser.add_argument("-p", "--password", nargs='*', help="ESXi host password", dest="password")

args = parser.parse_args()

selectedInfo = ''
# dump stats of last 48 hours by default
hours2Dump = 48

#check the input
selectedInfo = args.command
checkCommand(selectedInfo)
time2Dump = args.time2Dump
checkRange(selectedInfo, time2Dump)
unit = args.unit
checkUnit(unit, selectedInfo)
startTime = args.startTime
endTime = args.endTime
checkStartTimeAndEndTime(startTime, endTime)
hostname = args.hostname
username = args.username
passwords = args.password

if unit == "day":
   hours2Dump = time2Dump * 24
if unit == "hour":
   hours2Dump = time2Dump
checkDumpHours(hours2Dump, selectedInfo)

if onEsx:
   clusterInfo = cliutils.CLIUtil.GetVSANClusterInfo()

   #exit if VSAN is not enabled
   if clusterInfo['Enabled'] == 'false':
      print('VSAN is not enabled.')
      exit(0)

   if selectedInfo == 'svc_info':
      #list the stats object directly conconet here, but not directly run 'ls' in .mfs, because
      #we need find out the vsan datastore directory before 'ls'
      subClusterUuid = clusterInfo['Sub-Cluster UUID']
      vsanDir = 'vsan:%s%s%s-%s%s' % tuple(subClusterUuid.split('-'))
      #print to stderr to ensure the text showed before the subprocess call
      print('--------Perf Service Stats Object Dir Content--------')
      sys.stdout.flush()
      subprocess.call(['ls', '-l', '/vmfs/volumes/%s/.vsan.stats/' % vsanDir ])

   si, __, stub = ConnectToLocalHostd()

   vsanStub = SoapStubAdapterForLocalhost(
                        host='localhost',
                        version="vim.version.version10",
                        path='/vsan')
else:
   checkHost(hostname)
   checkUsernameAndPassword(username, passwords)
   # For python 2.7.9 and later, the default SSL context has more strict
   # connection handshaking rule. We may need turn off the hostname checking
   # and client side cert verification.
   context = ssl.create_default_context()
   context.check_hostname = False
   context.verify_mode = ssl.CERT_NONE

   stub = pyVmomi.SoapStubAdapter(hostname, 443,
        version='vim.version.version10',
        path='/sdk',
        sslContext=context)
   si = vim.ServiceInstance("ServiceInstance", stub)
   content = si.RetrieveServiceContent()
   loginSuccess = False
   for password in passwords:
      try:
         content.sessionManager.Login(userName=username, password=password)
         loginSuccess = True
         break
      except Exception as ex:
         if not isinstance(ex, vim.fault.InvalidLogin):
            raise
   if not loginSuccess:
      print("Login failed, please check the username and password.")
      sys.exit(1)

   vsanStub = pyVmomi.SoapStubAdapter(
            host=hostname,
            port=443,
            version='vim.version.version11',
            path = "/vsan",
            sslContext=context)

vsanStub.cookie = stub.cookie
vpm = vim.cluster.VsanPerformanceManager(
                      "vsan-performance-manager",
                       vsanStub)

# dump perfsvc info
# gather perf service node info and stats object info if it is a stats master
nodeInfos = vpm.QueryNodeInformation()

if selectedInfo == 'svc_info':
   print('--------Perf Service Node Information--------')
   print(str(nodeInfos[0]))

   #show stats object info
   if nodeInfos[0].isStatsMaster:
      print('--------Perf Service Stats Object Information--------')
      statsObjInfo = vpm.QueryStatsObjectInformation()
      print(str(statsObjInfo))

# dump perfsvc status of different priority
# P0 (Collection ON by default, extraction to support bundled ON by default): For metrics crucial for debugging
# P1 (Collection ON by default, extraction to support bundled OFF by default): To keep size of support bundle in check
# P2 (Collection OFF by default): For minimal performance impact. P2 is verbose level, only collected when enable verbose mode.
# Queried fields must be appended to the end of every entity type.
allFields = "All"
supportBundlePriorityMetrics = {}
supportBundlePriorityMetrics["P0"] = {
   "cluster-domclient": allFields,
   "host-domclient": allFields,
   "cluster-remotedomclient": allFields,
   "host-domowner": allFields,
   "host-domcompmgr": allFields,
   "clom-disk-stats": allFields,
   "clom-host-stats": allFields,
   "host-vsansparse": allFields,
   "vsan-pnic-net": [
           "rxThroughput", "rxPackets", "rxPacketsLossRate",
           "txThroughput", "txPackets", "txPacketsLossRate",
           "pauseCount", "portTxDrops", "portRxDrops",
           "ioChainDrops", "ioChainRxdrops", "ioChainTxdrops",
           "portRxpkts", "portTxpkts", "pfcCount", "rxErr", "rxDrp",
           "txErr", "txDrp", "rxCrcErr",
   ],
   "vsan-vnic-net": allFields,
   "vsan-host-net": allFields,
   "vsan-iscsi-host": allFields,
   "vsan-iscsi-target": allFields,
   "ddh-disk-stats": allFields,
   "nfs-client-vol": allFields,
   "system-mem": allFields,
   "vsan-distribution": allFields,
   "host-memory-slab": allFields,
   "host-memory-heap": allFields,
   "dom-proxy-owner": allFields,
   "cache-disk": [
           "iopsDevRead", "throughputDevRead", "latencyDevRead",
           "ioCountDevRead", "iopsDevWrite", "throughputDevWrite",
           "latencyDevWrite", "ioCountDevWrite", "latencyDevDAvg",
           "latencyDevGAvg", "latencyDevKAvg", "llogLogSpace",
           "llogDataSpace", "plogLogSpace", "plogDataSpace",
           "plogMDDataUsage", "plogDGDataUsage", "plogTotalCSBytes",
           "plogTotalZeroBytes", "plogTotalDelBytes", "plogTotalFSBytes",
           "plogTotalCFBytes", "plogTotalFSUnmapBytes", "plogTotalCFUnmapBytes",
           "plogTotalBytesDrained", "plogSsdBytesDrained", "plogZeroBytesDrained",
           "plogNumElevSSDReads", "plogNumElevMDWrites", "plogElevCycles",
           "plogNumWriteLogs", "plogNumCommitLogs", "plogNumFreedLogs",
           "plogNumFreedCommitLogs",
           "blkAttrCcheHitRt", "blkAttrCcheSz",
           "totalPlogRecoveryTime", "plogRecoveryReadTime",
           "plogRecoveryProcessTime", "numPlogRecoveryReads",
           "totalLlogRecoveryTime", "llogRecoveryReadTime",
           "llogRecoveryProcessTime", "numLlogRecoveryReads",
           "latencyRcRdQ", "latencyRcWrtQ",
           "latencyWbRdQ", "latencyWbWrtQ",
           "plogtotalRdLat", "plogtotalWrLat",
           "plogHelpRdQLat", "plogHelpWrQLat",
           "plogCumlEncRdLat", "plogCumlEncWrLat",
           "plogHelpRdQDepth", "plogHelpWrQDepth",
           "lgclCapUsed", "lgclCapReserved", "lgclCapUnrsvrd",
           "lgclCapConsUsage", "lgclCapConsPrep", "lgclCapUnmap",
           "lgclCapFsMetadata", "phyCapUsed", "phyCapT2",
           "phyCapCF", "phyCapRsrvd", "phyCapRsrvdUsed",
           "prepTblCnt", "commitTblCnt",
           "logP", "memP", "ssdP", "dataP", "zeroP", "maxP",
           "elevStartThresh", "elevUnthrottleThresh", "timeToSleepMs",
           "advtDataDestageRateAvg", "advtZeroDestageRateAvg",
           "checksumErrors", "totalDATABlksCorrected", "totalCRCCorrected",
           "latencyDevReadMin", "latencyDevReadMax",
           "latencyDevWriteMin", "latencyDevWriteMax", "plogDGZeroUsage",
           "plogZeroElevCycles", "plogNumZeroElevPrepLogs", "plogNumZeroElevCommitLogs",
           "plogNumFreedZeroElevPrepLogs", "plogNumFreedZeroElevCommitLogs",
           "zeroElevStartThreshold", "zeroElevUnthrottleThreshold",
           "zeroElevMaxP", "zeroElevTimeToSleepMs"

           ],
   "capacity-disk": [
           "iopsDevRead", "throughputDevRead", "latencyDevRead",
           "ioCountDevRead", "iopsDevWrite", "throughputDevWrite",
           "latencyDevWrite", "ioCountDevWrite", "latencyDevDAvg",
           "latencyDevGAvg", "iopsRead", "latencyRead", "ioCountRead",
           "iopsWrite", "latencyWrite", "ioCountWrite",
           "latencyDevKAvg", "llogLogSpace", "llogDataSpace",
           "plogLogSpace", "plogDataSpace", "plogMDDataUsage",
           "plogDGDataUsage", "plogTotalCSBytes", "plogTotalZeroBytes",
           "plogTotalDelBytes", "plogTotalFSBytes", "plogTotalCFBytes",
           "plogTotalFSUnmapBytes", "plogTotalCFUnmapBytes",
           "plogTotalBytesDrained", "plogSsdBytesDrained", "plogZeroBytesDrained",
           "plogNumElevSSDReads", "plogNumElevMDWrites", "plogElevCycles",
           "plogNumWriteLogs", "plogNumCommitLogs", "plogNumFreedLogs",
           "plogNumFreedCommitLogs",
           "checksumErrors", "cfTime", "blkAttrFlshTime", "vrstBarrTime",
           "plogIOTime", "numCFAct", "numCksumFlsh", "numVrstBar",
           "numPlogIOs",
           "plogHelpRdQLat", "plogHelpWrQLat",
           "plogCumlEncRdLat", "plogCumlEncWrLat",
           "plogHelpRdQDepth", "plogHelpWrQDepth",
           'virstoMetadataFlusherRunsPerSec', 'virstoMetadataFlusherPendingBuffers',
           'virstoMapBlockCacheEvictionsPerSec', 'commitFlusherExtentsProcessed',
           'virstoValidMapBlocks', 'commitFlusherComponentsToFlush',
           'commitFlusherExtentSizeProcessed', 'virstoInvalidMapBlocks',
           'virstoMapBlockCacheHitsPerSec', 'virstoFreeMapBlocks',
           'virstoInstanceHeapUtilization', 'virstoMapBlockCacheMissesPerSec',
           'capacityUsed', 'virstoMetadataFlushedPerRun', 'virstoDirtyMapBlocks',
           "lgclCapUsed", "lgclCapReserved", "lgclCapUnrsvrd",
           "lgclCapConsUsage", "lgclCapConsPrep", "lgclCapUnmap",
           "lgclCapFsMetadata", "phyCapUsed", "phyCapT2",
           "phyCapCF", "phyCapRsrvd", "phyCapRsrvdUsed",
           "zerosInFlight", "zerosInFlightSystem", "zerosProcessedSystem",
           "elevSSDReadLatency", "elevMDWriteLatency",
           "numCompressions", "numUncompressions",
           "diskTransientCapacityUsed", "dgTransientCapacityUsed",
           "avgDdpWriteTime", "avgDdpCommitTime", "avgElevIoSize",
           "ddpXmapBytesWritten", "ddpHmapBytesWritten", "ddpBmapBytesWritten",
           "ddpXmapBytesRead", "ddpHmapBytesRead", "ddpBmapBytesRead",
           "b0Data", "b1Data", "b2Data", "b3Data", "capacityCompressed",
           "multiElevCompressionTime", "multiElevCompressPct", "multiElevNumCompressedBlocks",
           "multiElevNumUncompressedBlocks", "multiElevDedupXmapHitRt", "multiElevNumXMapRd",
           "multiElevNumXMapWrt", "multiElevNumBitmapRd", "multiElevNumBitmapWrt",
           "multiElevAvgPreReadTime", "multiElevDataWriteTime",
           "multiElevTxnWritePrepTime", "multiElevTxnWriteWaitingTime",
           "multiElevTxnReplayIOTime", "multiElevTxnPreReadHmapWaitTime",
           "multiElevTxnPreReadXmapWaitTime",
           "multiElevTxnBuildTime", "multiElevTxnWriteTime", "multiElevTxnReplayTime",
           "multiElevTxnReplayXmapTime", "multiElevTxnReplayHashmapTime", "multiElevTxnReplayBitmapTime",
           "multiElevPendingTxnReplayYields", "multiElevTxnReplayBgWriteIOs", "multiElevTxnReplayFgWriteIOs",
           "multiElevTxnReplayReadIOHits", "multiElevNumGuestReads", "multiElevNumDdpMetadataReads",
           "multiElevNumDdpMetadataWrites", "multiElevAvgIdleTime",
           "multiElevNumHashmapRd", "multiElevNumHashmapWrt",
           "unmapInline", "unmapDelayed", "unmapPendingComponents",
           "unmapPendingComponentsQueued", "unmapPendingComponentsActive",
           "unmapQuota", "unmapQuotaAvailableBytes", "unmapQuotaConsumedBytes",
           "unmapQuotaConsumedPages", "unmapQuotaFailed",
           "unmapQuotaRelinquished", "unmapPendingBytes",
           "unmapsToUnallocatedBytes", "inlineUnmapsProcessedBytes",
           "unmapPendingPlacedBytes", "unmapPendingProcessedBytes",
           "unmapPendingProcessedPages", "unmapPendingInflightBytes",
           "plogCommitLogCbTime", "plogNumLbaEntriesInCurBkt",
           "plogNumLbaEntriesSkipped", "elevSMActs",
           "plogPrepSMActs", "plogCommitSMActs", "elevatorWaitOnCFTime",
           "b4Data", "b5Data", "b6Data", "b7Data",
           "totalDATABlksCorrected", "totalCRCCorrected",
           "plannedDeltaComponents", "unplannedDeltaComponents",
           "latencyDevReadMin", "latencyDevReadMax",
           "latencyDevWriteMin", "latencyDevWriteMax",
           "zeroesBucket0", "zeroesBucket1", "zeroesBucket2", "zeroesBucket3",
           "zeroesBucket4", "zeroesBucket5", "zeroesBucket6", "zeroesBucket7",
           "plogDGZeroUsage", "plogMDZeroUsage", "avgZeroElevDdpWriteTime", "avgZeroElevDdpCommitTime",
           "avgZeroElevIoSize", "zeroElevSMActivations", "plogZeroElevCycles",
           "numLbaEntriesInCurZeroBkt", "numNonZeroLbaEntriesSkipped",
           "plogNumZeroElevPrepLogs", "plogNumZeroElevCommitLogs",
           "plogNumFreedZeroElevPrepLogs", "plogNumFreedZeroElevCommitLogs",
           "plogZeroElevCommitLogCbTime", "zeroElevatorWaitOnCFTime",
           "elevCurBucket",  "zeroElevCurBucket", "curWBBucket",
           "zeroElevCurTxnScopes", "deleteCongestion", "deleteCongestionLocalMax",
           "incomingWriteRate", "incomingWriteMovingAvg", "zeroDestageRate",
           "zeroDestageRateMovingAvg", "currentDiskFullness",
           "expectedDiskFullness",
           ],
   "disk-group": [
           "iopsSched", "latencySched", "outstandingBytesSched",
           "iopsSchedQueueNS", "throughputSchedQueueNS", "latencySchedQueueNS",
           "iopsSchedQueueRec", "throughputSchedQueueRec", "latencySchedQueueRec",
           "iopsSchedQueueVM", "throughputSchedQueueVM", "latencySchedQueueVM",
           "iopsSchedQueueMeta", "throughputSchedQueueMeta", "latencySchedQueueMeta",
           "iopsDelayPctSched", "latencyDelaySched", "rcHitRate",
           "wbFreePct", "warEvictions", "quotaEvictions", "iopsRcRead",
           "latencyRcRead", "ioCountRcRead", "iopsWbRead", "latencyWbRead",
           "ioCountWbRead", "iopsRcWrite",
           "latencyRcWrite", "ioCountRcWrite", "iopsWbWrite",
           "latencyWbWrite", "ioCountWbWrite", "ssdBytesDrained",
           "zeroBytesDrained", "memCongestion", "slabCongestion",
           "ssdCongestion", "iopsCongestion", "logCongestion",
           "compCongestion", "iopsRead", "throughputRead", "latencyAvgRead",
           "readCount", "iopsWrite", "throughputWrite", "latencyAvgWrite",
           "writeCount","oioWrite", "oioRecWrite", "oioRecWriteSize",
           "rcSize", "wbSize", "capacity", "capacityUsed", "capacityReserved",
           "throughputSched", "iopsResyncRead", "tputResyncRead", "latResyncRead",
           "iopsResyncWrite", "tputResyncWrite", "latResyncWrite", "iopsResyncReadPolicy",
           "tputResyncReadPolicy", "latResyncWritePolicy", "iopsResyncReadDecom",
           "tputResyncReadDecom", "latResyncReadDecom", "iopsResyncWriteDecom",
           "tputResyncWriteDecom", "latResyncWriteDecom", "iopsResyncReadRebalance",
           "tputResyncReadRebalance", "latResyncWriteRebalance", "iopsResyncReadFixComp",
           "tputResyncReadFixComp", "latResyncReadFixComp", "iopsResyncWriteFixComp",
           "tputResyncWriteFixComp", "latResyncWriteFixComp", "maxCapacityUsed",
           "minCapacityUsed",
           "dedupedBytes", "hashedBytes",
           "txnWritePrepTime", "txnReplayIOTime", "txnWriteWaitingTime",
           "txnPreReadHmapWaitTime", "txnPreReadXmapWaitTime",
           "txnBuildTime", "txnWriteTime", "txnReplayTime",
           "hashCalcTime", "compressionTime", "dataWriteTime",
           "numHashmapRd", "numHashmapWrt",
           "numBitmapRd", "numBitmapWrt",
           "numXMapRd", "numXMapWrt",
           "dedupPct", "dedupCcheHitRt", "compressPct",
           "ddpTotalCap", "ddpFreeCap",
           "iopsReadCompMgr", "iopsWriteCompMgr", "iopsUnmapCompMgr",
           "iopsRecoveryWriteCompMgr", "iopsRecoveryUnmapCompMgr",
           "latencyReadCompMgr", "latencyWriteCompMgr", "latencyUnmapCompMgr",
           "latencyRecoveryWriteCompMgr", "latencyRecoveryUnmapCompMgr",
           "throughputReadCompMgr", "throughputWriteCompMgr", "throughputUnmapCompMgr",
           "throughputRecoveryWriteCompMgr", "throughputRecoveryUnmapCompMgr",
           "oioReadCompMgr", "oioWriteCompMgr", "oioUnmapCompMgr",
           "oioRecoveryWriteCompMgr", "oioRecoveryUnmapCompMgr",
           "componentCongestionReadSched", "componentCongestionWriteSched",
           "diskgroupCongestionReadSched", "diskgroupCongestionWriteSched",
           "namespaceBackpressureCongestionReadSched", "namespaceBackpressureCongestionWriteSched",
           "vmdiskBackpressureCongestionReadSched", "vmdiskBackpressureCongestionWriteSched",
           "metadataBackpressureCongestionReadSched", "metadataBackpressureCongestionWriteSched",
           "resyncBackpressureCongestionReadSched", "resyncBackpressureCongestionWriteSched",
           "pendingTxnReplayYields", "txnReplayBgWriteIOs",
           "txnReplayFgWriteIOs", "txnReplayReadIOHits",
           "oobLogCongestionIOPS",
           "drainRateMovingAvg", "overWriteFactorMovingAvg",
           "currentDrainRate", "currentTrueWBFillRate","currentOverWriteFactor",
           "currentIncomingRate", "bytesPerSecondBandwidth",
           "curBytesToSyncPolicy", "curBytesToSyncDecom",
           "curBytesToSyncRebalance", "curBytesToSyncFixComp",
           "txnReplayHashmapTime", "txnReplayXmapTime", "txnReplayBitmapTime",
           "memCongestionLocalMax", "slabCongestionLocalMax",
           "ssdCongestionLocalMax", "iopsCongestionLocalMax",
           "logCongestionLocalMax", "compCongestionLocalMax",
           "dedupBmapHitRt", "dedupHmapHitRt", "dedupXmapHitRt",
           "dedupBmapUsage", "dedupHmapUsage", "dedupXmapUsage",
           "numDdpMetadataReads", "numDdpMetadataWrites", "numGuestReads",
           "numCompressedHashBlocks",
           "avgIdleTime", "avgPreReadTime", "ddpWriteRate",
           "ddpCommitRate", "txnSizePerCommit", "mappedBytesPerCommit",
           "curBytesToSyncRepair", "timesOverWindowLimitWrite", "timesOverWindowLimitRead",
           "maxDeleteCongestion",
           ],
   "cmmds-workloadstats": [
           "rxAccept", "rxAgentUpdateRequest",
           "rxHeartbeatRequest", "rxMasterUpdate",
           "txAgentUpdateRequest", "txHeartbeatRequest",
           "txMasterCheckpoint", "txMasterUpdate",
           "agentBatchesSent", "totalUpdSentInAgentBatch",
           "checkPointBatchesSent", "totalUpdInBatchCkpt",
           "masterBatchesRecved", "totalUpdInMasterBatches"
           ],
   "lsom-world-cpu": allFields,
   "host-cpu": allFields,
   "dom-world-cpu": allFields,
   "statsdb": allFields,
   "nic-world-cpu": allFields,
   "cmmds-world-cpu": allFields,
   "vsan-cpu": allFields,
   "cluster-resync": allFields,
   "vsan-memory": allFields,
   "clom-disk-fullness-stats": allFields,
   "clom-slack-space-stats": allFields,
   "rdma-net": allFields,
   "rdma-world-cpu": allFields,
   "cluster-domcompmgr": allFields,
   "cluster-domowner": allFields,
   "vsan-file-service": allFields,
   "psa-completion-world-cpu": allFields,
   "psa-split-stats": allFields,
   "rdt-world-cpu": allFields,
   "rdt-net": allFields,
   "rdt-global-info": allFields,
   "rdt-connection-summary": allFields,
   "vnic-rdt-network-latency": allFields,
   "clom-workitem-stats": allFields,
   "cluster-rdt-network-latency": allFields,
   "rdt-network-latency": allFields,
   "computeCluster-remotedomclient": allFields,
   "host-localdomclient": allFields,
   "cluster-localdomclient": allFields,
   "host-remotedomclient": allFields,
   "computeHost-remotedomclient": allFields,
   "host-domownerserver-migration": allFields,
   "host-domscrubber": allFields,
   "host-domowner-observability": allFields,
   "host-domleafowner-observability": allFields,
   "cluster-domowner-observability": allFields,
   "cluster-domleafowner-observability": allFields,
   "cluster-domcompmgr-observability": allFields,
   "host-domcompmgr-observability": allFields,
   "cluster-domcmmds-observability": allFields,
   "host-domcmmds-observability": allFields,
   "vsan-tcpip-stats": allFields,
}

if IsVsanEsaEnabledInHost():
   supportBundlePriorityMetrics["P0"].update({
      "vsan-esa-disk-layer-allocator-stats": allFields,
      "vsan-esa-disk-layer-world-cpu": allFields,
      "splinter-overall-stats": allFields,
      "splinter-operation-stats": allFields,
      "splinter-lookup-stats": allFields,
      "splinter-task-stats": allFields,
      "splinter-trunk-page-stats": allFields,
      "splinter-branch-page-stats": allFields,
      "splinter-memtable-page-stats": allFields,
      "splinter-filter-page-stats": allFields,
      "splinter-range-page-stats": allFields,
      "splinter-misc-page-stats": allFields,
      "splinter-snowplough-stats": allFields,
      "splinter-range-delete-stats": allFields,
      "splinter-checkpoint-stats": allFields,
      "splinter-meta-page-stats": allFields,
      "splinter-premini-stats": allFields,
      "kvstore": allFields,
      "vsan-esa-disk-iolayer-stats": allFields,
      "vsan-esa-disk-iolayer-handle-stats": allFields,
      "vsan-esa-disk-layer-mdr-handle-stats": allFields,
      "vsan-esa-dom-scheduler": allFields,
      "vsan-esa-disk-layer": allFields,
      "vsan-esa-disk-scsifw": allFields,
      "vsan-zdom-gsc": allFields,
      "vsan-esa-cluster-resync": allFields,
      "vsan-esa-disk-layer-block-engine-stats": allFields,
      "vsan-esa-disk-layer-congestion-stats": allFields,
      "vsan-esa-disk-layer-transaction-stats": allFields,
      "vsan-esa-disk-layer-partition-stats": allFields,
      "vsan-esa-disk-layer-checksumerrors": allFields,
      "vsan-esa-distribution": allFields,
      "vsan-esa-disk-layer-allocator-unmap-stats": allFields,
      "host-domdisk-observability": allFields,
      "cluster-domdisk-observability": allFields,
   })
   supportBundlePriorityMetrics["P0"].update({
      "zdom-world-cpu": allFields,
      "zdom-io": allFields,
      "zdom-vtx": allFields,
      "zdom-overview": allFields,
      "zdom-llp": allFields,
      "zdom-snapshot": allFields,
      "zdom-seg-cleaning": allFields,
      "zdom-btree": allFields,
      "host-zdom-top-stats": allFields,
      "cluster-zdom-top-stats": allFields,
   })

if isVsan2ResyncEtaMonitorEnabled():
   supportBundlePriorityMetrics["P0"].update({
      "esa-disk-resync-eta": allFields,
      "esa-host-resync-eta": allFields,
      "esa-cluster-resync-eta": allFields,
   })


supportBundlePriorityMetrics["P1"] = {
   "cmmds-net": allFields,
   "cache-disk": [
           "plogReadQLatency", "plogWriteQLatency",
           "plogTotalBytesRead", "plogTotalBytesReadFromMD", "plogTotalBytesReadFromSSD",
           "plogTotalBytesReadByRC", "plogTotalBytesReadByVMFS", "plogNumTotalReads",
           "plogNumMDReads", "plogNumSSDReads", "plogNumRCReads", "plogNumVMFSReads",
           "rcHitRatePerMille"
           ],
   "capacity-disk": [
           "plogReadQLatency", "plogWriteQLatency",
           "plogTotalBytesRead", "plogTotalBytesReadFromMD", "plogTotalBytesReadFromSSD",
           "plogTotalBytesReadByRC", "plogTotalBytesReadByVMFS", "plogNumTotalReads",
           "plogNumMDReads", "plogNumSSDReads", "plogNumRCReads", "plogNumVMFSReads",
           ],
   "disk-group": [
           "rcMissRate","rcPartialMissRate", "latencyWriteLE", "iopsWriteLE",
           "throughputWriteLE", "latencyAvgOfAllIO", "iopsAvgOfAllIO",
           "throughputAvgOfAllIO", "iopsRcTotalRead", "iopsRcMemReads",
           "iopsRcSsdReads", "iopsRcRawar", "allEvictions", "readInvalidatedBytesRawar",
           "readInvalidatedBytesPatched", "readInvalidatedBytesWastedPatched",
           "plogRclNotFound", "plogInvalidationBitNotSet", "plogInvalidated",
           "plogPatched",
           "namespaceThroughputReadSched", "namespaceThroughputWriteSched",
           "metadataThroughputReadSched", "metadataThroughputWriteSched",
           "vmdiskThroughputReadSched", "vmdiskThroughputWriteSched",
           "resyncThroughputReadSched", "resyncThroughputWriteSched",
           "regulatorIopsReadSched", "regulatorIopsWriteSched",
           ],
   "cmmds-workloadstats": [
           "rxRetransmitRequest", "rxSnapshot",
           "rxMisc", "txMasterCkptTried", "txRetransmitRequest",
           "txSnapshot", "txSnapshotBytes", "txSnapshotTried",
           "txMasterUpdateTried",
           ],
   "cmmds-update-latency": allFields,
   "cmmds": allFields,
   "cmmds-compression": allFields,
}

if isVsanPnicPrivStatsMonitorEnabled():
   supportBundlePriorityMetrics["P0"].update({
      "vsan-pnic-priv-stats": allFields
   })

supportBundlePriorityMetrics["P2"] = {
   "vmdk-vsansparse": allFields,
   "dom-per-proxy-owner": [
                 "proxyReadCongestion", "proxyWriteCongestion", "proxyRWResyncCongestion",
                 "proxyIopsRead", "proxyTputRead", "proxyLatencyAvgRead",
                 "proxyReadCount", "proxyIopsWrite", "proxyTputWrite",
                 "proxyLatencyAvgWrite", "proxyWriteCount",
                 "proxyIopsRWResync", "proxyTputRWResync",
                 "proxyLatencyAvgRWResync", "proxyRWResyncCount", "anchorReadCongestion",
                 "anchorWriteCongestion", "anchorRWResyncCongestion",
                 "anchorIopsRead", "anchorTputRead", "anchorLatencyAvgRead",
                 "anchorReadCount", "anchorIopsWrite", "anchorTputWrite",
                 "anchorLatencyAvgWrite", "anchorWriteCount",
                 "anchorIopsRWResync", "anchorTputRWResync",
                 "anchorLatencyAvgRWResync", "anchorRWResyncCount",
   ],
   "disk-group": [
           "metadataQueueDepthReadSched", "metadataQueueDepthWriteSched",
           "namespaceQueueDepthReadSched", "namespaceQueueDepthWriteSched",
           "resyncQueueDepthReadSched", "resyncQueueDepthWriteSched",
           "vmdiskQueueDepthReadSched", "vmdiskQueueDepthWriteSched",
           "metadataDispatchedCostReadSched", "metadataDispatchedCostWriteSched",
           "namespaceDispatchedCostReadSched", "namespaceDispatchedCostWriteSched",
           "resyncDispatchedCostReadSched", "resyncDispatchedCostWriteSched",
           "vmdiskDispatchedCostReadSched", "vmdiskDispatchedCostWriteSched",
           "metadataLatencyReadSched", "metadataLatencyWriteSched",
           "namespaceLatencyReadSched", "namespaceLatencyWriteSched",
           "resyncLatencyReadSched", "resyncLatencyWriteSched",
           "vmdiskLatencyReadSched", "vmdiskLatencyWriteSched",
   ],
   "vsan-pnic-net": [
           "rxLgtErr", "rxOvErr",
           "rxFrmErr", "rxFifoErr", "rxMissErr",
           "txAbortErr", "txCarErr",
           "txFifoErr", "txHeartErr", "txWinErr",
   ],
   "cache-disk": [
           "advtDataDestageRateCur", "advtZeroDestageRateCur",
           "llogLog", "llogData", "plogLog", "plogData",
   ],
   "capacity-disk": [
           "plogWindowCommitTime", "elevOffset", "elevWindow",
           "elevNextWindow", "zeroElevLbaOffset",
           "plogZeroElevWindowCommitTime",
   ],
}

supportBundlePriorityMetrics["P3"] = {
   "vsan-pnic-net": allFields,
   "vsan-vnic-net": allFields,
   "vsan-host-net": allFields,
   "vsan-tcpip-stats": allFields,
}

supportBundlePriorityMetrics["P4"] = {
   "vscsi": allFields,
   "virtual-disk": ["iopsLimit", "NIOPS", "NIOPSDelayed"],
}

supportBundlePriorityMetrics["P5"] = {
   "ioinsight": [
           # Metrics
           "iopsRead", "iopsWrite", "iopsTotal", "throughputRead", "throughputWrite",
           "throughputSequential", "throughputRandom", "throughputTotal",
           "sequentialReadRatio", "sequentialWriteRatio", "sequentialRatio",
           "randomReadRatio", "randomWriteRatio", "randomRatio",
           "aligned4kReadRatio", "aligned4kWriteRatio", "aligned4kRatio",
           "unaligned4kReadRatio", "unaligned4kWriteRatio", "unaligned4kRatio",
           "readRatio", "writeRatio",
   ],
}

supportBundlePriorityMetrics["P7"] = {
   "vsan-direct-disk": [
      # Metrics
      "iopsDevRead", "throughputDevRead", "latencyDevRead",
      "oioDevRead", "iopsDevWrite", "throughputDevWrite",
      "oioDevWrite", "latencyDevWrite", "latencyDevDAvg",
      "latencyDevGAvg", "latencyDevKAvg"
   ],
   "vsan-direct-host": [
      # Metrics
      "iopsDevRead", "throughputDevRead", "latencyDevRead",
      "oioDevRead", "iopsDevWrite", "throughputDevWrite",
      "oioDevWrite", "latencyDevWrite"
   ],
   "vsan-direct-cluster": [
      # Metrics
      "iopsDevRead", "throughputDevRead", "latencyDevRead",
      "oioDevRead", "iopsDevWrite", "throughputDevWrite",
      "oioDevWrite", "latencyDevWrite"
   ],
}

if isVsanPerfHighResolutionEnabled() and not isWitnessHost():
   supportBundlePriorityMetrics["P8"] = {
      "hr-cluster-domclient": supportBundlePriorityMetrics["P0"]["cluster-domclient"],
      "hr-cluster-domcompmgr": supportBundlePriorityMetrics["P0"]["cluster-domcompmgr"],
      "hr-host-domclient": supportBundlePriorityMetrics["P0"]["host-domclient"],
      "hr-host-domcompmgr": supportBundlePriorityMetrics["P0"]["host-domcompmgr"],
      "hr-vsan-vnic-net": supportBundlePriorityMetrics["P0"]["vsan-vnic-net"],
      "hr-vsan-host-net": supportBundlePriorityMetrics["P0"]["vsan-host-net"],
      "hr-vsan-pnic-net": supportBundlePriorityMetrics["P0"]["vsan-pnic-net"],
      "hr-rdt-net": supportBundlePriorityMetrics["P0"]["rdt-net"],
      "hr-vsan-tcpip-stats": supportBundlePriorityMetrics["P0"]["vsan-tcpip-stats"],
   }
   if IsVsanEsaEnabledInHost():
      supportBundlePriorityMetrics["P8"]["hr-zdom-io"] = supportBundlePriorityMetrics["P0"]["zdom-io"]
      supportBundlePriorityMetrics["P8"]["hr-zdom-vtx"] = supportBundlePriorityMetrics["P0"]["zdom-vtx"]
      supportBundlePriorityMetrics["P8"]["hr-vsan-esa-disk-layer"] = supportBundlePriorityMetrics["P0"]["vsan-esa-disk-layer"]
      supportBundlePriorityMetrics["P8"]["hr-vsan-esa-disk-scsifw"] = supportBundlePriorityMetrics["P0"]["vsan-esa-disk-scsifw"]
   else:
      supportBundlePriorityMetrics["P8"]["hr-disk-group"] = supportBundlePriorityMetrics["P0"]["disk-group"]
      supportBundlePriorityMetrics["P8"]["hr-cache-disk"] = supportBundlePriorityMetrics["P0"]["cache-disk"]
      supportBundlePriorityMetrics["P8"]["hr-capacity-disk"] = supportBundlePriorityMetrics["P0"]["capacity-disk"]

supportBundlePriorityMetrics["P9"] = {
   "nvme-smart-stats": allFields,
}

if DATA_PROTECTION_ENABLED:
   supportBundlePriorityMetrics["P0"].update({
      # Drop following fields from support bundle, since they arent relevant at
      # the host level:
      # - totalConsumedSpaceDpVms
      # - totalUpitOverhead
      # - totalDpOverhead
      # Include all other fields
      "host-dataprotection": [
         "numLocalSnapshots", "numLocalQuiescedSnapshots", "numOwnedCgs",
         "numObjectSnapshots", "avgTimeLocalSnapshot",
         "avgTimeLocalQuiescedSnapshot", "numCreateImage",
         "avgTimeCreateImage", "numDeleteImage", "avgTimeDeleteImage",
         "numReleaseImage", "avgTimeReleaseImage", "avgDpdCpuRuntime",
         "maxDpdCpuRuntime", "bytesReserved", "bytesAllocated"
      ],
      "cluster-dataprotection": allFields,
      "upit-world-cpu": allFields,
      "upit": [
         "cpWriteIops", "cpWriteTput", "cpWriteLatency",
         "cpWriteLatencyStddev", "cacheMissReadIops",
         "cacheMissReadTput", "cacheMissReadLatency",
         "cacheMissReadLatencyStddev", "logReadIops",
         "logReadTput", "logReadLatency", "logReadLatencyStddev",
         "logWriteIops", "logWriteTput", "logWriteLatency",
         "logWriteLatencyStddev"
      ],
   })
   supportBundlePriorityMetrics["P2"].update({
      "vm-dataprotection": allFields,
   })

# put the witness node stats at the end of metrics definition
if isVsanPerfWitnessMetricsEnabled() and isWitnessHost():
   supportBundlePriorityMetrics["P0"] = {
      "host-domcompmgr": allFields,
      "cmmds": allFields,
      "cmmds-workloadstats": allFields,
      "cmmds-net": allFields,
      "disk-group": allFields,
   }
   supportBundlePriorityMetrics["P1"] = {}


def getPagingSize(priority, entityType):
   # default query merics paging size is 60 minutes
   pagingSize = 60 * QUERY_TIME_RANGE_1_HOUR
   # some object level metrics query paging size is 10 minutes
   if entityType in OBJECT_ENTITY_TYPES:
      pagingSize = 10
   # host and cluster query paging size is 12 hours
   elif entityType in HOST_ENTITY_TYPES:
      pagingSize = 60 * QUERY_TIME_RANGE_12_HOURS
   # nvme stats guardrail for paging size
   elif entityType in LONG_RETENTION_STATS_ENTITY_TYPES:
      pagingSize, dumpDuration, collectInterval = getLongRetentionStatsOptions(debugMode, longRetentionStatsModeIntervalInMinutes)
   return pagingSize

def getCollectInterval(entityType):
   # nvme stats guardrail for interval
   collectInterval = default_collectInterval
   if entityType in LONG_RETENTION_STATS_ENTITY_TYPES:
      pagingSize, dumpDuration, collectInterval = getLongRetentionStatsOptions(debugMode, longRetentionStatsModeIntervalInMinutes)
   return collectInterval



pagingResultSeparator = "--------------Stats Segment Separator--------------"

def buildRanges(minutes2Dump, endTime, priority, entityType, pagingSize=None, collectInterval=None):

   if not pagingSize:
      pagingSize = getPagingSize(priority, entityType)
   if not collectInterval:
      collectInterval = getCollectInterval(entityType)
   queryRange = minutes2Dump // pagingSize
   # If the query range less than 1 hour
   if queryRange == 0:
      startTime = endTime - datetime.timedelta(minutes=minutes2Dump)
      yield (startTime, endTime)
   for offset in range(queryRange):
      segEndTime = endTime - datetime.timedelta(minutes=offset*pagingSize)
      segStartTime = segEndTime - datetime.timedelta(minutes=pagingSize) \
                     + datetime.timedelta(seconds=collectInterval)
      yield (segStartTime, segEndTime)

def buildQuerySpec(priority="P0", endTime=None, startTime=None, pagingSize=None, collectInterval=None):
   if endTime is None:
      endTime = datetime.datetime.utcnow()
      minutes2Dump = hours2Dump * 60
   else:
      endTime = datetime.datetime.utcfromtimestamp(endTime)
      startTime = datetime.datetime.utcfromtimestamp(startTime)
      minutes2Dump = int((endTime - startTime).total_seconds() // 60)

   querySpecs = []
   metrics = supportBundlePriorityMetrics.get(priority)
   if not metrics:
      return []

   for entityType, fields in metrics.items():
      ranges = buildRanges(minutes2Dump, endTime, priority, entityType, pagingSize=pagingSize, collectInterval=collectInterval)
      for segStartTime, segEndTime in ranges:
         if fields == allFields:
            fields = None
         if entityType == "computeCluster-remotedomclient":
            hSpec = vim.cluster.VsanPerfQuerySpec(
            entityRefId='%s:*|*' % entityType,
            startTime=segStartTime,
            endTime=segEndTime,
            labels = fields
         )
         else:
            hSpec = vim.cluster.VsanPerfQuerySpec(
               entityRefId='%s:*' % entityType,
               startTime=segStartTime,
               endTime=segEndTime,
               labels = fields
            )
         querySpecs.append(hSpec)
   return querySpecs

# Refine the querSpecs according to the first round result.
# Case 1. In this script, if the querySpec throw InvalidArgument exception, which means the
#      entityRefId is not valid (the table doesn't exist), so in querySpecs list remove all
#      the querySpec with same entityRefId.
# Case 2. If hit the "no such column" exception, this means that the field is not valid in
#      some table, so update the query field of querySpec with same entityRefId
def updateQuerySpecs(querySpecs, querySpec, ex):
   # In Case 1, the script need handle vmodl.fault.InvalidArgument exception.
   # This exception happens when script query some table whic not existed in the old version host.
   # Remove all the querySpec with same entityRefId in querySpec list .
   if isinstance(ex, vmodl.fault.InvalidArgument):
      entityRefId = querySpec.entityRefId
      for qSpec in querySpecs:
         if qSpec.entityRefId == entityRefId:
            querySpecs.remove(qSpec)

   # In second case, the script needs catch the vmodl.fault.SystemError exception,
   # and rebuild the querySpec in this way:
   # remove all the fields following the first column of exception "no such column:",
   # because new added fields are appened to the end of every entity type list.
   # Other type exceptions will be caught, script continue to do next query.
   if isinstance(ex, vmodl.fault.SystemError):
      NO_SUCH_COLUMN = "no such column: "
      msg = ex.msg
      labels = querySpec.labels
      if not msg.startswith(NO_SUCH_COLUMN):
         return
      startSkipField = msg[len(NO_SUCH_COLUMN):]
      removeIdx = labels.index(startSkipField)
      entityRefId = querySpec.entityRefId
      for qSpec in querySpecs:
         if qSpec.entityRefId == entityRefId:
            querySpec.labels = labels[:removeIdx]
   return querySpecs

def printQueryResult(printSeparator, querySpec, withHeader):
   statsArray = vpm.QueryVsanPerf(querySpecs=[querySpec])
   if len(statsArray[0].sampleInfo) > 0:
      # P1 and P2 metrics share one header, if there are no existed P2 metrics in
      # database, then don't print seperator which before P2 result, and
      # don't print P2 metrics either.
      if printSeparator or not withHeader:
         print(pagingResultSeparator)
      else:
         printSeparator = True
      print(pyVmomi.SoapAdapter.Serialize(statsArray).decode('utf-8'))
      return printSeparator

def dumpStats(priority="P0", withHeader=True, endTime=None, startTime=None, pagingSize=None, collectInterval=None):
   querySpecs = buildQuerySpec(priority=priority, endTime=endTime, startTime=startTime, pagingSize=pagingSize, collectInterval=collectInterval)
   statsArray = None

   # Avoid keeping results of all tables in perfsvc memory and dump process memeory.
   printSeparator = False
   if "with_dump" in selectedInfo:
      if withHeader:
         print('--------------SOAP stats dump--------------')
      for querySpec in querySpecs:
         try:
            printSeparator = printQueryResult(printSeparator, querySpec, withHeader)
         except Exception as ex:
            if not isinstance(ex, vmodl.fault.SystemError) and \
                  not isinstance(ex, vmodl.fault.InvalidArgument):
               continue
            querySpecs = updateQuerySpecs(querySpecs, querySpec, ex)
            try:
               printSeparator = printQueryResult(printSeparator, querySpec, withHeader)
            except:
               pass
   else:
      if withHeader:
         print('--------------Perf Service Entity Stats--------------')
      for querySpec in querySpecs:
         statsArray = vpm.QueryVsanPerf(querySpecs=[querySpec])
         for stats in statsArray:
            print(stats)

if selectedInfo in ['selective_with_dump'] and nodeInfos[0].isStatsMaster:
   try:
      dumpStats(priority="P0", endTime=endTime, startTime=startTime)
      dumpStats(priority="P1", withHeader=False, endTime=endTime, startTime=startTime)
      dumpStats(priority="P2", withHeader=False, endTime=endTime, startTime=startTime)
      dumpStats(priority="P3", withHeader=False, endTime=endTime, startTime=startTime)
      dumpStats(priority="P4", withHeader=False, endTime=endTime, startTime=startTime)
      #dumpStats(priority="P5", withHeader=False, endTime=endTime, startTime=startTime)
   except Exception as ex:
      print ("Collect performance metrics HCIBench stats fail because %s." % ex)

#Dump default level (P0, P1) various stats for on-demand support bundle collection
if selectedInfo in ['perf_stats', 'perf_stats_with_dump']:
   try:
      dumpStats(priority="P0")
      # dump P1 metrics after P0, share the header with P0 metrics
      dumpStats(priority="P1", withHeader=False)
   except Exception as ex:
      print ("Collect performance metrics stats fail because %s." % ex)

#Dump extented level (P2) various stats for on-demand support bundle collection
if selectedInfo in ['perf_stats_extended', 'perf_stats_with_dump_extended']:
   try:
       dumpStats(priority="P2")
   except Exception as ex:
      print ("Collect performance metrics extended stats fail because %s." % ex)

# Dump data for diagnostic mode
if selectedInfo in ['perf_stats_diag', 'perf_stats_with_dump_diag']:
   try:
      dumpStats(priority="P3")
   except Exception as ex:
      print ("Collect diagnostic metrics fail because %s." % ex)

# Dump data for vscsi, virtual-disk
if selectedInfo in ['perf_stats_vmdk', 'perf_stats_with_dump_vmdk']:
   try:
      dumpStats(priority="P4")
   except Exception as ex:
      print ("Collect vmdk metrics fail because %s." % ex)

# Dump data for IOInsight stats
if selectedInfo in ['perf_stats_ioinsight', 'perf_stats_with_dump_ioinsight']:
   try:
      dumpStats(priority="P5")
   except Exception as ex:
      print ("Collect I/O Insight metrics fail because %s." % ex)

# Dump data for vSAN Direct stats
if selectedInfo in ['vsandirect_stats', 'vsandirect_stats_with_dump']:
   try:
      dumpStats(priority="P7")
   except Exception as ex:
      print ("Collect vSAN Direct metrics fail because %s." % ex)

# Dump data for high resolution mode
if selectedInfo in ['perf_stats_high_resolution', 'perf_stats_with_dump_high_resolution']:
   try:
      dumpStats(priority="P8")
   except Exception as ex:
      print ("Collect high resolution metrics fail because %s." % ex)

# Dump data for nvme smart stats
if selectedInfo in ['perf_stats_device_long_retention', 'perf_stats_with_dump_device_long_retention']:
   try:
      # We need to support the debug mode and customized collection interval
      pagingSize, dumpDuration, collectInterval = getLongRetentionStatsOptions(debugMode, longRetentionStatsModeIntervalInMinutes)
      currentTime = int(time.time())
      startTime = currentTime - dumpDuration
      dumpStats(priority="P9", endTime=currentTime, startTime=startTime, pagingSize=pagingSize, collectInterval=collectInterval)
   except Exception as ex:
      print ("Collect device stats metrics fail because %s." % ex)

