#!/usr/bin/env python
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
else:
   os.environ['VSAN_PYMO_SKIP_VC_CONN'] = '1'
   import vsanmgmtObjects

from argparse import ArgumentParser, RawTextHelpFormatter
try:
   from VsanConfigUtil import DATA_PROTECTION_ENABLED
except:
   DATA_PROTECTION_ENABLED = False


def commandsDescription(msg=None):
   msg = '''<svc_info|perf_stats_with_dump|perf_stats_with_dump_extended|perf_stats|perf_stats_extended|perf_stats_diag|perf_stats_with_dump_diag|perf_stats_vmdk|perf_stats_with_dump_vmdk|ioinsight_stats|ioinsight_stats_with_dump>
svc_info                                     Print vSAN performance service information.
perf_stats_with_dump [days|hours]            Dump vSAN performance service stats in SOAP format, argument is number of days, by default dump 2 days.
perf_stats_with_dump_extended [days|hours]   Dump vSAN performance service extended stats in SOAP format, argument is number of days, by default dump 2 days.
perf_stats_with_dump_diag  [days|hours]      Dump vSAN diagnostic stats in SOAP format, argument is number of days, by default print 2 days.
perf_stats_with_dump_vmdk  [days|hours]      Dump vSAN virtual SCSI, virtual disk, virtual machine stats in SOAP format, argument is number of days, by default print 2 days.
perf_stats  [days|hours]                     Print vSAN performance service stats, argument is number of days, by default print 2 days.
perf_stats_extended  [days|hours]            Print vSAN performance service extended stats, argument is number of days, by default print 2 days.
perf_stats_diag  [days|hours]                Print vSAN diagnostic stats, argument is number of days, by default print 2 days.
perf_stats_vmdk  [days|hours]                Print vSAN virtual SCSI, virtual disk, virtual machine stats, argument is number of days, by default print 2 days.
ioinsight_stats  [days|hours]                Print vSAN IOInsight stats, argument is number of days, by default print 2 days.
ioinsight_stats_with_dump   [days|hours]     Print vSAN IOInsight stats in SOAP format, argument is number of days, by default print 2 days.
selective_with_dump                          Print vSAN performance service selective stats, in this command, starttime and endtime must be passed. The format of stattime and endtime is Unix epoch time.
      '''
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

collectInterval = 300
try:
   configs = ReadConfigFile()
   if "interval" in configs:
      collectInterval = int(configs["interval"])
except:
   pass

def checkCommand(command):
   if command not in ['svc_info', 'perf_stats', 'perf_stats_with_dump',
                      'perf_stats_extended', 'perf_stats_with_dump_extended', 'selective_with_dump',
                      'perf_stats_diag', 'perf_stats_with_dump_diag', 'perf_stats_vmdk', 'perf_stats_with_dump_vmdk',
                      'ioinsight_stats', 'ioinsight_stats_with_dump']:
      print('Error: Invalid command, please use -h to get valid command.')
      sys.exit(1)

def checkRange(command, timeRange):
   if command in ['perf_stats', 'perf_stats_with_dump',
                  'perf_stats_extended', 'perf_stats_with_dump_extended',
                  'perf_stats_diag', 'perf_stats_with_dump_diag', 'perf_stats_vmdk', 'perf_stats_with_dump_vmdk',
                  'ioinsight_stats', 'ioinsight_stats_with_dump']:
      try:
         days2Dump = int(timeRange)
      except:
         print('The days for dump stats should be integer!')
         sys.exit(1)

def checkUnit(unit):
   if unit not in ['hour', 'day']:
      print('Invalid option, please use -h to get valid option!')
      sys.exit(1)

def checkDumpHours(hours2Dump):
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
checkUnit(unit)
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
checkDumpHours(hours2Dump)

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
           "avgDdpWriteTime", "avgDdpCommitTime", "avgElevIoSize", "b0Data",
           "b1Data", "b2Data", "b3Data", "capacityCompressed",
           "multiElevCompressionTime", "multiElevCompressPct", "multiElevNumCompressedBlocks",
           "multiElevNumUncompressedBlocks", "multiElevDedupXmapHitRt", "multiElevNumXMapRd",
           "multiElevNumXMapWrt", "multiElevNumBitmapRd", "multiElevNumBitmapWrt",
           "multiElevAvgPreReadTime", "multiElevDataWriteTime",
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
           "curBytesToSyncRepair",
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
   "wobtree": allFields,
   "cluster-domcompmgr": allFields,
   "cluster-domowner": allFields,
   "vsan-file-service": allFields,
   "psa-completion-world-cpu": allFields,
}

supportBundlePriorityMetrics["P1"] = {
   "cmmds-net": allFields,
   "cache-disk": [
           "plogReadQLatency", "plogWriteQLatency",
           "plogTotalBytesRead", "plogTotalBytesReadFromMD", "plogTotalBytesReadFromSSD",
           "plogTotalBytesReadByRC", "plogTotalBytesReadByVMFS", "plogNumTotalReads",
           "plogNumMDReads", "plogNumSSDReads", "plogNumRCReads", "plogNumVMFSReads",
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
   "cmmds": allFields,
}

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
           "elevNextWindow", "elevCurBucket",
   ],
}

supportBundlePriorityMetrics["P3"] = {
   "vsan-pnic-net": allFields,
   "vsan-vnic-net": allFields,
   "vsan-host-net": allFields,
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

hostEntityTypes = ["cluster-domclient", "host-domclient",
                    "cluster-remotedomclient", "host-domowner",
                    "host-domcompmgr", "clom-disk-stats", "clom-host-stats",
                    "host-vsansparse", "vsan-host-net", "host-cpu",
                    "cmmds", "cmmds-net", "cmmds-workloadstats"]
objectTypes = ["vmdk-vsansparse", "dom-per-proxy-owner", "vscsi", "virtual-disk", "ioinsight"]

def getPagingSize(priority, entityType):
   # default query merics paging size is 60 minutes
   pagingSize = 60
   # some object level metrics query paging size is 10 minutes
   if entityType in objectTypes:
      pagingSize = 10
   # host and cluster query paging size is 12 hours
   elif entityType in hostEntityTypes:
      pagingSize = 60 * 12
   return pagingSize


pagingResultSeparator = "--------------Stats Segment Separator--------------"

def buildRanges(minutes2Dump, endTime, priority, entityType):

   pagingSize = getPagingSize(priority, entityType)
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

def buildQuerySpec(priority="P0", endTime=None, startTime=None):
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
      ranges = buildRanges(minutes2Dump, endTime, priority, entityType)
      for segStartTime, segEndTime in ranges:
         if fields == "All":
            fields = None
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

def dumpStats(priority="P0", withHeader=True, endTime=None, startTime=None):
   querySpecs = buildQuerySpec(priority=priority, endTime=endTime, startTime=startTime)
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
if selectedInfo in ['ioinsight_stats', 'ioinsight_stats_with_dump']:
   try:
      dumpStats(priority="P5")
   except Exception as ex:
      print ("Collect IOInsight metrics fail because %s." % ex)
