import json
import os
import logging

def parseCmmdsFileByDir(dirname):
   filename = os.path.join(dirname, 'cmmds-tool_find--f-python.txt')
   if not os.path.exists(filename):
      return None
   return parseCmmdsFile(filename)

def parseCmmdsFile(filename):
   cmmdsByUuid = {}
   esaDiskMap = {}
   try:
      with open(filename, 'r') as fp:
         content = fp.read()
         cmmds = None
         try:
            cmmds = eval(content)
         except:
            logging.exception("Parse original cmmds-tool_find--f-python.txt fail, try to parse the file as much as possible.")
            if content.rfind("},\n]") < 0:
               logging.info("File cmmds-tool_find--f-python is not complete")
               index = content.rfind("},\n{")
               if index > 0:
                  content = content[0:index+2] + "]"
            cmmds = eval(content)
         if cmmds:
            for e in cmmds:
               cmmdsByUuid.setdefault(e['uuid'], {})
               cmmdsByUuid[e['uuid']][e['type']] = e
   except:
      logging.exception("Parse cmmds-tool_find--f-python.txt failed.")
   logging.debug("cmmdsByUuid => %s", cmmdsByUuid)
   return cmmdsByUuid

def isConvertedPerfUuidExisting(convertedPerfUuid, cmmdsByUuid):
   # convertedPerfUuid should be in CMMDS and the type should be DISK_PERF_TIER,
   # or it means this is not single tier, then directly return the original uuid 
   entry = cmmdsByUuid.get(convertedPerfUuid)
   return entry and 'DISK_PERF_TIER' in entry

#Given a UUID, the intention of this method is to return a tuple t = (devName, host, parent)
#where devName -> device name of the disk, host -> UUID of the host to which the disk
#belongs. The argument cmmdsByUuid is expected to have this info about which disk
#belongs to which host.
def lookupDisk(uuid, cmmdsByUuid, cache):
   if uuid in cache['disk']:
      return cache['disk'][uuid]
   # LSOM2 changes DISK entry to DISK_CAPACITY_TIER
   entry = cmmdsByUuid.get(uuid, {}).get('DISK') or cmmdsByUuid.get(uuid, {}).get('DISK_CAPACITY_TIER') or cmmdsByUuid.get(uuid, {}).get('DISK_PERF_TIER')
   if not entry:
      return (None, None, None)
   content = json.loads(entry['content'])
   parent = None
   if 'isSsd' in content and not content['isSsd'] and 'ssdUuid' in content:
      parent = lookupDisk(content['ssdUuid'], cmmdsByUuid, cache)
   host = lookupHostName(entry['owner'], cmmdsByUuid, cache)
   if 'devName' in content:
      out = ("%s-%s" % (content['devName'], uuid), host, parent)
   else:
      out = (uuid, host, parent)
   cache['disk'][uuid] = out
   return out

#This method provides a readable, unique identifier for a host which is
#identified by `uuid`. The argument cmmdsByUuid is expected to have this info
#about what readable data can be returned. In case of support bundles, the
#hosts hostname is returned, and for phonehome data, the host MOID is returned.
def lookupHostName(uuid, cmmdsByUuid, cache):
   if uuid in cache['host']:
      return cache['host'][uuid]
   entry = cmmdsByUuid.get(uuid, {}).get('HOSTNAME')
   if entry:
      content = json.loads(entry['content'])
      out = content['hostname']
      cache['host'][uuid] = out
      return out
   else:
      entry = cmmdsByUuid.get(uuid, {}).get('CMMDS_GARBAGE_COLLECTION_TTL')
      if not entry:
         return None
      cache['host'][uuid] = 'hostUuid_' + str(uuid)
      return cache['host'][uuid]

# Example UUIDs:
   # host-memory-heap:5890dccc-3598-ee3a-df0a-020026e21a4a|dom-Client-heap-0x431038f03000
   # host-domclient:5890dccc-3598-ee3a-df0a-020026e21a4a
   # host-domcompmgr:5890dccc-3598-ee3a-df0a-020026e21a4a
# @Return: (entityType - cache-disk, capacity-disk, host-memory-heap, etc
#           host       - host name (None if host name is not found)
#           entityValue - the ID of entity (in case of disk, the uuid of disk)
#          )

def lookupEntityId(entityRefId, cmmdsByUuid, cache):
   entityValue = ""
   extraKey = None
   logging.debug("query uuid to be processed: %s" % (entityRefId))
   try:
      entityType, nodeId = entityRefId.split(":", 1)
      nodeIdParts = nodeId.split("|")
      uuid = nodeIdParts[0]
      if len(nodeIdParts) > 1:
         entityValue = "%s" % "-".join(nodeIdParts[1:])
      if entityType == 'disk-group':
         entityType = 'cache-disk'

      #populate any cluster entities.
      if entityType.startswith('cluster-'):
         return [(entityType, "cluster-%s" % uuid, "", extraKey, uuid)]
   except Exception as e:
      logging.exception("Failed to split UUID: %s" % (uuid))
   try:
      host = lookupHostName(uuid, cmmdsByUuid, cache)
      if host:
         logging.debug("Found host only -- %s, %s, %s." % (entityType, host, entityValue))
         return [(entityType, host, entityValue, extraKey, uuid)]
   except Exception as e:
      logging.exception("Failed to lookup host name for UUID %s: %s" % (uuid, e))

   try:
      disk, host, parent = lookupDisk(uuid, cmmdsByUuid, cache)
      entityDetails = []
      if disk:
         logging.debug("Found disk only -- %s, %s, %s." % (entityType, host, disk))
         if "splinterdb" in entityType:
            entityValue = "%s" % "-".join(nodeIdParts)
            entityDetails.append((entityType, host, entityValue, None, None))
            # Hack for lsom2 dashboards
            entityType = 'lsom2-io-stats'

         entityDetails.append((entityType, host, disk, extraKey, uuid))
         return entityDetails
   except Exception as e:
      logging.exception("Failed to lookup disk name for UUID %s: %s" % (uuid, e))

   logging.debug("Found no useful info: %s" % entityRefId)
   # If the metrics not host or disk, it will direct show entity type and uuid.
   # For world id info, we need combine show the worlds from one host together
   if 'world' in entityType.lower():
      return [(entityType, uuid, entityRefId, extraKey, None)]
   return [(entityType, nodeId, entityRefId, extraKey, None)]
