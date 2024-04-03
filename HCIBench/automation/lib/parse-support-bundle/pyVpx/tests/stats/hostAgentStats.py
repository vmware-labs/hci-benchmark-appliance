#!/usr/bin/python

# Copyright (c) 2022 VMware, Inc. All rights reserved.
# VMware Confidential

from __future__ import print_function

__author__ = 'VMware, Inc.'
__copyright__   = "Copyright 2022 VMware, Inc. "

import sys
from string import Formatter
from struct import *
from optparse import OptionParser
from datetime import tzinfo, timedelta, datetime

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

def printAlways(*args, **kwargs):
   print(*args, file=sys.stderr, **kwargs)

verbose = False
def printVerbose(*args, **kwargs):
   if verbose:
      printAlways(args, kwargs)

def get_options():
    """
    Supports the command-line arguments listed below
    """

    parser = OptionParser()
    parser.add_option("-s", "--stats",
                      default="hostAgentStats-20.stats",
                      help=".stats file from the ESXi host "
                           "[default=hostAgentStats-20.stats]")
    parser.add_option("-i", "--idmap",
                      default="hostAgentStats.idMap",
                      help=".idMap file corresponding to the specified .stats file "
                           "[default=hostAgentStats.idMap]")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="print verbose information in the stderr stream")
    parser.add_option("-m", "--meta",
                      action="store_true", dest="printStatInfos", default=False,
                      help="print stats meta-information into stderr stream")
    parser.add_option("-g", "--show-missing",
                      action="store_true", dest="show_missing", default=False,
                      help="print only time-stamps ranges of missing stats to the stdout stream")
    parser.add_option("-o", "--output",
                      default="csv",
                      help="output format of the data printed in the stdout. "
                           "Supported: csv, pdh, raw [default=csv]")
    (options, _) = parser.parse_args()
    return options

ROLLUPS = [ "none", "avg", "max", "min" ]

class StatInfo:
   def __init__(self, header, entityId, statName):
      self.entityId = entityId
      self.statName = statName
      self.rollups = {}
      for i in range(header[6]):
         self.rollups[ROLLUPS[header[7 + (i * 2)]]] = header[7 + (i * 2) + 1]

   def getStatId(rollup = "none"):
      return self.rollups[rollup]

   def __str__(self):
       result = "%s@%s(" % (self.entityId, self.statName)
       for key in self.rollups.keys():
         result += "%s=%d," % (key, self.rollups[key])
       result += ")"
       return result

   def __repr__(self):
       return self.__str__()

def readIdMap(idmapFilename, printStatInfos=False):
   printVerbose("Reading %s ..." % (idmapFilename))
   statInfos = []

   idmapf = open(idmapFilename, "rb")
   try:
      headerArr = idmapf.read(32)
      header = unpack("QBBHIQQ", headerArr)
      if header[0] != 0x50414D5354415453:
         printVerbose("Error: Wrong signature %0X (expected %0X)" % (header[0], 0x50414D5354415453))
         return statInfos

      printVerbose("Info:     Signature = 0x%0X" % (header[0]))
      version = header[1]
      printVerbose("Info:       Version = %d" % (version))
      printVerbose("Info:     Reserved0 = 0x%0X" % (header[2]))
      printVerbose("Info:     Reserved1 = 0x%0X" % (header[3]))
      printVerbose("Info:  MaxCounterId = %d" % (header[4]))
      printVerbose("Info:  FileFreeSize = %d bytes" % (header[5]))
      offset = header[6]
      printVerbose("Info: FirstPosition = %d" % (offset))

      if version == 1:
         while True:
            idmapf.seek(offset)
            recordHdrArr = idmapf.read(74)
            recordHdr = unpack("=QQQQiBBBQBQBQBQ", recordHdrArr)
            if recordHdr[0] != 0x44455050414D4449:
               printVerbose("Error: Record @%d has wrong singature %0X (expected %0X) - skipping the rest" % (offset, recordHdr[0], 0x44455050414D4449))
               return statInfos
            if recordHdr[6] > 4:
               printVerbose("Error: Record @%d has wrong number of rollups %d (>4) - skipping the rest" % (offset, recordHdr[6]))
               return statInfos

            entityIdLenArr = idmapf.read(4)
            entityIdLen = unpack("I", entityIdLenArr)
            entityId = idmapf.read(entityIdLen[0])
            entityId = entityId[:-1]
            statNameLenArr = idmapf.read(4)
            statNameLen = unpack("I", statNameLenArr)
            statName = idmapf.read(statNameLen[0])
            statName = statName[:-1]

            statInfo = StatInfo(recordHdr, entityId, statName)
            statInfos.append(statInfo)

            if printStatInfos:
               printAlways("Info: statInfo@%d = %s" % (offset, str(statInfo)))

            if recordHdr[3] == 0:
               break
            offset += recordHdr[3]
      else:
         printVerbose("Error: Unknown file version %d" % (version))
         return statInfos

   finally:
      idmapf.close()

   printVerbose("... read %d entries" % (len(statInfos)))
   return statInfos

def readStats(statsFilename, statInfos):
   printVerbose("Reading %s ..." % (statsFilename))

   stats = open(statsFilename, "rb")
   try:
      headerArr = stats.read(8)
      header = unpack("II", headerArr)
      numSamples = header[0]
      printVerbose("Info:  NumberSamples = %d" % (numSamples))
      printVerbose("Info: SamplingPeriod = %d seconds" % (header[1]))

      formatStr = "%dQ" % (numSamples)
      timeStampsArr = stats.read(numSamples * 8)
      timeStamps = unpack(formatStr, timeStampsArr)

      allStats = []
      numRead = 0
      for statInfo in statInfos:
         sampleVectors = {}
         for rollup in statInfo.rollups:
            stats.seek(8 + (numSamples * 8) + statInfo.rollups[rollup] * (12 + numSamples * 8))
            vecHeaderArr = stats.read(12)
            vecHeader = unpack("=IQ", vecHeaderArr)
            if vecHeader[0] != 0:
               samplesArr = stats.read(numSamples * 8)
               samples = unpack(formatStr, samplesArr)
               sampleVectors[rollup] = (vecHeader[1], samples)
               numRead = numRead + 1
            else:
               printVerbose("%s@%s.%s is deleted" % (statInfo.entityId, statInfo.statName, rollup))
         if len(sampleVectors) > 0:
            allStats.append((statInfo, sampleVectors))

   finally:
      stats.close()

   printVerbose("... read %d stats" % (numRead))
   return timeStamps, allStats

def printStatsRaw(stats):
   timeStamps = stats[0]
   print("TimeStamps: %s" % (str(timeStamps)))

   for stat in stats[1]:
      statInfo = stat[0]
      for rollup in statInfo.rollups:
         samples = stat[1][rollup][1]
         print("%s@%s.%s: %s" % (statInfo.entityId, statInfo.statName, rollup, str(samples)))

def convertTimeStamps(timeStamps, earliestSample, latestSample):
   timeStampsArr = []
   i = earliestSample
   while True:
      dt = datetime.fromtimestamp(timeStamps[i], tz=UTC())
      timeStampsArr.append(dt)
      if i == latestSample: break;
      i = (i + 1) % len(timeStamps)
   return timeStampsArr

def convertSamples(timeStamps, samples, earliestSample, latestSample):
   samplesArr = []
   latestValidTimeStamp = samples[0]
   samples = samples[1]
   i = earliestSample
   while True:
      if latestValidTimeStamp >= timeStamps[i]:
         samplesArr.append(samples[i])
      else:
         # missing sample
         samplesArr.append(-1)
      if i == latestSample: break;
      i = (i + 1) % len(samples)
   return samplesArr

def convertStats(stats):
   printVerbose("Converting stats ...")

   timeStamps = stats[0]
   latestSample = -1
   earliestSample = -1
   for i in range(len(timeStamps)):
      if timeStamps[i] != -1:
         if latestSample == -1 or timeStamps[latestSample] < timeStamps[i]:
            latestSample = i
         if earliestSample == -1 or timeStamps[earliestSample] > timeStamps[i]:
            earliestSample = i

   printVerbose("Info:       latestSampleIndex = %d" % (latestSample))
   printVerbose("Info:   latestSampleTimeStamp = %d seconds" % (timeStamps[latestSample]))
   printVerbose("Info:     earliestSampleIndex = %d" % (earliestSample))
   printVerbose("Info: earliestSampleTimeStamp = %d seconds" % (timeStamps[earliestSample]))

   allStats = []

   for stat in stats[1]:
      statInfo = stat[0]
      sampleVectors = {}
      for rollup in statInfo.rollups:
         samples = stat[1][rollup]
         samples = convertSamples(timeStamps, samples, earliestSample, latestSample)
         sampleVectors[rollup] = samples
      if len(sampleVectors) > 0:
         allStats.append((statInfo, sampleVectors))

   timeStamps = convertTimeStamps(timeStamps, earliestSample, latestSample)

   printVerbose("... done!")
   return timeStamps, allStats

def printMissingStats(stats):
   timeStamps = stats[0]
   print("TimeStamps: [%s; %s]" % (str(timeStamps[0]), str(timeStamps[-1])))

   for stat in stats[1]:
      statInfo = stat[0]
      for rollup in statInfo.rollups:
         ranges = ""
         samples = stat[1][rollup]

         firstMissing = None
         totalMissing = 0
         missingNum = 0
         for idx in range(len(timeStamps)):
            if samples[idx] == 18446744073709551615: # 18446744073709551615 == -1 indicates missing sample
               if not firstMissing:
                  firstMissing = str(timeStamps[idx])
               missingNum = missingNum + 1

               if firstMissing and idx == len(timeStamps) - 1:
                  rangeOne = None
                  if missingNum > 1:
                     rangeOne = "[%s; %s]" % (firstMissing, str(timeStamps[idx]))
                  else:
                     rangeOne = firstMissing

                  if ranges:
                     ranges += ", "
                  ranges += rangeOne
                  totalMissing = totalMissing + missingNum
                  if totalMissing == len(timeStamps):
                     ranges += " - entire period"
            else:
               if firstMissing:
                  rangeOne = None
                  if missingNum > 1 and idx > 0:
                     rangeOne = "[%s; %s]" % (firstMissing, str(timeStamps[idx - 1]))
                  else:
                     rangeOne = firstMissing

                  if rangeOne:
                     if ranges:
                        ranges += ", "
                     ranges += rangeOne
                     totalMissing = totalMissing + missingNum

               firstMissing = None
               missingNum = 0

         if ranges:
            print("%s@%s.%s missing %d samples: " % (statInfo.entityId, statInfo.statName, rollup, totalMissing) + ranges)

def sampleToString(sample):
   if sample == 18446744073709551615: # 18446744073709551615 == -1 indicates missing sample
      return "-1"
   else:
      return str(sample)

def printStatsCSV(stats):
   timeStamps = stats[0]
   print("TimeStamps, " + ", ".join(map(str, timeStamps)))

   for stat in stats[1]:
      statInfo = stat[0]
      for rollup in statInfo.rollups:
         samples = stat[1][rollup]
         print("%s@%s.%s, " % (statInfo.entityId, statInfo.statName, rollup) + ", ".join(map(sampleToString, samples)))

def printStatsPDH(stats):
   timeStamps = stats[0]
   stats = stats[1]

   headerLine = "\"(PDH-CSV 4.0)\","
   for stat in stats:
      statInfo = stat[0]
      for rollup in statInfo.rollups:
         parsed = statInfo.statName.split("-", 1)
         group = parsed[0]
         parsed = parsed[1].split("#", 1)
         name = parsed[0]
         instance = ""
         if len(parsed) > 1:
            instance = parsed[1]
         headerLine += "\"\\\\%s\\%s(%s)\%s" % (statInfo.entityId, group, instance, name)
         if rollup != "none":
            headerLine += ".%s" % (rollup)
         headerLine += "\","
   headerLine = headerLine[:-1]
   print(headerLine)

   for t in range(len(timeStamps)):
      timeLine = "\"%s\"," % (timeStamps[t].strftime("%m/%d/%Y %H:%M:%S.000"))
      for stat in stats:
         statInfo = stat[0]
         for rollup in statInfo.rollups:
            samples = stat[1][rollup]
            timeLine += "\"%s\"," % (sampleToString(samples[t]))
      timeLine = timeLine[:-1]
      print(timeLine)

def main(argv):
   options = get_options()
   global verbose
   verbose = options.verbose

   statInfos = readIdMap(options.idmap, options.printStatInfos)
   if len(statInfos) == 0:
      printVerbose("Error: No stats to read")
      return 1

   # TODO: add some sort of query/filter mechanism here
   selected = statInfos # for now: print everything
   stats = readStats(options.stats, selected)

   if options.output == "raw":
      printStatsRaw(stats)
      return 0

   stats = convertStats(stats)

   if options.show_missing:
      printMissingStats(stats)
   elif options.output == "csv":
      printStatsCSV(stats)
   elif options.output == "pdh":
      printStatsPDH(stats)
   else:
      print("Error: Wrong output format specified")
      return 1

   return 0


# Start program
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
