#!/usr/bin/python

import gc
import sys
import atexit
import time
import timeit

import pyVmomi
import pyVim

from pyVmomi.VmomiSupport import newestVersions
from optparse import OptionParser

def GetOptions():
    """
    Supports the command-line arguments listed below
    """
    parser = OptionParser()
    parser.add_option("-H", "--host",
                      default="sof-40609-srv",
                      help="Remote host to connect to.")
    parser.add_option("-e", "--endpoint",
                      default=None,
                      help="Specify which StatsRegistry endpoint to use (all by default).")
    parser.add_option("-u", "--user",
                      default="root",
                      help="User name to use when connecting to hostd.")
    parser.add_option("-p", "--password",
                      default="",
                      help="Password to use when connecting to hostd.")
    parser.add_option("-s", "--samples",
                      type="int", default=1,
                      help="Number of samples to be taken (-1 == infinite).")
    parser.add_option("-i", "--interval",
                      type="int", default=1,
                      help="Interval (in seconds) between samplings.")
    parser.add_option("-v", "--verbose",
                      action="store_true", default=False,
                      help="Print the received stats instances on screen.")
    parser.add_option("-k", "--keep",
                      action="store_true", default=False,
                      help="Whether to keep the created queries on the server.")
    (options, _) = parser.parse_args()
    return options


class Attribute:
   def __init__(self, name, type, wildcard):
      self.name = name
      self.type = type
      self.wildcard = wildcard

   def __str__(self):
       return "%s:%s" % (self.name, self.type)

   def __repr__(self):
       return self.__str__()

class Counter:
   def __init__(self, id, name, attributes, type, unit, description):
      self.id = id
      self.name = name
      self.attributes = attributes
      self.type = type
      self.unit = unit
      self.description = description

   def __str__(self):
      attributes = ''
      for attr in self.attributes:
         if attributes != '':
            attributes += ', '
         attributes += str(attr)
      return "%d: %s(%s) [%s, %s]: %s" % (self.id, self.name, attributes, self.type, self.unit, self.description)

   def __repr__(self):
       return self.__str__()

class Stat:
   def __init__(self, cntr, attributesValues):
      self.cntr = cntr
      self.attributesValues = attributesValues

   def __str__(self):
      attributesValues = ''
      for i in range(0, len(self.attributesValues)):
         if attributesValues != '':
            attributesValues += ', '
         attributesValues += self.cntr.attributes[i].name + "='" + self.attributesValues[i] + "'"
      return "%s(%s)" % (self.cntr.name, attributesValues)

   def __repr__(self):
      return self.__str__()

   def __eq__(self, other):
      return self.__dict__ == other.__dict__

def executeQuery(query, timer):
   gcold = gc.isenabled()
   gc.disable()
   try:
      beginTime = timer()
      result = query.Execute();
      endTime = timer()
      elapsedTime = endTime - beginTime
      print("Elapsed %f" % (elapsedTime))
      return result;
   finally:
      if gcold:
         gc.enable()

def TestRawStats(sr):
   print("Testing raw stats for StatsRegistry endpoint:'%s'" % (sr._GetMoId()))
   counters = {}

   #
   # Going to request all possible counters
   #
   rawSpec = pyVmomi.Vim.Stats.Query.Spec()

   #
   # Just for the test - show raw stats, also
   #
   rawStat = sr.QueryRawStatsInt()
   print("Raw counters (%d):" % (len(rawStat)))
   for stat in rawStat:
      statLabel = stat.key
      statId = stat.id
      attributes = []
      attributesValues = []

      request = True
      for attr in stat.statDef.attribute:
         attributes.append(Attribute(attr.name.key, attr.type.key, attr.wildcardAllowed))
         if attr.wildcardAllowed:
            attributesValues.append("*")
         else:
            request = False

      if statId not in counters.keys():
         for attr in stat.statDef.attribute:
            attributes.append(Attribute(attr.name.key, attr.type.key, attr.wildcardAllowed))
         cntr = Counter(stat.id,
                        stat.statDef.name.key,
                        attributes,
                        stat.statDef.type.key,
                        stat.statDef.unit.key,
                        stat.statDef.name.summary)
         counters[statId] = cntr
      print("\t%s" % (counters[statId]))

      if request:
         instance = pyVmomi.Vim.Stats.StatInstance()
         instance.label = statLabel
         instance.id = statId
         if len(attributesValues) > 0:
            instance.attribute = attributesValues
         rawSpec.instance.append(instance)
      else:
         print("\tSkipping to request stat %s. At least one attribute is not supporting wild-card." % (cntr))

   if len(rawSpec.instance) > 0:
      print("Executing query for raw stats: ")
      for inst in rawSpec.instance:
         cntr = counters[inst.id]
         stat = Stat(cntr, inst.attribute)
         print("\t%s" % (stat))

      result = sr.QueryStatValuesInt(rawSpec)
      print("Result (%d):" % (len(result)))
      for value in result:
         cntr = counters[value.id]
         stat = Stat(cntr, value.attribute)

         if (value.value != -9223372036854775808):
            if cntr.unit != 'percent':
               print("\t%s = %d %s" % (stat, value.value, cntr.unit))
            else:
               print("\t%s = %.2f %%" % (stat, float(value.value) / 100))
         else:
            print("\t%s = N/A" % (stat))

def TestCookedStats(sr):
   print("Testing cooked stats for StatsRegistry endpoint:'%s'" % (sr._GetMoId()))
   counters = {}

   #
   # Going to request all possible counters
   #
   querySpec = pyVmomi.Vim.Stats.Query.Spec()

   #
   # Just for the test - show raw stats, also
   #
   supportedStat = sr.supportedStat
   print("Supported counters (%d):" % (len(supportedStat)))
   for stat in supportedStat:
      statLabel = stat.key
      statId = stat.id
      attributes = []
      attributesValues = []

      request = True
      for attr in stat.statDef.attribute:
         attributes.append(Attribute(attr.name.key, attr.type.key, attr.wildcardAllowed))
         if attr.wildcardAllowed:
            attributesValues.append("*")
         else:
            request = False

      # Just for the experiment
      # if (stat.statDef.name.key[0:3] != "cpu" and stat.statDef.name.key[0:3] != "mem") or len(attributes) != 1 or attributes[0].type != "VM":
      #   request = False


      cntr = Counter(statId,
                     stat.statDef.name.key,
                     attributes,
                     stat.statDef.type.key,
                     stat.statDef.unit.key,
                     stat.statDef.name.summary)
      counters[statId] = cntr
      if options.verbose:
         print("\t%s" % (cntr))

      if request:
         instance = pyVmomi.Vim.Stats.StatInstance()
         instance.label = statLabel
         instance.id = statId
         if len(attributesValues) > 0:
            instance.attribute = attributesValues
         querySpec.instance.append(instance)
      else:
         print("\tSkipping to request stat %s. At least one attribute is not supporting wild-card." % (cntr))

   if len(querySpec.instance) > 0:
      #
      # This call is creating a managed object in the HostD
      #
      query = sr.CreateQuery(querySpec)

      if options.verbose:
         print("Executing: ")
         for inst in querySpec.instance:
            cntr = counters[inst.id]
            stat = Stat(cntr, inst.attribute)
            print("\t%s" % (stat))

      timer = time.time

      print("First pass .............")
      result = executeQuery(query, timer)
      previousSampleTS = result.timestamp

      iteration = 1
      while iteration <= options.samples or options.samples == -1:
         print("............. sleeping %d seconds ............." % (options.interval))
         time.sleep(options.interval)

         #
         # We need to do second pass and take the result from it,
         # because many statistics are delta or rate and they need at least two
         # samples in order to produce valid value.
         #
         print("............. iteration %d ............." % (iteration))
         try:
            result = executeQuery(query, timer)
            print("Result sampled between %s and %s (%d):" % (previousSampleTS, result.timestamp, len(result.statValue)))
            if not options.verbose:
               print("Use with --verbose option to see actual result.")
            previousSampleTS = result.timestamp

            #
            # Eventually print the result on the screen?
            #
            stats = None
            for value in result.statValue:
               cntr = counters[value.id]
               stat = Stat(cntr, value.attribute)
               statStr = str(stat)

               if stats is not None:
                  if statStr in stats:
                     raise Exception("Duplicate stat returned: ",  statStr)
                  stats.add(statStr)
               else:
                  stats = set([statStr])

               if options.verbose:
                  if (value.value != -9223372036854775808):
                     if cntr.unit != 'percent':
                        print("\t%s = %d %s" % (statStr, value.value, cntr.unit))
                     else:
                        print("\t%s = %.2f %%" % (statStr, float(value.value) / 100))
                  else:
                     print("\t%s = N/A" % (statStr))

         except Exception as e:
            print("Caught exception '%s' while executing query." % str(e))

         iteration = iteration + 1
   else:
      print("No counters to request!")

def ClearQueries(sr):
   print("Queries available on the server for StatsRegistry endpoint '%s':" % (sr._GetMoId()))
   queries = sr.RetrieveQueriesInt()
   print(queries)

   #
   # Queries should be deleted automatically when the sessions expires.
   # However, here we are testing hostd.stats.Query.destroy() method.
   #
   print("Deleting queries...")
   for q in queries:
      q.Destroy()


def TestStatsRegistryEndpoint(sr):
   print("Testing StatsRegistry endpoint:'%s'" % (sr._GetMoId()))
   #TestRawStats(sr)
   TestCookedStats(sr)

def main():
   from pyVim.connect import SmartConnect, Disconnect
   import ssl

   # Process command line
   global options
   options = GetOptions()

   si = SmartConnect(host = options.host,
                     user = options.user,
                     pwd = options.password,
                     sslContext=ssl._create_unverified_context())

   if not options.keep:
      # If we are going to keep the queries we should not disconnect
      # because the sessions will be destroyed together with all queries.
      atexit.register(Disconnect, si)

   hsi = si.RetrieveInternalContent()
   srEndpoints = hsi.GetStatsRegistry()
   for sr in srEndpoints:
      if options.endpoint is None or sr._GetMoId() == options.endpoint:
         TestStatsRegistryEndpoint(sr)
         if not options.keep:
            ClearQueries(sr)


# Start program
if __name__ == "__main__":
   main()
