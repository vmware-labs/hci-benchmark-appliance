# -*- coding: utf-8 -*-

"""
Copyright 2015-2021 VMware, Inc.  All rights reserved.
-- VMware Confidential

"""

"""
Sample description can be as follows:
Description supports markdown
newline == \n\n
"description" : "Dashboard details\n\n**metric1** : metric1 details\n\n""

"""

def fmt_desc(lvl, desc_list):
   stat_desc_fn = lambda name, desc: "- %s: %s" % (name, desc)
   level_desc_fn = lambda lvl: "**Level:** %s" % (lvl)
   desc_fn = lambda metrics_list: "**Description:**\n\n%s" % '\n\n'.join([stat_desc_fn(n, d) for n, d in metrics_list])
   return "%s\n\n%s" % (level_desc_fn(lvl), desc_fn(desc_list))

def get_world_metrics_definition():
   uctPctDef = {
      'title': 'CPU Utilization Percentage',
      'metrics': [ "usedPct", ],
      'unit': u"percent",
      'min': 0,
   }
   readyPctDef = {
      'title': 'CPU Ready Percentage',
      'metrics': [ "readyPct", ],
      'unit': u"percent",
      'min': 0,
   }
   runPctDef = {
      'title': 'CPU Run Percentage',
      'metrics': [ "runPct", ],
      'unit': u"percent",
      'min': 0,
   }
   return [uctPctDef, readyPctDef, runPctDef]

def get_vsan_zdom_vtx_overview_metrics_definition():
   overview = {
      'title': 'Overview',
      'metrics': [
         ('rateTxnReadWrite', 'Read and Write Transaction')
      ],
      'unit': u"short",
      'min': 0,
   }
   maxLatencyPerTxn = {
      'title': 'Max Latency Per Transaction',
      'metrics': [
         'txnDLogMaxLatUs', 'txnBankMaxLatUs',
         'txnSegCtxDataMaxLatUs', 'txnSegCtxLLPMaxLatUs',
         'txnVatWriteSegMaxLatUs', 'txnUnmapMaxLatUs',
         'txnCacheFlushMaxLatUs', 'txnDelExtMiddleTreeMaxLatUs',
         'txnPrefetchMaxLatUs', 'txnBankMaxLatUs',
      ],
      'unit': u"µs",
      'min': 0,
   }
   prefetchCacheMaxGetLatUs = {
      'title': 'Prefetch Cache Max Get Lat',
      'metrics': [
         ('prefetchCacheMaxGetLatUs', 'allOpTotIOLatSumUs'),
      ],
      'unit': u"µs",
      'min': 0,
   }
   return [overview, maxLatencyPerTxn, prefetchCacheMaxGetLatUs]

def get_vsan_zdom_vtx_blockcache_metrics_definition():
   overallBlockCacheMiss = {
      'title': 'Overall Block Cache Miss',
      'metrics': [
         ('rateTotalCacheMiss', 'Total'),
         ('rateSegCleaningCtxDataCacheMiss', 'Seg Cleaning'),
         ('ratePrefetchCacheMiss', 'Prefetch'),
         ('rateBankFlushCacheMiss', 'Bank Flush'),
         ('rateLookUpCacheMiss', 'LookUp'),
      ],
      'unit': u"short",
      'min': 0,
   }
   overallBlockRefRef = {
      'title': 'Overall Block Cache Ref',
      'metrics': [
         ('rateTotalCacheRef', 'Total Get Tput'),
         ('rateBankFlushTotalCacheRef', 'BankFlushTotCacheRef'),
         ('rateSegCleaningCtxDataTotalCacheRef', 'SegCleaningCtxDataTotCacheRef')
      ],
      'unit': u"short",
      'min': 0,
   }
   overallBlockGetLatency = {
      'title': 'Overall Block Cache Get Latency',
      'metrics': [
         ('latAvgCacheGet', 'allOpCacheGetLatSumUs'),
         ('latAvgTotalOpIO', 'allOpTotIOLatSumUs')
      ],
      'unit': u"µs",
      'min': 0,
   }
   overallBlockMaxLatency = {
      'title': 'Overall Block Cache Get Latency',
      'metrics': [
         ('allOpCacheMaxGetLatUSec', 'allOpTotIOLatSumUs')
      ],
      'unit': u"µs",
      'min': 0,
   }
   return [overallBlockCacheMiss, overallBlockRefRef, overallBlockGetLatency, overallBlockMaxLatency]

def get_vsan_zdom_vtx_prefetch_metrics_definition():
   prefetchCacheMiss = {
      'title': 'Prefetch Cache Miss',
      'metrics': [
         ('rateTxnPrefetchTotalCacheMiss', 'prefetchCacheMiss'),
         ('rateTxnPrefetchLogicalTreeCacheMiss', 'prefetchLogicalTreeCacheMiss'),
         ('rateTxnPrefetchMiddleTreeCacheMiss', 'prefetchMiddleTreeCacheMiss'),
         ('rateTxnPrefetchSutCacheMiss', 'prefetchSutCacheMiss')
      ],
      'unit': u"short",
      'min': 0,
   }
   prefetchCacheRef = {
      'title': 'Prefetch Cache Ref',
      'metrics': [
         ('rateTxnPrefetchTotalCacheRef', 'prefetchTotCacheRef'),
         ('rateTxnPrefetchLogicalTreeCacheRef', 'prefetchLogicalTreeCacheRef'),
         ('rateTxnPrefetchMiddleTreeCacheRef', 'prefetchMiddleTreeCacheRef'),
         ('rateTxnPrefetchSutCacheRef', 'prefetchSutCacheRef')
      ],
      'unit': u"short",
      'min': 0,
   }
   return [prefetchCacheMiss, prefetchCacheRef]

def get_vsan_zdom_vtx_bank_flush_metrics_definition():
   bankFlushCacheMiss = {
      'title': 'Bank Flush Cache Miss',
      'metrics': [
         ('rateTxnBankTotalCacheMiss', 'bankFlushCacheMiss'),
         ('rateTxnBankLogicalTreeCacheMiss', 'bankFlushLogicalTreeCacheMiss'),
         ('rateTxnBankMiddleTreeCacheMiss', 'bankFlushMiddleTreeCacheMiss'),
         ('rateTxnBankSutCacheMiss', 'bankFlushSutCacheMiss')
      ],
      'unit': u"short",
      'min': 0,
   }
   bankFlushCacheRef = {
      'title': 'Bank Flush Cache Ref',
      'metrics': [
         ('rateTxnBankTotalCacheRef', 'bankFlushTotCacheRef'),
         ('rateTxnBankLogicalTreeCacheRef', 'bankFlushLogicalTreeCacheRef'),
         ('rateTxnBankMiddleTreeCacheRef', 'bankFlushMiddleTreeCacheRef'),
         ('rateTxnBankSutCacheRef', 'bankFlushSutCacheRef')
      ],
      'unit': u"short",
      'min': 0,
   }
   bankFlushLatency = {
      'title': 'Bank Flush Per Txn Latency',
      'metrics': [
         ('latAvgTxnBank', 'txnBankLatUs'),
         ('latAvgTxnBankTotalIO', 'Paging in cache')
      ],
      'unit': u"µs",
      'min': 0,
   }
   return [bankFlushCacheMiss, bankFlushCacheRef, bankFlushLatency]

def get_vsan_zdom_vtx_check_pointer_metrics_definition():
   spaceUsage = {
      'title': 'Space Usage',
      'metrics': [
         ('maxDiscUsedPct', 'maxDiscUsedPct')
      ],
      'unit': u"percent",
      'min': 0,
   }
   checkPointerWorkerWakeupMs = {
      'title': 'Worker Wakeup Interval',
      'metrics': [
         ('checkpointWorkerWakeupMs', 'checkpointWorkerWakeupMs')
      ],
      'unit': u"µs",
      'min': 0,
   }
   return [spaceUsage, checkPointerWorkerWakeupMs]

def get_vsan_zdom_vtx_unmap_metrics_definition():
   unmapCacheMiss = {
      'title': 'Unmap Cache Miss',
      'metrics': [
         ('rateTxnUnmapTotalCacheMiss', 'Total'),
         ('rateTxnUnmapLogicalTreeCacheMiss', 'Logical Tree'),
         ('rateTxnUnmapMiddleTreeCacheMiss', 'Middle Tree'),
         ('rateTxnUnmapSutCacheMiss', 'SUT')
      ],
      'unit': u"short",
      'min': 0,
   }
   unmapLatency = {
      'title': 'Unmap Per Txn Latency',
      'metrics': [
         ('latAvgTxnUnmap', 'Tot'),
         ('latAvgTxnUnmapTotalIO', 'Cache Miss Time')
      ],
      'unit': u"µs",
      'min': 0,
   }
   return [unmapCacheMiss, unmapLatency]

def get_vsan_zdom_vtx_seg_cleaning_metrics_definition():
   segCleaningCacheMiss = {
      'title': 'Seg Cleaning Cache Miss',
      'metrics': [
         ('rateTxnSegCleaningCtxDataTotalCacheMiss', 'Total'),
         ('rateTxnSegCleaningCtxDataLogicalTreeCacheMiss', 'Logical Tree'),
         ('rateTxnSegCleaningCtxDataMiddleTreeCacheMiss', 'Middle Tree'),
         ('rateTxnSegCleaningCtxDataSutCacheMiss', 'SUT')
      ],
      'unit': u"short",
      'min': 0,
   }
   segCleaningCacheRef = {
      'title': 'Seg Cleaning Cache Ref',
      'metrics': [
         ('rateTxnSegCleaningCtxDataTotalCacheRef', 'Total'),
         ('rateTxnSegCleaningCtxDataLogicalTreeCacheRef', 'Logical Tree'),
         ('rateTxnSegCleaningCtxDataMiddleTreeCacheRef', 'Middle Tree'),
         ('rateTxnSegCleaningCtxDataSutCacheRef', 'SUT')
      ],
      'unit': u"short",
      'min': 0,
   }
   return [segCleaningCacheMiss, segCleaningCacheRef]

def get_zdom_overview():
   return {
      'title': 'zDOM: Overview Stats',
      'tag' :  'zdom',
      'repeat': True,
      'metrics': [
         {
            'title': 'ZDOM Overview',
            'metrics': [
               ('bankFlushError', 'bankFlushError'),
               ('numZdomObjects', 'numZdomObjects')
            ],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'ZOM IO',
            'metrics': [
               ('tputDLogWrite', 'dLog Throughput'),
               ('tputBankFlush', 'bank Throughput'),
               ('tputMLogWrite', 'mLog Throughput'),
               ('tputUnmap', 'unmap Throughput')
            ],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'ZDOM VTX',
            'metrics': [
               ('rateTxnCreateOpBankCount', 'txnCreateOpBankCount'),
               ('rateTxnCreateOpSegMoveFreeCount', 'txnCreateOpSegMoveFreeCount'),
               ('rateTxnCreateOpUnmapCount', 'txnCreateOpUnmapCount')
            ],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'ZDOM Segment Cleaning',
            'metrics': [
               ('tputSegCleanUnmap', 'Seg-cleaner Unmap'),
               ('tputSegCleanWrite', 'Seg-cleaner Write'),
               ('tputSegCleanRead', 'Seg-cleaner Read'),
            ],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'ZDOM LLP',
            'metrics': [
               ('tputVatWriteback', 'Vat Writeback'),
            ],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'ZDOM Snapshot',
            'metrics': [
               ('snapCreateCount', 'snapCreateCount'),
               ('snapDeleteCount', 'snapDeleteCount'),
               ('latAvgSnapCreate', 'snapCreateAvgLat'),
               ('latAvgSnapDelete', 'snapDeleteAvgLat')
            ],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'ZDOM Log Bypass Throughput',
            'metrics': [
               ('tputBypassWrite')
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'ZDOM Log Bypass Percent',
            'metrics': [
               ('bypassWritePercent')
            ],
            'unit': u"percent",
            'min': 0,
            'detailOnly': True,
         },
      ],
      'entityToShow':'zdom-overview',
   }

def get_zdom_snapshot():
   return {
      'title': 'zDOM: Snapshot Stats',
      'tag' :  'zdom',
      'repeat': True,
      'metrics': [
         {
            'title': 'Logical Map pages deleted',
            'metrics': [
               ('logicalMapPagesDeleteCount', 'PhysicalExtentsWithoutPerzDOM'),
            ],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'Logical Map pages read count',
            'metrics': [
               ('logicalMapPagesReadCount', 'LogicalMapReadWithoutPerzDOM'),
            ],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'MiddleMap Physical Extents Deleted',
            'metrics': [
               ('middleMapExtentsDeleteCount', 'PhysicalExtentsWithoutPerzDOM'),
            ],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'Snapshot Deletion Transaction Log Per Txn',
            'metrics': [
               ('ioSizeTxnSnapDeleteLog', 'txnSnapDeleteLog'),
               ('ioSizeTxnSnapDelMetaUpdateLog', 'txnSnapDelMetaUpdateLog'),
               ('ioSizeTxnDelExtMiddleTreeLog', 'txnDelExtMiddleTreeLog'),
            ],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'Snapshot Deletion Transaction Log Throughput',
            'metrics': [
               ('tputTxnSnapDeleteLog', 'txnSnapDeleteLogBytes'),
               ('tputTxnSnapDelMetaUpdateLog', 'txnSnapDelMetaUpdateLogBytes'),
               ('tputTxnDelExtMiddleTreeLog', 'txnDelExtMiddleTreeLogBytes')
            ],
            'unit': u"Bps",
            'min': 0,
         },
      ],
      'entityToShow':'zdom-snapshot',
   }

def get_zdom_llp():
   return {
      'title': 'zDOM: LLP Stats',
      'tag' :  'zdom',
      'repeat': True,
      'metrics': [
         {
            'title': 'Cache WB Segment Bytes',
            'metrics': [
               ('tputTruncVatWriteBack', 'TruncateWB TPut Needed'),
               ('rateTruncVatWriteBackNumSegments', 'TruncateWB TPut Actual'),
               ('tputMpVatWriteBack', 'MemPressWB TPut Needed'),
               ('rateMpVatWriteBackNumSegments', 'MemPressWB TPut Actual')
            ],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'Latency of Vat WB',
            'metrics': [
               ('latAvgTruncVatWriteBack', 'TruncWB Latency, per Truncation'),
               ('latAvgMpVatWriteBack', 'MemPressWB Latency')
            ],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'Barrier for Vat Gather Latency',
            'metrics': [
               ('latAvgTruncVatWriteBack', 'TruncWB Latency, per Truncation'),
               ('latAvgMpVatWriteBack', 'MemPressWB Latency'),
               ('latAvgMLogBarrierGatherVat', 'Barrier Vat Gather Latency'),
               ('latAvgTruncVatWriteBackCopyOut', 'Trunc Vat WB Copy out latency')
            ],
            'unit': u"µs",
            'min': 0,
         },
      ],
      'entityToShow':'zdom-llp',
   }

def get_zdom_seg_cleaning():
   return {
      'title': 'zDOM: Segment Cleaning Stats',
      'tag' :  'zdom',
      'repeat': True,
      'metrics': ZdomSegmentCleaningMetrics,
      'entityToShow':'zdom-seg-cleaning',
   }

def get_zdom_seg_cleaning_bucket():
   return {
      'title': 'zDOM: Segment Cleaning Bucket Stats',
      'tag' :  'zdom',
      'repeat': True,
      'metrics': ZdomSegmentCleaningBucketMetrics,
      'entityToShow':'zdom-seg-cleaning',
   }


def get_vsan_zdom_gsc_capacity():
   return {
      'title': 'zDOM: GSC Capacity Tier',
      'tag' :  'zdom',
      'repeat': True,
      'metrics': ZdomGscCapacityPartitionMetrics,
      'entityToShow':'vsan-zdom-gsc',
   }

def get_vsan_zdom_top():
   return {
      'title': 'zDOM: Top Stats (Stats of IO entering zDOM)',
      'tag' :  'zdom',
      'repeat': True,
      'metrics': [
         {
            'title': 'Latency',
            'metrics': ['latencyAvgRead', 'latencyAvgWrite',
                        'latencyAvgUnmap', ],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
         },
         {
            'title': 'IOPS',
            'metrics': ['iopsRead', 'iopsWrite', 'iopsUnmap'],
            'unit': u"iops",
            'min': 0,
         },
         {
            'title': 'Tput',
            'metrics': ['throughputRead', 'throughputWrite',
                        'throughputUnmap'],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'OIO',
            'metrics': ['oio', 'oioRead', 'oioWrite'],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'OIO number',
            'metrics': ['numOio', 'numOioRead', 'numOioWrite'],
            'unit': u"short",
            'min': 0,
         },
      ],
      'entityToShow':'-zdom-top-stats',
   }


Vsan2DomDiskMetrics = [
   {
      'title': 'IOPS',
      'metrics': [('iopsReadCompMgr', 'Read'),
                  ('iopsWriteCompMgr', 'Write'),
                  ('iopsUnmapCompMgr', 'Unmap'),
                  ('iopsRecoveryWriteCompMgr', 'Recovery Write'),
                  ('iopsRecoveryUnmapCompMgr', 'Recovery Unmap')],
      'unit': u"iops",
      'min': 0,
   },
   {
      'title': 'Bandwidth',
      'metrics': [('throughputReadCompMgr', 'Read'),
                  ('throughputWriteCompMgr', 'Write'),
                  ('throughputUnmapCompMgr', 'Unmap'),
                  ('throughputRecoveryWriteCompMgr', 'Recovery Write'),
                  ('throughputRecoveryUnmapCompMgr', 'Recovery Unmap')],
      'unit': u"Bps",
      'min': 0,
   },
   {
      'title': 'Latency',
      'metrics': [('latencyReadCompMgr', 'Read'),
                  ('latencyWriteCompMgr', 'Write'),
                  ('latencyUnmapCompMgr', 'Unmap'),
                  ('latencyRecoveryWriteCompMgr', 'Recovery Write'),
                  ('latencyRecoveryUnmapCompMgr', 'Recovery Unmap')],
      'unit': u"µs",
      'min': 0,
   },
   {
      'title': 'OIO',
      'metrics': [('oioReadCompMgr', 'Read'),
                  ('oioWriteCompMgr', 'Write'),
                  ('oioUnmapCompMgr', 'Unmap'),
                  ('oioRecoveryWriteCompMgr', 'Recovery Write'),
                  ('latencyAvgRecUnmap', 'Recovery Unmap')],
      'unit': u"short",
      'min': 0,
   },
   {
      'title': 'IOPS Regulator',
      'metrics': [('regulatorIopsReadSched', 'Read'),
                  ('regulatorIopsWriteSched', 'Write')],
      'unit': u"iops",
      'min': 0,
      'detailOnly': True,
   },
   {
      'title': 'LSOM Congestion',
      'metrics': [('componentCongestionReadSched', 'Read Component'),
                  ('componentCongestionWriteSched', 'Write Component'),
                  ('diskgroupCongestionReadSched', 'Read DiskGroup'),
                  ('diskgroupCongestionWriteSched', 'Write DiskGroup')],
      'unit': u"short",
      'min': 0,
      'detailOnly': True,
   },
   {
      'title': 'Scheduler Queue Depth',
      'metrics': [('metadataQueueDepthReadSched', 'Read Metadata'),
                  ('metadataQueueDepthWriteSched', 'Write Metadata'),
                  ('namespaceQueueDepthReadSched', 'Read Namespace'),
                  ('namespaceQueueDepthWriteSched', 'Write Namespace'),
                  ('resyncQueueDepthReadSched', 'Read Resync'),
                  ('resyncQueueDepthWriteSched', 'Write Resync'),
                  ('vmdiskQueueDepthReadSched', 'Read VM Disk'),
                  ('vmdiskQueueDepthWriteSched', 'Write VM Disk')],
      'unit': u"iops",
      'min': 0,
      'detailOnly': True,
   },
   {
      'title': 'Backpressure Congestion',
      'metrics': [('metadataBackpressureCongestionReadSched', 'Read Metadata'),
                  ('metadataBackpressureCongestionWriteSched', 'Write Metadata'),
                  ('namespaceBackpressureCongestionReadSched', 'Read Namespace'),
                  ('namespaceBackpressureCongestionWriteSched', 'Write Namespace'),
                  ('resyncBackpressureCongestionReadSched', 'Read Resync'),
                  ('resyncBackpressureCongestionWriteSched', 'Write Resync'),
                  ('vmdiskBackpressureCongestionReadSched', 'Read VM Disk'),
                  ('vmdiskBackpressureCongestionWriteSched', 'Write VM Disk')],
      'unit': u"short",
      'min': 0,
      'detailOnly': True,
   },
   {
      'title': 'Scheduler Cost Bandwidth',
      'metrics': [('metadataDispatchedCostReadSched', 'Read Metadata'),
                  ('metadataDispatchedCostWriteSched', 'Write Metadata'),
                  ('namespaceDispatchedCostReadSched', 'Read Namespace'),
                  ('namespaceDispatchedCostWriteSched', 'Write Namespace'),
                  ('resyncDispatchedCostReadSched', 'Read Resync'),
                  ('resyncDispatchedCostWriteSched', 'Write Resync'),
                  ('vmdiskDispatchedCostReadSched', 'Read VM Disk'),
                  ('vmdiskDispatchedCostWriteSched', 'Write VM Disk')],
      'unit': u"Bps",
      'min': 0,
      'detailOnly': True,
   },
   {
      'title': 'Scheduler Bandwidth',
      'metrics': [('metadataThroughputReadSched', 'Read Metadata'),
                  ('metadataThroughputWriteSched', 'Write Metadata'),
                  ('namespaceThroughputReadSched', 'Read Namespace'),
                  ('namespaceThroughputWriteSched', 'Write Namespace'),
                  ('resyncThroughputReadSched', 'Read Resync'),
                  ('resyncThroughputWriteSched', 'Write Resync'),
                  ('vmdiskThroughputReadSched', 'Read VM Disk'),
                  ('vmdiskThroughputWriteSched', 'Write VM Disk')],
      'unit': u"Bps",
      'min': 0,
      'detailOnly': True,
   },
   {
      'title': 'Delayed IO Percentage',
      'metrics': [
         ('iopsDelayPctSched', 'Delayed IO Percentage')
      ],
      'unit': u"percent",
      'min': 0,
      'detailOnly': True,
      'description' : fmt_desc('Developer', [
         ('Delayed IO Percentage', 'The percentage of IOs which go though vSAN internal queues')
      ]),
   },
   {
      'title': 'Delayed IO Average Latency',
      'metrics': [
         ('latencyDelaySched', 'Delayed IO Average Latency'),
         ('latencySchedQueueNS', 'Latency of Namespace Queue'),
         ('latencySchedQueueRec', 'Latency of Recovery Queue'),
         ('latencySchedQueueVM', 'Latency of VM Queue'),
         ('latencySchedQueueMeta', 'Latency of Meta Queue')
      ],
      'unit': u"µs",
      'thresholds': [30000, 50000],
      'min': 0,
      'detailOnly': True,
      'description' : fmt_desc('Developer', [
         ('Delayed IO Average Latency', 'The average latency of total IOs which go though vSAN internal queues'),
         ('Latency of Namespace Queue', 'The Latency of the namespace IO queue in the vSAN internal scheduler'),
         ('Latency of Recovery Queue', 'The Latency of the recovery IO queue in the vSAN internal scheduler'),
         ('Latency of VM Queue', 'The Latency of the VM IO queue in the vSAN internal scheduler'),
         ('Latency of Meta Queue', 'The Latency of the meta IO queue in the vSAN internal scheduler'),
      ]),
   },
   {
      'title': 'Delayed IOPS',
      'metrics': [
         ('iopsSched', 'Total Delayed IOPS'),
         ('iopsSchedQueueNS', 'IOPS of Namespace Queue'),
         ('iopsSchedQueueRec', 'IOPS of Recovery Queue'),
         ('iopsSchedQueueVM', 'IOPS of VM Queue'),
         ('iopsSchedQueueMeta', 'IOPS of Meta Queue')
      ],
      'unit': u"iops",
      'min': 0,
      'detailOnly': True,
      'description' : fmt_desc('Developer', [
         ('Total Delayed IOPS', 'The IOPS of total IOs which go through vSAN internal queues'),
         ('IOPS of Namespace Queue', 'The IOPS of the namespace IO queue in the vSAN internal scheduler'),
         ('IOPS of Recovery Queue', 'The IOPS of the recovery IO queue in the vSAN internal scheduler'),
         ('IOPS of VM Queue', 'The IOPS of the VM IO queue in the vSAN internal scheduler'),
         ('IOPS of Meta Queue', 'The IOPS of the meta IO queue in the vSAN internal scheduler'),
      ]),
   },
   {
      'title': 'Delayed IO Throughput',
      'metrics': [
         ('throughputSched', 'Total Queue Throughput'),
         ('throughputSchedQueueNS', 'Throughput of Namespace Queue'),
         ('throughputSchedQueueRec', 'Throughput of Recovery Queue'),
         ('throughputSchedQueueVM', 'Throughput of VM Queue'),
         ('throughputSchedQueueMeta', 'Throughput of Meta Queue')
      ],
      'unit': u"Bps",
      'min': 0,
      'detailOnly': True,
      'description' : fmt_desc('Developer', [
         ('Total Queue Throughput', 'The throughput of total delayed IO in the vSAN internal scheduler'),
         ('Throughput of Namespace Queue', 'The throughput of the namespace IO queue in the vSAN internal scheduler'),
         ('Throughput of Recovery Queue', 'The throughput of the recovery IO queue in the vSAN internal scheduler'),
         ('Throughput of VM Queue', 'The throughput of the VM IO queue in the vSAN internal scheduler'),
         ('Throughput of Meta Queue', 'The throughput of the meta IO queue in the vSAN internal scheduler'),
      ]),
   },
]

Vsan2DomSchedulerMetrics = [
   {
      'title': 'Latency',
      'metrics': ['latencySched',
                  'latencySchedQueueNS', 'latencySchedQueueRec',
                  'latencySchedQueueVM', 'latencySchedQueueMeta',
                  'latencyDelaySched', 'latResyncRead', 'latResyncWrite',
                  'latResyncReadPolicy', 'latResyncWritePolicy',
                  'latResyncReadDecom', 'latResyncWriteDecom',
                  'latResyncReadRebalance', 'latResyncWriteRebalance',
                  'latResyncReadFixComp', 'latResyncWriteFixComp',
                  ],
      'unit': u"µs",
      'thresholds': [30000, 50000],
      'min': 0,
   },
   {
      'title': 'IOPS',
      'metrics': ['iopsSched',
                  'iopsSchedQueueNS', 'iopsSchedQueueRec',
                  'iopsSchedQueueVM', 'iopsSchedQueueMeta',
                  'iopsDirectSched',
                  'iopsResyncRead', 'iopsResyncWrite',
                  'iopsResyncReadPolicy', 'iopsResyncWritePolicy',
                  'iopsResyncReadDecom', 'iopsResyncWriteDecom',
                  'iopsResyncReadRebalance', 'iopsResyncWriteRebalance',
                  'iopsResyncReadFixComp', 'iopsResyncWriteFixComp',
                  ],
      'unit': u"iops",
      'min': 0,
   },
   {
      'title': 'Tput',
      'metrics': ['throughputSched',
                  'throughputSchedQueueNS', 'throughputSchedQueueRec',
                  'throughputSchedQueueVM', 'throughputSchedQueueMeta',
                  'tputResyncRead', 'tputResyncWrite',
                  'tputResyncReadPolicy', 'tputResyncWritePolicy',
                  'tputResyncReadDecom', 'tputResyncWriteDecom',
                  'tputResyncReadRebalance', 'tputResyncWriteRebalance',
                  'tputResyncReadFixComp', 'tputResyncWriteFixComp',
                  ],
      'unit': u"Bps",
      'min': 0,
   },
   {
      'title': 'Bytes',
      'metrics': ['outstandingBytesSched'],
      'unit': u"bytes",
      'min': 0,
   },
   {
      'title': 'Percentage IO Delay',
      'metrics': ['iopsDelayPctSched'],
      'unit': u"percent",
      'min': 0,
   },
   {
      'title': 'Bytes to Sync',
      'metrics': ['curBytesToSyncPolicy', 'curBytesToSyncDecom',
                  'curBytesToSyncRebalance', 'curBytesToSyncFixComp',
                  'curBytesToSyncRepair'],
      'unit': u"bytes",
      'min': 0,
   },
]

Vsan2ClusterResyncMetrics = [
   {
      'title': 'Resync IOPS',
      'metrics': [('iopsResyncReadPolicy', 'Policy Change Read'),
                  ('iopsResyncWritePolicy', 'Policy Change Write'),
                  ('iopsResyncReadDecom', 'Evacuation Read'),
                  ('iopsResyncWriteDecom', 'Evacuation Write'),
                  ('iopsResyncReadRebalance', 'Rebalance Read'),
                  ('iopsResyncWriteRebalance', 'Rebalance Write'),
                  ('iopsResyncReadFixComp', 'Repair Read'),
                  ('iopsResyncWriteFixComp', 'Repair Write')],
      'unit': u"iops",
      'min': 0,
   },
   {
      'title': 'Resync Throughput',
      'metrics': [('tputResyncReadPolicy', 'Policy Change Read'),
                  ('tputResyncWritePolicy', 'Policy Change Write'),
                  ('tputResyncReadDecom', 'Evacuation Read'),
                  ('tputResyncWriteDecom', 'Evacuation Write'),
                  ('tputResyncReadRebalance', 'Rebalance Read'),
                  ('tputResyncWriteRebalance', 'Rebalance Write'),
                  ('tputResyncReadFixComp', 'Repair Read'),
                  ('tputResyncWriteFixComp', 'Repair Write')],
      'unit': u"Bps",
      'min': 0,
   },
   {
      'title': 'Resync Latency',
      'metrics': [('latResyncReadPolicy', 'Policy Change Read'),
                  ('latResyncWritePolicy', 'Policy Change Write'),
                  ('latResyncReadDecom', 'Evacuation Read'),
                  ('latResyncWriteDecom', 'Evacuation Write'),
                  ('latResyncReadRebalance', 'Rebalance Read'),
                  ('latResyncWriteRebalance', 'Rebalance Write'),
                  ('latResyncReadFixComp', 'Repair Read'),
                  ('latResyncWriteFixComp', 'Repair Write')],
      'unit': u"µs",
      'min': 0,
   },
   {
      'title': 'Resync IO Count',
      'metrics': [('readCountPolicy', 'Policy Change Read Count'),
                  ('recWriteCountPolicy', 'Policy Change Write Count'),
                  ('readCountDecom', 'Evacuation Read Count'),
                  ('recWriteCountDecom', 'Evacuation Write Count'),
                  ('readCountRebalance', 'Rebalance Read Count'),
                  ('recWriteCountRebalance', 'Rebalance Write Count'),
                  ('readCountFixComp', 'Repair Read Count'),
                  ('recWriteCountFixComp', 'Repair Write Count')],
      'unit': u"short",
      'min': 0,
   },
]

ZdomSegmentCleaningMetrics = [
   {
      'title': 'Segment Cleaning Ops',
      'metrics': [
         ('numPasses', 'numPasses'),
         ('numSegsUnmapped', 'numSegsUnmapped'),
         ('numSegsNotUnmappable', 'numSegsNotUnmappable'),
         ('numSegsOverwrite', 'numSegsOverwritten'),
         ('numSegsFreed', 'numSegsFreed'),
         ('numSegsRead', 'numSegsRead'),
         ('numSegsWrite', 'numSegsWritten'),
      ],
      'unit': u"short",
      'min': 0,
   },
   {
      'title': 'Segment Cleaning Ops Number Free',
      'metrics': [
         ('numFree', 'numFree'),
      ],
      'unit': u"short",
      'min': 0,
   },
   {
      'title': 'Segment Cleaning Ops breakdown',
      'metrics': [
         ('numDataSegsRead', 'numDataSegsRead'),
         ('numLLPSegsRead', 'numLLPSegsRead'),
         ('numDataSegsWrite', 'numDataSegsWritten'),
         ('numLLPSegsWrite', 'numLLPSegsWritten'),
      ],
      'unit': u"short",
      'min': 0,
   },
   {
      'title': 'Latency of Segment Cleaning Ops',
      'metrics': [
         ('latAvgPassRuntime', 'passRunTimeUSec'),
         ('latAvgSleepTime', 'sleepTimeUSec'),
         ('latAvgUnmapDispatchTime', 'unmapDispatchTimeUSec')
      ],
      'unit': u"µs",
      'min': 0,
   },
]

ZdomSegmentCleaningBucketMetrics = [
   {
      'title': 'LLP Bucket Number Entries',
      'metrics': [
         'bucketLLPLowest', 'bucketLLPLow', 'bucketLLPMid',
         'bucketLLPHigh', 'bucketLLPHighest',
      ],
      'unit': u"short",
      'min': 0,
   },
   {
      'title': 'Data Bucket Number Entries',
      'metrics': [
         'bucketDataLowest', 'bucketDataLow', 'bucketDataMid',
         'bucketDataHigh', 'bucketDataHighest',
      ],
      'unit': u"short",
      'min': 0,
   },
   {
      'title': 'Total Bucket Number Entries',
      'metrics': [
         'bucketLowest', 'bucketLow', 'bucketMid',
         'bucketHigh', 'bucketHighest',
      ],
      'unit': u"short",
      'min': 0,
   },
   {
      'title': 'Avg Goodness of Bucket Number Entries',
      'metrics': [
         'avgGoodnessLowest', 'avgGoodnessLow', 'avgGoodnessMid',
         'avgGoodnessHigh', 'avgGoodnessHighest',
      ],
      'unit': u"short",
      'min': 0,
   },
]

ZdomGscCapacityPartitionMetrics = [
   {
      'title': 'GSC goodness threshold',
      'metrics': [
         ("avgProactiveGoodnessCapacity", "Average proactive cleaning goodness threshold"),
         ("avgReactiveGoodnessCapacity", "Average Reactive cleaning goodness threshold"),
      ],
      'unit': u"short",
      'min': 0,
   },
   {
      'title': 'GSC cleaning rate',
      'metrics': [
         ("proactiveCleaningRateCapacity", "Proactive cleaning rate per second"),
         ("reactiveCleaningRateCapacity", "Reactive cleaning rate per second"),
         ("currentWriteRateCapacity", "Current write workload rate per second"),
         ("maxWriteRateCapacity", "Max write workload rate per second"),
      ],
      'unit': u"Bps",
      'min': 0,
   },
   {
      'title': 'GSC disk fullness',
      'metrics': [
         ("physDiskFullnessPctCapacity", "Physical Disk fullness percentage"),
         ("rawDiskFullnessPctCapacity", "RAW Disk fullness percentage")
      ],
      'unit': u"percent",
      'min': 0,
   },
   {
      'title': 'GSC goodness map entries',
      'metrics': [
         ("rateObjGoodnessMapEntriesCapacity", "Rate of object goodness map entries for disk"),
      ],
      'unit': u"short",
      'min': 0,
   },
]

def get_vsan2_dom_disks_perf():
   return {
      'title': 'DOM vSAN ESA: Disks Performance Tier',
      'tag' :  'dom_vsan-esa',
      'repeat': True,
      'metrics': Vsan2DomDiskMetrics,
      'entityToShow':'vsan2-dom-scheduler-perf',
   }

def get_vsan2_dom_disks_capacity():
   return {
      'title': 'DOM vSAN ESA: Disks Capacity Tier',
      'tag' :  'dom_vsan-esa',
      'repeat': True,
      'metrics': Vsan2DomDiskMetrics,
      'entityToShow':'vsan2-dom-scheduler-capacity',
   }

def get_vsan2_dom_disks_both():
   return {
      'title': 'DOM vSAN ESA: Disks Both Tiers',
      'tag' :  'dom_vsan-esa',
      'repeat': True,
      'metrics': Vsan2DomDiskMetrics,
      'entityToShow':'vsan2-dom-scheduler-.*',
   }

def get_vsan2_dom_scheduler_perf():
   return {
      'title': 'DOM vSAN ESA: Comp Scheduler Performance Tier',
      'tag' :  'dom_vsan-esa',
      'repeat': True,
      'metrics': Vsan2DomSchedulerMetrics,
      'entityToShow':'vsan2-dom-scheduler-perf',
   }

def get_vsan2_dom_scheduler_capacity():
   return {
      'title': 'DOM vSAN ESA: Comp Scheduler Capacity Tier',
      'tag' :  'dom_vsan-esa',
      'repeat': True,
      'metrics': Vsan2DomSchedulerMetrics,
      'entityToShow':'vsan2-dom-scheduler-capacity',
   }

def get_vsan2_dom_scheduler_both():
   return {
      'title': 'DOM vSAN ESA: Comp Scheduler Both Tiers',
      'tag' :  'dom_vsan-esa',
      'repeat': True,
      'metrics': Vsan2DomSchedulerMetrics,
      'entityToShow':'vsan2-dom-scheduler-.*',
   }

def get_vsan2_cluster_resync_perf():
   return {
      'title': 'DOM vSAN ESA: Cluster Resync Performance Tier',
      'tag' :  'dom_vsan-esa',
      'repeat': True,
      'metrics': Vsan2ClusterResyncMetrics,
      'entityToShow':'vsan2-cluster-resync-perf',
   }

def get_vsan2_cluster_resync_capacity():
   return {
      'title': 'DOM vSAN ESA: Cluster Resync Capacity Tier',
      'tag' :  'dom_vsan-esa',
      'repeat': True,
      'metrics': Vsan2ClusterResyncMetrics,
      'entityToShow':'vsan2-cluster-resync-capacity',
   }

dashboardPatch = {
   'dom_net' : {
      'title': 'DOM vSAN & vSAN ESA: Network Scheduler',
      'repeat': True,
      'tag' :  'dom',
      'metrics': [
         {
            'title': 'DOM Network Latency',
            'metrics': [('numNetSchedRollingAvgLatUs', 'Latency'),
                        ],
            'unit': u"µs",
            'min': 0,
            'description': "Rolling Average Network Latency",
         },
         {
            'title': 'DOM Network Throttled Iops',
            'metrics': [('numNetSchedOwnerIops', 'Owner'),
                        ('numNetSchedCompIops', 'Comp'),
                        ('numNetSchedOwnerRecoveryWriteIops', 'Owner RecoveryWrites'),
                        ('numNetSchedCompRecoveryWriteIops', 'Comp RecoveryWrites'),
                        ('numNetSchedOwnerResyncReadIops', 'Owner ResyncReads'),
                        ('numNetSchedCompResyncReadIops', 'Comp ResyncReads'),
                        ],
            'unit': u"iops",
            'min': 0,
            'description': "Iops of different ops going through the network scheduler on this host",
         },
         {
            'title': 'DOM Network Throttled Throughput',
            'metrics': [('numNetSchedOwnerTpThrottled', 'Owner'),
                        ('numNetSchedCompTpThrottled', 'Comp'),
                        ('numNetSchedOwnerRecoveryWriteTpThrottled', 'Owner RecoveryWrite'),
                        ('numNetSchedCompRecoveryWriteTpThrottled', 'Comp RecoveryWrite'),
                        ('numNetSchedOwnerResyncReadTpThrottled', 'Owner ResyncRead'),
                        ('numNetSchedCompResyncReadTpThrottled', 'Comp ResyncRead'),
                        ],
            'unit': u"Bps",
            'min': 0,
            'description': "Throughput of different ops bytes going through the network scheduler on this host",
         },
         {
            'title': 'DOM Network Applied Iops Limit',
            'metrics': [('numNetSchedOwnerIopsLimit', 'Owner'),
                        ('numNetSchedCompIopsLimit', 'Comp'),
                        ('numNetSchedOwnerRecoveryWriteIopsLimit', 'Owner RecoveryWrite'),
                        ('numNetSchedCompRecoveryWriteIopsLimit', 'Comp RecoveryWrite'),
                        ('numNetSchedOwnerResyncReadIopsLimit', 'Owner ResyncRead'),
                        ('numNetSchedCompResyncReadIopsLimit', 'Comp ResyncRead'),
                        ],
            'unit': u"iops",
            'min': 0,
            'description': "Iops limit applied to different ops bytes going through the network scheduler on this host",
         },
         {
            'title': 'Number of Bands Controller when Throttling IOs',
            'metrics': [('numNetSchedHighBand', 'High Bands'),
                        ('numNetSchedMidBand', 'Middle Bands'),
                        ('numNetSchedLowdBand', 'Low Bands'),
                        ('numNetSchedHighBandLowLimit', 'High Band Low Limit'),
                        ('numNetSchedLowBandHighLimit', 'Low Band High Limit'),
                        ('numNetSchedMidBandHighLimit', 'Middle Band High Limit'),
                        ('numNetSchedHighBandHighShare', 'High Band High Share'),
                        ('numNetSchedMidBandLowShare', 'Middle Band Low Share'),
                        ],
            'unit': u"short",
            'min': 0,
            'description': "Number of bands in which the scheduler takes action",
         },
         {
            'title': 'Controller Activations',
            'metrics': [('numNetSchedControllerActivations', 'Number of Activations'),
                        ],
            'unit': u"short",
            'min': 0,
            'description': "Number of network scheduler controller activations",
         },
         {
            'title': 'Average Resync Share per Activation',
            'metrics': [('numNetSchedResyncTotalSharePercent', 'Resync Share Percent'),
                        ],
            'unit': u"percent",
            'min': 0,
            'description': "Number of network scheduler controller activations",
            'detailOnly': True,
         },
         {
            'title': 'Average Controller Iops Limit per Activation',
            'metrics': [('numNetSchedControllerIopsLimit', 'Iops Limit per activation'),
                        ],
            'unit': u"short",
            'min': 0,
            'description': "Average Iops Limit per activation",
            'detailOnly': True,
         },
         {
            'title': 'Average Applied Delay per Op',
            'metrics': [('netSchedAvgOwnerRecoveryWriteDelayMs', 'Owner RecoveryWrite'),
                        ('netSchedAvgCompRecoveryWriteDelayMs', 'Comp RecoveryWrite'),
                        ('netSchedAvgOwnerResyncReadDelayMs', 'Owner Resync Read'),
                        ('netSchedAvgCompResyncReadDelayMs', 'Comp Resync Read'),
                        ],
            'unit': u"ms",
            'min': 0,
            'description': "Average applied delay for resync IOs",
            'detailOnly': True,
         },
         {
            'title': 'Allocated Bandwidth Per Session (MB/s)',
            'metrics': [('netSchedBWDiscoveredPerDiscoverySession', 'Discovery Phase'),
                        ('netSchedBWReallocatedPerReallocationSession', 'Reallocation Phase'),
                        ],
            'unit': u"Bps",
            'min': 0,
            'description': "Bandwidth discovered or reallocated for resync in MBps",
            'detailOnly': True,
         },
         {
            'title': 'Guest/Resync Iops Session Stats',
            'metrics': [('netSchedGuestIopsIncreasePerReallocationSession', 'Guest Iops Increase in Reallocation'),
                        ('netSchedGuestIopsDecreasePerDiscoverySession', 'Guest Iops Decrease in Discovery'),
                        ('netSchedResyncIopsIncreasePerDiscoverySession', 'Resync Iops Increase in Discovery'),
                        ('netSchedResyncIopsDecreasePerReallocationSession', 'Resync Iops Decrease in Reallocation')],
            'unit': u"iops",
            'min': 0,
            'description': "Guest/Resync Iops behavior during discovery/reallocation phases",
            'detailOnly': True,
         },
         {
            'title': 'Average Bandwidth Utilization',
            'metrics': [('netSchedBWDiscoveryUtilizationPct', 'Discovery'),
                        ('netSchedBWReallocationUtilizationRatio', 'Reallocation')],
            'unit': u"percent",
            'min': 0,
            'description': "Bandwidth Utilization per Bandwidth Discovey/Reallocation Action",
            'detailOnly': True,
         },
         {
            'title': 'Bandwidth Discovery/Reallocation Stopping Conditions',
            'metrics': [('netSchedBWDiscoveryStopsDueToHighLatencyPct', 'Discovery - High Latency'),
                        ('netSchedBWDiscoveryStopsDueToGainsFromGuestPct', 'Discovery - Guest Drop'),
                        ('netSchedBWDiscoveryStopsDueToLowUtilizationPct', 'Discovery - Low Utilization'),
                        ('netSchedBWReallocationStopsDueToLowUtilizationPct', 'Reallocation - Low Utilization'),
                        ('netSchedBWReallocationStopsDueToHighSharePct', 'Reallocatiion - High Share'),
                        ],
            'unit': u"percent",
            'min': 0,
            'description': "Percent of reasons why discovery or reallocation stopped",
            'detailOnly': True,
         },
         {
            'title': 'Latency increase percent per Discovery Session',
            'metrics': [('netSchedLatencyIncreaseFromResyncPerDiscoverySessionPct', 'Increase Percent')],
            'unit': u"percent",
            'min': 0,
            'description': "Latency increase in percent per discovery session",
            'detailOnly': True,
         },
         {
            'title': 'Bandwidth Discovery/Reallocation Intervals',
            'metrics': [('netSchedBWDiscoveryAvgIntervalsUs', 'Discovery Phase'),
                        ('netSchedBWReallocationAvgIntervalsUs', 'Reallocation Phase'),
                        ],
            'unit': u"µs",
            'min': 0,
            'description': "Average Interval between two discovery/reallocation phases",
            'detailOnly': True,
         },
         {
            'title': 'Bandwidth Discovery/Reallocation Session Stats',
            'metrics': [('netSchedBWDiscoverySessions', 'Discovery Sessions'),
                        ('netSchedBWReallocationSessions', 'Reallocation Sessions'),
                        ('netSchedBWDiscoveryActions', 'Discovery Iterations'),
                        ('netSchedBWReallocationActions', 'Reallocation Iterations'),
                        ],
            'unit': u"short",
            'min': 0,
            'description': "Number of sessions/actions for discovery/reallocation",
            'detailOnly': True,
         },
         {
            'title': 'Scheduler Seen Throughtput per Activation',
            'metrics': [('numNetSchedSeenTotalTpBps', 'Total'),
                        ('numNetSchedSeenResyncTpBps', 'Resync'),
                        ('numNetSchedSeenNonResyncTpBps', 'Non-Resync'),
                        ],
            'unit': u"Bps",
            'min': 0,
            'description': "Scheduler Seen Throughput per activation",
            'detailOnly': True,
         },
         {
            'title': 'Scheduler Seen Throughtput per Activation',
            'metrics': [('numNetSchedSeenTotalTpBps', 'Total'),
                        ('numNetSchedSeenResyncTpBps', 'Resync'),
                        ('numNetSchedSeenNonResyncTpBps', 'Non-Resync'),
                        ],
            'unit': u"Bps",
            'min': 0,
            'description': "Scheduler Seen Throughput per activation",
            'detailOnly': True,
         },
         {
            'title': 'Time in Bands',
            'metrics': [('numNetSchedHighBandSec', 'High Band'),
                        ('numNetSchedMidBandSec', 'Middle Band'),
                        ('numNetSchedLowBandSec', 'Low Band'),
                        ],
            'unit': u"s",
            'min': 0,
            'description': "Time spent in different controller bands of the scheduler",
            'detailOnly': True,
         },
      ],
      'entityToShow':'host-domowner',
   },
   'dom_owner' : {
      'title': 'DOM vSAN & vSAN ESA: Owner',
      'repeat': True,
      'tag' :  'dom',
      'metrics': [
         {
            'title': 'Latency',
            'metrics': [('latencyAvgRead', 'Read'),
                        ('latencyAvgWrite', 'Write'),
                        ('latencyAvgResyncRead', 'Resync Read'),
                        ('latencyAvgRecWrite', 'Recovery Write'),
                        ('latencyAvgUnmap', 'Unmap'),
                        ('latencyAvgRecUnmap', 'Recovery Unmap'),
                        ('serverSwitchAvglatency', 'Server Switch'),
                        ('latencyAvgServiceVMRead', 'ServiceVM Read'),
                        ('latencyAvgServiceVMWrite', 'ServiceVM Write'),
                        ],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
            'description': "Average read/write latency of I/Os generated by all vSAN owner in the host",
         },
         {
            'title': 'IOPS',
            'metrics': [('iopsRead', 'Read'),
                        ('iopsWrite', 'Write'),
                        ('iopsResyncRead', 'Resync Read'),
                        ('iopsRecWrite', 'Recovery Write'),
                        ('iopsUnmap', 'Unmap'),
                        ('iopsRecUnmap', 'Recovery Unmap')
                        ],
            'unit': u"iops",
            'min': 0,
            'description': "Read/Write IOPS consumed by all vSAN owner in the host\n\n**iopsRead** : Read IOPS\n\n**iopsWrite** : Write IOPS"
         },
         {
            'title': 'Throughput',
            'metrics': [('tputRead', 'Read'),
                        ('tputWrite', 'Write'),
                        ('tputResyncRead', 'Resync Read'),
                        ('tputRecWrite', 'Recovery Write'),
                        ('tputUnmap', 'Unmap'),
                        ('tputRecUnmap', 'Recovery Unmap'),
                        ('tputServiceVMRead', 'ServiceVM Read'),
                        ('tputServiceVMWrite', 'ServiceVM Write'),
                        ],
            'unit': u"Bps",
            'min': 0,
            'description': "Read/Write throughput consumed by all vSAN owner in the host"
         },
         {
            'title': 'congestion',
            'metrics': [('readCongestion', 'Read'),
                        ('writeCongestion', 'Write'),
                        ('recoveryWriteCongestion', 'RecWrite'),
                        ('unmapCongestion', 'Unmap'),
                        ('recoveryUnmapCongestion', 'RecUnmap')],
            'unit': u"short",
            'thresholds': [30, 60], # XXX: Need better thresholds
            'min': 0,
            'max': 255,
            'description': "Congestions of I/Os generated by all vSAN owner in the host"
         },
         {
            'title': 'Outstanding IO',
            'metrics': [('oio', 'OIO'),
                        ('highOIOAvgOIO', 'AvgOIOAtHighOIO'),
                        ('highOIOAvgOIORead', 'AvgOIOAtHighOIO-Read'),
                        ('highOIOAvgOIOWrite', 'AvgOIOAtHighOIO-Write')],
            'unit': u"short",
            'min': 0,
            'description': "Outstanding I/O from all vSAN owner in the host"
         },
         {
            'title': 'Throughput derived from High OIO',
            'metrics': [('highOIOThroughputRead', 'Read'),
                        ('highOIOThroughputWrite', 'Write'),
                        ],
            'unit': u"Bps",
            'min': 0,
            'description': "Read/Write throughput consumed by all vSAN owners in the host, as if high OIO periods consitutue the complete measuring interval",
            'detailOnly': True,
         },
         {
            'title': 'Bytes from High OIO',
            'metrics': [('highOIOBytesRead', 'Read'),
                        ('highOIOBytesWrite', 'Write'),
                        ],
            'unit': u"bytes",
            'min': 0,
            'description': "Number of bytes of Read/Write consumed by all vSAN owners in the host, during high OIO periods",
            'detailOnly': True,
         },
         {
            'title': 'Number of High OIO Periods',
            'metrics': [('highOIONumTimesRead', 'Read'),
                        ('highOIONumTimesWrite', 'Write'),
                        ],
            'unit': u"short",
            'min': 0,
            'description': "Number of times of Read/Write high OIO periods consumed by all vSAN owners in the host",
            'detailOnly': True,
         },
         {
            'title': 'Average Number of I/Os in a High OIO Period',
            'metrics': [('highOIOAvgIOCountRead', 'Read'),
                        ('highOIOAvgIOCountWrite', 'Write'),
                        ],
            'unit': u"short",
            'min': 0,
            'description': "Number of times of Read/Write high OIO periods consumed by all vSAN owners in the host",
            'detailOnly': True,
         },
         {
            'title': 'High OIO Duration Metrics',
            'metrics': [('highOIODurationMs', 'Total Duration'),
                        ('highOIOAvgDurationMs', 'Avg Duration'),
                        ('highOIODurationMsRead', 'Total Duration for Reads'),
                        ('highOIOAvgDurationMsRead', 'Avg Duration for Reads'),
                        ('highOIODurationMsWrite', 'Total Duration for Writes'),
                        ('highOIOAvgDurationMsWrite', 'Avg Duration for Writes')],
            'unit': u"ms",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Latency Std Dev',
            'metrics': [('latencyStddev', 'Latency Std Dev'),
                        ('latencyStddevRead', 'Read Latency Std Dev'),
                        ('latencyStddevWrite', 'Write Latency Std Dev'),
                        ('serverSwitchlatencyStddev', 'Server Switch Latency Std Dev')],
            'unit': u"µs",
            'min': 0,
            'description': "Standard deviation of read/write latency of I/Os generated by all vSAN owner in the host"
         },
         {
            'title': 'Leaf Owner Latency',
            'metrics': [('readLeafOwnerLatency', 'Read'),
                        ('writeLeafOwnerLatency', 'Write'),
                        ('recoveryWriteLeafOwnerLatency', 'Recovery Write'),
                        ('unmapLeafOwnerLatency', 'Unmap'),
                        ('recoveryUnmapLeafOwnerLatency', 'Recovery Unmap'),
                        ('readLeafOwnerLatencyRemote', 'Read Remote'),
                        ('writeLeafOwnerLatencyRemote', 'Write Remote'),
                        ('resyncReadLeafOwnerLatencyRemote', 'Resync Read Remote'),
                        ('recoveryWriteLeafOwnerLatencyRemote', 'Recovery Write Remote'),
                        ('readLeafOwnerLatencyLocal', 'Read Local'),
                        ('writeLeafOwnerLatencyLocal', 'Write Local'),
                        ('resyncReadLeafOwnerLatencyLocal', 'Resync Read Local'),
                        ('recoveryWriteLeafOwnerLatencyLocal', 'Recovery Write Local')],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Multi-leaf Owner Avg Max Latency',
            'metrics': [('readLeafOwnerMaxLatencyAvgUs', 'Read'),
                        ('writeLeafOwnerMaxLatencyAvgUs', 'Write'),
                        ('unmapLeafOwnerMaxLatencyAvgUs', 'Unmap')],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Parallel Resync',
            'metrics': ['numCompleteResyncOps', 'numCompleteRwrOps',
                        'numCompleteResyncRwrBatches', 'avgResyncParallelism',
                        ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Number of various resync Jobs',
            'metrics': [('numPendingResyncJobs', 'PendingJobs'),
                        ('numPendingDecomResyncJobs', 'PendingDecomJobs'),
                        ('numSuspendedResyncJobs', 'SuspendedJobs'),
                        ('numSuspendedResyncChangemaps', 'SuspendedChangemaps'),
                        ('numSuspendedSharedResyncJobs', 'SuspendedSharedJobs'),
                        ('numSuspendedPriorityResyncJobs', 'SuspendedPriorityJobs'),
                        ('numRunningResyncJobs', 'RunningJobs'),
                        ('numInflightSharedResyncJobs', 'InflightSharedJobs'),
                        ('numInflightPriorityResyncJobs', 'InflightPriorityJobs')],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Resync Scheduler Slots',
            'metrics': [('numPendingFullResyncJobs', 'pending full'),
                        ('numRunningFullResyncJobs', 'running full'),
                        ('numPendingDeltaToBaseResyncJobs', 'pending delta-to-base'),
                        ('numRunningDeltaToBaseResyncJobs', 'running delta-to-base'),
                        ('numPendingSiblingToDeltaResyncJobs', 'pending sibling-to-delta'),
                        ('numRunningSiblingToDeltaResyncJobs', 'running sibling-to-delta'),
                        ('numSuspendedSiblingToDeltaResyncJobs', 'suspended sibling-to-delta'),
                        ('numSuspendedDeltaToBaseResyncJobs', 'suspended delta-to-base'),
                        ('numSuspendedFullResyncJobs', 'supended full'),
                        ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Delta Creation Latency',
            'metrics': [('avgDeltaCreationDomCreationLatency', 'DOM Creation'),
                        ('avgDeltaCreationDomActiveLatency', 'DOM Active'),
                        ],
            'unit': u"s",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('DOM Creation', 'The duration in seconds it took to create the delta component. It spans from the moment DOM receives the CLOM message, to the completion of the DOM reconfigure.'),
               ('DOM Active', 'The duration in seconds it took to activate the unplanned delta component. It is usually the time it took to resync the stale unplanned delta component before its first activation.'),
            ]),

         },
         {
            'title': 'Number of Deltas Created',
            'metrics': [('totalDeltasCreatedCount', 'deltas created'),
                        ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Number of Completed Resyncs',
            'metrics': [('numCompleteDeltaToBaseResyncOps', 'delta to base'),
                        ('numCompleteSiblingToDeltaResyncOps', 'sibling to delta'),
                        ('numCompleteFullResyncOps', 'full'),
                        ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'RAID-EC Cache Hit-Miss Ratio Percent',
            'metrics': [('ownerECCacheHitMissRatio', 'Hit-Miss Rate Pct')],
            'unit': u"percent",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'RAID-EC Cache',
            'metrics': [('ownerECCacheNumCachedObjects', 'Objects using cache'),
                        ('ownerECCacheNumFailedAllocs', 'Cache alloc failures'),
                        ('ownerECCacheNumSuccessAllocs', 'Cache alloc success')],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'RAID-EC Stats',
            'metrics': [('ecWriteCount', 'Number of writes'),
                        ('ecStridedWriteCount', 'Number of attempted strided writes'),
                        ('ecStridedWriteHits', 'Number of successful strided writes'),
                        ('ecCachedWriteCount', 'Number of attempted cache write'),
                        ('ecCachedWriteHits', 'Number of reads avoided due to cache'),
                        ('ecFswCount', 'Number of full-stripe writes')],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': '2PC Stats',
            'metrics': [('twoPCPrepareRetryCount', 'Number of retries due to prepare limits'),
                        ('twoPCCommitCount', 'Number of inclusive commits'),
                        ('twoPCCommitSize', 'Inclusive commit size')],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': '2PC Queue Stats',
            'metrics': [('twoPCPrepareLimitRetryResyncIOPS', 'Retried Resync'),
                        ('twoPCPrepareLimitRetryGuestIOPS', 'Retried Guest'),
                        ('twoPCPrepareLimitRetryOtherIOPS', 'Retried Other'),
                        ('twoPCBatchCommitSyncIOPS', 'Committed Sync'),
                        ('twoPCBatchCommitResyncIOPS', 'Committed Resync'),
                        ('twoPCBatchCommitGuestIOPS', 'Committed Guest'),
                        ('twoPCBatchCommitOtherIOPS', 'Committed Other'),
                        ('twoPCBatchCommitBlockedBySyncIOPS', 'Blocked by Sync'),
                        ('twoPCBatchCommitBlockedByResyncIOPS', 'Blocked by Resync'),
                        ('twoPCBatchCommitBlockedByGuestIOPS', 'Blocked by Guest'),
                        ('twoPCBatchCommitBlockedByOtherIOPS', 'Blocked by Other')],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': '2PC Retry Latency',
            'metrics': [('twoPCPrepareLimitRetryResyncAvgTimeMs', 'Resync'),
                        ('twoPCPrepareLimitRetryGuestAvgTimeMs',  'Guest'),
                        ('twoPCPrepareLimitRetryOtherAvgTimeMs', 'Other')],
            'unit': u"ms",
            'thresholds': [500, 3000],
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': '2PC Commit Latency',
            'metrics': [('owner2PCCommitLatencyAvgUs', 'Commit Latency')],
            'unit': u"µs",
            'thresholds': [500, 3000],
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Reserved LSN Utilization',
            'metrics': [('twoPCReservedLSNUsedCount', 'Used'),
                        ('twoPCReservedLSNUnusedCount', 'Unused'),
                        ('twoPCReservedLSNExhaustedCount', 'Exhausted')],
            'unit': u"short",
            'thresholds': [100, 500],
            'min': 0,
            'detailOnly': True,
         },
      ],
      'entityToShow':'host-domowner',
   },
   'cluster_dom_owner' : {
      'title': 'DOM vSAN & vSAN ESA: Cluster Owner',
      'repeat': True,
      'tag' :  'dom',
      'metrics': [
         {
            'title': 'Parallel Resync',
            'metrics': ['numCompleteResyncOps', 'numCompleteRwrOps',
                        'numCompleteResyncRwrBatches', 'avgResyncParallelism',
                        ],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'Number of various resync Jobs',
            'metrics': [('numPendingResyncJobs', 'PendingJobs'),
                        ('numPendingDecomResyncJobs', 'PendingDecomJobs'),
                        ('numSuspendedResyncJobs', 'SuspendedJobs'),
                        ('numSuspendedResyncChangemaps', 'SuspendedChangemaps'),
                        ('numSuspendedSharedResyncJobs', 'SuspendedSharedJobs'),
                        ('numSuspendedPriorityResyncJobs', 'SuspendedPriorityJobs'),
                        ('numRunningResyncJobs', 'RunningJobs'),
                        ('numInflightSharedResyncJobs', 'InflightSharedJobs'),
                        ('numInflightPriorityResyncJobs', 'InflightPriorityJobs')],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'Resync Scheduler Slots',
            'metrics': [('numPendingFullResyncJobs', 'pending full'),
                        ('numRunningFullResyncJobs', 'running full'),
                        ('numPendingDeltaToBaseResyncJobs', 'pending delta-to-base'),
                        ('numRunningDeltaToBaseResyncJobs', 'running delta-to-base'),
                        ('numPendingSiblingToDeltaResyncJobs', 'pending sibling-to-delta'),
                        ('numRunningSiblingToDeltaResyncJobs', 'running sibling-to-delta'),
                        ('numSuspendedSiblingToDeltaResyncJobs', 'suspended sibling-to-delta'),
                        ('numSuspendedDeltaToBaseResyncJobs', 'suspended delta-to-base'),
                        ('numSuspendedFullResyncJobs', 'supended full'),
                        ],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'Delta Creation Latency',
            'metrics': [('avgDeltaCreationDomCreationLatency', 'DOM Creation'),
                        ('avgDeltaCreationDomActiveLatency', 'DOM Active'),
                        ],
            'unit': u"s",
            'min': 0,
            'description' : fmt_desc('Developer', [
               ('DOM Creation', 'The duration in seconds it took to create the delta component. It spans from the moment DOM receives the CLOM message, to the completion of the DOM reconfigure.'),
               ('DOM Active', 'The duration in seconds it took to activate the unplanned delta component. It is usually the time it took to resync the stale unplanned delta component before its first activation.'),
            ]),

         },
         {
            'title': 'Number of Deltas Created',
            'metrics': [('totalDeltasCreatedCount', 'deltas created'),
                        ],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'Number of Completed Resyncs',
            'metrics': [('numCompleteDeltaToBaseResyncOps', 'delta to base'),
                        ('numCompleteSiblingToDeltaResyncOps', 'sibling to delta'),
                        ('numCompleteFullResyncOps', 'full'),
                        ],
            'unit': u"short",
            'min': 0,
         },
      ],
      'entityToShow':'cluster-domowner',
   },
   'dom_owner_server_migration' : {
      'title': 'DOM vSAN & vSAN ESA: Owner Server Migration',
      'repeat': True,
      'tag' :  'dom',
      'metrics': [
         {
            'title': 'Ingress',
            'metrics': ['ingressMigrations',],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'Latency (NS)',
            'metrics': ['ingressLatencyNs',
                        'emaLatencyNs',
                        'avgLatencyNs'
                        ],
            'unit': u"ns",
            'min': 0,
         },
      ],
      'entityToShow':'host-domownerserver-migration',
   },
   'vsan_client' : {
      'title': 'DOM vSAN & vSAN ESA: Global Client',
      'tag' :  'dom',
      'repeat': True,
      'metrics': [
         {
            'title': 'Latency',
            'metrics': ['latencyAvgRead', 'latencyAvgWrite',
                        'latencyAvgUnmap', 'serverSwitchAvglatency'],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
         },
         {
            'title': 'IOPS',
            'metrics': ['iopsRead', 'iopsWrite', 'iopsUnmap'],
            'unit': u"iops",
            'min': 0,
         },
         {
            'title': 'Tput',
            'metrics': ['throughputRead', 'throughputWrite',
                        'throughputUnmap'],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'congestion',
            'metrics': [('readCongestion', 'Read Congestion'),
                        ('writeCongestion', 'Write Congestion'),
                        ('unmapCongestion', 'Unmap Congestion'),
                        ('congestion', 'Total Congestion')],
            'unit': u"short",
            'thresholds': [30, 60], # XXX: Need better thresholds
            'min': 0,
            'max': 255,
         },
         {
            'title': 'oio',
            'metrics': ['oio'],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'Latency Std Dev',
            'metrics': [('latencyStddev', 'Latency Std Dev'),
                        ('latencyStddevRead', 'Read Latency Std Dev'),
                        ('latencyStddevWrite', 'Write Latency Std Dev')],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'Client In-Memory Read-Cache - HitRate',
            'metrics': ['clientCacheHitRate'],
            'unit': 'short', # XXX
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Client In-Memory Read-Cache - IOPS',
            'metrics': ['iopsRead', 'clientCacheHits'],
            'unit': 'iops',
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Burst Per Second',
            'metrics': ['burstsPerSecond'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Burst Time',
            'metrics': ['avgBurstTotalTime', 'avgBurstArrivalTime', 'avgBurstCompletionTime'],
            'unit': u"µs",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Burst Peak OIO',
            'metrics': ['avgBurstPeakOIO'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Burst Peak Outstanding KB',
            'metrics': ['avgBurstPeakOutstandingKb'],
            'unit': u"KBps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Pct Time to Peak',
            'metrics': ['avgPctTimeToPeak'],
            'unit': u"µs",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'IOPS Within Bursts',
            'metrics': ['IOPSWithinBursts'],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Bandwidth Within Bursts',
            'metrics': ['bandwidthWithinBursts'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Skipped Bursts',
            'metrics': ['numBurstStatsSkipped'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Burst Per Second Multi Obj',
            'metrics': ['burstsPerSecondMultiObj'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Burst Time Multi Obj',
            'metrics': [
               'avgBurstTotalTimeMultiObj',
               'avgBurstArrivalTimeMultiObj'
               'avgBurstCompletionTimeMultiObj'
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Burst Peak OIO Multi Obj',
            'metrics': ['avgBurstPeakOIOMultiObj'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Burst Peak Outstanding KB Multi Obj',
            'metrics': ['avgBurstPeakOutstandingKbMultiObj'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Pct Time to Peak Multi Obj',
            'metrics': ['avgPctTimeToPeakMultiObj'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'IOPS Within Bursts Multi Obj',
            'metrics': ['IOPSWithinBurstsMultiObj'],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Bandwidth Within Bursts Multi Obj',
            'metrics': ['bandwidthWithinBurstsMultiObj'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'IOPS Within Bursts Excl First Obj',
            'metrics': ['IOPSWithinBurstsExclFirstObj'],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Bandwidth Within Bursts Excl First Obj',
            'metrics': ['bandwidthWithinBurstsExclFirstObj'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Less  Skewed Multi Bursts Per Second',
            'metrics': ['lessSkewedMultiBurstsPerSecond'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
      ],
      'entityToShow':'-domclient',
   },
   'vsan_local_client' : {
      'title': 'DOM vSAN & vSAN ESA: Local Client',
      'tag' :  'dom',
      'repeat': True,
      'metrics': [
         {
            'title': 'Latency',
            'metrics': ['latencyAvgRead', 'latencyAvgWrite'],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
         },
         {
            'title': 'IOPS',
            'metrics': ['iops', 'iopsRead', 'iopsWrite'],
            'unit': u"iops",
            'min': 0,
         },
          {
            'title': 'IO Count',
            'metrics': ['ioCount'],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'Tput',
            'metrics': ['throughputRead', 'throughputWrite'],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'congestion',
            'metrics': [('congestion', 'Total Congestion')],
            'unit': u"short",
            'thresholds': [30, 60], # XXX: Need better thresholds
            'min': 0,
            'max': 255,
         },
         {
            'title': 'oio',
            'metrics': ['oio'],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'numOio',
            'metrics': ['numOio'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'RW Count',
            'metrics': ['readCount', 'writeCount'],
            'unit': 'short',
            'min': 0,
            'detailOnly': True,
         },
      ],
      'entityToShow':'localdomclient',
   },
   'vsan_host_remote_client' : {
      'title': 'DOM vSAN & vSAN ESA: vSAN Enabled Host Remote Client',
      'tag' :  'dom',
      'repeat': True,
      'metrics': [
         {
            'title': 'Latency',
            'metrics': ['latencyAvgRead', 'latencyAvgWrite'],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
         },
         {
            'title': 'IOPS',
            'metrics': ['iops', 'iopsRead', 'iopsWrite'],
            'unit': u"iops",
            'min': 0,
         },
          {
            'title': 'IO Count',
            'metrics': ['ioCount'],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'Tput',
            'metrics': ['throughputRead', 'throughputWrite'],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'congestion',
            'metrics': [('congestion', 'Total Congestion')],
            'unit': u"short",
            'thresholds': [30, 60], # XXX: Need better thresholds
            'min': 0,
            'max': 255,
         },
         {
            'title': 'oio',
            'metrics': ['oio'],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'numOio',
            'metrics': ['numOio'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'RW Count',
            'metrics': ['readCount', 'writeCount'],
            'unit': 'short',
            'min': 0,
            'detailOnly': True,
         },
      ],
      'entityToShow':'host-remotedomclient',
   },
   'vsan_cluster_remote_client' : {
      'title': 'DOM vSAN & vSAN ESA: vSAN Enabled Cluster Remote Client',
      'tag' :  'dom',
      'repeat': True,
      'metrics': [
         {
            'title': 'Latency',
            'metrics': ['latencyAvgRead', 'latencyAvgWrite',
                        'latencyAvgUnmap'],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
         },
         {
            'title': 'IOPS',
            'metrics': ['iopsRead', 'iopsWrite', 'iopsUnmap'],
            'unit': u"iops",
            'min': 0,
         },
         {
            'title': 'Tput',
            'metrics': ['throughputRead', 'throughputWrite',
                        'throughputUnmap'],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'congestion',
            'metrics': ['readCongestion', 'writeCongestion',
                        'unmapCongestion'],
            'unit': u"short",
            'thresholds': [30, 60], # XXX: Need better thresholds
            'min': 0,
            'max': 255,
         },
         {
            'title': 'oio',
            'metrics': ['oio'],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'Latency Std Dev',
            'metrics': [('latencyStddev', 'Latency Std Dev'),
                        ('latencyStddevRead', 'Read Latency Std Dev'),
                        ('latencyStddevWrite', 'Write Latency Std Dev')],
            'unit': u"µs",
            'min': 0,
         },
      ],
      'entityToShow':'cluster-remotedomclient',
   },
   'compute_only_cluster_remote_dom_client' : {
      'title': 'DOM vSAN & vSAN ESA: Compute Only Cluster Remote Client',
      'tag' :  'dom',
      'repeat': True,
      'metrics': [
         {
            'title': 'Latency',
            'metrics': ['latencyAvgRead', 'latencyAvgWrite'],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
         },
         {
            'title': 'IOPS',
            'metrics': ['iopsRead', 'iopsWrite'],
            'unit': u"iops",
            'min': 0,
         },
         {
            'title': 'Tput',
            'metrics': ['throughputRead', 'throughputWrite'],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'congestion',
            'metrics': ['congestion'],
            'unit': u"short",
            'thresholds': [30, 60], # XXX: Need better thresholds
            'min': 0,
            'max': 255,
         },
         {
            'title': 'oio',
            'metrics': ['oio'],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'numOio',
            'metrics': ['numOio'],
            'unit': u"short",
            'min': 0,
         },
      ],
      'entityToShow':'computeCluster-remotedomclient',
   },
   'compute_only_host_remote_dom_client' : {
      'title': 'DOM vSAN & vSAN ESA: Compute Only Host Remote Client',
      'tag' :  'dom',
      'repeat': True,
      'metrics': [
         {
            'title': 'Latency',
            'metrics': ['latencyAvg', 'latencyAvgRead', 'latencyAvgWrite', 'latencyAvgUnmap'],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
         },
         {
            'title': 'Latency Std Dev',
            'metrics': [('latencyStddev', 'Latency Std Dev'),
                        ('latencyStddevRead', 'Read Latency Std Dev'),
                        ('latencyStddevWrite', 'Write Latency Std Dev'),
                        ('latencyStddevUnmap', 'Unmap Latency Std Dev')],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'IOPS',
            'metrics': ['iops', 'iopsRead', 'iopsWrite', 'iopsUnmap'],
            'unit': u"iops",
            'min': 0,
         },
         {
            'title': 'Tput',
            'metrics': ['throughput', 'throughputRead', 'throughputWrite', 'throughputUnmap'],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'congestion',
            'metrics': ['congestion', 'readCongestion', 'writeCongestion', 'unmapCongestion'],
            'unit': u"short",
            'thresholds': [30, 60], # XXX: Need better thresholds
            'min': 0,
            'max': 255,
         },
         {
            'title': 'oio',
            'metrics': ['oio'],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'numOio',
            'metrics': ['numOio'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'IO Count',
            'metrics': ['ioCount', 'readCount', 'writeCount', 'unmapCount'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
      ],
      'entityToShow':'computeHost-remotedomclient',
   },
   'dom_comp_scheduler' : {
      'title': 'DOM vSAN: Comp Scheduler',
      'tag' :  'dom_vsan1',
      'repeat': True,
      'metrics': [
         {
            'title': 'Latency',
            'metrics': ['latencySched',
                        'latencySchedQueueNS', 'latencySchedQueueRec',
                        'latencySchedQueueVM', 'latencySchedQueueMeta',
                        'latencyDelaySched', 'latResyncRead', 'latResyncWrite',
                        'latResyncReadPolicy', 'latResyncWritePolicy',
                        'latResyncReadDecom', 'latResyncWriteDecom',
                        'latResyncReadRebalance', 'latResyncWriteRebalance',
                        'latResyncReadFixComp', 'latResyncWriteFixComp',
                        ],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
         },
         {
            'title': 'IOPS',
            'metrics': ['iopsSched',
                        'iopsSchedQueueNS', 'iopsSchedQueueRec',
                        'iopsSchedQueueVM', 'iopsSchedQueueMeta',
                        'iopsDirectSched',
                        'iopsResyncRead', 'iopsResyncWrite',
                        'iopsResyncReadPolicy', 'iopsResyncWritePolicy',
                        'iopsResyncReadDecom', 'iopsResyncWriteDecom',
                        'iopsResyncReadRebalance', 'iopsResyncWriteRebalance',
                        'iopsResyncReadFixComp', 'iopsResyncWriteFixComp',
                        ],
            'unit': u"iops",
            'min': 0,
         },
         {
            'title': 'Tput',
            'metrics': ['throughputSched',
                        'throughputSchedQueueNS', 'throughputSchedQueueRec',
                        'throughputSchedQueueVM', 'throughputSchedQueueMeta',
                        'tputResyncRead', 'tputResyncWrite',
                        'tputResyncReadPolicy', 'tputResyncWritePolicy',
                        'tputResyncReadDecom', 'tputResyncWriteDecom',
                        'tputResyncReadRebalance', 'tputResyncWriteRebalance',
                        'tputResyncReadFixComp', 'tputResyncWriteFixComp',
                        ],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'Bytes',
            'metrics': ['outstandingBytesSched'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'Percentage IO Delay',
            'metrics': ['iopsDelayPctSched'],
            'unit': u"percent",
            'min': 0,
         },
         {
            'title': 'Bytes to Sync',
            'metrics': ['curBytesToSyncPolicy', 'curBytesToSyncDecom',
                        'curBytesToSyncRebalance', 'curBytesToSyncFixComp',
                        'curBytesToSyncRepair'],
            'unit': u"bytes",
            'min': 0,
         },
      ],
      'entityToShow':'cache-disk',
   },
   'dom_comp_mgr' : {
      'title': 'DOM vSAN & vSAN ESA: Comp Manager',
      'tag' :  'dom',
      'repeat': True,
      'metrics': [
         {
            'title': 'Latency',
            'metrics': ['latencyAvgRead', 'latencyAvgWrite', 'latencyAvgRecWrite', 'latAvgResyncRead', 'latencyAvgUnmap', 'latencyAvgRecUnmap', 'latencyAvgServiceVMRead', 'latencyAvgServiceVMWrite'],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
         },
         {
            'title': 'IOPS',
            'metrics': ['iopsRead', 'iopsWrite', 'iopsRecWrite', 'iopsResyncRead', 'iopsUnmap', 'iopsRecUnmap'],
            'unit': u"iops",
            'min': 0,
         },
         {
            'title': 'Tput',
            'metrics': ['throughputRead', 'throughputWrite', 'throughputRecWrite', 'tputResyncRead', 'throughputUnmap', 'throughputRecUnmap', 'tputServiceVMRead', 'tputServiceVMWrite'],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'congestion',
            'metrics': ['congestion', 'readCongestion', 'writeCongestion', 'recWriteCongestion', 'resyncReadCongestion', 'unmapCongestion', 'recUnmapCongestion'],
            'unit': u"short",
            'thresholds': [30, 60], # XXX: Need better thresholds
            'min': 0,
            'max': 255,
         },
         {
            'title': 'Outstanding IO',
            'metrics': ['oio'],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'Latency Std Dev',
            'metrics': [('latencyStddev', 'Latency Std Dev'),
                        ('latencyStddevRead', 'Read Latency Std Dev'),
                        ('latencyStddevWrite', 'Write Latency Std Dev')],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'IO Counts',
            'metrics': ['readCount', 'writeCount', 'resyncReadCount', 'recWriteCount', 'unmapCount', 'recUnmapCount'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Congestion Grouped by Resources',
            'metrics': [('sharedCongestion', 'Diskgroup Congestion'),
                        ('componentCongestion', 'Component Congestion')],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Bandwidth Limit',
            'metrics': [('regulatorIopsRead', 'Bandwidth Limit for Non-write'),
                        ('regulatorIopsWrite', 'Bandwidth Limit for Write')],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Queue Depth (queued but not dispatched)',
            'metrics': ['vmdiskQueueDepthRead', 'vmdiskQueueDepthWrite',
                        'namespaceQueueDepthRead', 'namespaceQueueDepthWrite',
                        'metadataQueueDepthRead', 'metadataQueueDepthWrite',
                        'resyncQueueDepthRead', 'resyncQueueDepthWrite'],
            'unit' : u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Normalized IO Cost',
            'metrics': ['vmdiskDispatchedCostRead', 'vmdiskDispatchedCostWrite',
                        'namespaceDispatchedCostRead', 'namespaceDispatchedCostWrite',
                        'metadataDispatchedCostRead', 'metadataDispatchedCostWrite',
                        'resyncDispatchedCostRead', 'resyncDispatchedCostWrite'],
            'unit' : u"Bps",
            'min': 0,
            'detailOnly': True,
         },
      ],
      'entityToShow':'domcompmgr',
   },
   'congestion' : {
      'repeat': False,
      'tag' :  'lsom',
      'title': 'LSOM: Congestion',
      'metrics': [
         {
            'title': m,
            'metrics': [m],
            'unit': u"short",
            'min': 0,
            'max': 255,
            'thresholds': [30, 60], # XXX: Need better thresholds
            'detailOnly': False,
         } for m in ['slabCongestion', 'iopsCongestion', 'compCongestion', 'logCongestion', 'memCongestion', 'ssdCongestion', 'maxDeleteCongestion']
      ],
      'entityToShow':'cache-disk',
   },
   'disk_groups' : {
      'title': 'LSOM: Disk Groups',
      'repeat': True,
      'tag' :  'lsom',
      'entityToShow':'meta-disk-groups',
   },
   'cache_disk' : {
      'title': 'LSOM: Cache Disk',
      'repeat': True,
      'tag' :  'lsom',
      'metrics': [
         {
            'title': 'Device IOPS',
            'metrics': [
               ('iopsDevRead', 'Read IOPS'),
               ('iopsDevWrite', 'Write IOPS'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Device Throughput',
            'metrics': [('throughputDevRead', 'Read'),
                        ('throughputDevWrite', 'Write')],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Device Latency',
            'metrics': [('latencyDevDAvg', 'DAVG'),
                        ('latencyDevKAvg', 'KAVG'),
                        ('latencyDevGAvg', 'GAVG'),
                        ('latencyDevRead', 'RDLAT'),
                        ('latencyDevWrite', 'WRLAT'),
                        ('latencyWriteLE', 'WRLAT-LE')],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Device Latency (MAX)',
            'metrics': [ ('latencyDevReadMax', 'RDLAT-MAX'),
                         ('latencyDevWriteMax', 'WRLAT-MAX')],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Device Latency (MIN)',
            'metrics': [('latencyDevReadMin', 'RDLAT-MIN'),
                        ('latencyDevWriteMin', 'WRLAT-MIN')],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Disk Group IOPS',
            'metrics': [
               ('iopsRead', 'Read IOPS'),
               ('iopsWrite', 'Write IOPS'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Disk Group Throughput',
            'metrics': [('throughputRead', 'Read'),
                        ('throughputWrite', 'Write')],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Disk Group Latency',
            'metrics': [('latencyAvgRead', 'Read'),
                        ('latencyAvgWrite', 'Write')],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Congestion',
            'metrics': [
               ('slabCongestion', 'Slab Congestion'),
               ('iopsCongestion', 'Iops Congestion'),
               ('compCongestion', 'Comp Congestion'),
               ('logCongestion', 'Log Congestion'),
               ('memCongestion', 'Mem Congestion'),
               ('ssdCongestion', 'SSD Congestion'),
               ('maxDeleteCongestion', 'Delete Congestion'),
            ],
            'unit': u"short",
            'thresholds': [30, 60], # XXX: Need better thresholds
            'min': 0,
            'max': 255,
            'metrics_ry' : [
               ('bytesPerSecondBandwidth', 'Log Congestion Bandwidth'),
            ],
            'unit_ry': u"Bps",
            'min_ry': 0,
            'detailOnly': False,
            'description': fmt_desc('Support', [
               ('Slab Congestion', 'Congestion caused by usage of slots in slabs'),
               ('Iops Congestion', 'Congestion raised when a component consumes disportionately high IOPs'),
               ('Comp Congestion', 'Congestion raised when a component has too many entries in the commit table'),
               ('Log Congestion', 'Congestion raised on high log build-up'),
               ('Mem Congestion', 'Congestion raised on high memory usage'),
               ('SSD Congestion', 'Congestion raised on high usage of cache-tier'),
               ('Delete Congestion', 'Max delete congestion raised on high disk usage of compression-only disk'),
               ('Log Congestion Bandwidth', 'A bandwidth recommendation to upper layers based on elevator throughput and workload characteristics (a lower value means more throttling is required). A value of zero means no throttling is required.'),
            ]),
         },
         {
            'title': 'DiskGroup Capacity Usage',
            'metrics': ['phyCapUsed',
                        'phyCapT2',
                        'phyCapCF',
                        'phyCapRsrvd',
                        'phyCapRsrvdUsed',
                        ],
            'unit': u"percent",
            'min': 0,
            'max': 100,
            'detailOnly': True,
         },
         {
            'title': 'Max Congestion during sampling period',
            'metrics': [
               'slabCongestionLocalMax', 'iopsCongestionLocalMax',
               'compCongestionLocalMax', 'logCongestionLocalMax',
               'memCongestionLocalMax', 'ssdCongestionLocalMax'
            ],
            'unit': u"short",
            'thresholds': [30, 60], # XXX: Need better thresholds
            'min': 0,
            'max': 255,
            'detailOnly': True,
         },
         {
            'title': 'oobLogCongestionIOPS',
            'metrics': ['oobLogCongestionIOPS'],
            'unit' : u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Over write Throughput',
            'metrics' : [
               ('overwritesIops', 'Overwrite Xput')
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'overWriteFactorData',
            'metrics': ['overWriteFactorMovingAvg', 'currentOverWriteFactor'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'oobLogCongestionMetrics',
            'metrics' : [
               'currentTrueWBFillRate', 'currentDrainRate',
               'currentIncomingRate'
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Write Buffer Entry Count',
            'metrics': [('prepTblCnt', 'Prep Table'),
                        ('commitTblCnt', 'Commit Table'),
                        ],
            'unit': u"short",
            'detailOnly': True,
         },
         {
            'title': 'Write Buffer usage (percentage)',
            'metrics': [('wbFreePct', 'WB Free Pct'),
                        ('llogLogSpace', 'LLOG Log Space'),
                        ('llogDataSpace', 'LLOG Data Space'),
                        ('plogLogSpace', 'PLOG Log Space'),
                        ('plogDataSpace', 'PLOG Data Space'),
                        ('elevStartThresh', 'Data Elev Start Threshold'),
                        ('elevUnthrottleThresh', 'Data Elev Unthrottle Threshold'),
                        ('zeroElevStartThreshold', 'Zero Elev Start Threshold'),
                        ('zeroElevUnthrottleThreshold', 'Zero Elev Unthrottle Threshold'),
                        ],
            'unit': u"percent",
            'min': 0,
            'max': 100,
            'detailOnly': False,
         },
         {
            'title': 'Write Buffer Usage (bytes)',
            'metrics': [('wbSize', 'WB size'),
                        ('llogLog', 'LLOG Log'),
                        ('llogData', 'LLOG Data'),
                        ('plogLog', 'PLOG Log'),
                        ('plogData', 'PLOG Data'),
                        ('bytesOverwritten', 'Bytes Overwritten'),
                        ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Elev throttling params',
            'metrics': ['logP',
                        'memP',
                        'ssdP',
                        'dataP',
                        'zeroP',
                        'maxP',
                        'zeroElevMaxP',
                        ],
            'unit': u"percent",
            'min': 0,
            'max': 100,
            'detailOnly': True,
         },
         {
            'title': 'Elevator throttling sleep time',
            'metrics': [
               ("timeToSleepMs", "Data Elev Sleep Time"),
               ("zeroElevTimeToSleepMs", " Zero Elev Sleep Time"),
            ],
            'unit': u"ms",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Destage sampling correction (available only in verbose mode)',
            'metrics': [
               ("destageSampleTime", "Sample Window"),
               ("timeSleptInSample", "Time slept in window"),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Elevator Throughput',
            'metrics': [
               ("plogTotalBytesDrained", "TotalDrained"),
               ("plogSsdBytesDrained", "SSDDrained"),
               ("plogZeroBytesDrained", "ZeroDrained"),
               # New
               ("plogTotalTputDrained", "Total"),
               ("plogSsdTputDrained", "SSD"),
               ("plogZeroTputDrained", "Zeros"),
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Elevator Advertized Capability',
            'metrics': [
               ("advtDataDestageRateCur", "Current Data Destage"),
               ("advtDataDestageRateAvg", "Avg Data Destage"),
               ("advtZeroDestageRateCur", "Current Zeros Destage"),
               ("advtZeroDestageRateAvg", "Avg Zeros Destage"),
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Latency',
            'metrics': [('plogReadQLatency', 'Read Queue'),
                        ('plogWriteQLatency', 'Write Queue'),
                        ('plogtotalRdLat', 'Total Read'),
                        ('plogtotalWrLat', 'Total Write'),
                        ('plogHelpRdQLat', 'Helper Q Write'),
                        ('plogHelpWrQLat', 'Helper Q Read'),
                        ],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'DDP Scheduling',
            'metrics': [
               ('avgIdleTime', 'Idle'),
               ('avgPreReadTime', 'Pre-Read'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Cumulative Enc Latency',
            'metrics': [('plogCumlEncRdLat', 'Enc Read'),
                        ('plogCumlEncWrLat', 'Enc Write')],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Average Queue Depth',
            'metrics': [('plogHelpRdQDepth', 'Helper WQ'),
                        ('plogHelpWrQDepth', 'Helper RQ')
                        ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Read Throughput',
            'metrics': [
               ("plogTotalBytesRead", "Total"),
               ("plogTotalBytesReadFromMD", "MD"),
               ("plogTotalBytesReadFromSSD", "SSD"),
               ("plogTotalBytesReadByRC", "RC"),
               ("plogTotalBytesReadByVMFS", "VMFS"),
               # New
               ("plogTotalTputRead", "Total"),
               ("plogTotalTputReadFromMD", "MD"),
               ("plogTotalTputReadFromSSD", "SSD"),
               ("plogTotalTputReadByRC", "RC"),
               ("plogTotalTputReadByVMFS", "VMFS"),
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG ReadOPS',
            'metrics': [
               ("plogNumTotalReads", "Total"),
               ("plogNumMDReads", "MD"),
               ("plogNumSSDReads", "SSD"),
               ("plogNumRCReads", "RC"),
               ("plogNumVMFSReads", "VMFS"),
               # New
               ("plogNumTotalReadOPS", "Total"),
               ("plogNumMDReadOPS", "MD"),
               ("plogNumSSDReadOPS", "SSD"),
               ("plogNumRCReadOPS", "RC"),
               ("plogNumVMFSReadOPS", "VMFS"),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Data Usage',
            'metrics': [
               #("plogMDDataUsage", "MDData"),
               ("plogDGDataUsage", "DGData"),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Write Throughput',
            'metrics': [
               ("plogTotalCSBytes", "CS"),
               ("plogTotalZeroBytes", "Zero"),
               ("plogTotalDelBytes", "Delete"),
               ("plogTotalFSBytes", "fsBytes"),
               ("plogTotalCFBytes", "cfBytes"),
               ("plogTotalFSUnmapBytes", "fsUnmapBytes"),
               ("plogTotalCFUnmapBytes", "cfUnmapBytes"),
               # New
               ("plogTotalCSTput", "CS"),
               ("plogTotalZeroTput", "Zero"),
               ("plogTotalDelTput", "Delete"),
               ("plogTotalFSTput", "fsBytes"),
               ("plogTotalCFTput", "cfBytes"),
               ("plogTotalFSUnmapTput", "fsUnmapBytes"),
               ("plogTotalCFUnmapTput", "cfUnmapBytes"),
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Logs',
            'metrics': [
               ("plogNumWriteLogs", "WriteLogs"),
               ("plogNumCommitLogs", "CommitLogs"),
               ("plogNumFreedLogs", "WriteLogsFreed"),
               ("plogNumFreedCommitLogs", "CommitLogsFreed"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Dedup Throughput',
            'metrics': ['dedupedBytes','hashedBytes','dedupTput', 'hashTput'],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'DDP Internal Rates',
            'metrics': ['ddpWriteRate','ddpCommitRate'],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'DDP Bytes per commit',
            'metrics': ['txnSizePerCommit', 'mappedBytesPerCommit'],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Dedup Run Time',
            'metrics': ["txnBuildTime", "txnWriteTime", "txnReplayTime",
                        "hashCalcTime", "compressionTime", "dataWriteTime",
                        "txnReplayHashmapTime", "txnReplayXmapTime",
                        "txnReplayBitmapTime"],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Dedup Metadata IO',
            'metrics': ["numHashmapRd", "numHashmapWrt", "numBitmapRd", "numBitmapWrt", "numXMapRd", "numXMapWrt",],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Dedup Percentages',
            'metrics': ["dedupPct", "dedupCcheHitRt", "compressPct"],
            'unit': u"percent",
            'min': 0,
            'max': 100,
            'detailOnly': True,
         },
         {
            'title': 'Dedup Capacity',
            'metrics': [#'capacity', 'capacityReserved', 'capacityUsed', 'rcSize', 'wbSize',
               "ddpTotalCap", "ddpFreeCap",],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Dedup Txn Replay Optimization',
            'metrics': ["pendingTxnReplayYields", "txnReplayWriteIOs",
                        "txnReplayReadIOHits"],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'LLOG Latency',
            'metrics': [
               ("latencyRcRead", "RC Read"),
               ("latencyWbRead", "WB Read"),
               ("latencyRcWrite", "RC Write"),
               ("latencyWbWrite", "WB Write"),
               ("latencyRcRdQ", "RC Read Queue"),
               ("latencyRcWrtQ", "RC Write Queue"),
               ("latencyWbRdQ", "WB Read Queue"),
               ("latencyWbWrtQ", "WB Write Queue"),
            ],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'LLOG IOPs',
            'metrics': [
               ("iopsRcRead", "RC Read"),
               ("iopsWbRead", "WB Read"),
               ("iopsRcWrite", "RC Write"),
               ("iopsWbWrite", "WB Write"),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Block attribute cache size',
            'metrics': ["blkAttrCcheSz",],
            'unit': u"mbytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Blk Attr cache hit rate',
            'metrics': ['blkAttrCcheHitRt'],
            'unit': u"percent",
            'min': 0,
            'max': 100,
            'detailOnly': True,
         },
         {
            'title' : 'Compressed Blocks in Dedup',
            'metrics': ['numCompressedHashBlocks'],
            'unit': u"short",
            'detailOnly': True,
         },
         {
            'title': 'Dedup IO Distribution',
            'metrics': ['numDdpMetadataReads', 'numDdpMetadataWrites',
                        'numGuestReads'],
            'unit': u"short",
            'detailOnly': True,
         },
         {
            'title': 'Checksum Error (& Corrected)',
            'metrics': [
               'checksumErrors', 'totalDATABlksCorrected', 'totalCRCCorrected'
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Zero Usage',
            'metrics': [
               ("plogDGZeroUsage", "DGZero"),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
      ],
      'entityToShow':'cache-disk',
   },
   'read_cache' : {
      'title': 'LSOM: Read Cache',
      'repeat': True,
      'tag' :  'lsom',
      'metrics': [
         {
            'title': 'RC Hit Rate (Hybrid Only)',
            'metrics': ['rcHitRate', 'rcPartialMissRate'],
            'unit': u"percent",
            'min': 0,
            'max': 100,
            'detailOnly': False,
         },
         {
            'title': 'RC Hit Rate (Hybrid Only)(per-mille)',
            'metrics': ['rcHitRatePerMille'],
            'unit': u"short",
            'min': 0,
            'max': 1000,
            'detailOnly': False,
         },
         {
            'title': 'RC IOPs Breakdown (Hybrid Only)',
            'metrics': [('iopsRead','Total Reads'),
                        ('iopsRcMemReads','RC Mem reads'),
                        ('iopsRcSsdReads','RC SSD reads'),
                        ('iopsRcTotalRead','RC Hits'),
                        ('iopsRcRawar','R-a-W-a-R'),
                        ],
            'unit' : u"iops",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'RC Evictions',
            'metrics': [('quotaEvictions', 'Quota'),
                        ('warEvictions', 'Writes after Read'),
                        ('allEvictions', 'All evictions')],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'RC Bytes read from invalidated lines (Hybrid only)',
            'metrics': [('readInvalidatedBytesRawar','R-W-R bytes'),
                        ('readInvalidatedBytesPatched','Patched bytes'),
                        ('readInvalidatedBytesWastedPatched','Wasted patched bytes'),
                        ],
            'unit' : u"bytes",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Counters from the PLOG callback path to RC (Hybrid only)',
            'metrics': [('plogRclNotFound','RCL not found'),
                        ('plogInvalidationBitNotSet','Inv bit not set'),
                        ('plogInvalidated','Invalidated'),
                        ('plogPatched','Patched'),
                        ],
            'unit' : u"short",
            'min': 0,
            'detailOnly': False,
         },
      ],
      'entityToShow':'cache-disk',
   },
   'capacity_disk' : {
      'title': 'LSOM: Capacity Disk',
      'repeat': True,
      'tag' :  'lsom',
      'metrics': [
         {
            'title': 'Device IOPS',
            'metrics': [('iopsDevRead', 'Read'),
                        ('iopsDevWrite', 'Write')],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Device Throughput',
            'metrics': [('throughputDevRead', 'Read'),
                        ('throughputDevWrite', 'Write')],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Device Latency',
            'metrics': [
               ('latencyDevDAvg', 'DAVG'),
               ('latencyDevKAvg', 'KAVG'),
               ('latencyDevGAvg', 'GAVG'),
               ('latencyDevRead', 'RDLAT'),
               ('latencyDevWrite', 'WRLAT'),
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Device Latency (MAX)',
            'metrics': [
               ('latencyDevReadMax', 'RDLAT-MAX'),
               ('latencyDevWriteMax', 'WRLAT-MAX')
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Device Latency (MIN)',
            'metrics': [
               ('latencyDevReadMin', 'RDLAT-MIN'),
               ('latencyDevWriteMin', 'WRLAT-MIN'),
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Latencies',
            'metrics': [
               ("plogReadQLatency", 'Read Queue'),
               ("plogWriteQLatency", 'Write Queue'),
               ("plogHelpRdQLat", 'Helper Q Read'),
               ("plogHelpWrQLat", 'Helper Q Write'),
               ("latencyRead", 'Read Total'),
               ("latencyWrite", 'Write Total'),
            ],
            'unit': u"µs",
            'min': 0,
            'thresholds': [30000, 50000],
            'detailOnly': True,
         },
         {
            'title': 'PLOG Cumulative Enc Latency',
            'metrics': [
               ("plogCumlEncRdLat", "Enc Read Latency"),
               ("plogCumlEncWrLat", "Enc Write Latency"),
            ],
            'unit': u"µs",
            'min': 0,
            'thresholds': [30000, 50000],
            'detailOnly': True,
         },
         {
            'title': 'PLOG Average Queue Depth',
            'metrics': [
               ("plogHelpRdQDepth", "Helper RQ Depth"),
               ("plogHelpWrQDepth", "Helper WQ Depth"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Capacity',
            'metrics': [
               ("capacityUsed", "Capacity Used"),
               ("capacityCompressed", "Capacity Compressed")
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Multi Elevator Compression Time',
            'metrics': [
               ("multiElevCompressionTime", "Compression Time"),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Multi Elevator Compression Percentage',
            'metrics': [
               ("multiElevCompressPct", "Compression Percentage"),
            ],
            'unit': u"percent",
            'min': 0,
            'max': 100,
            'detailOnly': True,
         },
         {
            'title': 'Multi Elevator Compression Blocks',
            'metrics': [
               ("multiElevNumCompressedBlocks", "Compressed Blocks"),
               ("multiElevNumUncompressedBlocks", "Uncompressed Blocks"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Multi Elevator Metadata IO',
            'metrics': [
               ("multiElevNumHashmapRd", "Hashmap Reads"),
               ("multiElevNumHashmapWrt", "Hashmap Writes"),
               ("multiElevNumBitmapRd", "Bitmap Reads"),
               ("multiElevNumBitmapWrt", "Bitmap Writes"),
               ("multiElevNumXMapRd", "Xmap Reads"),
               ("multiElevNumXMapWrt", "Xmap Writes"),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Multi Elevator IO Scheduling',
            'metrics': [
               ('multiElevAvgIdleTime', 'Idle'),
               ('multiElevAvgPreReadTime', 'Pre-Read'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Multi Elevator Run Time',
            'metrics': [
               ("multiElevTxnBuildTime", "Txn Build Time"),
               ("multiElevTxnWriteTime", "Txn Write Time"),
               ("multiElevTxnReplayTime", "Txn Replay Time"),
               ("multiElevCompressionTime", "Compression Time"),
               ("multiElevDataWriteTime", "Data Write Time"),
               ("multiElevTxnReplayHashmapTime", "Txn Replay Hashmap Time"),
               ("multiElevTxnReplayXmapTime", "Txn Replay Xmap Time"),
               ("multiElevTxnReplayBitmapTime", "Txn Replay Bitmap Time"),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Multi Elevator Txn Replay Optimization',
            'metrics': [
               ("multiElevPendingTxnReplayYields", "Pending Replay Yields"),
               ("multiElevTxnReplayReadIOHits", "Replay Read IO Hits"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Multi Elevator IO Distribution',
            'metrics': [
               ("multiElevNumDdpMetadataReads", "Dedup Metadata Reads"),
               ("multiElevNumDdpMetadataWrites", "Dedup Metadata Writes"),
               ("multiElevNumGuestReads", "Guest Reads"),
            ],
            'unit': u"short",
            'detailOnly': True,
         },
         {
            'title': 'Transient Capacity Used',
            'metrics': [
               ("dgTransientCapacityUsed",
                "Disk Group"),
               ("diskTransientCapacityUsed",
                "Disk")
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'PLOG Read Throughput',
            'metrics': [
               ("plogTotalBytesRead", "Total"),
               ("plogTotalBytesReadFromMD", "MD"),
               ("plogTotalBytesReadFromSSD", "SSD"),
               ("plogTotalBytesReadByRC", "RC"),
               ("plogTotalBytesReadByVMFS", "VMFS"),
               # New
               ("plogTotalTputRead", "Total"),
               ("plogTotalTputReadFromMD", "MD"),
               ("plogTotalTputReadFromSSD", "SSD"),
               ("plogTotalTputReadByRC", "RC"),
               ("plogTotalTputReadByVMFS", "VMFS"),
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG ReadOPS',
            'metrics': [
               ("plogNumTotalReads", "Total"),
               ("plogNumMDReads", "MD"),
               ("plogNumSSDReads", "SSD"),
               ("plogNumRCReads", "RC"),
               ("plogNumVMFSReads", "VMFS"),
               # New
               ("plogNumTotalReadOPS", "Total"),
               ("plogNumMDReadOPS", "MD"),
               ("plogNumSSDReadOPS", "SSD"),
               ("plogNumRCReadOPS", "RC"),
               ("plogNumVMFSReadOPS", "VMFS"),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Data Usage',
            'metrics': [
               ("plogMDDataUsage", "MDData"),
               ("plogDGDataUsage", "DGData"),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Write Throughput',
            'metrics': [
               ("plogTotalCSBytes", "CS"),
               ("plogTotalZeroBytes", "Zero"),
               ("plogTotalDelBytes", "Delete"),
               ("plogTotalFSBytes", "fsBytes"),
               ("plogTotalCFBytes", "cfBytes"),
               ("plogTotalFSUnmapBytes", "fsUnmapBytes"),
               ("plogTotalCFUnmapBytes", "cfUnmapBytes"),
               # New
               ("plogTotalCSTput", "CS"),
               ("plogTotalZeroTput", "Zero"),
               ("plogTotalDelTput", "Delete"),
               ("plogTotalFSTput", "fsBytes"),
               ("plogTotalCFTput", "cfBytes"),
               ("plogTotalFSUnmapTput", "fsUnmapBytes"),
               ("plogTotalCFUnmapTput", "cfUnmapBytes"),
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Elev (aka Destage/Drain) Tput',
            'metrics': [
               ("plogTotalBytesDrained", "TotalDrained"),
               ("plogSsdBytesDrained", "SSDDrained"),
               ("plogZeroBytesDrained", "ZeroDrained"),
               # New
               ("plogTotalTputDrained", "TotalDrained"),
               ("plogSsdTputDrained", "SSDDrained"),
               ("plogZeroTputDrained", "ZeroDrained"),
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'PLOG bucket data usage',
            'metrics': [('b0Data', 'Bucket 0'),
                        ('b1Data', 'Bucket 1'),
                        ('b2Data', 'Bucket 2'),
                        ('b3Data', 'Bucket 3'),
                        ('b4Data', 'Bucket 4'),
                        ('b5Data', 'Bucket 5'),
                        ('b6Data', 'Bucket 6'),
                        ('b7Data', 'Bucket 7'),
                        ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG bucket zero usage',
            'metrics': [('zeroesBucket0', 'Bucket 0'),
                        ('zeroesBucket1', 'Bucket 1'),
                        ('zeroesBucket2', 'Bucket 2'),
                        ('zeroesBucket3', 'Bucket 3'),
                        ('zeroesBucket4', 'Bucket 4'),
                        ('zeroesBucket5', 'Bucket 5'),
                        ('zeroesBucket6', 'Bucket 6'),
                        ('zeroesBucket7', 'Bucket 7'),
                        ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Delete Congestion',
            'metrics': [('deleteCongestion', 'Delete Congestion'),
                        ('deleteCongestionLocalMax', 'Max Delete Congestion during sampling'),
                        ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Data Elev OPs & Activations',
            'metrics': [
               ("plogNumElevSSDReads", "Elev SSD read ops"),
               ("plogNumElevMDWrites", "Elev SSD write ops"),
               ("elevBHActivations", "Elev base handler activations"),
               ("plogNumLbaEntriesInCurBkt", "LBA entries in current bucket"),
               ("plogNumLbaEntriesSkipped", "LBA entries skipped"),
               ("plogElevCycles", "ELEV_BASE -> DOELEVIO transitions"),
               ("elevSMActs", "Elev SM activations"),
               ("plogElevDoNotRun", "Elev should not start"),
               ("elevAlreadyRunning", "Elev already running"),
               ("plogPrepSMActs", "PLOG Prep SM activations"),
               ("numDelTasks", "PLOG Del tasks"),
               ("numDelYields", "PLOG Del yields"),
               ("delSMActs", "PLOG Del acts"),
               ("numDelCompleted", "PLOG Del Completed"),
               ("plogCommitSMActs", "PLOG Commit SM activations"),
               ("plogWindowCommitStart", "Commit start for window"),
               ("plogWindowCommitEnd", "Commit end for window"),
               # New
               ("plogNumElevSSDReadOPS", "ElevSSDOPS"),
               ("plogNumElevMDWriteOPS", "ElevMDOPS"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Data Elevator Commit Related Logs',
            'metrics': [
               ("plogNumWriteLogs", "WriteLogs"),
               ("plogNumCommitLogs", "CommitLogs"),
               ("plogNumFreedLogs", "WriteLogsFreed"),
               ("plogNumFreedCommitLogs", "CommitLogsFreed"),
               ("plogNumOverlapSkipped", "Overlap skipped"),
               ("plogNumOverlapRetired", "Overlap retired"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Data Elevator Commit Related Timing',
            'metrics': [
               ('plogCommitLogCbTime', 'Log entry commit time (verbose)'),
               ('elevatorWaitOnCFTime', 'Wait in CF ready state'),
               ('plogWindowCommitTime', 'Time to commit a complete window'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Elevator Extra stats',
            'metrics': [
               ("elevOffset", "Data Elev LBA Offset"),
               ("zeroElevLbaOffset", "Zero Elev LBA Offset"),
               ("elevWindow", "Data Elev Current Window"),
               ("elevNextWindow", "Data Elev Next Window"),
               ('elevCurBucket', 'Data Elev Current bucket'),
               ('zeroElevCurBucket', 'Zero Elev Current bucket'),
               ('curWBBucket', 'Current WB bucket'),
               ('zeroElevCurTxnScopes', 'Zero Elev TxnScopes'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Data Elev Latency',
            'metrics': [
               ("elevSSDReadLatency", "SSD Read"),
               ("elevMDWriteLatency", "MD Write"),
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'DDP Write / Commit Time by Data Elevator',
            'metrics': [('avgDdpWriteTime', 'DDP Write'),
                        ('avgDdpCommitTime', 'DDP Commit'),
                        ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'DDP Data Elev IO Size',
            'metrics': [('avgElevIoSize', 'IO Size'),
                        ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Virsto Map Blocks',
            'metrics': [
               ("virstoValidMapBlocks", "Valid"),
               ("virstoInvalidMapBlocks", "Invalid"),
               ("virstoDirtyMapBlocks", "Dirty"),
               ("virstoFreeMapBlocks", "Free"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Virsto Map Block Cache',
            'metrics': [
               ("virstoMapBlockCacheHitsPerSec", "Hits/sec"),
               ("virstoMapBlockCacheMissesPerSec", "Misses/sec"),
               ("virstoMapBlockCacheEvictionsPerSec", "Evictions/Sec"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Virsto Metadata Flusher Runs',
            'metrics': [
               ("virstoMetadataFlusherRunsPerSec", "Runs/sec"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Virsto Metadata Pending data',
            'metrics': [
               ("virstoMetadataFlusherPendingBuffers", "Pending buffers"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Virsto Metadata Flush Tput',
            'metrics': [
               ("virstoMetadataFlushedPerRun", "KB Flushed per Run"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Virsto Instance',
            'metrics': [
               ("virstoInstanceHeapUtilization", "HeapUsed"),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Commit Flusher Components',
            'metrics': [
               ("commitFlusherComponentsToFlush", "ComponentsToFlush"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Commit Flusher Extents',
            'metrics': [
               ("commitFlusherExtentsProcessed", "ExtentsCount"),
               ("commitFlusherExtentSizeProcessed", "ExtentsSize"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Time in commit flusher',
            'metrics': [
               ("cfTime", "Commit Flusher"),
               ("blkAttrFlshTime", "Checksum blkattr"),
               ("vrstBarrTime", "Virsto Metadata"),
               ("plogIOTime", "PLOG IO"),
            ],
            'unit': u"ms",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Commit flusher run breakdown',
            'metrics': [
               ("numCFAct", "Commit Flusher"),
               ("numCksumFlsh", "Checksum blkattr"),
               ("numVrstBar", "Virsto MetaData"),
               ("numPlogIOs", "PLOG IO"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Checksum Error (& Corrected)',
            'metrics': [
               'checksumErrors', 'totalDATABlksCorrected', 'totalCRCCorrected'
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Zero Stats',
            'metrics': [
               ("zerosInFlight", "Total Zero Bytes In Flight"),
               ("zerosInFlightSystem", "Transient Zero Bytes In Flight"),
               ("zerosProcessedSystem","Transient Zero Bytes Processed"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Unmap Quota Stats',
            'metrics': [
               ("unmapQuota", "Unmap Bytes Allowed"),
               ("unmapQuotaAvailableBytes", "Unmap Bytes Quota Available"),
               ("unmapQuotaConsumedBytes","Unmap Bytes Quota Consumed"),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Unmap Fairness Stats',
            'metrics': [
               ("unmapInline", "Unmaps Processed Inline"),
               ("unmapDelayed", "Unmaps Processed Background"),
               ("unmapQuotaConsumedPages","Unmap Pages Consumed"),
               ("unmapQuotaFailed","Times Quota Full"),
               ("unmapQuotaRelinquished","Times Quota Relinquished"),
               ("unmapPendingProcessedPages", "Released Pages"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Pending Unmap Component Stats',
            'metrics': [
               ("unmapPendingComponents", "Components"),
               ("unmapPendingComponentsQueued", "Components Queued"),
               ("unmapPendingComponentsActive", "Components Active"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Pending Unmap Stats',
            'metrics': [
               ("unmapPendingBytes", "Pending Bytes"),
               ("unmapPendingPlacedBytes", "Placed Bytes"),
               ("unmapPendingProcessedBytes", "Released Bytes"),
               ("unmapPendingInflightBytes", "Inflight Release Bytes"),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Number of Delta Components',
            'metrics': [('unplannedDeltaComponents', 'Unplanned'),
                        ('plannedDeltaComponents', 'Planned')],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Zero Usage',
            'metrics': [
               ("plogMDZeroUsage", "MDZero"),
               ("plogDGZeroUsage", "DGZero"),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'DDP Write / Commit Time by Zero Elevator',
            'metrics': [('avgZeroElevDdpWriteTime', 'DDP Write'),
                        ('avgZeroElevDdpCommitTime', 'DDP Commit'),
                        ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'DDP Zero Elev IO Size',
            'metrics': [('avgZeroElevIoSize', 'IO Size'),
                        ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Zero Elev OPs & Activations',
            'metrics': [
               ("numLbaEntriesInCurZeroBkt", "LBA entries in current bucket"),
               ("numNonZeroLbaEntriesSkipped", "LBA entries skipped"),
               ("plogZeroElevCycles", "ZE_Base -> ZE_DoIOs transitions"),
               ("zeroElevSMActivations", "Elev SM activations"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Zero Elevator Commit Related Logs',
            'metrics': [
               ("plogNumZeroElevPrepLogs", "PrepareLogs"),
               ("plogNumZeroElevCommitLogs", "CommitLogs"),
               ("plogNumFreedZeroElevPrepLogs", "PrepareLogsFreed"),
               ("plogNumFreedZeroElevCommitLogs", "CommitLogsFreed"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG Zero Elevator Commit Related Timing',
            'metrics': [
               ('plogZeroElevCommitLogCbTime', 'Log entry commit time (verbose)'),
               ('zeroElevatorWaitOnCFTime', 'Wait in CF ready state'),
               ('plogZeroElevWindowCommitTime', 'Time to commit a complete window'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
         },
      ],
      'entityToShow':'capacity-disk',
   },
   'cmmds' : {
      'title': 'CMMDS: Verbose Stats (Verbose Dump)',
      'repeat': True,
      'tag' :  'cmmds',
      'metrics': [
                    {
                       'title': 'Messages/sec',
                       'metrics': ['multicastMessagesReceived', 'multicastMessagesSent', 'unicastMessagesReceived', 'unicastMessagesSent'],
                       'unit': u"iops",
                       'min': 0,
                       'detailOnly': False,
                    },
                    {
                       'title': 'Tput',
                       'metrics': ['multicastBytesReceived', 'multicastBytesSent', 'unicastBytesReceived', 'unicastBytesSent',],
                       'unit': u"Bps",
                       'min': 0,
                       'detailOnly': False,
                    },
                    {
                       'title': 'Updates/sec',
                       'metrics': ['updatesApplied', 'updatesRequested'],
                       'unit': u"short",
                       'min': 0,
                       'detailOnly': False,
                    },
                 ] + [
                    # XXX: The below should be properly formatted and put
                    # in panels, or explicitly decided to not be shown, but
                    # then for whom do we collect them?
                    {
                       'title': m,
                       'metrics': [m],
                       'unit': u"short",
                       'detailOnly': True,
                    }
                    for m in ['inboundTraffic', 'outboundTraffic', 'statsTime', ]
                 ],
      'entityToShow':'cmmds:',
   },
   'clom-disk-stats' : {
      'title': 'CLOM: Disk Stats',
      'repeat': False,
      'tag' :  'clom',
      'metrics':[
         {
            'title': m,
            'metrics': [m],
            'unit': u"short",
            'detailOnly': True,
         }
         for m in ['diskCompCntRatio', 'diskDataCompCntRatio', 'diskgrpDataCompCntRatio',
                   'nodeCompCntRatio', 'nodeDataCompCntRatio', 'diskFullness',
                   'updatesApplied', 'updatesRequested', 'fitness', 'maxActResvSpaceUtil',
                   'placementGroup', 'rcResvUtil', 'resourceStddevChange', 'unresvAddrSpaceUtil',
                   'usageVariance', 'versionWeight' ]
      ],
      'entityToShow':'clom-disk-stats',
   },
   'clom_host_stats' : {
      'title': 'CLOM: Host Stats',
      'repeat': False,
      'tag' :  'clom',
      'metrics':[
         {
            'title': m,
            'metrics': [m],
            'unit': u"short",
            'detailOnly': True,
         }
         for m in ['nodeCompCntRatio', 'nodeDataCompCntRatio']
      ],
      'entityToShow':'clom-host-stats',
   },
   'clom-disk-fullness-stats' : {
      'title': 'CLOM: Disk Fullness Stats',
      'repeat': False,
      'tag' :  'clom',
      'metrics': [
         {
            'title': m,
            'metrics': [m],
            'unit': u"short",
            'detailOnly': True,
         }
         for m in ["physFreeCapacity", "physFullness", "logicalFullness", "transientCapacityUsed",
                   "rebalFullness", "dedupRatio", "pendingWrites", "pendingDelete", "logicalCapacityRequested",
                   "physDiskCapacityReserved", "actualBytesSchedToMove", "actualBytesMoving",
                   "rebalStatus", "numComponents"]
      ],
      'entityToShow': 'clom-disk-fullness-stats',
   },
   'clom-slack-space-stats' : {
      'title': 'CLOM: Slack Space Stats',
      'repeat': False,
      'tag' :  'clom',
      'metrics': [
         {
            'title': m,
            'metrics': [m],
            'unit': u"short",
            'detailOnly': True,
         }
         for m in ["repairQueuedBytes", "repairQueuedObjects", "decomQueuedBytes", "decomQueuedObjects",
                   "rebalanceQueuedBytes", "rebalanceQueuedObjects", "fixComplianceQueuedBytes",
                   "fixComplianceQueuedObjects", "changeQueuedBytes", "changeQueuedObjects",
                   "moveQueuedBytes", "moveQueuedObjects", "consolidateQueuedBytes", "consolidateQueuedObjects",
                   "concatQueuedBytes", "concatQueuedObjects", "totalQueuedBytes", "totalQueuedObjects",
                   "totalQueuedWorkItems"]
      ],
      'entityToShow': 'clom-slack-space-stats',
   },
   'clom-workitem-stats' : {
      'title': 'CLOM: WorkItem Stats',
      'repeat': False,
      'tag' :  'clom',
      'metrics': [
         {
            'title': m,
            'metrics': [m],
            'unit': u"short",
            'detailOnly': True,
         }
         for m in ["thinPlacementSuccessCount", "thickPlacementSuccessCount", "reactiveRebalanceSuccessCount",
                   "proactiveRebalanceSuccessCount", "cleanupSuccessCount", "repairSuccessCount",
                   "decomSuccessCount", "deltaDecomSuccessCount", "unplannedDeltaSuccessCount",
                   "concatSuccessCount", "forceRepairSuccessCount", "changeSuccessCount",
                   "changePendingSuccessCount", "complianceSuccessCount", "totalSuccessCount"]
      ],
      'entityToShow': 'clom-workitem-stats',
   },
   'vsan-distribution' : {
      'title': 'VSAN Distribution',
      'repeat': False,
      'repeatByHost': False,
      'metrics':[
         {
            'title': m,
            'metrics': [m],
            'unit': u"short",
            'detailOnly': True,
         }
         for m in [
            "components", "ioComponents",
            "domClients", "domOwners",
            "domColocated", "unplannedDeltaComponents",
            "plannedDeltaComponents",
         ]
      ],
      'entityToShow':'vsan-distribution',
   },
   'vsan-esa-distribution' : {
      'title': 'VSAN ESA Distribution',
      'repeat': False,
      'repeatByHost': False,
      'metrics':[
         {
            'title': m,
            'metrics': [m],
            'unit': u"short",
            'detailOnly': True,
         }
         for m in [
            "components", "ioComponents", "maxComponents",
            "domClients", "domOwners", "domColocated"
         ]
      ],
      'entityToShow':'vsan-esa-distribution',
   },
   'host-memory' : {
      'title': 'Memory: Heaps and Slabs',
      'repeat': False,
      'repeatByHost': True,
      'metrics':[
         {
            'title': 'Slab Utilization',
            'metrics': ['slabUtil'],
            'unit': u"short",
            'min': 0,
            'max': 100,
            'detailOnly': True,
         },
         {
            'title': 'Slab Allocation Failures',
            'metrics': ['slabAllocFailures'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Heap Utilization',
            'metrics': ['heapUtil'],
            'unit': u"short",
            'min': 0,
            'max': 100,
            'detailOnly': True,
         },
         {
            'title': 'Heap Allocation Failures',
            'metrics': ['heapAllocFailures'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
      ],
      'useRegex': True,
      'entityToShow': 'host-memory-.*',
   },
   'rdt-info' : {
      'title': 'RDT: Info',
      'repeat': False,
      'repeatByHost': False,
      'tag': 'rdt',
      'metrics':[
         {
            'title': 'Checksum Mismatch Count',
            'metrics': ['checksumMismatchCount'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Association Count',
            'metrics': ['assocCount'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Maximum Association Count Reached',
            'metrics': ['maxAssocCountReached'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'RDT Connection Count',
            'metrics': ['rdtConnCount'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Maximum RDT Connection Count Reached',
            'metrics': ['maxRDTConnCountReached'],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Total Bytes transferred',
            'metrics': ['totalTxBytes'],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Maximum Bytes transferred',
            'metrics': ['maxTxBytes'],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Total Bytes Recieved',
            'metrics': ['totalRxBytes'],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Maximum Bytes Recieved',
            'metrics': ['maxRxBytes'],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         }
      ],
      'useRegex': True,
      'entityToShow': 'rdt-.*',
   },
   'vnic-rdt-network-latency' : {
      'title': 'RDT: Virtual NIC Stats',
      'repeat': False,
      'repeatByHost': True,
      'entityToShow': 'vnic-rdt-network-latency',
      'tag': 'rdt',
      'metrics':[
         {
            'title': 'Network Latency & Outbound Queueing Latency',
            'metrics': ['avgLatency', 'txQLatAvg'],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'Network Latency & Outbound Queueing Latency (MAX)',
            'metrics': ['maxLatency', 'txQLatMax'],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'Network Latency & Outbound Queueing Latency (MIN)',
            'metrics': ['minLatency', 'txQLatMin'],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'Space Available In RX Socket/TX Socket And TX Context Queue',
            'metrics': ['rxSbSpaceAvg', 'txSbSpaceAvg', 'txCtxQAvg', ],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'Space Available In RX Socket/TX Socket And TX Context Queue (MAX)',
            'metrics': ['rxSbSpaceMax', 'txSbSpaceMax', 'txCtxQMax'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'Space Available In RX Socket/TX Socket And TX Context Queue (MIN)',
            'metrics': ['rxSbSpaceMin', 'txSbSpaceMin', 'txCtxQMin'],
            'unit': u"bytes",
            'min': 0,
         },
      ],
   },
   'rdt-network-latency' : {
      'title': 'RDT: Host Stats',
      'repeat': False,
      'repeatByHost': False,
      'entityToShow': 'rdt-network-latency',
      'tag': 'rdt',
      'metrics':[
         {
            'title': 'RDT Network Latency',
            'metrics': ['avgLatency'],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'RDT Network Latency (MAX)',
            'metrics': ['maxLatency'],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'RDT Network Latency (MIN)',
            'metrics': ['minLatency'],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'Space Available In RX Socket',
            'metrics': ['rxSbSpaceAvg'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'Space Available In RX Socket (MAX)',
            'metrics': ['rxSbSpaceMax'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'Space Available In RX Socket (MIN)',
            'metrics': ['rxSbSpaceMin'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'Space Available In TX Socket',
            'metrics': ['txSbSpaceAvg'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'Space Available In TX Socket (MAX)',
            'metrics': ['txSbSpaceMax'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'Space Available In TX Socket (MIN)',
            'metrics': ['txSbSpaceMin'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'TX Context Queue',
            'metrics': ['txCtxQAvg'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'TX Context Queue (MAX)',
            'metrics': ['txCtxQMax'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'TX Context Queue (MIN)',
            'metrics': ['txCtxQMin'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'RDT Network Outbound Queueing Latency',
            'metrics': ['txQLatAvg'],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'RDT Network Outbound Queueing Latency (MAX)',
            'metrics': ['txQLatMax'],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'RDT Network Outbound Queueing Latency (MIN)',
            'metrics': ['txQLatMin'],
            'unit': u"µs",
            'min': 0,
         },
      ],
   },
   'cmmds-compression' : {
      'title': 'CMMDS: Compression Stats',
      'repeat': False,
      'tag' :  'cmmds',
      'metrics':[
         {
            'title': 'Total Compressed Bytes',
            'metrics': ['totalCompressedBytes'],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Total Uncompressed Bytes',
            'metrics': ['totalUncompressedBytes'],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         }
      ],
      'entityToShow': 'cmmds-compression',
   },

   'vmdk-vsansparse' : {
      'title': 'LSOM: vSANSparse VMDK (Verbose Dump)',
      'repeat': True,
      'tag' :  'lsom',
      'metrics': [
                    {
                       'title': 'Latency',
                       'metrics': ['latencyCacheLookup', 'latencyGwe', 'latencyRead', 'latencyWrite'],
                       'unit': u"µs",
                       'min': 0,
                       'detailOnly': False,
                    },
                    {
                       'title': 'IOPS',
                       'metrics': ['iopsGwe', 'iopsRead', 'iopsRmw', 'iopsWrite', 'iopsWriteConflicts'],
                       'unit': u"iops",
                       'min': 0,
                       'detailOnly': False,
                    },
                    {
                       'title': 'Tput',
                       'metrics': ['throughputRead', 'throughputWrite'],
                       'unit': u"Bps",
                       'min': 0,
                       'detailOnly': False,
                    },
                    {
                       'title': 'Cache HitRate',
                       'metrics': ['cacheHitRate'],
                       'unit': u"short",
                       'min': 0,
                       'detailOnly': False,
                    },
                 ] + [
                    # XXX: The below should be properly formatted and put
                    # in panels, or explicitly decided to not be shown, but
                    # then for whom do we collect them?
                    {
                       'title': m,
                       'metrics': [m],
                       'unit': u"short",
                       'detailOnly': True,
                    }
                    for m in ['cacheAllocFails', 'cacheEntries', 'cacheEvictAttempts', 'cacheHitRate', 'cacheInserts', 'cacheLockContentions', 'cacheRemoves', 'cacheUpdateLatency',
                              'lruLockContentions', 'readsToLayer']
                 ],
      'entityToShow':'vmdk-vsansparse',
   },
   'host-vsansparse' : {
      'title': 'LSOM: vSANSparse Host',
      'repeat': True,
      'tag' :  'lsom',
      'metrics': [
                    {
                       'title': 'Latency',
                       'metrics': ['latencyCacheLookup', 'latencyGwe', 'latencyRead', 'latencyWrite'],
                       'unit': u"µs",
                       'min': 0,
                       'detailOnly': False,
                    },
                    {
                       'title': 'IOPS',
                       'metrics': ['iopsGwe', 'iopsRead', 'iopsRmw', 'iopsWrite', 'iopsWriteConflicts'],
                       'unit': u"iops",
                       'min': 0,
                       'detailOnly': False,
                    },
                    {
                       'title': 'Tput',
                       'metrics': ['throughputRead', 'throughputWrite'],
                       'unit': u"Bps",
                       'min': 0,
                       'detailOnly': False,
                    },
                    {
                       'title': 'Cache HitRate',
                       'metrics': ['cacheHitRate'],
                       'unit': u"short",
                       'min': 0,
                       'detailOnly': False,
                    },
                 ] + [
                    # XXX: The below should be properly formatted and put
                    # in panels, or explicitly decided to not be shown, but
                    # then for whom do we collect them?
                    {
                       'title': m,
                       'metrics': [m],
                       'unit': u"short",
                       'detailOnly': True,
                    }
                    for m in ['cacheAllocFails', 'cacheEntries', 'cacheEvictAttempts', 'cacheInserts', 'cacheLockContentions', 'cacheRemoves', 'cacheUpdateLatency', 'lruLockContentions', 'readsToLayer']
                 ],
      'entityToShow':'host-vsansparse',
   },
   'vsan-host-net' : {
      'title': 'Networking: Host',
      'repeat': True,
      'tag' :  'network',
      'metrics': [
         {
            'title': 'Packets/sec (average)',
            'metrics': ['rxPackets', 'txPackets'],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Throughput (average)',
            'metrics': ['rxThroughput', 'txThroughput'],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Discards Rate (per-mille)',
            'metrics': [
               ('rxPacketsLossRate', 'rxPacketsDiscardsRate'),
               ('txPacketsLossRate', 'txPacketsDiscardsRate')
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'vSwitch Port Drops (per-mille)',
            'metrics': ['portRxDrops', 'portTxDrops'],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'IO Chain Drops (per-mille)',
            'metrics': ['ioChainRxdrops', 'ioChainTxdrops'],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'TcpTxRexmit Rate (per-mille)',
            'metrics': ['tcpTxRexmitRate'],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'TcpRxErrRate Rate (per-mille)',
            'metrics': ['tcpRxErrRate'],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
      ],
      'entityToShow':'vsan-host-net',
   },
   'vsan-pnic-net' : {
      'title': 'Networking: Physical NIC',
      'tag' :  'network',
      'repeat': True,
      'metrics': [
         {
            'title': 'Packets/sec (average)',
            'metrics': ['rxPackets', 'txPackets'],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Throughput (average)',
            'metrics': ['rxThroughput', 'txThroughput'],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Error Rate (per-mille)',
            'metrics': [
               ('rxPacketsLossRate', 'rxPacketsErrorRate'),
               ('txPacketsLossRate', 'txPacketsErrorRate'),
               'rxCrcErr', 'txCarErr', 'rxErr', 'txErr',
               'rxMissErr', 'rxOvErr', 'rxFifoErr',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'vSwitch Port Drops (per-mille)',
            'metrics': ['portRxDrops', 'portTxDrops'],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'IO Chain Drops (per-mille)',
            'metrics': ['ioChainRxdrops', 'ioChainTxdrops', 'ioChainDrops'],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Flow Control (per-mille)',
            'metrics': ['pauseCount', 'pfcCount',],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
      ],
      'entityToShow':'vsan-pnic-net',
   },
   'vsan_vnic_net' : {
      'title': 'Networking: Virtual NIC',
      'repeat': True,
      'tag' :  'network',
      'metrics': [
         {
            'title': 'Packets/sec (average)',
            'metrics': ['rxPackets', 'txPackets'],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Throughput (average)',
            'metrics': ['rxThroughput', 'txThroughput'],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Discards Rate (per-mille)',
            'metrics': [
               ('rxPacketsLossRate', 'rxPacketsDiscardsRate'),
               ('txPacketsLossRate', 'txPacketsDiscardsRate')
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'vSwitch Port Drops (per-mille)',
            'metrics': ['portRxDrops', 'portTxDrops'],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'IO Chain Drops (per-mille)',
            'metrics': ['ioChainRxdrops', 'ioChainTxdrops'],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
      ],
      'entityToShow':'vsan-vnic-net',
   },
   'vsan_tcp_ip' : {
      'title': 'Networking: TCP IP',
      'repeat': True,
      'tag' :  'network',
      'metrics': [
         {
            'title': 'Packets/sec (average)',
            'metrics': ['tcpRxPackets', 'tcpTxPackets'],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Throughput (average)',
            'metrics': ['tcpRxThroughput', 'tcpTxThroughput'],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'TCP Connections (ikb 57375)',
            'metrics': [
               # metrics from vsan67 U1 only
               'tcpKeeptimeo', 'tcpPersisttimeo', 'tcpRexmttimeo',
               'tcpTimeoutdrop', 'tcpConndrops', 'tcpDrops',
               'tcpKeepdrops', 'tcpRcvmemdrop', 'tcpConnects',
               # end

               'tcpHalfopenDropRate', 'tcpTimeoutDropRate',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'TCP Transmission (ikb 57375)',
            'metrics': [
               # metrics from vsan67 U1 only
               'tcpSndacks', 'tcpRcvackpack',
               'tcpRcvduppack', 'tcpRcvoopack', 'tcpRcvdupack',
               'tcpSackRexmits', 'tcpSackSendBlocks', 'tcpSackRcvBlocks',
               # end

               'tcpTxRexmitRate', 'tcpRcvdupackRate',
               'tcpRcvoopackRate', 'tcpRcvduppackRate',
               'tcpSackSendBlocksRate', 'tcpSackRcvBlocksRate',
               'tcpSackRexmitsRate',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'TCP/IP Errors (per-mille)',
            'metrics': [
               # metrics from vsan67 U1 only
               'tcpBadsyn', 'tcpBadrst',
               'tcpRcvbadsum', 'tcpRcvbadoff', 'tcpRcvshort',
               # end

               'tcpErrs', 'ipErrs', 'ip6Errs',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'TCP Congestion (average)',
            'metrics': [
               'tcpSndZeroWin', 'tcpEcnCe',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
      ],
      'entityToShow':'vsan-vnic-net',
   },
   'nfs_client_vol' : {
      'title': 'NFS',
      'repeat': True,
      'metrics': [
         {
            'title': 'IO',
            'metrics': ['reads', 'writes'],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Bytes',
            'metrics': ['readBytes', 'writeBytes'],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Time',
            'metrics': ['readTime', 'writeTime',
                        ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
      ],
      'entityToShow':'nfs-client-vol',
   },
   'ddh-disk-stats' : {
      'title': 'LSOM: DDH Disk Stats',
      'repeat': True,
      'tag' :  'lsom',
      'metrics': [
         {
            'title': 'IOPs',
            'metrics': [
               "avgReadIOPS", "avgWriteIOPS",
               "avgUnmapIOPS",
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Throughput',
            'metrics': [
               "avgReadTPut", "avgWriteTput",
               "avgUnmapTput",
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Latency',
            'metrics': [
               "avgReadLatency", "avgWriteLatency",
               "avgUnmapLatency",
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Log Congestion',
            'metrics': [
               "logCongestion",
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'PLOG IORetry Unweighted Moving Avg Latency',
            'metrics': [
               "ioretryReadLatencyUnwtdMvgAvg",
               "ioretryWriteLatencyUnwtdMvgAvg",
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG IORetry Unweighted Moving Avg Latency Std Dev',
            'metrics': [
               "ioretryReadLatencyUnwtdMvgStdDev",
               "ioretryWriteLatencyUnwtdMvgStdDev",
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG IORetry IOPS',
            'metrics': [
               "ioretryReadIopsAvg", "ioretryWriteIopsAvg",
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'PLOG IORetry IOPS Moving Avg',
            'metrics': [
               "ioretryReadIopsMvgAvg", "ioretryWriteIopsMvgAvg",
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Log Segment Number',
            'metrics': [
               ("llogStartSegNo", "LLOG Start Seg"),
               ("llogCurrentSegNo", "LLOG Current Seg"),
               ("plogStartSegNo", "PLOG Start Seg"),
               ("plogCurrentSegNo", "PLOG Current Seg"),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Interval',
            'metrics': [
               "intervalCount", "latencyIntervalSecs",
               "elapsedSecsInInterval",
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Exceed counts',
            'metrics': [
               "readLatencyExCount", "writeLatencyExCount",
               "minimumReadIOsExceededCount", "minimumWriteIOsExceededCount",
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Mean Latency',
            'metrics': [
               "currentReadLatencyMean", "currentWriteLatencyMean",
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': True,
         },
      ],
      'entityToShow':'ddh-disk-stats',
   },
   'cmmds-workload-stats' : {
      'title': 'CMMDS: Workload Stats',
      'repeat': True,
      'tag' :  'cmmds',
      'metrics': [
         {
            'title': 'Rx Stats',
            'metrics': [
               "rxAccept", "rxAgentUpdateRequest",
               "rxHeartbeatRequest", "rxMasterUpdate",
               "rxRetransmitRequest", "rxSnapshot",
               "rxMisc",
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Tx Stats',
            'metrics': [
               "txAgentUpdateRequest",
               "txHeartbeatRequest", "txMasterCheckpoint",
               "txMasterCkptTried", "txRetransmitRequest",
               "txSnapshot", "txSnapshotBytes", "txSnapshotTried",
               "txMasterUpdate", "txMasterUpdateTried",
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Batch Stats',
            'metrics': [
               "agentBatchesSent", "totalUpdSentInAgentBatch",
               "checkPointBatchesSent", "totalUpdInBatchCkpt",
               "masterBatchesRecved", "totalUpdInMasterBatches"
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
      ],
      'entityToShow':'cmmds-workloadstats',
   },
   'cmmds-update-latency' : {
      'title': 'CMMDS: Update Latency',
      'repeat': True,
      'tag' :  'cmmds',
      'metrics': [
         {
            'title': 'Updates Per Second',
            'metrics': [
               "localUpdatesReceived", "localUpdatesTransmitted",
               "localUpdatesCompleted", "updatesReceivedAtLeader",
               "updatesCommitedAtLeader",
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Average Updates Latency',
            'metrics': [
               "latencyCumulativeUpdate",
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Max Updates Latency',
            'metrics': [
               "latencyMaxUpdate",
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Min Updates Latency',
            'metrics': [
               "latencyMinUpdate",
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': False,
         },
      ],
      'entityToShow':'cmmds-update-latency',
   },
   'cmmds-net' : {
      'title': 'CMMDS: Net Stats',
      'repeat': True,
      'tag' :  'cmmds',
      'metrics': [
         {
            'title': 'Rx/Tx',
            'metrics': [
               "rdtRx", "rdtTx", "groupRx", "groupTxUcast", "groupTxMcast"
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Throughput',
            'metrics': [
               "rdtRxThroughput", "rdtTxThroughput", "groupRxThroughput",
               "groupTxUcastThroughput", "groupTxMcastThroughput"
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
      ],
      'entityToShow':'cmmds-net',
   },
   'vsan-iscsi-host' : {
      'title': 'iSCSI: Host Level Stats',
      'repeat': True,
      'metrics': [
         {
            'title': 'IOPs',
            'metrics': [
               "iopsRead", "iopsWrite", "iopsTotal"
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Throughput',
            'metrics': [
               "bandwidthRead", "bandwidthWrite", "bandwidthTotal"
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Latency',
            'metrics': [
               "latencyRead", "latencyWrite", "latencyTotal"
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Queue Depth',
            'metrics': [
               "queueDepth"
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
      ],
      'entityToShow':'vsan-iscsi-host',
   },
   'vsan-iscsi-target' : {
      'title': 'iSCSI: Target Level Stats',
      'repeat': True,
      'metrics': [
         {
            'title': 'IOPs',
            'metrics': [
               "iopsRead", "iopsWrite", "iopsTotal"
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Throughput',
            'metrics': [
               "bandwidthRead", "bandwidthWrite", "bandwidthTotal"
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Latency',
            'metrics': [
               "latencyRead", "latencyWrite", "latencyTotal"
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Queue Depth',
            'metrics': [
               "queueDepth"
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
      ],
      'entityToShow':'vsan-iscsi-target',
   },
   'vsan-iscsi-lun' : {
      'title': 'iSCSI: LUN Level Stats',
      'repeat': True,
      'metrics': [
         {
            'title': 'IOPs',
            'metrics': [
               "iopsRead", "iopsWrite", "iopsTotal"
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Throughput',
            'metrics': [
               "bandwidthRead", "bandwidthWrite", "bandwidthTotal"
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Latency',
            'metrics': [
               "latencyRead", "latencyWrite", "latencyTotal"
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Queue Depth',
            'metrics': [
               "queueDepth"
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
      ],
      'entityToShow':'vsan-iscsi-lun',
   },
   'lsom-world-cpu' : {
      'title': 'LSOM: Worlds',
      'repeat': False,
      'repeatByHost': True,
      'tag' :  'lsom',
      'metrics': get_world_metrics_definition(),
      'entityToShow':'lsom-world-cpu',
   },
   'dom-world-cpu' : {
      'title': 'DOM vSAN & vSAN ESA: Worlds',
      'repeat': False,
      'repeatByHost': True,
      'tag' :  'dom',
      'metrics': get_world_metrics_definition(),
      'entityToShow':'dom-world-cpu',
   },
   'psa-completion-world-cpu' : {
      'title': 'PSA Completion: Worlds',
      'repeat': False,
      'repeatByHost': True,
      'metrics': get_world_metrics_definition(),
      'entityToShow': 'psa-completion-world-cpu',
   },
   'cmmds-world-cpu' : {
      'title': 'CMMDS: Worlds',
      'repeat': False,
      'repeatByHost': True,
      'tag' :  'cmmds',
      'metrics': get_world_metrics_definition(),
      'entityToShow':'cmmds-world-cpu',
   },
   'rdt-world-cpu' : {
      'title': 'RDT: Worlds',
      'repeat': False,
      'repeatByHost': True,
      'tag': 'rdt',
      'metrics': get_world_metrics_definition(),
      'entityToShow':'rdt-world-cpu',
   },
   'host-cpu' : {
      'title': 'PCPU Average: Host System',
      'repeat': False,
      'metrics': [
         {
            'title': 'CPU Core Utilization',
            'metrics': [
               "coreUtilPct",
            ],
            'unit': u"percent",
            'min': 0,
         },
         {
            'title': 'PCPU Used Percentage',
            'metrics': [
               "pcpuUsedPct",
            ],
            'unit': u"percent",
            'min': 0,
         },
         {
            'title': 'PCPU Util Percentage',
            'metrics': [
               "pcpuUtilPct",
            ],
            'unit': u"percent",
            'min': 0,
            'max': 100,
         },
      ],
      'entityToShow':'host-cpu',
   },
   'vsan-cpu' : {
      'title': 'Worlds: vSAN & vSAN ESA Overall',
      'repeat': False,
      'metrics': get_world_metrics_definition(),
      'entityToShow':'vsan-cpu',
   },
   'system-mem' : {
      'title': 'Memory: Host System',
      'repeat': False,
      'metrics': [
         {
            'title': 'Total Memory Used',
            'metrics': ['totalMbMemUsed'],
            'unit': u"mbytes",
            'thresholds': [30000, 50000],
            'min': 0,
         },
         {
            'title': 'Percentage Memory Used',
            'metrics': ['pctMemUsed'],
            'unit': u"percent",
            'min': 0,
         },
         {
            'title': 'Tput',
            'metrics': ['overcommitRatio'],
            'unit': u"percentunit",
            'min': 0,
         },
      ],
      'entityToShow':'system-mem',
   },
   'vsan-memory' : {
      'title': 'Memory: vSAN & vSAN ESA Overall',
      'repeat': False,
      'metrics': [
         {
            'title': 'Kernel World Reserved',
            'metrics': ['kernelReservedSize'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'User World Reserved',
            'metrics': ['uwReservedSize'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'User World Consumed',
            'metrics': ['uwConsumedSize'],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'User World Reserved Breakdown',
            'metrics': ["vsanmgmtdReservedSize", "vsanmgmtdWatchdogReservedSize",
               "clomdReservedSize", "osfsdReservedSize", "cmmdsdReservedSize",
               "vitdReservedSize", "vsandevicemonitordReservedSize",
               "vsanobserverReservedSize", "vsantracedReservedSize",
               "epdReservedSize", "cmmdsTimeMachineReservedSize",],
            'unit': u"bytes",
            'min': 0,
         },
         {
            'title': 'User World Consumed Breakdown',
            'metrics': ["vsanmgmtdConsumedSize", "vsanmgmtdWatchdogConsumedSize",
               "clomdConsumedSize", "osfsdConsumedSize", "cmmdsdConsumedSize",
               "vitdConsumedSize", "vsandevicemonitordConsumedSize",
               "vsanobserverConsumedSize", "vsantracedConsumedSize",
               "epdConsumedSize", "cmmdsTimeMachineConsumedSize",],
            'unit': u"bytes",
            'min': 0,
         },
      ],
      'entityToShow':'vsan-memory',
   },
   'dom_proxy_owner' : {
      'title': 'DOM vSAN & vSAN ESA: Proxy Owner Aggregated',
      'repeat': True,
      'tag' :  'dom',
      'metrics': [
         {
            'title': 'IOPs',
            'metrics': ['proxyIops', 'proxyIopsRead', 'proxyIopsWrite',
                        'proxyIopsRWResync', 'anchorIops', 'anchorIopsRead',
                        'anchorIopsWrite', 'anchorIopsRWResync'],
            'unit': u"iops",
            'thresholds': [30000, 50000],
            'min': 0,
         },
         {
            'title': 'Throughput',
            'metrics': ['proxyThroughput', 'proxyTputRead', 'proxyTputWrite',
                        'proxyTputRWResync', 'anchorThroughput',
                        'anchorTputRead', 'anchorTputWrite', 'anchorTputRWResync'],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'Latency',
            'metrics': ['proxyLatencyAvg', 'proxyLatencyAvgRead',
                        'proxyLatencyAvgWrite', 'proxyLatencyAvgRWResync',
                        'anchorLatencyAvg', 'anchorLatencyAvgRead',
                        'anchorLatencyAvgWrite', 'anchorLatencyAvgRWResync'],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'Congestion',
            'metrics': ['proxyCongestion', 'proxyReadCongestion',
                        'proxyWriteCongestion', 'proxyRWResyncCongestion',
                        'anchorCongestion', 'anchorReadCongestion',
                        'anchorWriteCongestion', 'anchorRWResyncCongestion',
                        ],
            'unit': u"short",
            'min': 0,
            'max': 255,
         },
         {
            'title': 'IO Count',
            'metrics': ['proxyIoCount', 'proxyReadCount',
                        'proxyWriteCount', 'proxyRWResyncCount',
                        'anchorIoCount', 'anchorReadCount',
                        'anchorWriteCount', 'anchorRWResyncCount',
                        ],
            'unit': u"short",
            'min': 0,
         },
      ],
      'entityToShow':'dom-proxy-owner',
   },
   'dom_per_proxy_owner' : {
      'title': 'DOM vSAN & vSAN ESA: Proxy Owner (Verbose Dump)',
      'repeat': True,
      'tag' :  'dom',
      'metrics': [
         {
            'title': 'IOPs',
            'metrics': ['proxyIops', 'proxyIopsRead', 'proxyIopsWrite',
                        'proxyIopsRWResync', 'anchorIops', 'anchorIopsRead',
                        'anchorIopsWrite', 'anchorIopsRWResync'],
            'unit': u"iops",
            'thresholds': [30000, 50000],
            'min': 0,
         },
         {
            'title': 'Throughput',
            'metrics': ['proxyThroughput', 'proxyTputRead', 'proxyTputWrite',
                        'proxyTputRWResync', 'anchorThroughput',
                        'anchorTputRead', 'anchorTputWrite', 'anchorTputRWResync'],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'Latency',
            'metrics': ['proxyLatencyAvg', 'proxyLatencyAvgRead',
                        'proxyLatencyAvgWrite', 'proxyLatencyAvgRWResync',
                        'anchorLatencyAvg', 'anchorLatencyAvgRead',
                        'anchorLatencyAvgWrite', 'anchorLatencyAvgRWResync'],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'Congestion',
            'metrics': ['proxyCongestion', 'proxyReadCongestion',
                        'proxyWriteCongestion', 'proxyRWResyncCongestion',
                        'anchorCongestion', 'anchorReadCongestion',
                        'anchorWriteCongestion', 'anchorRWResyncCongestion',
                        ],
            'unit': u"short",
            'min': 0,
            'max': 255,
         },
         {
            'title': 'IO Count',
            'metrics': ['proxyIoCount', 'proxyReadCount',
                        'proxyWriteCount', 'proxyRWResyncCount',
                        'anchorIoCount', 'anchorReadCount',
                        'anchorWriteCount', 'anchorRWResyncCount',
                        ],
            'unit': u"short",
            'min': 0,
         },
      ],
      'entityToShow':'dom-per-proxy-owner',
   },
   'nic-world-cpu' : {
      'title': 'Networking: Worlds',
      'repeat': False,
      'repeatByHost': True,
      'tag' :  'network',
      'metrics': get_world_metrics_definition(),
      'entityToShow':'nic-world-cpu',
   },
   'rdma-world-cpu' : {
      'title': 'RDMA: Worlds',
      'repeat': False,
      'repeatByHost': True,
      'metrics': get_world_metrics_definition(),
      'entityToShow':'rdma-world-cpu',
   },
   'rdma-net' : {
      'title': 'RDMA: Net Stats',
      'repeat': True,
      'metrics': [
         {
            'title': 'Packets/sec (average)',
            'metrics': [
               "rxPackets", "txPackets",
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Throughput',
            'metrics': [
               "rxThroughput", "txThroughput",
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Error Rate (per-mille)',
            'metrics': [
               "rxPacketsErrorRate", "txPacketsErrorRate",
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'PFC stats',
            'metrics': [
               'pri3SentPFCFrames', 'pri3ReceivedPFCFrames',
               'pri4SentPFCFrames', 'pri4ReceivedPFCFrames',
               'pri5SentPFCFrames', 'pri5ReceivedPFCFrames',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
      ],
      'entityToShow':'rdma-net',
   },
   'dom_diskgroup' : {
      'repeat': True,
      'title': 'DOM vSAN: Disk Groups',
      'tag' :  'dom_vsan1',
      'metrics': [
         {
            'title': 'IOPS',
            'metrics': [('iopsReadCompMgr', 'Read'),
                        ('iopsWriteCompMgr', 'Write'),
                        ('iopsUnmapCompMgr', 'Unmap'),
                        ('iopsRecoveryWriteCompMgr', 'Recovery Write'),
                        ('iopsRecoveryUnmapCompMgr', 'Recovery Unmap')],
            'unit': u"iops",
            'min': 0,
         },
         {
            'title': 'Bandwidth',
            'metrics': [('throughputReadCompMgr', 'Read'),
                        ('throughputWriteCompMgr', 'Write'),
                        ('throughputUnmapCompMgr', 'Unmap'),
                        ('throughputRecoveryWriteCompMgr', 'Recovery Write'),
                        ('throughputRecoveryUnmapCompMgr', 'Recovery Unmap')],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'Latency',
            'metrics': [('latencyReadCompMgr', 'Read'),
                        ('latencyWriteCompMgr', 'Write'),
                        ('latencyUnmapCompMgr', 'Unmap'),
                        ('latencyRecoveryWriteCompMgr', 'Recovery Write'),
                        ('latencyRecoveryUnmapCompMgr', 'Recovery Unmap')],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'OIO',
            'metrics': [('oioReadCompMgr', 'Read'),
                        ('oioWriteCompMgr', 'Write'),
                        ('oioUnmapCompMgr', 'Unmap'),
                        ('oioRecoveryWriteCompMgr', 'Recovery Write'),
                        ('latencyAvgRecUnmap', 'Recovery Unmap')],
            'unit': u"short",
            'min': 0,
         },
         {
            'title': 'IOPS Regulator',
            'metrics': [('regulatorIopsReadSched', 'Read'),
                        ('regulatorIopsWriteSched', 'Write')],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'LSOM Congestion',
            'metrics': [('componentCongestionReadSched', 'Read Component'),
                        ('componentCongestionWriteSched', 'Write Component'),
                        ('diskgroupCongestionReadSched', 'Read DiskGroup'),
                        ('diskgroupCongestionWriteSched', 'Write DiskGroup')],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Scheduler Queue Depth',
            'metrics': [('metadataQueueDepthReadSched', 'Read Metadata'),
                        ('metadataQueueDepthWriteSched', 'Write Metadata'),
                        ('namespaceQueueDepthReadSched', 'Read Namespace'),
                        ('namespaceQueueDepthWriteSched', 'Write Namespace'),
                        ('resyncQueueDepthReadSched', 'Read Resync'),
                        ('resyncQueueDepthWriteSched', 'Write Resync'),
                        ('vmdiskQueueDepthReadSched', 'Read VM Disk'),
                        ('vmdiskQueueDepthWriteSched', 'Write VM Disk')],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Backpressure Congestion',
            'metrics': [('metadataBackpressureCongestionReadSched', 'Read Metadata'),
                        ('metadataBackpressureCongestionWriteSched', 'Write Metadata'),
                        ('namespaceBackpressureCongestionReadSched', 'Read Namespace'),
                        ('namespaceBackpressureCongestionWriteSched', 'Write Namespace'),
                        ('resyncBackpressureCongestionReadSched', 'Read Resync'),
                        ('resyncBackpressureCongestionWriteSched', 'Write Resync'),
                        ('vmdiskBackpressureCongestionReadSched', 'Read VM Disk'),
                        ('vmdiskBackpressureCongestionWriteSched', 'Write VM Disk')],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Scheduler Cost Bandwidth',
            'metrics': [('metadataDispatchedCostReadSched', 'Read Metadata'),
                        ('metadataDispatchedCostWriteSched', 'Write Metadata'),
                        ('namespaceDispatchedCostReadSched', 'Read Namespace'),
                        ('namespaceDispatchedCostWriteSched', 'Write Namespace'),
                        ('resyncDispatchedCostReadSched', 'Read Resync'),
                        ('resyncDispatchedCostWriteSched', 'Write Resync'),
                        ('vmdiskDispatchedCostReadSched', 'Read VM Disk'),
                        ('vmdiskDispatchedCostWriteSched', 'Write VM Disk')],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Scheduler Bandwidth',
            'metrics': [('metadataThroughputReadSched', 'Read Metadata'),
                        ('metadataThroughputWriteSched', 'Write Metadata'),
                        ('namespaceThroughputReadSched', 'Read Namespace'),
                        ('namespaceThroughputWriteSched', 'Write Namespace'),
                        ('resyncThroughputReadSched', 'Read Resync'),
                        ('resyncThroughputWriteSched', 'Write Resync'),
                        ('vmdiskThroughputReadSched', 'Read VM Disk'),
                        ('vmdiskThroughputWriteSched', 'Write VM Disk')],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Delayed IO Percentage',
            'metrics': [
               ('iopsDelayPctSched', 'Delayed IO Percentage')
            ],
            'unit': u"percent",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Delayed IO Percentage', 'The percentage of IOs which go though vSAN internal queues')
            ]),
         },
         {
            'title': 'Delayed IO Average Latency',
            'metrics': [
               ('latencyDelaySched', 'Delayed IO Average Latency'),
               ('latencySchedQueueNS', 'Latency of Namespace Queue'),
               ('latencySchedQueueRec', 'Latency of Recovery Queue'),
               ('latencySchedQueueVM', 'Latency of VM Queue'),
               ('latencySchedQueueMeta', 'Latency of Meta Queue')
            ],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Delayed IO Average Latency', 'The average latency of total IOs which go though vSAN internal queues'),
               ('Latency of Namespace Queue', 'The Latency of the namespace IO queue in the vSAN internal scheduler'),
               ('Latency of Recovery Queue', 'The Latency of the recovery IO queue in the vSAN internal scheduler'),
               ('Latency of VM Queue', 'The Latency of the VM IO queue in the vSAN internal scheduler'),
               ('Latency of Meta Queue', 'The Latency of the meta IO queue in the vSAN internal scheduler'),
            ]),
         },
         {
            'title': 'Delayed IOPS',
            'metrics': [
               ('iopsSched', 'Total Delayed IOPS'),
               ('iopsSchedQueueNS', 'IOPS of Namespace Queue'),
               ('iopsSchedQueueRec', 'IOPS of Recovery Queue'),
               ('iopsSchedQueueVM', 'IOPS of VM Queue'),
               ('iopsSchedQueueMeta', 'IOPS of Meta Queue')
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Total Delayed IOPS', 'The IOPS of total IOs which go through vSAN internal queues'),
               ('IOPS of Namespace Queue', 'The IOPS of the namespace IO queue in the vSAN internal scheduler'),
               ('IOPS of Recovery Queue', 'The IOPS of the recovery IO queue in the vSAN internal scheduler'),
               ('IOPS of VM Queue', 'The IOPS of the VM IO queue in the vSAN internal scheduler'),
               ('IOPS of Meta Queue', 'The IOPS of the meta IO queue in the vSAN internal scheduler'),
            ]),
         },
         {
            'title': 'Delayed IO Throughput',
            'metrics': [
               ('throughputSched', 'Total Queue Throughput'),
               ('throughputSchedQueueNS', 'Throughput of Namespace Queue'),
               ('throughputSchedQueueRec', 'Throughput of Recovery Queue'),
               ('throughputSchedQueueVM', 'Throughput of VM Queue'),
               ('throughputSchedQueueMeta', 'Throughput of Meta Queue')
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Total Queue Throughput', 'The throughput of total delayed IO in the vSAN internal scheduler'),
               ('Throughput of Namespace Queue', 'The throughput of the namespace IO queue in the vSAN internal scheduler'),
               ('Throughput of Recovery Queue', 'The throughput of the recovery IO queue in the vSAN internal scheduler'),
               ('Throughput of VM Queue', 'The throughput of the VM IO queue in the vSAN internal scheduler'),
               ('Throughput of Meta Queue', 'The throughput of the meta IO queue in the vSAN internal scheduler'),
            ]),
         },
         {
            'title': 'Times Over Window Limit',
            'metrics': [
               ('timesOverWindowLimitRead', 'Read'),
               ('timesOverWindowLimitWrite', 'Write'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
      ],
      'entityToShow':'cache-disk',
   },
   'cluster-resync' : {
      'title': 'DOM vSAN: Cluster Resync',
      'tag' :  'dom_vsan1',
      'repeat': True,
      'metrics': [
         {
            'title': 'Resync IOPS',
            'metrics': [('iopsResyncReadPolicy', 'Policy Change Read'),
                        ('iopsResyncWritePolicy', 'Policy Change Write'),
                        ('iopsResyncReadDecom', 'Evacuation Read'),
                        ('iopsResyncWriteDecom', 'Evacuation Write'),
                        ('iopsResyncReadRebalance', 'Rebalance Read'),
                        ('iopsResyncWriteRebalance', 'Rebalance Write'),
                        ('iopsResyncReadFixComp', 'Repair Read'),
                        ('iopsResyncWriteFixComp', 'Repair Write')],
            'unit': u"iops",
            'min': 0,
         },
         {
            'title': 'Resync Throughput',
            'metrics': [('tputResyncReadPolicy', 'Policy Change Read'),
                        ('tputResyncWritePolicy', 'Policy Change Write'),
                        ('tputResyncReadDecom', 'Evacuation Read'),
                        ('tputResyncWriteDecom', 'Evacuation Write'),
                        ('tputResyncReadRebalance', 'Rebalance Read'),
                        ('tputResyncWriteRebalance', 'Rebalance Write'),
                        ('tputResyncReadFixComp', 'Repair Read'),
                        ('tputResyncWriteFixComp', 'Repair Write')],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'Resync Latency',
            'metrics': [('latResyncReadPolicy', 'Policy Change Read'),
                        ('latResyncWritePolicy', 'Policy Change Write'),
                        ('latResyncReadDecom', 'Evacuation Read'),
                        ('latResyncWriteDecom', 'Evacuation Write'),
                        ('latResyncReadRebalance', 'Rebalance Read'),
                        ('latResyncWriteRebalance', 'Rebalance Write'),
                        ('latResyncReadFixComp', 'Repair Read'),
                        ('latResyncWriteFixComp', 'Repair Write')],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'Resync IO Count',
            'metrics': [('readCountPolicy', 'Policy Change Read Count'),
                        ('recWriteCountPolicy', 'Policy Change Write Count'),
                        ('readCountDecom', 'Evacuation Read Count'),
                        ('recWriteCountDecom', 'Evacuation Write Count'),
                        ('readCountRebalance', 'Rebalance Read Count'),
                        ('recWriteCountRebalance', 'Rebalance Write Count'),
                        ('readCountFixComp', 'Repair Read Count'),
                        ('recWriteCountFixComp', 'Repair Write Count')],
            'unit': u"short",
            'min': 0,
         },
      ],
      'entityToShow':'cluster-resync',
   },
   'virtual-disk' : {
      'title': 'VM: Virtual Disk (VMDK Dump)',
      'repeat': True,
      'metrics': [
         {
            'title': 'IOPS Limit',
            'metrics': [('iopsLimit', 'IOPS Limit'),
                        ('NIOPS', 'Normalized IOPS'),
                        ('NIOPSDelayed', 'Normalized IOPS Delayed'),
                        ],
            'unit': u"iops",
            'min': 0,
         },
      ],
      'entityToShow':'virtual-disk',
   },
   'vscsi' : {
      'title': 'VM: Virtual SCSI (VMDK Dump)',
      'repeat': True,
      'metrics': [
         {
            'title': 'IOPS',
            'metrics': [('iopsRead', 'IOPS Read'),
                        ('iopsWrite', 'IOPS Write'),
                        ],
            'unit': u"iops",
            'min': 0,
         },
         {
            'title': 'Throughput',
            'metrics': [('throughputRead', 'Throughput Read'),
                        ('throughputWrite', 'Throughput Write'),
                        ],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'Latency',
            'metrics': [('latencyRead', 'Latency Read'),
                        ('latencyWrite', 'Latency Write'),
                        ],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'Count',
            'metrics': [('readCount', 'Read Count'),
                        ('writeCount', 'Write Count'),
                        ],
            'unit': u"short",
            'min': 0,
         },
      ],
      'entityToShow':'vscsi',
   },
   'vsan-file-service' : {
      'title': 'VDFS: File service',
      'repeat': True,
      'metrics': [
         {
            'title': 'IOPS',
            'metrics': [
               "readOpTotal", "writeOpTotal",
            ],
            'unit': u"iops",
            'min': 0,
         },
         {
            'title': 'Throughput',
            'metrics': [
               "readRequested", "readTransferred", "writeRequested", "writeTransferred",
            ],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'Latency',
            'metrics': [
               "readLatency", "writeLatency",
            ],
            'unit': u"µs",
            'min': 0,
         },
      ],
      'entityToShow':'vsan-file-service',
   },
   'zdom-io' : {
      'title': 'zDOM: IO Stats',
      'repeat': True,
      'tag' :  'zdom',
      'metrics': [
         {
            'title': 'IOPS',
            'metrics': [
               "iops", "iopsLookup", "iopsMultiRead", "iopsBankWrite",
               "iopsDurableLog", "iopsBankFlushFSW", "iopsBankBtree", "iopsBankReadWait",
               "iopsSnapCreate", "iopsSnapLookup", "iopsSnapDelete", "iopsBankOverlap",
            ],
            'unit': u"iops",
            'min': 0,
         },
         {
            'title': 'Throughput',
            'metrics': [
               "tputLookup", "tputMultiRead", "tputBankWrite",
               "tputDurableLog", "tputBankFlushFSW", "tputBankBtree",
               "tputSnapCreate", "tputSnapLookup", "tputSnapDelete",
               "tputBankOverlap",
            ],
            'unit': u"Bps",
            'min': 0,
         },
         {
            'title': 'Latency (Average)',
            'metrics': [
               'latencyAvgLookup', 'latencyAvgMultiRead', 'latencyAvgBankWrite',
               'latencyAvgDurableLog', 'latencyAvgBankFlushFSW', 'latencyAvgBankBtree',
               'latencyAvgSnapCreate', 'latencyAvgSnapLookup', 'latencyAvgSnapDelete',
               'totalBankLat', 'bankTxnCreateLat',
            ],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'Latency (Max)',
            'metrics': [
               'latencyMaxLookup', 'latencyMaxMultiRead', 'latencyMaxBankWrite',
               'latencyMaxDurableLog', 'latencyMaxBankFlushFSW', 'latencyMaxBankBtree',
               'latencyMaxSnapCreate', 'latencyMaxSnapLookup', 'latencyMaxSnapDelete',
            ],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'Latency (ListWait)',
            'metrics': [
               'latencyAvgLookupListWait', 'latencyAvgBankWriteListWait',
               'latencyAvgDurableLogListWait', 'latencyAvgBankFlushFSWListWait',
            ],
            'unit': u"µs",
            'min': 0,
         },
         {
            'title': 'Latency (Standard deviation)',
            'metrics': [
               'latencyStddevLookup', 'latencyStddevMultiRead', 'latencyStddevBankWrite',
               'latencyStddevDurableLog', 'latencyStddevBankFlushFSW', 'latencyStddevBankBtree',
               'latencyStddevSnapCreate', 'latencyStddevSnapLookup', 'latencyStddevSnapDelete',
            ],
            'unit': u"µs",
            'min': 0,
         },
      ],
      'entityToShow':'zdom-io',
   },
   'zdom-overview' : get_zdom_overview(),
   'zdom-snapshot' : get_zdom_snapshot(),
   'zdom-llp' : get_zdom_llp(),
   'zdom-vtx-overview' : {
      'title': 'zDOM: VTX Overview',
      'repeat': True,
      'tag':  'zdom',
      'metrics': get_vsan_zdom_vtx_overview_metrics_definition(),
      'entityToShow': 'zdom-vtx',
   },
   'zdom-vtx-block' : {
      'title': 'zDOM: VTX Overall Block Cache',
      'repeat': True,
      'tag':  'zdom',
      'metrics': get_vsan_zdom_vtx_blockcache_metrics_definition(),
      'entityToShow': 'zdom-vtx',
   },
   'zdom-vtx-prefetch' : {
      'title': 'zDOM: VTX Prefetch',
      'repeat': True,
      'tag':  'zdom',
      'metrics': get_vsan_zdom_vtx_prefetch_metrics_definition(),
      'entityToShow': 'zdom-vtx',
   },
   'zdom-vtx-bank-flush' : {
      'title': 'zDOM: VTX Bank Flush',
      'repeat': True,
      'tag':  'zdom',
      'metrics': get_vsan_zdom_vtx_bank_flush_metrics_definition(),
      'entityToShow': 'zdom-vtx',
   },
   'zdom-vtx-check-pointer' : {
      'title': 'zDOM: VTX Check Pointer',
      'repeat': True,
      'tag':  'zdom',
      'metrics': get_vsan_zdom_vtx_check_pointer_metrics_definition(),
      'entityToShow': 'zdom-vtx',
   },
   'zdom-vtx-unmap' : {
      'title': 'zDOM: VTX Unmap',
      'repeat': True,
      'tag':  'zdom',
      'metrics': get_vsan_zdom_vtx_unmap_metrics_definition(),
      'entityToShow': 'zdom-vtx',
   },
   'zdom-vtx-seg-cleaning' : {
      'title': 'zDOM: VTX Segment Cleaning',
      'repeat': True,
      'tag':  'zdom',
      'metrics': get_vsan_zdom_vtx_seg_cleaning_metrics_definition(),
      'entityToShow': 'zdom-vtx',
   },
   'zdom-seg-cleaning': get_zdom_seg_cleaning(),
   'zdom-seg-cleaning_bucket': get_zdom_seg_cleaning_bucket(),
   'vsan-zdom-gsc-capacity': get_vsan_zdom_gsc_capacity(),
   'vsan-zdom-top': get_vsan_zdom_top(),
   'zdom-world-cpu' : {
      'title': 'zDOM: Worlds',
      'repeat': False,
      'repeatByHost': True,
      'tag' :  'zdom',
      'metrics': get_world_metrics_definition(),
      'entityToShow':'zdom-world-cpu',
   },
   'splinterdb': {
      'title': 'LSOM2: SplinterDB Stats',
      'tag' :  'lsom2',
      'repeat': True,
      'entityToShow': 'splinterdb',
      'metrics': [
         {
            'title': 'Overall',
            'metrics': [
               ('height', 'Height'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
            'description' : fmt_desc('Developer', [
               ('Height', 'Splinter Tree Height'),
            ]),
         },
         {
            'title': 'Insert IOps',
            'metrics': [
               ('insertions', 'Insert'),
               ('updates', 'Update'),
               ('deletions', 'Delete'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
            'description' : fmt_desc('Developer', [
               ('Insert', 'Insert IOps'),
               ('Update', 'Update IOps'),
               ('Delete', 'Delete IOps'),
            ]),
         },
         {
            'title': 'Insert/Update/Delete Latency',
            'metrics': [
               ('insertLatencyAvg', 'Avg Insert'),
               ('updateLatencyAvg', 'Avg Update'),
               ('deleteLatencyAvg', 'Avg Delete'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description' : fmt_desc('Developer', [
               ('Avg Insert', 'Average Insert Latency(ns)'),
               ('Avg Update', 'Average Update Latency(ns)'),
               ('Avg Delete', 'Average Delete Latency(ns)'),
            ]),
         },
         {
            'title': 'Insert/Update/Delete (MAX)',
            'metrics': [
               ('insertLatencyMax', 'Max Insert'),
               ('updateLatencyMax', 'Max Update'),
               ('deleteLatencyMax', 'Max Delete'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Max Insert', 'Maximum Insert Latency(ns)'),
               ('Max Update', 'Maximum Update Latency(ns)'),
               ('Max Delete', 'Maximum Delete Latency(ns)'),
            ]),
         },
         {
            'title': 'Lookup Ops',
            'metrics': [
               ('posLookups', 'Positive'),
               ('negLookups', 'Negative'),
               ('filterLookups', 'Filter'),
               ('branchLookups', 'Branch'),
               ('memtableLookups', 'Memtable'),
               ('asyncLookupCacheMissAvg', 'Async LU Cache Miss Avg per LU'),
               ('filterFalsePositives', 'Filter False Positives'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
            'description' : fmt_desc('Developer', [
               ('Positive', 'Positive Lookup Ops'),
               ('Negative', 'Negative Lookup Ops'),
               ('Filter', 'Filter Lookup Ops'),
               ('Branch', 'Branch Lookup Ops'),
               ('Memtable', 'Memtable Lookup Ops'),
               ('Filter False Positives', 'Filter False Positives'),
               ('Async LU Cache Miss Max per LU', 'Async Lookup Cache Miss Max per Lookup'),
            ]),
         },
         {
            'title': 'Lookup Ops (MAX)',
            'metrics': [
               ('asyncLookupCacheMissMax', 'Async LU Cache Miss Max per LU'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Async LU Cache Miss Avg per LU', 'Async Lookup Cache Miss Avg per Lookup'),
            ]),
         },
         {
            'title': 'Lookup Latency',
            'metrics': [
               ('lookupLatencyAvg', 'Avg Lookup'),
               ('lookupRangeLatencyAvg', 'Avg Lookup Range Delete'),
               ('asyncLookupInvocationLatencyAvg', 'Avg Async Lookup Invo'),
               ('rangeQueryLatencyAvg', 'Avg Lookup Range'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description' : fmt_desc('Developer', [
               ('Avg Lookup', 'Average Lookup Latency(ns)'),
               ('Avg Lookup Range Delete', 'Average Lookup Range Delete Latency(ns)'),
               ('Avg Async Lookup Invo', 'Average Async Lookup Invocation Time(ns)'),
               ('Avg Lookup Range', 'Average Lookup Range Latency(ns) per tuple'),
            ]),
         },
         {
            'title': 'Lookup Latency (MAX)',
            'metrics': [
               ('lookupLatencyMax', 'Max Lookup'),
               ('lookupRangeLatencyMax', 'Max Lookup Range Delete'),
               ('asyncLookupInvocationLatencyMax', 'Max Async Lookup Invo'),
               ('rangeQueryLatencyMax', 'Max Lookup Range'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Max Lookup', 'Maximum Lookup Latency(ns)'),
               ('Max Lookup Range Delete', 'Maximum Lookup Range Delete Latency(ns)'),
               ('Max Async Lookup Invo', 'Maximum Async Lookup Invocation Time(ns)'),
               ('Max Lookup Range', 'Maximum Lookup Range Latency(ns) per tuple'),
            ]),
         },
         {
            'title': 'Range Delete Latency',
            'metrics': [
               ('rangeDeleteLatencyAvg', 'Avg Range Delete'),
               ('rangeDeleteClobberLatencyAvg', 'Avg Range Delete Clobber'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description' : fmt_desc('Developer', [
               ('Avg Range Delete', 'Average Range Delete Latency(ns)'),
               ('Avg Range Delete Clobber', 'Average Range Delete Clobber Latency(ns)'),
            ]),
         },
         {
            'title': 'Range Delete Latency (MAX)',
            'metrics': [
               ('rangeDeleteLatencyMax', 'Max Range Delete'),
               ('rangeDeleteClobberLatencyMax', 'Max Range Delete Clobber'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Max Range Delete', 'Maximum Range Delete Latency(ns)'),
               ('Max Range Delete Clobber', 'Maximum Range Delete Clobber Latency(ns)'),
            ]),
         },
         {
            'title': 'Cache Latency',
            'metrics': [
               ('cacheMissTimeAvgBranch', 'Avg Branch'),
               ('cacheMissTimeAvgBranchRange', 'Avg Branch Range'),
               ('cacheMissTimeAvgFilter', 'Avg Filter'),
               ('cacheMissTimeAvgMisc', 'Avg Misc'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description' : fmt_desc('Developer', [
               ('Avg Branch', 'Average Branch Cache Miss Latency(ns)'),
               ('Avg Branch Range', 'Average Branch Range Cache Miss Latency(ns)'),
               ('Avg Filter', 'Average Filter Cache Miss Latency(ns)'),
               ('Avg Misc', 'Average Misc Cache Miss Latency(ns)'),
            ]),
         },
         {
            'title': 'Cache Latency (MAX)',
            'metrics': [
               ('cacheMissTimeMaxBranch', 'Max Branch'),
               ('cacheMissTimeMaxBranchRange', 'Max Branch Range'),
               ('cacheMissTimeMaxFilter', 'Max Filter'),
               ('cacheMissTimeMaxMisc', 'Max Misc'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Max Branch', 'Maximum Branch Cache Miss Latency(ns)'),
               ('Max Branch Range', 'Maximum Branch Range Cache Miss Latency(ns)'),
               ('Max Filter', 'Maximum Filter Cache Miss Latency(ns)'),
               ('Max Misc', 'Maximum Misc Cache Miss Latency(ns)'),
            ]),
         },
         {
            'title': 'Cache Hit Rate',
            'metrics': [
               ('cacheHRBranch', 'Branch'),
               ('cacheHRBranchRange', 'Branch Range'),
               ('cacheHRFilter', 'Filter'),
               ('cacheHRMisc', 'Misc'),
            ],
            'unit': u"percent",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Branch', 'Branch Cache Hit Rate'),
               ('Branch Range', 'Branch Range Cache Hit Rate'),
               ('Filter', 'Filter Cache Hit Rate'),
               ('Misc', 'Misc Cache Hit Rate'),
            ]),
         },
         {
            'title': 'Cache',
            'metrics': [
               ('cacheHitsTrunk', 'Trunk Hits'),
               ('cacheHitsBranch', 'Branch Hits'),
               ('cacheMissesBranch', 'Branch Misses'),
               ('cacheHitsBranchRange', 'Branch Range Hits'),
               ('cacheMissesBranchRange', 'Branch Range Misses'),
               ('cacheHitsMemtable', 'Memtable Hits'),
               ('cacheHitsMemtableRange', 'Memtable Range Hits'),
               ('cacheHitsFilter', 'Filter Hits'),
               ('cacheMissesFilter', 'Filter Misses'),
               ('cacheHitsMisc', 'Misc Hits'),
               ('cacheMissesMisc', 'Misc Misses'),
               ('cacheHitsBranchMeta', 'Branch Meta Hits'),
               ('cacheHitsBranchRangeMeta', 'Branch Range Meta Hits'),
               ('cacheHitsFilterMeta', 'Filter Meta Hits'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Trunk Hits', 'Trunk Cache Hits'),
               ('Branch Hits', 'Branch Cache Hits'),
               ('Branch Misses', 'Branch Cache Misses'),
               ('Branch Range Hits', 'Branch Range Cache Hits'),
               ('Branch Range Misses', 'Branch Range Cache Misses'),
               ('Memtable Hits', 'Memtable Cache Hits'),
               ('Memtable Range Hits', 'Memtable Range Cache Hits'),
               ('Filter Hits', 'Filter Cache Hits'),
               ('Filter Misses', 'Filter Cache Misses'),
               ('Misc Hits', 'Misc Cache Hits'),
               ('Misc Misses', 'Misc Cache Misses'),
               ('Branch Meta Hits', 'Branch Meta Cache Hits'),
               ('Branch Range Meta Hits', 'Branch Range Meta Cache Hits'),
               ('Filter Meta Hits', 'Filter Meta Cache Hits'),
            ]),
         },
         {
            'title': 'Footprint',
            'metrics': [
               ('footprintTrunk', 'Trunk'),
               ('footprintBranch', 'Branch'),
               ('footprintBranchRange', 'Branch Range'),
               ('footprintMemtable', 'Memtable'),
               ('footprintMemtableRange', 'Memtable Range'),
               ('footprintFilter', 'Filter'),
               ('footprintBranchMeta', 'Branch Meta'),
               ('footprintBranchRangeMeta', 'Branch Range Meta'),
               ('footprintFilterMeta', 'Filter Meta'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Trunk', 'Trunk Footprint(pages)'),
               ('Branch', 'Branch Footprint(pages)'),
               ('Branch Range', 'Branch Range Footprint(pages)'),
               ('Memtable', 'Memtable Footprint(pages)'),
               ('Memtable Range', 'Memtable Range Footprint(pages)'),
               ('Filter', 'Filter Footprint(pages)'),
               ('Branch Meta', 'Branch Meta Footprint(pages)'),
               ('Branch Range Meta', 'Branch Range Meta Footprint(pages)'),
               ('Filter Meta', 'Filter Meta Footprint(pages)'),
            ]),
         },
         {
            'title': 'Flush',
            'metrics': [
               ('fullFlushes', 'Full'),
               ('countFlushes', 'Count'),
               ('memtableFlushes', 'Memtable'),
               ('rootFullFlushes', 'Root Full'),
               ('rootCountFlushes', 'Root Count'),
               ('failedFlushes', 'Failed'),
               ('memtableFailedFlushes', 'Memtable Failed'),
               ('rootFailedFlushes', 'Root Failed'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Full', 'Full Flushes'),
               ('Count', 'Count Flushes'),
               ('Memtable', 'Memtable Flushes'),
               ('Root Full', 'Root Full Flushes'),
               ('Root Count', 'Root Count Flushes'),
               ('Failed', 'Failed Flushes'),
               ('Memtable Failed', 'Memtable Failed Flushes'),
               ('Root Failed', 'Root Failed Flushes'),
            ]),
         },
         {
            'title': 'Compaction',
            'metrics': [
               ('compactions', 'Compactions'),
               ('rootCompactions', 'Root Compactions'),
               ('compactionAvgTuples', 'Avg Compaction Tuples'),
               ('rootCompactionAvgTuples', 'Avg Root Compaction Tuples'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Compactions', 'Number of Compactions'),
               ('Root Compactions', 'Number of Root Compactions'),
               ('Avg Compaction Tuples', 'Average Tuples Per Compaction'),
               ('Avg Root Compaction Tuples', 'Average Tuples Per Root Compaction'),
            ]),
         },
         {
            'title': 'Split',
            'metrics': [
               ('indexSplits', 'Index Splits'),
               ('leafSplits', 'Leaf Splits'),
               ('discardedDeletes', 'Discarded Deletes'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Index Splits', 'Number of Index Splits'),
               ('Leaf Splits', 'Number of Leaf Splits'),
               ('Discarded Deletes', 'Number of Completed Deletes'),
            ]),
         },
         {
            'title': 'Filter',
            'metrics': [
               ('filtersBuilt', 'Filters Built'),
               ('rootFiltersBuilt', 'Root Filters Built'),
               ('filterAvgTuples', 'Avg Filter Tuples'),
               ('rootFilterAvgTuples', 'Avg Root Filter Tuples'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Filters Builts', 'Number of Filters Built'),
               ('Root Filters Builts', 'Number of Root Filters Built'),
               ('Avg Filter Tuples', 'Average Tuples Per Filter'),
               ('Avg Root Filter Tuples', 'Average Tuples Per Root Filter'),
            ]),
         },
         {
            'title': 'Task',
            'metrics': [
               ('totalTasks', 'Total'),
               ('currentOutstandingTasks', 'Current Outstanding'),
               ('memtablePendingTasks', 'Memtable Pending'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Total', 'Total Tasks'),
               ('Current Outstanding', 'Current Outstanding Tasks'),
               ('Memtable Pending', 'Memtable Pending Tasks'),
            ]),
         },
         {
            'title': 'Task (MAX)',
            'metrics': [
               ('maxOutstandingTasks', 'Max Outstanding'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Max Outstanding', 'Maximum Outstanding Tasks'),
            ]),
         },
         {
            'title': 'Task Latency',
            'metrics': [
               ('totalTaskLatencyNs', 'Total'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Total', 'Total Tasks Latency(ns)'),
            ]),
         },
         {
            'title': 'Task Latency (MAX)',
            'metrics': [
               ('taskRuntimeMaxNs', 'Max Runtime'),
               ('maxTaskLatencyNs', 'Max Latency'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Max Runtime', 'Maximum Task Runtime(ns)'),
               ('Max Latency', 'Maximum Task Latency(ns)'),
            ]),
         },
         {
            'title': 'Snowplough Stats',
            'metrics': [
               ('snowpTotalScans', 'TotalScans'),
               ('snowpTotalRootLeaf', 'Root Leaf Traversals'),
               ('snowpEmptyFlushes', 'Empty Flushes'),
               ('snowpNoRoomFlushes', 'No Room Flushes'),
               ('snowpClaimFailures', 'Claim Failures'),
               ('snowpLockTimeMsec', 'Lock Time(msec)'),
               ('snowpFlushesAttempted', 'Flushes Attempted'),
               ('snowpActualFlushes', 'Flushes actually done'),
               ('snowpLeafSplits', 'Leaf splits'),
               ('snowpCurrentTasks', 'Current Outstanding Tasks'),
               ('snowpTotalTasks', 'Total Tasks Run'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('TotalScans', 'Number of scans of the entire tree'),
               ('Root Leaf Traversals', 'Total number of root to leaf traversals'),
               ('Empty Flushes', 'Number of times parent had nothing to flush'),
               ('No Room Flushes', 'Number of times child didnt have room'),
               ('Claim Failures', 'Number of times we failed to get a claim'),
               ('Lock Time(msec)', 'Total time(msec) that nodes were locked'),
               ('Flushes Attempted', 'Number of flushes attempted'),
               ('Flushes actually done', 'Number of flushes actually triggered'),
               ('Leaf splits', 'Number of leaf splits triggered by snowplough'),
               ('Current Outstanding Tasks', 'Current outstanding tasks in snowplough'),
               ('Total Tasks Run', 'Total number of snowplough tasks run'),
            ]),
         },
         {
            'title': 'Checkpoint Latency',
            'metrics': [
               ('checkptCacheFlushLatencyAvg', 'Average Cache Flush Time'),
               ('checkptCacheCopyLatencyAvg', 'Average Cache Copy Time'),
               ('checkptWriteLatencyAvg', 'Average Write Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'description': fmt_desc('Developer', [
               ('Average Cache Flush Time', 'The average time it takes for checkpoint to perform a cache flush'),
               ('Average Cache Copy Time', 'The average time it takes for checkpoint to perform a cache copy'),
               ('Average Write Time', 'The average time it takes for checkpoint to perform a write to disk'),
            ])
         },
         {
            'title': 'Checkpoint Latency (MAX)',
            'metrics': [
               ('checkptCacheFlushLatencyMax', 'Maximum Cache Flush Time'),
               ('checkptCacheCopyLatencyMax', 'Maximum Cache Copy Time'),
               ('checkptWriteLatencyMax', 'Maximum Write Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'description': fmt_desc('Developer', [
               ('Maximum Cache Flush Time', 'The maximum time it takes for checkpoint to perform a cache flush'),
               ('Maximum Cache Copy Time', 'The maximum time it takes for checkpoint to perform a cache copy'),
               ('Maximum Write Time', 'The maximum time it takes for checkpoint to perform a write to disk'),
            ])
         },
         {
            'title': 'Premini Page Usage',
            'metrics': [
               ('preminiAllocatedTrunkPages', 'Trunk'),
               ('preminiAllocatedMemtablePages', 'Memtable'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Trunk', 'Trunk(pages)'),
               ('Memtable', 'Memtable(pages)'),
            ]),
         },
         {
            'title': 'Congestion Stats',
            'metrics': [('taskCongestion', 'Task congestion'),
                        ('spaceCongestion', 'Space congestion'),
                        ('trunkCongestion', 'Trunk congestion')],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
            'description': fmt_desc('Developer', [
               ('Congestion based on task queue length', 'Congestion based on disk space usage'),
               ('Congestion based on trunk size', ''),
            ])
         },
      ],
   },
   'lsom2-stats' : {
      'title': 'LSOM2: Stats',
      'tag' :  'lsom2',
      'repeat': True,
      'entityToShow': 'lsom2-io-stats',
      'metrics': [
         {
            'title': 'LSOM2 IOPS',
            'metrics': [
               ('iopsRead', 'Read IOPS'),
               ('iopsWrite', 'Write IOPS'),
               ('iopsUnmap', 'Unmap IOPS'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Read IOPS', 'The number of read operations per second'),
               ('Write IOPS', 'The number of write operations per second'),
               ('Unmap IOPS', 'The number of Unmap operations per second'),
            ])
         },
         {
            'title': 'LSOM2 Read/Write Throughput',
            'metrics': [
               ('tputRead', 'Read Throughput'),
               ('tputReadDisk', 'Disk Read Throughput'),
               ('tputWrite', 'Write Throughput'),
               ('tputUnmap', 'Unmap Throughput'),
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Read Throughput', 'Total bytes read. Includes all blocks, even if the block has not been written to.'),
               ('Disk Read Throughput', 'Total bytes read from disk. If a block has not been written to, then it will not be included.'),
               ('Write Throughput', 'Bytes written per second'),
               ('Unmap Throughput', 'Bytes Unmap per second'),
            ])
         },
         {
            'title': 'LSOM2 Read/Write Latency',
            'metrics': [
               ('avgLatRead', 'Average Read Time'),
               ('avgLatWrite', 'Average Write Time'),
               ('avgLatUnmap', 'Average Unmap Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Average Read Time', 'Average time it takes to perform a single read'),
               ('Average Write Time', 'Average time it takes to perform a single write'),
               ('Average Unmap Time', 'Average time it takes to perform a single Unmap'),
            ])
         },
         {
            'title': 'LSOM2 Read/Write Latency (MAX)',
            'metrics': [
               ('maxReadTime', 'Maximum Read Time'),
               ('maxWriteTime', 'Maximum Write Time'),
               ('maxUnmapTime', 'Maximum Unmap Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Maximum Read Time', 'The maximum time it takes to perform a single read'),
               ('Maximum Write Time', 'The maximum time it takes to perform a single write'),
               ('Maximum Unmap Time', 'The maximum time it takes to perform a single Unmap'),
            ])
         },
         {
            'title': 'LSOM2 Read/Write Latency (MIN)',
            'metrics': [
               ('minReadTime', 'Minimum Read Time'),
               ('minWriteTime', 'Minimum Write Time'),
               ('minUnmapTime', 'Minimum Unmap Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Minimum Read Time', 'The minimum time it takes to perform a single read'),
               ('Minimum Write Time', 'The minimum time it takes to perform a single write'),
               ('Minimum Unmap Time', 'The minimum time it takes to perform a single Unmap'),
            ])
         },
         {
            'title': "Allocator API Latency",
            'metrics': [
               ('avgAllocBlockTime', 'Alloc API latency'),
               ('avgReserveBlockTime', 'Reserve API latency'),
               ('avgFinalizeBlockTime', 'Finalize API latency'),
               ('avgFreeTime', 'Free block API latency'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Alloc Block Latency', 'Average time to call BA_AllocBlocks'),
               ('Reserve Block Latency', 'Average time to call BA_ReserveBlocks'),
               ('Finalize Block Latency', 'Average time to call BA_FinalizeBlocks'),
               ('Free Block Latency', 'Average time to call BAMarkBlockAsFreed')
            ])
         },
         {
            'title': "Allocator Checkpoint Latency",
            'metrics': [
               ('cpAvgMergeBitmapsTime', 'Avg Merge Bitmap Time'),
               ('cpAvgProcessFreeListTime', 'Avg Process Free Lists Time'),
               ('cpAvgFlushPagesTime', 'Avg Flush Pages Time'),
               ('cpAvgCleanupTime', 'Avg Cleanup Time'),
               ('cpAvgCheckpointTime', 'Avg Checkpoint Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Avg Merge Bitmap Time', 'Average time to merge alloc/resv bitmaps'),
               ('Avg Process Free Lists Time', 'Average time to process free lists'),
               ('Avg Flush Pages Time', 'Average time to flush bitmap pages'),
               ('Avg Cleanup Time', 'Average time to run cleanup stage'),
               ('Avg Checkpoint Time', 'Average time to run full checkpoint'),
            ])
         },
         {
            'title': "Allocator Checkpoint Latency (MAX)",
            'metrics': [
               ('cpMaxMergeBitmapsTime', 'Max Merge Bitmap Time'),
               ('cpMaxProcessFreeListTime', 'Max Process Free Lists Time'),
               ('cpMaxFlushPagesTime', 'Max Flush Pages Time'),
               ('cpMaxCleanupTime', 'Max Cleanup Time'),
               ('cpMaxCheckpointTime', 'Max Checkpoint Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Max Merge Bitmap Time', 'Maximum time to merge alloc/resv bitmaps'),
               ('Max Process Free Lists Time', 'Maximum time to process free lists'),
               ('Max Flush Pages Time', 'Maximum time to flush bitmap pages'),
               ('Max Cleanup Time', 'Maximum time to run cleanup stage'),
               ('Max Checkpoint Time', 'Maximum time to run full checkpoint'),
            ])
         },
         {
            'title': "Allocator Checkpoint Latency (MIN)",
            'metrics': [
               ('cpMinMergeBitmapsTime', 'Min Merge Bitmap Time'),
               ('cpMinProcessFreeListTime', 'Min Process Free Lists Time'),
               ('cpMinFlushPagesTime', 'Min Flush Pages Time'),
               ('cpMinCleanupTime', 'Min Cleanup Time'),
               ('cpMinCheckpointTime', 'Min Checkpoint Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Min Merge Bitmap Time', 'Minimum time to merge alloc/resv bitmaps'),
               ('Min Process Free Lists Time', 'Minimum time to process free lists'),
               ('Min Flush Pages Time', 'Minimum time to flush bitmap pages'),
               ('Min Cleanup Time', 'Minimum time to run cleanup stage'),
               ('Min Checkpoint Time', 'Minimum time to run full checkpoint'),
            ])
         },
         {
            'title': "Allocator Block Throughput",
            'metrics': [
               ('blksAllocdTput', 'Alloc Block Throughput'),
               ('blksReservedTput', 'Reserve Block Throughput'),
               ('blksFinalizedTput', 'Finalize Block Throughput'),
               ('blksFreedTput', 'Free Block Throughput')
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Alloc Block Throughput', 'Throughput of blocks allocated with BA_AllocBlocks'),
               ('Reserve Block Throughput', 'Throughput of blocks reserve with BA_ReserveBlocks'),
               ('Finalize Block Throughput', 'Throughput of blocks finalized with BA_FinalizeBlocks'),
               ('Free Block Throughput', 'Throughput of blocks freed with MarkBlockAsFreed')
            ])
         },
         {
            'title': 'Allocator API Throughput',
            'metrics': [
               ('allocBlockApiTput',      'Alloc Block API Throughput'),
               ('reserveBlockApiTput',    'Reserve Block API Throughput'),
               ('finalizeBlockApiTput',   'Finalize Block API Throughput'),
               ('freeApiTput',            'Free API Throughput'),
               ('addToFreeListApiTput',   'Add To FreeList API Throughput'),
               ('processFreeListApiTput', 'Process FreeList API Throughput')
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Alloc Block API Throughput',      'Throughput of BA_AllocBlocks API'),
               ('Reserve Block API Throughput',    'Throughput of BA_ReserveBlocks API'),
               ('Finalize Block API Throughput',   'Throughput of BA_FinalizeBlocks API'),
               ('Free API Throughput',             'Throughput of BAMarkBlockAsFreed API'),
               ('Add To FreeList API Throughput',  'Throughput of BA_AddToFreeList'),
               ('Process FreeList API Throughput', 'Throughput of BA_ProcessFreeList')
            ])
         },
         {
            'title': 'Allocator Reserve Blocks Latency',
            'metrics': [
               ('avgReserveBlockTime', 'Avg Reserve Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Avg Reserve Time', 'Average time to reserve a block'),
            ])
         },
         {
            'title': 'Allocator Reserve Blocks Latency (MAX)',
            'metrics': [
               ('maxReserveBlockTime', 'Max Reserve Time')
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Max Reserve Time', 'Maximum time to reserve a block')
            ])
         },
         {
            'title': 'Allocator Reserve Blocks Latency (MIN)',
            'metrics': [
               ('minReserveBlockTime', 'Min Reserve Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Min Reserve Time', 'Minimum time to reserve a block'),
            ])
         },
         {
            'title': 'Allocator Process Free List Latency',
            'metrics': [
               ('avgProcessFreeListTime', 'Avg ProcessFreeList Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Avg ProcessFreeList Time', 'Average time to process a world\'s free list'),
            ])
         },
         {
            'title': 'Allocator Process Free List Latency (MAX)',
            'metrics': [
               ('maxProcessFreeListTime', 'Max ProcessFreeList Time')
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Max ProcessFreeList Time', 'Maximum time to process a world\'s free list'),
            ])
         },
         {
            'title': 'Allocator Process Free List Latency (MIN)',
            'metrics': [
               ('minProcessFreeListTime', 'Min ProcessFreeList Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Min ProcessFreeList Time', 'Minimum time to process a world\'s free list'),
            ])
         },
         {
            'title': 'Allocator FreeLists Processed Throughput',
            'metrics': [
               ('freeListsProcessedTput', 'FreeLists Processed Throughput'),
               ('pbasAddedToFreeListTput', 'Pbas Added To FreeList Throughput'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('FreeLists Processed Throughput', 'The throughput of freelists processed via BA_ProcessFreeList'),
               ('Pbas Added To FreeList Throughput', 'Throughput of Pbas Added to Delayed Free List with BA_AddToFreeList')
            ])
         },
         {
            'title': 'Allocator Checkpoint Write IOPS',
            'metrics': [
               ('cpWriteIOPS', 'Checkpoint Write IOPS')
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Checkpoint Write IOPS', 'Checkpoint Write IO per second')
            ])
         },
         {
            'title': 'Allocator Checkpoint Write Throughput',
            'metrics': [
               ('cpWriteIOTput', 'Checkpoint Write Throughput')
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Checkpoint Write Throughput', 'Bytes written by the allocator checkpoint')
            ])
         },
         {
            'title' : 'Allocated Space',
            'metrics': [
               ('allocatedSpace', 'Allocated Percentage'),
               ('spacePendingFree', 'Allocated Space Pending Free Percentage')
            ],
            'unit': u"percent",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description' : fmt_desc('Support', [
               ('Allocated Percentage', 'The percentage of space currently allocated'),
               ('Allocated Space Pending Free Percentage', 'The percentage of space pending free from a checkpoint operation'),
            ])
         },
         {
            'title': 'Capacity',
            'metrics': [
               ('capacity', 'Capacity'),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description' : fmt_desc('Developer', [
               ('Capacity', 'Total capacity of the bitmap'),
            ])
         },
         {
            'title': 'Component Table Checkpoint Latency',
            'metrics': [
               ('ctFlushMinTime', 'Min Page Flush Time'),
               ('ctFlushAvgTime', 'Avg Page Flush Time'),
               ('ctFlushMaxTime', 'Max Page Flush Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Min Page Flush Time', 'Minimum time to flush pages to disk during checkpoint writes'),
               ('Avg Page Flush Time', 'Average time to flush pages to disk during checkpoint writes'),
               ('Max Page Flush Time', 'Maximum time to flush pages to disk during checkpoint writes'),
            ])
         },
         {
            'title': 'Component Table Checkpoint Pages Flushed',
            'metrics': [
               ('ctNumPagesFlushed', 'Pages Flushed To Disk'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('Pages Flushed To Disk', 'Number of pages flushed to disk during checkpoint'),
            ])
         },
         {
            'title': 'Component Table Component Stats',
            'metrics': [
               ('ctNumFreeComp', 'FREE Components'),
               ('ctNumReservedComp', 'RESERVED Components'),
               ('ctNumActiveComp', 'ACTIVE Components'),
               ('ctNumDeletedComp', 'DELETED Components'),
               ('ctNumZombieComp', 'ZOMBIE Components'),
               ('ctNumFailedReserves', 'Failed Reserve Component IDs'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
            'group': True,
            'description': fmt_desc('Developer', [
               ('FREE Components', 'Number of FREE components'),
               ('RESERVED Components', 'Number of RESERVED components'),
               ('ACTIVE Components', 'Number of ACTIVE components'),
               ('DELETED Components', 'Number of DELETED components'),
               ('ZOMBIE Components', 'Number of ZOMBIE components'),
               ('Failed Reserve Component IDs', 'Number of failed calls to reserve CompTable entry'),
            ])
         },
         {
            'title': 'LSOM2 Congestion',
            'metrics': [
               ('global', 'Global Congestion'),
               ('beData', 'Be Data Congestion'),
               ('beDataAllocator', 'Be Data Allocator Congestion'),
               ('bePolicyAllocator', 'Be Policy Allocator Congestion'),
               ('wal', 'Write Ahead Log Congestion'),
               ('walAllocator', 'Write Ahead Log Allocator Congestion'),
               ('splLogical', 'Splinter Logical Table Congestion'),
               ('splPrepare', 'Splinter Prepare Table Congestion'),
               ('splAttr', 'Splinter Attribute Table Congestion'),
               ('splAllocator', 'Splinter Allocator Congestion'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'LSOM2 Transaction',
            'metrics': [
               ('numCheckpoints', 'Number of Checkpoints'),
               ('numCheckpointTriggers', 'Number of Checkpoint Triggers'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'LSOM2 Transaction Time',
            'metrics': [
               ('avgCheckpointTime', 'Average Checkpoint Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'LSOM2 Transaction Time (MAX)',
            'metrics': [
               ('maxCheckpointTime', 'Max Checkpoint Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'LSOM2 Transaction Time (MIN)',
            'metrics': [
               ('minCheckpointTime', 'Min Checkpoint Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'LSOM2 WAL Utilization',
            'metrics': [
               ('capacityUsed', 'Used Capacity'),
               ('capacityTotal', 'Total Capacity'),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'LSOM2 WAL Density',
            'metrics': [
               ('tputAppend', 'Append Tput'),
               # rename for there is tputWrite in graph 'LSOM2 Read/Write Throughput'
               ('tputWriteLsom2Partition', 'Write Tput'),
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Device IOPS',
            'metrics': [
               ('iopsDevRead', 'Read IOPS'),
               ('iopsDevWrite', 'Write IOPS'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Device Throughput',
            'metrics': [('throughputDevRead', 'Read'),
                        ('throughputDevWrite', 'Write')],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': True,
         },
         {
            'title': 'Device Latency',
            'metrics': [('latencyDevDAvg', 'DAVG'),
                        ('latencyDevKAvg', 'KAVG'),
                        ('latencyDevGAvg', 'GAVG'),
                        ('latencyDevRead', 'RDLAT'),
                        ('latencyDevWrite', 'WRLAT'),
                        ],
            'unit': u"µs",
            'thresholds': [30000, 50000],
            'min': 0,
            'detailOnly': True,
         },
      ]
   },
   'lsom2-world-cpu' : {
      'title': 'LSOM2: Worlds',
      'tag' :  'lsom2',
      'repeat': False,
      'repeatByHost': True,
      'metrics': [
         {
            'title': 'CPU Run Percentage',
            'metrics': [
               "runPct",
            ],
            'unit': u"percent",
            'min': 0,
            'description' : fmt_desc('Customer', [
               ('LSOM2-IO-*', 'Cpu threads which belong to lsom2'),
            ]) + '\n\n' + fmt_desc('Developer', [
               ('[DiskUuid-][SplinterName-]WorldName', 'Cpu threads created by splinter'),
            ]),
         },
         {
            'title': 'CPU Ready Percentage',
            'metrics': [
               "readyPct",
            ],
            'unit': u"percent",
            'min': 0,
            'description' : fmt_desc('Customer', [
               ('LSOM2-IO-*', 'Cpu threads which belong to lsom2'),
            ]) + '\n\n' + fmt_desc('Developer', [
               ('[DiskUuid-][SplinterName-]WorldName', 'Cpu threads created by splinter'),
            ]),
         },
      ],
      'entityToShow':'lsom2-world-cpu',
   },
   'lsom2-iolayer-stats' : {
      'title':  'LSOM2: IOLayer Stats',
      'tag': 'lsom2',
      'repeat': True,
      'entityToShow': 'lsom2-iolayer-stats',
      'metrics': [
         {
            'title': 'LSOM2 IOLayer IOPS',
            'metrics': [
               ('readIOPS', 'Read IOPS'),
               ('writeIOPS', 'Write IOPS'),
               ('iops', 'Total IOPS'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Read IOPS', 'The number of read operations per second'),
               ('Write IOPS', 'The number of write operations per second'),
               ('Total IOPS', 'The number of operations per second'),
            ])
         },
         {
            'title': 'LSOM2 IOLayer Read/Write Latency',
            'metrics': [
               ('avgReadLatency', 'Average Read Latency'),
               ('avgWriteLatency', 'Average Write Latency'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Average Read Latency', 'Average time taken for a single read operation'),
               ('Average Write Latency', 'Average time taken for a single write operation'),
            ])
         },
         {
            'title': 'LSOM2 IOLayer Maximum Read/Write Latency',
            'metrics': [
               ('maxReadLatency', 'Maximum Read Latency'),
               ('maxWriteLatency', 'Maximum Write Latency'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Maximum Read Latency', 'Maximum time taken for a single read operation'),
               ('Maximum Write Latency', 'Maximum time taken for a single write operation'),
            ])
         },
         {
            'title': 'LSOM2 IOLayer Read/Write Throughput',
            'metrics': [
               ('readThroughput', 'Read Throughput'),
               ('writeThroughput', 'Write Throughput'),
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Read Throughput', 'Throughput for read operations'),
               ('Write Throughput', 'Throughput for write operations'),
            ])
         },
         {
            'title': 'LSOM2 IOLayer Read/Write IO Size',
            'metrics': [
               ('readIoSize', 'Read IoSize'),
               ('writeIoSize', 'Write IoSize'),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Read IoSize', 'IoSize for read operations'),
               ('Write IoSize', 'IoSize for write operations'),
            ])
         },
      ]
   },
   'lsom2-iolayer-handle-stats' : {
      'title':  'LSOM2: IOLayer Handle Stats',
      'tag': 'lsom2',
      'repeat': True,
      'entityToShow': 'lsom2-iolayer-handle-stats',
      'metrics': [
         {
            'title': 'LSOM2 IOLayer Handle IOPS',
            'metrics': [
               ('readIOPS', 'Read IOPS'),
               ('writeIOPS', 'Write IOPS'),
               ('iops', 'Total IOPS'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Read IOPS', 'The number of read operations per second'),
               ('Write IOPS', 'The number of write operations per second'),
               ('Total IOPS', 'The number of operations per second'),
            ])
         },
         {
            'title': 'LSOM2 IOLayer Handle Read/Write Latency',
            'metrics': [
               ('avgReadLatency', 'Average Read Latency'),
               ('avgWriteLatency', 'Average Write Latency'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Average Read Latency', 'Average time taken for a single read operation'),
               ('Average Write Latency', 'Average time taken for a single write operation'),
            ])
         },
         {
            'title': 'LSOM2 IOLayer Handle Maximum Read/Write Latency',
            'metrics': [
               ('maxReadLatency', 'Maximum Read Latency'),
               ('maxWriteLatency', 'Maximum Write Latency'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Maximum Read Latency', 'Maximum time taken for a single read operation'),
               ('Maximum Write Latency', 'Maximum time taken for a single write operation'),
            ])
         },
         {
            'title': 'LSOM2 IOLayer Handle Read/Write Throughput',
            'metrics': [
               ('readThroughput', 'Read Throughput'),
               ('writeThroughput', 'Write Throughput'),
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Read Throughput', 'Throughput for read operations'),
               ('Write Throughput', 'Throughput for write operations'),
            ])
         },
         {
            'title': 'LSOM2 IOLayer Handle Read/Write IO Size',
            'metrics': [
               ('readIoSize', 'Read IoSize'),
               ('writeIoSize', 'Write IoSize'),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Read IoSize', 'IoSize for read operations'),
               ('Write IoSize', 'IoSize for write operations'),
            ])
         },
      ]
   },
   'lsom2-mdr-handle-stats' : {
      'title':  'LSOM2: MDR Handle Stats',
      'tag': 'lsom2',
      'repeat': True,
      'entityToShow': 'lsom2-mdr-handle-stats',
      'metrics': [
         {
            'title': 'LSOM2 MDR Handle IOPS',
            'metrics': [
               ('readIOPS', 'Read IOPS'),
               ('writeIOPS', 'Write IOPS'),
               ('iops', 'Total IOPS'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Read IOPS', 'The number of read operations per second'),
               ('Write IOPS', 'The number of write operations per second'),
               ('Total IOPS', 'The number of operations per second'),
            ])
         },
         {
            'title': 'LSOM2 MDR Handle Read/Write Latency',
            'metrics': [
               ('avgReadLatency', 'Average Read Latency'),
               ('avgWriteLatency', 'Average Write Latency'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Average Read Latency', 'Average time taken for a single read operation'),
               ('Average Write Latency', 'Average time taken for a single write operation'),
            ])
         },
         {
            'title': 'LSOM2 MDR Handle Maximum Read/Write Latency',
            'metrics': [
               ('maxReadLatency', 'Maximum Read Latency'),
               ('maxWriteLatency', 'Maximum Write Latency'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Maximum Read Latency', 'Maximum time taken for a single read operation'),
               ('Maximum Write Latency', 'Maximum time taken for a single write operation'),
            ])
         },
         {
            'title': 'LSOM2 MDR Handle Read/Write Throughput',
            'metrics': [
               ('readThroughput', 'Read Throughput'),
               ('writeThroughput', 'Write Throughput'),
            ],
            'unit': u"Bps",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Read Throughput', 'Throughput for read operations'),
               ('Write Throughput', 'Throughput for write operations'),
            ])
         },
         {
            'title': 'LSOM2 MDR Handle Read/Write IO Size',
            'metrics': [
               ('readIoSize', 'Read IoSize'),
               ('writeIoSize', 'Write IoSize'),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Read IoSize', 'IoSize for read operations'),
               ('Write IoSize', 'IoSize for write operations'),
            ])
         },
         {
            'title': 'LSOM2 MDR Handle Read/Write OIO',
            'metrics': [
               ('readOIO', 'Read OIO'),
               ('writeOIO', 'Write OIO'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Read OIO', 'OIO for read operations'),
               ('Write OIO', 'OIO for write operations'),
            ])
         },
      ]
   },
   'vsan2-dom-disks-perf': get_vsan2_dom_disks_perf(),
   'vsan2-dom-disks-capacity': get_vsan2_dom_disks_capacity(),
   'vsan2-dom-disks-both': get_vsan2_dom_disks_both(),
   'vsan2-dom-scheduler-perf': get_vsan2_dom_scheduler_perf(),
   'vsan2-dom-scheduler-capacity': get_vsan2_dom_scheduler_capacity(),
   'vsan2-dom-scheduler-both': get_vsan2_dom_scheduler_both(),
   'vsan2-cluster-resync-perf': get_vsan2_cluster_resync_perf(),
   'vsan2-cluster-resync-capacity': get_vsan2_cluster_resync_capacity(),
   'vsan-esa-dom-capacity-fullness': {
      'title': 'DOM vSAN ESA: Capacity Fullness',
      'tag' :  'dom_vsan-esa',
      'repeat': True,
      'entityToShow': 'vsan-esa-dom-capacity-fullness',
      'metrics': [
         {
            'title': 'State',
            'metrics': [
               ('state', 'State of scheduler'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('State', 'State of scheduler'),
            ])
         },
         {
            'title': 'Target/Free Rate',
            'metrics': [
               ('freeingRate', 'Freeing rate'),
               ('targetRate', 'Target rate'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Freeing Rate', 'Freeing rate'),
               ('Target Rate', 'Target rate'),
            ])
         },
         {
            'title': 'Token Weight',
            'metrics': [
               ('tokenWeight', 'Current weight for bank writes'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('TokenWeight', 'Current weight for bank writes'),
            ])
         },
         {
            'title': 'Token Rate',
            'metrics': [
               ('maxTokensAllowed', 'Max tokens allowed'),
               ('availTokens', 'Currently available tokens'),
               ('tokensConsumedRate', 'Tokens consumed by bank'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Max Tokens Allowed', 'Max tokens allowed'),
               ('Available Tokens', 'Currently available tokens'),
               ('Consumed Tokens Rate', 'Tokens consumed by bank'),
            ])
         },
         {
            'title': 'Bank IOPS Unthrottled',
            'metrics': [
               ('unthrottledBankIOPS', 'Bank unthrottled IOPS'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Unthrottled Bank IOPS', 'Number of bank IOPS unthrottled'),
            ])
         },
         {
            'title': 'Prev fullness (per-mille)',
            'metrics': [
               ('diskFullnessPermil', 'Prev fullness'),
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Customer', [
               ('Disk Fullness Per Mille', 'Previous fullness per mille'),
            ])
         },
         {
            'title': 'Unmap/SegWrite/Bankwrite Rate',
            'metrics': [
               ('unmapRate', 'Cleaner unmaps'),
               ('segWriteRate', 'Cleaner write'),
               ('bankWriteRate', 'Bank writes processed'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
            'description': fmt_desc('Customer', [
               ('Unmap Rate', 'Number of cleaner unmaps'),
               ('Seg Write Rate', 'Number of cleaner write'),
               ('Bank Write Rate', 'Number of bank writes processed'),
            ])
         },
         {
            'title': 'Ops Rate',
            'metrics': [
               ('numThrottledOpsRate', 'Throttled Ops'),
               ('numOpsAbortedRate', 'Aborted Ops'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
            'description': fmt_desc('Customer', [
               ('Throttled Ops Rate', 'Number of Ops that were throttled'),
               ('Aborted Ops Rate', 'Aborted operations'),
            ])
         },
      ]
   },
   'psa-split-stats' : {
      'title':  'PSA: Split Stats',
      'repeat': True,
      'entityToShow': 'psa-split-stats',
      'metrics': [
         {
            'title': 'PSA Split Stats',
            'metrics': [
               ('totalSplits', 'Total Split Commands'),
               ('align', 'Align'),
               ('maxXfer', 'Max Transfer'),
               ('pae', 'PAE'),
               ('sgSize', 'SG Size'),
               ('dmaBoundary', 'DMA Boundary'),
               ('sgElemSizeBounceBuffer', 'Bounce Buffer'),
               ('sgElemSizeCloneBuffer', 'Clone Buffer'),
               ('sgElemMultSectorSize', 'Multiple Sector Size')
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Developer', [
               ('Total Split Commands', 'Total commands that are split in PSA layer'),
               ('Align', 'Splits due to alignment'),
               ('Max Transfer', 'Splits due to max transfer'),
               ('PAE', 'Splits due to PAE'),
               ('SG Size', 'Splits due to SG size'),
               ('DMA Boundary', 'Splits due to DMA boundary'),
               ('Bounce Buffer', 'Splits due to SG Element Size (Bounce Buffer)'),
               ('Clone Buffer', 'Splits due to SG Element Size (Clone Buffer)'),
               ('Multiple Sector Size', 'Splits due to SG Element Size (Multiplier)')
            ])
         },
      ]
   },
   'kvstore': {
      'title': 'LSOM2: KVStore Stats',
      'tag' :  'lsom2',
      'repeat': True,
      'entityToShow': 'kvstore',
      'metrics': [
         {
            'title': "Allocator API Latency",
            'metrics': [
               ('avgAllocBlockTime', 'Alloc API latency'),
               ('avgFreeTime', 'Free block API latency'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Developer', [
               ('Alloc Block Latency', 'Average time to call BA_AllocBlocks'),
               ('Free Block Latency', 'Average time to call BAMarkBlockAsFreed')
            ])
         },
         {
            'title': "Allocator Checkpoint Latency",
            'metrics': [
               ('cpMaxMergeBitmapsTime', 'Max Merge Bitmap Time'),
               ('cpMinMergeBitmapsTime', 'Min Merge Bitmap Time'),
               ('cpAvgMergeBitmapsTime', 'Avg Merge Bitmap Time'),
               ('cpMaxProcessFreeListTime', 'Max Process Free Lists Time'),
               ('cpMinProcessFreeListTime', 'Min Process Free Lists Time'),
               ('cpAvgProcessFreeListTime', 'Avg Process Free Lists Time'),
               ('cpMaxCleanupTime', 'Max Cleanup Time'),
               ('cpMinCleanupTime', 'Min Cleanup Time'),
               ('cpAvgCleanupTime', 'Avg Cleanup Time'),
               ('cpMaxCheckpointTime', 'Max Checkpoint Time'),
               ('cpMinCheckpointTime', 'Min Checkpoint Time'),
               ('cpAvgCheckpointTime', 'Avg Checkpoint Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Developer', [
               ('Max Merge Bitmap Time', 'Maximum time to merge alloc/resv bitmaps'),
               ('Min Merge Bitmap Time', 'Minimum time to merge alloc/resv bitmaps'),
               ('Avg Merge Bitmap Time', 'Average time to merge alloc/resv bitmaps'),
               ('Max Process Free Lists Time', 'Maximum time to process free lists'),
               ('Min Process Free Lists Time', 'Minimum time to process free lists'),
               ('Avg Process Free Lists Time', 'Average time to process free lists'),
               ('Max Cleanup Time', 'Maximum time to run cleanup stage'),
               ('Min Cleanup Time', 'Minimum time to run cleanup stage'),
               ('Avg Cleanup Time', 'Average time to run cleanup stage'),
               ('Max Checkpoint Time', 'Maximum time to run full checkpoint'),
               ('Min Checkpoint Time', 'Minimum time to run full checkpoint'),
               ('Avg Checkpoint Time', 'Average time to run full checkpoint'),
            ])
         },
         {
            'title': "Allocator Block Throughput",
            'metrics': [
               ('blksAllocdTput', 'Alloc Block Throughput'),
               ('blksFreedTput', 'Free Block Throughput')
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Developer', [
               ('Alloc Block Throughput', 'Throughput of blocks allocated with BA_AllocBlocks'),
               ('Free Block Throughput', 'Throughput of blocks freed with MarkBlockAsFreed')
            ])
         },
         {
            'title': 'Allocator API Throughput',
            'metrics': [
               ('allocBlockApiTput',      'Alloc Block API Throughput'),
               ('freeApiTput',            'Free API Throughput'),
               ('addToFreeListApiTput',   'Add To FreeList API Throughput'),
               ('processFreeListApiTput', 'Process FreeList API Throughput')
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Developer', [
               ('Alloc Block API Throughput',      'Throughput of BA_AllocBlocks API'),
               ('Free API Throughput',             'Throughput of BAMarkBlockAsFreed API'),
               ('Add To FreeList API Throughput',  'Throughput of BA_AddToFreeList'),
               ('Process FreeList API Throughput', 'Throughput of BA_ProcessFreeList')
            ])
         },
         {
            'title': 'Allocator Process Free List Latency',
            'metrics': [
               ('minProcessFreeListTime', 'Min ProcessFreeList Time'),
               ('avgProcessFreeListTime', 'Avg ProcessFreeList Time'),
               ('maxProcessFreeListTime', 'Max ProcessFreeList Time')
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Developer', [
               ('Min ProcessFreeList Time', 'Minimum time to process a world\'s free list'),
               ('Avg ProcessFreeList Time', 'Average time to process a world\'s free list'),
               ('Max ProcessFreeList Time', 'Maximum time to process a world\'s free list'),
            ])
         },
         {
            'title': 'Allocator FreeLists Processed Throughput',
            'metrics': [
               ('freeListsProcessedTput', 'FreeLists Processed Throughput'),
               ('pbasAddedToFreeListTput', 'Pbas Added To FreeList Throughput'),
            ],
            'unit': u"iops",
            'min': 0,
            'detailOnly': True,
            'description': fmt_desc('Developer', [
               ('FreeLists Processed Throughput', 'The throughput of freelists processed via BA_ProcessFreeList'),
               ('Pbas Added To FreeList Throughput', 'Throughput of Pbas Added to Delayed Free List with BA_AddToFreeList')
            ])
         },
         {
            'title': "Allocator Alloc/Free Latency",
            'metrics': [
               ('freeLatencyAvg', 'Avg Free Time'),
               ('freeLatencyMax', 'Max Free Time'),
               ('allocLatencyAvg', 'Avg Alloc Time'),
               ('allocLatencyMax', 'Max Alloc Time'),
            ],
            'unit': u"ns",
            'min': 0,
            'detailOnly': False,
            'description': fmt_desc('Developer', [
               ('Avg Free Time', 'Average time for a free call'),
               ('Max Free Time', 'Maximum time for a free call'),
               ('Avg Alloc Time', 'Average time for an alloc call'),
               ('Max Alloc Time', 'Maximum time for an alloc call'),
            ])
         },
         {
            'title' : 'Allocated Space',
            'metrics': [
               ('allocatedSpace', 'Allocated Percentage'),
               ('spacePendingFree', 'Allocated Space Pending Free Percentage')
            ],
            'unit': u"percent",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Support', [
               ('Allocated Percentage', 'The percentage of space currently allocated'),
               ('Allocated Space Pending Free Percentage', 'The percentage of space pending free from a checkpoint operation'),
            ])
         },
         {
            'title': 'Capacity',
            'metrics': [
               ('capacity', 'Capacity'),
            ],
            'unit': u"bytes",
            'min': 0,
            'detailOnly': True,
            'description' : fmt_desc('Developer', [
               ('Capacity', 'Total capacity of the bitmap'),
            ])
         },
         {
            'title': "KVStore Checkpoint Stats",
            'metrics': [('cpWriteLockAvgNs', 'Checkpoint Write Lock Avg'),
                        ('cpWriteLockMaxNs', 'Checkpoint Write Lock Max'),
                        ('cpReadLockMaxNs', 'Checkpoint Read Lock Max')],
            'unit': u"ns",
            'min': 0,
            'detailOnly': True,
            'description': fmt_desc('Developer', [
               ('Write lock average hold time ns', 'write lock max hold time ns'),
               ('Read lock max hold time ns', ''),
            ])
         },
      ]
   },
   'ioinsight': {
      'title':  'IOInsight Stats (IOInsight Dump)',
      'repeat': True,
      'entityToShow': 'ioinsight',
      'metrics': [
         {
            'title': 'IOPS',
            'metrics': [
               'iopsRead',
               'iopsWrite',
               'iopsTotal',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Throughput',
            'metrics': [
               'throughputRead',
               'throughputWrite',
               'throughputTotal',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Sequential & Random Throughput',
            'metrics': [
               'throughputSequential',
               'throughputRandom',
               'throughputTotal',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Sequential & Random IO Ratio',
            'metrics': [
               'sequentialReadRatio',
               'sequentialWriteRatio',
               'sequentialRatio',
               'randomReadRatio',
               'randomWriteRatio',
               'randomRatio',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': '4K Aligned & Unaligned IO Ratio',
            'metrics': [
               'aligned4kReadRatio',
               'aligned4kWriteRatio',
               'aligned4kRatio',
               'unaligned4kReadRatio',
               'unaligned4kWriteRatio',
               'unaligned4kRatio',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Read & Write IO Ratio',
            'metrics': [
               'readRatio',
               'writeRatio',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
      ]
   },
   'statsdb': {
      'title':  'Stats DB metrics',
      'repeat': True,
      'entityToShow': 'statsdb',
      'metrics': [
         {
            'title': 'IOPS',
            'metrics': [
               'iopsRead',
               'iopsWrite',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Throughput',
            'metrics': [
               'tputRead',
               'tputWrite',
            ],
            'unit': u"short",
            'min': 0,
            'detailOnly': False,
         },
         {
            'title': 'Latency',
            'metrics': [
               'latRead',
               'latWrite',
            ],
            'unit': u"µs",
            'min': 0,
            'detailOnly': False,
         },
      ]
   }
}

def getDashboardPatch():
   return dashboardPatch

if __name__ == "__main__":
   import json
   print(json.dumps(dashboardPatch))
