# -*- coding: utf-8 -*-

"""
Copyright 2015-2022 VMware, Inc.  All rights reserved.
-- VMware Confidential

"""

from xml.dom import minidom
import time
import datetime
import xml.etree.cElementTree as ET
import itertools

import sys
import os
sys.path.append('%s/../pyVpx' % os.path.dirname(__file__))
sys.path.append('%s/..' % os.path.dirname(__file__))
try:
   from pyVmomi import vim, vmodl, VmomiSupport, SoapStubAdapter
except:
   # Running as a script
   sys.path.append('../pyVpx')
   sys.path.append('..')
   from pyVmomi import vim, vmodl, VmomiSupport, SoapStubAdapter

import pyVmomi
os.environ['VSAN_PYMO_SKIP_VC_CONN'] = '1'
import vsanmgmtObjects
import cmmds
import json
import subprocess
import StringIO
import logging
import uuid
#from humbugRedis import HumbugRedisInstance as Redis

import threading
import Queue
from multiprocessing.pool import ThreadPool
MAX_ITEMS = 4
THREAD_RUNNING_TIME = 180 # thread will abort if running more than 3 mins
gQueue = Queue.Queue(MAX_ITEMS)
producer = ThreadPool(MAX_ITEMS)
consumer = ThreadPool(MAX_ITEMS)
producerLock = threading.Lock()
consumerLock = threading.Lock()
producerResult = []
consumerResult = []
INFLUX_BATCH = 20000
gEntities = []

try:
   # try to avoid module' object has no attribute '_strptime' error
   timeStamp = time.mktime(
      datetime.datetime.strptime("2021-11-05 20:07:00", "%Y-%m-%d %H:%M:%S").timetuple())
except:
   pass



validParsers = ["SoapParser", "TextParser", "JsonParser"]
avgLatMetrics = ['avgLatRead', 'avgLatWrite', 'avgLatUnmap']

def getValidParsers():
   return validParsers

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

class VSANPerfDumpParser:
   def __init__(self, dumpPath, parser, hostDiskMapFile=None, redisKey=None):
      self.dumpPath = dumpPath
      self.data=[]
      self.dataByTag = {}
      self.hostDiskMapFile = hostDiskMapFile
      if parser in validParsers:
         self.parser = parser
      else:
         raise Exception("Illegal parser %s" % parser)
      self.dateFormat = "%Y-%m-%d %H:%M:%S"
      self.timeStampCache = {}
      self.cmmdsByUuid = None
      self.newLayout = False
#      self.redis = Redis.instance()
      self.redisKey = redisKey
      self.entities = []
      self.dataPointsNum = 0
      self.parsingTime = 0
      self.waitQueueInProducer = 0
      self.waitQueueInConsumer = 0
      self.influxTime = 0
      self.fileNumLines = 0

   def Parse(self, writeFn):
      self.numSkipped = 0
      self.numValues = 0
      dir = os.path.dirname(self.dumpPath)
      if self.hostDiskMapFile:
         with open(self.hostDiskMapFile) as data_file:
            self.cmmdsByUuid = json.load(data_file)
      else:
         self.cmmdsByUuid = cmmds.parseCmmdsFileByDir(dir)
      self.cmmdsCache = {'host': {}, 'disk': {}}
      if self.parser == "SoapParser":
         try:
            self.ParseVmodlDumpFile(self.dumpPath, writeFn)
            return
         except Exception as e:
            logging.exception("Soap parser failed: %s" % e)
            raise Exception("Soap parser failed: %s" % (e))
      elif self.parser == "JsonParser":
         try:
            with open(self.dumpPath, 'r') as fp:
               self.ParseJson(fp)
         except Exception as e:
            logging.exception("JSON parser failed: %s" % e)
            raise Exception("Json parser failed: %s" % (e))
      elif self.parser == "TextParser":
         try:
            self.ParseText(self.dumpPath)
         except Exception as e:
            logging.exception("Text parser failed: %s" % e)
            raise Exception("Text parser failed: %s" % (e))
      else:
         raise Exception("Invalid parser %s" % self.parser)
      self.FlushBatchData(writeFn)

   def file_len(self, fname):
      try:
         p = subprocess.Popen(['wc', '-l', fname], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
         result, err = p.communicate()
         if p.returncode != 0:
            return None
         return int(result.strip().split()[0])
      except:
         logging.exception("Error getting file length")
         return None

   def ParseVmodlDumpFile(self, dumpPath, writeFn):
      beginMarker = "--------------SOAP stats dump--------------\n"
      separationMarker = "--------------Stats Segment Separator--------------\n"
      state = 0
      vmodl = None
      entities = []
      lineCount = 0
      self.fileNumLines = self.file_len(dumpPath)
      with open(dumpPath, 'r') as fp:
         for line in fp:
            lineCount += 1
            if line == beginMarker or line == separationMarker:
               continue
            try:
               # consumer thread is launched inside producer thread
               result = producer.apply_async(self.ParseXML, (line, writeFn, lineCount,))
               producerResult.append(result)
            except Exception as e:
               logging.error("Failed to parse line \"%s\": %s" % (line, e))
      try:
          [result.wait(THREAD_RUNNING_TIME) for result in producerResult]
          [result.wait(THREAD_RUNNING_TIME) for result in consumerResult]
          gQueue.put(self._ProcessEntities(gEntities, {}))
          self.FlushBatchDataThreading(writeFn, self.fileNumLines)
          logging.info("producer threads waitting time for having queue is not full %f" % self.waitQueueInProducer)
          logging.info("consumer threads waitting time for having queue is not empty %f" % self.waitQueueInConsumer)
      except Exception as e:
         logging.exception("Failed to parse entity: %s" % (e))

   def ResolveName(self, entityRefId):
      if self.cmmdsByUuid is None:
         colonIndex = entityRefId.index(':')
         entityType = entityRefId[:colonIndex]
         entityId = entityRefId[colonIndex+1:]
         return [(entityType, None, None, None, entityId)]

      return cmmds.lookupEntityId(
         entityRefId, self.cmmdsByUuid, self.cmmdsCache)

   def _ProcessSampleInfo(self, sampleInfo):
      if sampleInfo not in self.timeStampCache.keys():
         dates = sampleInfo.split(',')
         dates[:] = [ self.ConvertTimestamp(dt)
                      for dt in dates
                    ]
         self.timeStampCache[sampleInfo] = dates
      else:
         dates = self.timeStampCache[sampleInfo]
      return dates

   # The space is a special char for influxdb, it need to be escaped or the influx will meet exception.
   def _EscapeSpace(self, stringValue):
      if stringValue:
         return stringValue.replace(" ", "\ ")
      return stringValue

   # The data is grouped by tag, followed by timestamp.
   # This is ideal for insertion into influxDB, as we want all
   # metrics of a given entityType to have one row per timestamp.
   def _ProcessTaggedDataPoints(self):
      for tag, tsVals in self.dataByTag.items():
         (entityType, hostName, entityName) = tag

         entityType = self._EscapeSpace(entityType)
         hostName = self._EscapeSpace(hostName)
         entityName = self._EscapeSpace(entityName)

         objKey = entityName or hostName
         measurement = entityType
         if not hostName:
            linePrefix = '%s,object=\"%s\" ' % (measurement, entityType)
         else:
            linePrefix = '%s,object=\"%s:%s-%s\",objKey=\"%s\" ' \
                         % (measurement, hostName, entityType, entityName, objKey)
         for ts, valTuples in tsVals.items():
            vals = ",".join(["%s=%s" % (k, v) for k, v in valTuples])
            line = "%s %s %s" % (linePrefix, vals, ts)
            self.Insert([line])
      self.dataByTag = {}

   def ConvertPerfUuidFromCapacityDiskUuidIfSingleTier(self, originalUuid):
      capacityInt = uuid.UUID(originalUuid).int
      perfInt = capacityInt + 1
      perfStr = hex(perfInt)[2:]
      perfUuidStr = str(uuid.UUID(perfStr[0:-1])) # humbug use python2
      logging.debug("If single tier, the perf uuid str for capacity uuid %s is %s", originalUuid, perfUuidStr)
      if cmmds.isConvertedPerfUuidExisting(perfUuidStr, self.cmmdsByUuid):
         return perfUuidStr
      else:
         return originalUuid

   def _HackForVsan2DiskAndDomSchedulerMetrics(self, metricLabel, entityRefId):
      LSOM2_IO_STATS_ENTITY_TYPES = (
         'lsom2-allocator-stats','vsan-esa-disk-layer-allocator-stats',
         'lsom2-block-engine-stats','vsan-esa-disk-layer-block-engine-stats',
         'lsom2-congestion-stats', 'vsan-esa-disk-layer-congestion-stats',
         'lsom2-transaction-stats', 'vsan-esa-disk-layer-transaction-stats',
         'vsan2-disk-lsom2', 'vsan-esa-disk-lsom2', 'vsan-esa-disk-layer',
         'vsan2-disk-scsifw', 'vsan-esa-disk-scsifw', 'vsan-esa-disk-layer-partition-stats',
      )
      SPLINTER_STATS_ENTITY_TYPES = (
         'splinter-overall-stats', 'splinter-operation-stats',
         'splinter-lookup-stats', 'splinter-task-stats',
         'splinter-trunk-page-stats', 'splinter-branch-page-stats',
         'splinter-memtable-page-stats', 'splinter-filter-page-stats',
         'splinter-range-page-stats', 'splinter-misc-page-stats',
         'splinter-snowplough-stats', 'splinter-range-delete-stats',
         'splinter-checkpoint-stats', 'splinter-meta-page-stats',
         'splinter-premini-stats',
      )
      VSAN2_DOM_SCHEDULER_ENTITY_TYPES = (
         'vsan2-dom-scheduler', 'vsan-esa-dom-scheduler',
      )
      VSAN2_CLUSTER_RESYNC_ENTITY_TYPES = (
         'vsan2-cluster-resync', 'vsan-esa-cluster-resync',
      )
      LSOM2_RENAMED_ENTITY_TYPES_MAPPING = {
         'vsan-esa-disk-iolayer-handle-stats': 'lsom2-iolayer-handle-stats',
         'vsan-esa-disk-iolayer-stats': 'lsom2-iolayer-stats',
         'vsan-esa-disk-layer-mdr-handle-stats': 'lsom2-mdr-handle-stats',
         'vsan-esa-disk-layer-world-cpu': 'lsom2-world-cpu',
         'vsan-zdom-stats': 'zdom-io',
      }
      # rename for there is tputWrite in graph 'LSOM2 Read/Write Throughput'
      VSAN2_LSOM2_METRICS_RENAME_TYPES = {
         'vsan-esa-disk-layer-partition-stats': {
            'tputWritePerf': 'tputWriteLsom2PartitionPerf',
            'tputWriteCapacity': 'tputWriteLsom2PartitionCapacity',
         },
      }

      # "str.startswith()" accepts a tuple of prefixes to look for
      if entityRefId.startswith(
         LSOM2_IO_STATS_ENTITY_TYPES +
         SPLINTER_STATS_ENTITY_TYPES +
         VSAN2_DOM_SCHEDULER_ENTITY_TYPES +
         VSAN2_CLUSTER_RESYNC_ENTITY_TYPES +
         tuple(LSOM2_RENAMED_ENTITY_TYPES_MAPPING.keys())
      ):
         orgEntityType, entityId = entityRefId.split(':', 1)
         if orgEntityType in LSOM2_IO_STATS_ENTITY_TYPES:
            entityType = 'lsom2-io-stats'
         elif orgEntityType in SPLINTER_STATS_ENTITY_TYPES:
            entityType = 'splinterdb'
         elif orgEntityType in LSOM2_RENAMED_ENTITY_TYPES_MAPPING:
            entityType = LSOM2_RENAMED_ENTITY_TYPES_MAPPING[orgEntityType]
         else:
            entityType = orgEntityType

         if orgEntityType in VSAN2_LSOM2_METRICS_RENAME_TYPES:
            logging.debug('orig vsan-esa-disk-layer-partition-stats metricLabel => %s, orgEntityType => %s'
              % (metricLabel, orgEntityType))
            if metricLabel in VSAN2_LSOM2_METRICS_RENAME_TYPES[orgEntityType]:
               metricLabel = VSAN2_LSOM2_METRICS_RENAME_TYPES[orgEntityType][metricLabel]
            logging.debug('new vsan-esa-disk-layer-partition-stats metricLabel => %s, orgEntityType => %s'
              % (metricLabel, orgEntityType))

         if metricLabel.endswith('Perf'):
            metricLabel = metricLabel[0:-4]
            entityId = str(self.ConvertPerfUuidFromCapacityDiskUuidIfSingleTier(entityId))
            if orgEntityType in VSAN2_DOM_SCHEDULER_ENTITY_TYPES:
               entityType = 'vsan2-dom-scheduler-perf'
            elif orgEntityType in VSAN2_CLUSTER_RESYNC_ENTITY_TYPES:
               entityType = 'vsan2-cluster-resync-perf'
         elif metricLabel.endswith('Capacity'):
            metricLabel = metricLabel[0:-8]
            if orgEntityType in VSAN2_DOM_SCHEDULER_ENTITY_TYPES:
               entityType = 'vsan2-dom-scheduler-capacity'
            elif orgEntityType in VSAN2_CLUSTER_RESYNC_ENTITY_TYPES:
               entityType = 'vsan2-cluster-resync-capacity'
         entityRefId = '%s:%s' % (entityType, entityId)
      return metricLabel, entityRefId

   def _ProcessAndInsertDataPoint(self, metricLabel, entityRefId, dates, values, entities, logInfo):
      # 'entities' maintains a unique list of all entities seen
      logging.debug("Original metricLabel => %s, entityRefId => %s, dates => %s, values => %s, entities => %s",
         metricLabel, entityRefId, dates, values, entities)
      metricLabel, entityRefId = self._HackForVsan2DiskAndDomSchedulerMetrics(metricLabel, entityRefId)
      logging.debug("Updated metricLabel => %s, entityRefId => %s, dates => %s, values => %s, entities => %s",
         metricLabel, entityRefId, dates, values, entities)
      entities.add(entityRefId)

#      entityType, entityId = entityRefId.split(':')
#      logInfo.setdefault(
#         entityType, {'metrics': [], 'entities': []})
#      if metricLabel not in logInfo[entityType]['metrics']:
#         logInfo[entityType]['metrics'].append(metricLabel)
#      if entityId not in logInfo[entityType]['entities']:
#         logInfo[entityType]['entities'].append(entityId)

      if self.newLayout:
         tag = self.ResolveName(entityRefId)
         self.dataByTag.setdefault(tag, {})
         for ts, val in zip(dates, values.split(",")):
            if val == "None" or val == "":
               continue
            self.dataByTag[tag].setdefault(ts, [])
            self.dataByTag[tag][ts].append((metricLabel, val))
      else:
         resolvedEntityDetails = self.ResolveName(entityRefId)
         for resolvedEntity in resolvedEntityDetails:
            (entityType, hostName, entityName, extraKey, uuid) = resolvedEntity
            for ts, val in zip(dates, values.split(",")):
               if val == "None" or val == "":
                  continue

               element = self.FormatEntry(ts, entityType, hostName, entityName, metricLabel, val, extraKey)
               if element:
                  self.Insert([element])

   def _ProcessEntities(self, entities, logInfo):
      entities = list(entities)
#      for entity, info in logInfo.iteritems():
#         print "Metrics: %s" % entity
#         for chunk in chunks(sorted(info['metrics']), 6):
#            print "   %s," % ", ".join(["'%s'" % c for c in chunk])
#         for chunk in chunks(info['entities'], 6):
#            print "   %s" % chunk
      entities = list(set(entities))
      self.entities = []
      dataList = []
      for e in entities:
         resolvedEntities = self.ResolveName(e)
         for resolvedEntity in resolvedEntities:
            (entityType, hostName, entityValue, extraKey, uuid) = resolvedEntity

            #logging.exception("Resolved: %s, %s, %s" % (entityType, hostName, entityValue));
            cmd = None
            if not hostName:
               obj = entityType
            else:
               obj = "%s:%s-%s" % (hostName, entityType, entityValue)
            if self.newLayout:
               if hostName:
                  cmd = "entities,host=\"%s\" value=\"foo\"" % (hostName)
            else:
               if not hostName:
                  cmd = "entities,object=\"%s\" value=\"foo\"" % (entityType)
               else:
                  cmd = "entities,host=\"%s\",object=\"%s\" value=\"foo\"" % (hostName, obj)
            entityInfo = {
               'obj': obj,
               'host': hostName,
               'type': entityType,
               'val': entityValue,
               'diskUuid': uuid,
            }
            if entityType == 'capacity-disk':
               diskUuid = e.split("|")[0].split(":")[1]
               disk, host, parent = cmmds.lookupDisk(diskUuid, self.cmmdsByUuid, self.cmmdsCache)
               if parent is not None:
                  parentObj = "%s:%s-%s" % (parent[1], 'cache-disk', parent[0])
                  entityInfo['parent'] = parentObj
                  #logging.info(entityInfo)
            self.entities.append(entityInfo)
            if cmd:
               self.Insert([cmd])
               dataList.append(cmd)
#              print cmd
      return dataList

   def ParseXML(self, line, writeFn, lineIndex):
      def _processEntityWithValue(dataList, dates, metricValue, entityRefId, entities):
         for value in metricValue:
            values = value[1].text.split(",")
            # skip it when all values are None
            if len(set(values).difference({"None", ""})) == 0:
               continue

            newlabel, newRefId = \
               self._HackForVsan2DiskAndDomSchedulerMetrics(value[0][0].text,
                                                         entityRefId)
            # TODO: Remove this since it is hacking nanoseconds value
            if 'lsom2-io-stats' in newRefId and newlabel in avgLatMetrics:
               values = [str(int(val) * 1000) for val in values]                                                  
            if newRefId not in entities:
               resolvedEntityList = self.ResolveName(newRefId)
               entities[newRefId] = resolvedEntityList
            else:
               resolvedEntityList = entities[newRefId]
            for resolvedEntity in resolvedEntityList:
               entityType, hostName, entityName, extraKey, uuid = resolvedEntity
               objKey = entityName or hostName
               if extraKey:
                  objKey = extraKey
               if not hostName:
                  elementTemp = 'entityType=\"%s\",objKey=\"%s\",object=\"%s:%s\"' % (
                  entityType, uuid, entityType, uuid)
               else:
                  elementTemp = 'entityType=\"%s\",host=\"%s\",objKey=\"%s\",object=\"%s:%s-%s\"' \
                                % (entityType, hostName, objKey, hostName,
                                   entityType, entityName)
               label = newlabel

               labelValues = ['%s,%s value=%s %s' % (label, elementTemp, val, ts)
                              for ts, val in itertools.izip(dates, values)
                              if val not in {"None", ""}]
               # logging.info(labelValues[0])
               dataList.extend(labelValues)

      startWaitTime = time.time()
      while gQueue.full():
         time.sleep(0.1)
      with producerLock:
         self.waitQueueInProducer += (time.time() - startWaitTime)

      entities = {}
      dataList = []
      startTime = time.time()
      xmlData = ET.fromstring(line)
      try:
         for metricCsv in xmlData:
            entityRefId = self._EscapeSpace(str(metricCsv[0].text))
            sampleInfo = metricCsv[1].text
            metricValue = metricCsv[2:]
            if sampleInfo == "":
               # There were no samples collected, so skip this one
               continue
            try:
               dates = self._ProcessSampleInfo(sampleInfo)
            except Exception as e:
               logging.exception("Failed to process sample info : %s" % (e))


            _processEntityWithValue(dataList, dates, metricValue, entityRefId, entities)
            if len(dataList) > INFLUX_BATCH * 2.0:
               while gQueue.full():
                  time.sleep(0.1)
               gQueue.put(dataList)
               dataList = [] # new dataList
               # the matched consumer thread is launched
               result = consumer.apply_async(self.FlushBatchDataThreading,
                                             (writeFn, lineIndex,))
               consumerResult.append(result)

      except:
         import traceback
         logging.info(traceback.format_exc())
      gEntities.extend(list(entities.keys()))

      startWaitTime = time.time()
      with producerLock:
         self.waitQueueInProducer += (time.time() - startWaitTime)
         self.parsingTime += (time.time() - startTime)

      if len(dataList) > 0:
         while gQueue.full():
            time.sleep(0.1)
         gQueue.put(dataList)
         # the matched consumer thread is launched
         result = consumer.apply_async(self.FlushBatchDataThreading, (writeFn, lineIndex,))
         consumerResult.append(result)

   def ParseVmodl(self, vmodl):
      logInfo = {}
      entities = set()
      for metricCsv in vmodl:
         if metricCsv.sampleInfo == "":
            # There were no samples collected, so skip this one
            continue
         try:
            dates = self._ProcessSampleInfo(metricCsv.sampleInfo)
         except Exception as e:
            logging.exception("Failed to process sample info : %s" % (e))
         for value in metricCsv.value:
            label = value.metricId.label
            try:
               self._ProcessAndInsertDataPoint(
                  label, metricCsv.entityRefId, dates, value.values,
                  entities, logInfo
               )
            except Exception as e:
               logging.exception("Failed to parse value: %s" % (e))
      return entities

   def ParseJson(self, dumpFp):
      logInfo = {}
      entities = set()
      for metricCsv in json.load(dumpFp):
         if metricCsv['sampleInfo'] == "":
            # There were no samples collected, so skip this one
            continue
         dates = self._ProcessSampleInfo(metricCsv['sampleInfo'])
         for value in metricCsv['value']:
            label = value['metricId']['label']

            self._ProcessAndInsertDataPoint(
               label, metricCsv['entityRefId'],
               dates, value['values'],
               entities, logInfo
            )
      self._ProcessEntities(entities, logInfo)

   # Datestring: Date in format specified in self.dateFormat
   def ConvertTimestamp(self, datestring):
      timeStamp = time.mktime(datetime.datetime.strptime(datestring, self.dateFormat).timetuple())
      timeStampString = "%d" % (timeStamp)
      return timeStampString

   def FormatEntry(self, timestamp, entityType, hostName, entityName, metric, value, extraKey=None):
      entityType = self._EscapeSpace(entityType)
      hostName = self._EscapeSpace(hostName)
      entityName = self._EscapeSpace(entityName)

      objKey = entityName or hostName
      if extraKey:
         objKey = extraKey

      # Indexing:
      # Repeat dashboards use queries based on "object" tag (prefix) match
      # NoRepeat dashboards use queries based on "entityType" and "host" match, with a "objType" group by.
      #   XXX: However, "object" is made up of hostName and entityType,
      #        so a prefix match is the same as a entityType+host match
      #
      # Values:
      # Currently we store only a single value per measurement under the name "value".
      # However, for a given entity we will store many measurements at the same timestamp
      # all sharing the same tags. That bloats the index unnessarily.
      if not hostName:
         element = '%s,object=\"%s\",entityType=\"%s\" value=%s %s' \
                    % (metric, entityType, entityType, value, timestamp)
      else:
         element = '%s,object=\"%s:%s-%s\",host=\"%s\",objKey=\"%s\",entityType=\"%s\" value=%s %s' \
                    % (metric, hostName, entityType, entityName, hostName, objKey, entityType, value, timestamp)
      return element

   # InfluxDB API can batch entries separated by new-line character
   def GetBatchData(self):
      self._ProcessTaggedDataPoints()
      return self.data

   def FlushBatchDataThreading(self, writeFn, index):
      startWaitTime = time.time()
      while gQueue.empty():
         time.sleep(0.1)
      with consumerLock:
         self.waitQueueInConsumer += (time.time() - startWaitTime)

      # checking queue is not empty
      startTime = time.time()
      dataList = gQueue.get()

      self.dataPointsNum += len(dataList)
      if len(dataList) == 0:
         logging.info("Processing %s/%s lines for dataList len %d" % (index, self.fileNumLines, len(dataList)))
      progress = "Processing %s/%s lines, batching dataPoints %s" % (
      index, self.fileNumLines, self.dataPointsNum)
      writeFn(dataList, progress)

      del dataList # clean memory
      with consumerLock:
         self.influxTime += (time.time() - startTime)

      logging.info("The elapsed time for processing data %f and influxDb %f" % (
      self.parsingTime, self.influxTime))

   def FlushBatchData(self, writeFn, minDataPoints = 0):
      self._ProcessTaggedDataPoints()
      if len(self.data) > minDataPoints:
         writeFn(self.data)
         self.dataPointsNum += len(self.data)
         self.data = []

   def Insert(self, elements):
      self.data.extend(elements)


   def PrintCacheSize(self):
      print(len(self.timeStampCache))

   def ParseText(self, path):
      # Nested function to parse
      def getValue(str):
         if '\'' in str:
            l = str.split('\'')
            return l[1]
         elif 'unset' in str:
            return 'unset'
         else:
            raise Exception('Parsing error')

      entity = ''
      metric = ''
      val = ''
      dates= []
      f = open(path)
      logInfo = {}
      entities = set()
      for line in f.readlines():
         if 'sampleInfo' in line:
            sampleInfoKey = getValue(line)
            # Caching
            dates = self._ProcessSampleInfo(sampleInfoKey)
         elif 'entityRefId' in line:
            entity = getValue(line)
         elif "label" in line:
            metric = getValue(line)
         elif "values" in line:
            val = getValue(line)
            if dates and entity and metric and val:
               self._ProcessAndInsertDataPoint(
                  metric, entity, dates, val,
                  entities, logInfo
               )

      self._ProcessEntities(entities, logInfo)

#      self.PrintCacheSize()

def main():
   parser = VSANPerfDumpParser("testData/python_usrlibvmwarevsanperfsvcvsan-perfsvc-statuspyc-perf_stats_with_dump.txt", "SoapParser");
   batchData = parser.Parse(None)
#   print "\n".join(batchData)

if __name__ == "__main__":
    main()


#################################### Construction for Python API #####################################
#            element = '%s host=%s value=%s %s\n' % (measurementName, entityName, vl, dt)
#         for dt, vl in zip(dates, values):
#            element = {
#               "measurement": measurementName,
#               "tags": {
#                   "host#": entityName,
#               },
#               "time": time.mktime(datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S').timetuple()),
#               "fields": {
#                   "value": vl
#               }
#            }
