import config
import getopt
import json
import logging
import os
import requests
import sys
import glob
import time
import traceback
from PerfStatsParser import VSANPerfDumpParser, chunks, getValidParsers, INFLUX_BATCH
from grafanaUtil import GrafanaClient
from dashboardUtil import DashboardGenerator
#from humbugRedis import HumbugRedisInstance as Redis
import hashlib

def isGrafanaV8():
   conf = config.HumbugConfig.config
   g_host = conf['GRAFANA_HOST']
   g_port = conf['GRAFANA_PORT']
   g_user = conf['GRAFANA_USER']
   g_pass = conf['GRAFANA_PASS']

   grafana_client = GrafanaClient(g_host, g_port, g_user, g_pass)
   return grafana_client.isNewGrafana()

def setupGrafana(bundle, entities, graphFilename):
   db_name = bundle

   conf = config.HumbugConfig.config
   g_host = conf['GRAFANA_HOST']
   g_port = conf['GRAFANA_PORT']
   g_user = conf['GRAFANA_USER']
   g_pass = conf['GRAFANA_PASS']
   db_host = conf['INFLUXDB_EXT_HOST']
   db_port = conf['INFLUXDB_EXT_PORT']
   db_user = conf['INFLUXDB_USER']
   db_pass = conf['INFLUXDB_PASS']

   grafana_client = GrafanaClient(g_host, g_port, g_user, g_pass)
   grafana_client.createDatasource(db_name, db_user, db_pass, db_host, db_port)

   # new grafana no need delete and create dashboards
   if grafana_client.isNewGrafana():
      return ""

   # Do not attempt to parallelize, as that will lead to errors,
   # presumably due to references between dashboards
   dbGenerator = DashboardGenerator(graphFilename)


   dashboardPostfix, dbs = dbGenerator.getDashboards(db_name, entities)

   for db in dbs:
      try:
         grafana_client.createDashboard(db)
      except Exception as e:
         logging.error("Failed to create dashboard: %s" % str(e))
         continue

   # dashboard 6 characters hash
   return dashboardPostfix

def CreateInfluxDatabase(bundle):
   # Create Database
   retention = ""
   if False:
       retention = "WITH DURATION 21d"
   dbCreateCmd = 'CREATE DATABASE %s %s' % (bundle, retention)
   INFLUXDB_URL = config.HumbugConfig.config['INFLUXDB_URL']
   result = requests.post(
      "%s/query" % INFLUXDB_URL,
      data={'q': dbCreateCmd})
   if result.status_code / 100 != 2:  # Status code 2xx is success
      logging.error("Failed to create influxDB database")

def WriteInfluxPoints(session, batchData, bundle):
   INFLUXDB_URL = config.HumbugConfig.config['INFLUXDB_URL']
   dbWriteURL = "%s/write?db=%s&precision=s" % (INFLUXDB_URL, bundle)
   logging.debug("Total amount of data points: %d" % len(batchData))
   i = 0
   batchSizeInflation = int(INFLUX_BATCH * 1.1)
   for chunk in chunks(batchData, INFLUX_BATCH):
      i += 1
      logging.debug("Writing data chunk %d of length %d" % (i, len(chunk)))
      body = "\n".join(chunk)
      # Write Data
      result = session.post(dbWriteURL, data = body)
      if result.status_code / 100 != 2:  # Status code 2xx is success
         logging.error("Failed to write batch data to influxDB : %d (%s)" % (result.status_code, result.text))
         if result.status_code == 503:
            break

def GetDbTimerange(bundle):
   def singleValueQuery(query):
      INFLUXDB_URL = config.HumbugConfig.config['INFLUXDB_URL']
      result = requests.get(
         '%s/query' % INFLUXDB_URL,
         params = {'db':bundle, 'q': query, 'epoch':'ms'})
      if result.status_code / 100 != 2:  # Status code 2xx is success
         # print stacktrace of exception.
         logging.exception("Failed to get limit for time range.")
         raise Exception("Failed to get lower limit for time range")
      result = json.loads(result.text)
      return result.get('results')[0].get('series')[0].get('values')[0][0]

   # Get time range
   smallestTS = "select first(value) from iops"
   largestTS = "select last(value) from iops"

   lowTS = None
   highTS = None
   #Attempt to get the time ranges from the iops(more common) measurement, if not
   #return none and caller have to decide on range.
   try:
      lowTS = singleValueQuery(smallestTS)
      highTS = singleValueQuery(largestTS)
   except:
      pass

   return (lowTS, highTS)

def GenerateDashboardURL(bundle, bundlePostfix):
   url = None
   lowTS = None
   highTS = None

   lowTS, highTS = GetDbTimerange(bundle)

   if (lowTS == None) or (highTS == None):
      # If DB does not exists/fail to query timerange. make default
      # timerange as now-14d to now.
      logging.info ("Setting timerange as 'now-14d to now'.")
      lowTS = "now-14d"
      highTS = "now"

   if bundlePostfix:
      url = "%s/dashboard/db/dom-owner-%s?from=%s&to=%s&var-SupportBundle=%s&var-dashboardDB=dashboardDB&var-DomOwner=All" % (config.HumbugConfig.config['GRAFANA_EXT_URL'], bundlePostfix, lowTS, highTS, bundle)
   else:
      url = "%s/d/vsan_client/dom-client?orgId=1&from=%s&to=%s&var-datasource=%s" % (config.HumbugConfig.config['GRAFANA_EXT_URL'], lowTS, highTS, bundle)

   return url

def printUsage():
   logging.error("python perf_analysis.py -f <fileName> -p <parserType> -n <supportBundleName> -i <internalHumbugIp> -e <externalHumbugIp> -d <hostDiskMapping>")

def validateArgs(fileName, parserType, name, grafanaIntIp, grafanaExtIp, hostDiskMapFile):
   if not name:
      logging.error("Missing name of support bundle. Use option: -n (or --name)")
      return False
   if not fileName:
      logging.error("Missing filename. Use option: -f (or --fileName)")
      return False
   if not parserType or parserType not in getValidParsers():
      logging.error("Enter valid parser. Use option: --parser. Valid parsers: %s" % getValidParsers())
      return False
   if not grafanaIntIp and not grafanaExtIp:
      logging.error("Enter a valid internal or extern ip for grafana. Use options --int-ip or --ext-ip")
      return False
   return True


def main(argv):
   """
   Main function for the script.

   Value for args from a sample run:
      Name: esx_sc_rdops_vm17_dhcp_6_6_eng_vmware_com_2017_02_02__18_39_1000506887
      FileName: /ssd/humbug/backend1/extractor/extracted/0/04bba0f15fc17e56d9fe59b17f029348/esx-sc-rdops-vm17-dhcp-6-6.eng.vmware.com-2017-02-02--18.39-1000506887/commands/python_usrlibvmwarevsanperfsvcvsan-perfsvc-statuspyc-perf_stats_with_dump.txt
      Internal IP: haproxy1
      External IP: 10.192.191.229
      Host disk mapping file: None
      Parser: SoapParser
   """
   try:
      opts, args = getopt.getopt(argv,"hf:p:i:e:d:n:g:sz",["fileName=", "parser=", "int-ip=", "ext-ip=", "name=",
                                                         "host-disk-map-file=", "port=", "skipgrafana", "skipinflux"])
   except getopt.GetoptError:
      logging.error('perf_analysis.py -f <fileName> -p <parser>')
      sys.exit(2)
   grafanaIntIp = '127.0.0.1'
   grafanaExtIp = '127.0.0.1'
   name = None
   fileName = None
   parserType = None
   grafanaIntIp = None
   grafanaExtIp = None
   hostDiskMapFile = None
   port = 3000
   skipGrafana = False
   skipInflux = False
   for opt, arg in opts:
      if opt == '-h':
         printUsage()
         sys.exit()
      if opt in ("-f", "--fileName"):
         fileName = arg
         os.environ['PERF_DUMP_PATH'] = '/'.join(fileName.split('/')[:-1])
      if opt in ("-p", "--parser"):
         parserType = arg
      if opt in ("-n", "--name"):
         name = arg
      if opt in ("-i", "--int-ip"):
         grafanaIntIp = arg
      if opt in ("-e", "--ext-ip"):
         grafanaExtIp = arg
      if opt in ("-d", "--host-disk-map-file"):
         hostDiskMapFile = arg
      if opt in ("-g", "--port"):
         port = int(arg)
      if opt in ("-s", "--skipgrafana"):
         skipGrafana = True
      if opt in ("-x", "--skipinflux"):
         skipInflux = True

   if not validateArgs(fileName, parserType, name, grafanaIntIp, grafanaExtIp, hostDiskMapFile):
      printUsage()
      sys.exit(3)


   config.HumbugConfig.configParams(grafanaIntIp, grafanaExtIp, port)
   bundle = name.replace('.', '_').replace('-', '_')
   redisKey = '%s_python' % name
   #redis = Redis.instance()

   def RedisUpdatePerfLink():
      if False: #redis:
         # we can give perf url at this step for avoiding parsing and inserting perf data points
         if isGrafanaV8():
            bundlePostfix = ''
         else:
            bundlePostfix = hashlib.sha1(bundle).hexdigest()[0:5]
         perfUrlLink = GenerateDashboardURL(bundle, bundlePostfix)
         redis.hset(redisKey, 'perflink', perfUrlLink)

   def RedisUpdateError(errorStr):
      if False: #redis:
         redis.hset(redisKey, 'error', errorStr)

   _config_default_logger(bundle)


   '''logging.debug("Parsed params, checking if DB exists ...")
   # Check if there is some data already uploaded
   lowTS = None
   highTS = None
   try:
      lowTS, highTS = GetDbTimerange(bundle)
      lowTS = int(lowTS) / 1000
      highTS = int(highTS) / 1000
      logging.info("lowTS %d, highTS %d" % (lowTS, highTS))
   except Exception as ex:
      logging.exception("Got exception from DB query: %s" % str(ex))
      # Exception means the DB didn't exist
      pass'''


   # 1) Create influx DB that will store all our metrics for the given bundle
   logging.debug("Create DB and write data points")
   if False: #redis:
      redis.hset(redisKey, 'progress', 'CreatingInfluxDb')
      redis.expire(redisKey, 24 * 60 * 60) # expired within one day
   try:
      CreateInfluxDatabase(bundle)
   except Exception as e:
      errorStr = "Failed to create database and write datapoints: %s" % (e)
      logging.error(errorStr)
      RedisUpdateError(errorStr)

   # Use a session so we keep reusing the same TCP connection
   stats = {'numDataPoints': 0}
   requestsSession = requests.Session()
   def FlushData(batchData, progressStr=None):
      if skipInflux:
         logging.info("Skipping writing %u data points to influx DB" % len(batchData))
         return
      if False: #redisKey and redis and progressStr:
         redis.hset(redisKey, 'progress', progressStr)
         logging.info(progressStr)

      stats['numDataPoints'] += len(batchData)
      WriteInfluxPoints(requestsSession, batchData, bundle)
      logging.info("Writing %u data points to influx DB" % len(batchData))

   # 2) Parse the input, write out data to influx DB
   logging.info("Parsing the dump file ...")
   if isGrafanaV8():
      bundlePostfix = setupGrafana(bundle, [], "")
   RedisUpdatePerfLink()

   t1 = time.time()
   entities = []
   try:
      parser = VSANPerfDumpParser(fileName, parserType, hostDiskMapFile, redisKey)
      parser.Parse(FlushData)
      entities.extend(parser.entities)
   except Exception as e:
      errorStr = "Failed to parse data: %s" % (e)
      logging.info(traceback.format_exc())
      logging.error(errorStr)
      RedisUpdateError(errorStr)
      return

   # P1 & P2 data parsing and write out to influx DB
   t2 = time.time()
   try:
      files =[]
      for fileprefix in ["*perf_stats_with_dump*", "*selective_with_dump*", "*ioinsight_stats_with_dump*"]:
         filetype = os.path.join(os.path.dirname(os.path.realpath(fileName)), fileprefix)
         files.extend(glob.glob(filetype))
      if files and fileName in files:
         files.remove(fileName)
      else:
         files = [fileName]
      logging.info("Additional perf files %s" % str(files))
      for perfFile in files:
        try:
            logging.info("Loading file %s" % perfFile)
            parser = VSANPerfDumpParser(perfFile, parserType, hostDiskMapFile, redisKey)
            parser.Parse(FlushData)
            entities.extend(parser.entities)
            entities = {frozenset(item.items()): item for item in entities}.values()
            logging.debug("Done: numSkipped: %s, numValues: %s" % (
                  parser.numSkipped, parser.numValues))
            RedisUpdatePerfLink()
        except Exception as ex:
            logging.error("Failed to file: %s:  %s" % (perfFile, traceback.format_exc()))
   except Exception as e:
      logging.error("Failed to parse data: %s" % (e))


   #logging.info("entities = %s" % json.dumps(entities, indent=2))

   t3 = time.time()

   t4 = time.time()
   # 4) Register bundle DB with Grafana, create/adjust our dashboards
   # creating Grafana dashboards very quickly, so mark redis progress done
   # also add error msg if creating Grafana dashboards has issues and report to UI
   if False: #redis:
      redis.hset(redisKey, 'progress', 'finished')
   bundlePostfix = ""
   try:
      if not skipGrafana:
         graphFilename = os.path.join(
            os.path.dirname(fileName), 'perfsvc-graph_info.json')
         if not os.path.exists(graphFilename):
            graphFilename = None
         if not isGrafanaV8():
            bundlePostfix = setupGrafana(bundle, entities, graphFilename)
   except Exception as e:
      errorStr = "Failed to setup grafana: %s" % (e)
      logging.error(errorStr)
      RedisUpdateError(errorStr)
   t5 = time.time()

   logging.info("Took: parse=%.3fs, uploadmetrics=%.3fs, metaDB=%.3fs, grafana=%.3fs, total=%.3fs" % (t2 - t1, t3 - t2, t4 - t3, t5 - t4, t5 - t1))
   logging.info("Num data points: %u" % stats['numDataPoints'])

   # 5) Craft output
   url = GenerateDashboardURL(bundle, bundlePostfix)
   if False: #redis:
      redis.hset(redisKey, 'perflink', url)
   logging.info(url)
   print(url)


def _config_default_logger(bundle_name):
   root = logging.getLogger()
   root.setLevel(logging.DEBUG)

   default_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

   path_to_logfile = os.environ.get('PERF_DUMP_PATH', '/unicorn/log/')
   log_filename = "%s/%s.stderr.log" % (path_to_logfile, bundle_name)

   fh = logging.FileHandler(log_filename)
   fh.setLevel(logging.INFO)
   fh.setFormatter(default_format)

   ch = logging.StreamHandler(sys.stderr)
   ch.setLevel(logging.INFO)
   ch.setFormatter(default_format)

   root.addHandler(ch)
   root.addHandler(fh)


if __name__ == '__main__':
   main(sys.argv[1:])
