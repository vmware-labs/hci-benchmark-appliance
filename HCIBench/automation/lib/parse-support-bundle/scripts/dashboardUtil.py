# -*- coding: utf-8 -*-

import copy
import hashlib
import json
import logging
import os
import traceback
from dashTemplatePatch import getDashboardPatch


class DashboardGenerator:
   ENABLE_NEW_INFLUX_LAYOUT = False
   CURRENT_PATH = os.path.dirname(__file__)
   DASHBOARD_WITH_REPEATS_FILE = os.path.join(CURRENT_PATH, "dashboard.json")
   DASHBOARD_WITHOUT_REPEAT_FILE = os.path.join(CURRENT_PATH, "dashboard_noRepeat.json")

   def __init__(self, graphFilename):
      self.db_with_repeats = self._load_json_file(self.DASHBOARD_WITH_REPEATS_FILE)
      self.db_without_repeats = self._load_json_file(self.DASHBOARD_WITHOUT_REPEAT_FILE)

      if graphFilename and os.path.exists(graphFilename):
         self.extraDashInfo = self._load_json_file(graphFilename)
      else:
         self.extraDashInfo = None

   def _load_json_file(self, filename):
      with open(filename, 'r') as fp:
         return json.load(fp)

   def _set_datasource(cls, db):
      changed = False
      ds = '$SupportBundle'
      for row in db['rows']:
         if 'panels' not in row:
            continue
         for panel in row['panels']:
            if 'datasource' in panel and panel['datasource'] != ds:
               panel['datasource'] = ds
               changed = True
      for temp in db['templating']['list']:
         if temp['name'] in ['host', 'entitySelected',
                             'entityForFullSizedGraphs']:
            if temp['datasource'] != ds:
               temp['datasource'] = ds
               changed = True
      return changed

   def getDashboards(self, bundle, entities):
      origdb = self.db_with_repeats
      origdbNoRepeats = self.db_without_repeats
      extraDashInfo = self.extraDashInfo

      bundlePostfix = self._dashboard_hash(bundle)
      dashboards = getDashboardPatch()

      if extraDashInfo:
         logging.info("Adding additional dashboards: %s" % extraDashInfo.keys())
         dashboards.update(extraDashInfo)

      adminMode = False

      for db in [origdb, origdbNoRepeats]:
         db["editable"] = adminMode
         db["hideControls"] = not adminMode

      dbs = []

      try:
         dbs += self._createDasboardsWithRepeats(bundle, bundlePostfix, dashboards, origdb, entities)
      except Exception as e:
         logging.error(traceback.format_exc())
         raise Exception("Failed to create dashboard with repeats: %s" % (e))

      try:
         dbs += self._createDasboardsWithoutRepeats(bundlePostfix, dashboards, origdbNoRepeats)
      except Exception as e:
         logging.error(traceback.format_exc())
         raise Exception("Failed to create dashboard without repeats: %s" % (e))

      return bundlePostfix, dbs

   def _dashboard_hash(self, bundle):
      return hashlib.sha1(bundle).hexdigest()[0:5]

   def _adjustPanel(self, panel, panelConf, thresholdLine=True):
      panel['title'] = panelConf['title']
      if panelConf.get('description'):
         panel['description'] = panelConf.get('description')
      panel['yaxes'][0]['format'] = panelConf['unit']
      if 'min' in panelConf:
         panel['yaxes'][0]['min'] = panelConf['min']
      if 'max' in panelConf:
         panel['yaxes'][0]['max'] = panelConf['max']

      panel['yaxes'][1]['format'] = panelConf.get('unit_ry', panelConf['unit'])
      if 'min_ry' in panelConf:
         panel['yaxes'][1]['min'] = panelConf['min_ry']
      if 'max_ry' in panelConf:
         panel['yaxes'][1]['max'] = panelConf['max_ry']

      if 'thresholds' in panelConf:
         vals = panelConf['thresholds']
         tidx = 1
         for val in vals:
            panel["grid"]['threshold%d' % tidx] = val
            tidx += 1
            if thresholdLine == False:
               panel['grid']["thresholdLine"] = False

   def _createDasboardsWithoutRepeats(self, bundlePostfix, dashboards, origdb):
      dbs = []
      for dbid, dbinfo in dashboards.iteritems():
         if dbinfo['repeat']:
            continue
         db = copy.deepcopy(origdb)
         # db['title'] = '%s %s' % (dbinfo['title'], postfix)
         db['title'] = '%s %s' % (dbinfo['title'], bundlePostfix)
         dbTag = dbinfo.get("tag")
         if dbTag:
            db['tags'] = ['vsan-overview-%s-%s' % (dbTag, bundlePostfix)]
         else:
            db['tags'] = ['vsan-overview-%s' % bundlePostfix]
         if dbid in ['dom_owner', 'vsan_client', 'dom_comp_mgr', 'cache_disk']:
            db['tags'].append('vsan-overview-top-%s' % bundlePostfix)
         db['timezone'] = 'utc'
         # Formats: µs, iops, short, Bps, KBps
         firstMetric = None
         if len(db['rows']) != 1:
            raise Exception("Template for non-repeating dashboards \
                             should have only one row. Currently: %d",
                            len(db['rows']))
         idx = db['rows'][0]['panels'][0]['id']
         outputRows = [self._createTitleRow(dbinfo['title'], isNoRepeat=True)]
         for metricDetails in dbinfo['metrics']:
            if not isinstance(metricDetails, dict):
               metricDetails = {
                  'title': metricDetails[0],
                  'metrics': [metricDetails[0]],
                  'unit': metricDetails[1][0],
               }
            row = copy.deepcopy(db['rows'][0])
            row['title'] = metricDetails['title']
            panel = row['panels'][0]
            panel['id'] = idx
            idx = idx + 1
            target = panel['targets'][0]
            target['measurement'] = metricDetails['metrics'][0]
            for tag in target['tags']:
               if tag['key'] == 'entityType':
                  tag['value'] = "/%s/" % (dbinfo['entityToShow'])
            if DashboardGenerator.ENABLE_NEW_INFLUX_LAYOUT:
               # target.setdefault('alias', metricDetails['metrics'][0])
               target['measurement'] = dbinfo['entityToShow']
               target['select'][0][0]['params'][0] = metricDetails['metrics'][0]
               target['tags'] = [{
                  'key': "object",
                  'operator': "=~",
                  'value': "/^\"$host:%s-/" % (dbinfo['entityToShow'])
               }]
            else:
               target['measurement'] = metricDetails['metrics'][0]
               target['select'][0][0]['params'][0] = 'value'
               target['tags'] = [
                  {
                     'key': "host",
                     'operator': "=~",
                     'value': "/^$host$/"
                  },
                  {
                     "condition": "AND",
                     'key': "entityType",
                     'operator': "=~",
                     'value': "/%s/" % (dbinfo['entityToShow'])
                  },
               ]

            self._adjustPanel(panel, metricDetails)
            outputRows.append(row)

         db['rows'] = outputRows
         db["links"] = [
            {
               "asDropdown": False,
               "icon": "external link",
               "includeVars": True,
               "keepTime": True,
               "tags": ['vsan-overview-top-%s' % bundlePostfix],
               "targetBlank": False,
               "title": "Dashboards",
               "type": "dashboards",
               "url": ""
            },
            {
               "asDropdown": True,
               "icon": "external link",
               "includeVars": True,
               "keepTime": True,
               "tags": ['vsan-overview-dom-%s' % bundlePostfix],
               "targetBlank": False,
               "title": "DOM vSAN & vSAN ESA",
               "type": "dashboards",
               "url": ""
            },
            {
               "asDropdown": True,
               "icon": "external link",
               "includeVars": True,
               "keepTime": True,
               "tags": ['vsan-overview-dom_vsan1-%s' % bundlePostfix],
               "targetBlank": False,
               "title": "DOM vSAN",
               "type": "dashboards",
               "url": ""
            },
            {
               "asDropdown": True,
               "icon": "external link",
               "includeVars": True,
               "keepTime": True,
               "tags": ['vsan-overview-dom_vsan-esa-%s' % bundlePostfix],
               "targetBlank": False,
               "title": "DOM vSAN ESA",
               "type": "dashboards",
               "url": ""
            },
            {
               "asDropdown": True,
               "icon": "external link",
               "includeVars": True,
               "keepTime": True,
               "tags": ['vsan-overview-zdom-%s' % bundlePostfix],
               "targetBlank": False,
               "title": "zDOM",
               "type": "dashboards",
               "url": ""
            },
            {
               "asDropdown": True,
               "icon": "external link",
               "includeVars": True,
               "keepTime": True,
               "tags": ['vsan-overview-lsom-%s' % bundlePostfix],
               "targetBlank": False,
               "title": "LSOM",
               "type": "dashboards",
               "url": ""
            },
            {
               "asDropdown": True,
               "icon": "external link",
               "includeVars": True,
               "keepTime": True,
               "tags": ['vsan-overview-lsom2-%s' % bundlePostfix],
               "targetBlank": False,
               "title": "LSOM2",
               "type": "dashboards",
               "url": ""
            },
            {
               "asDropdown": True,
               "icon": "external link",
               "includeVars": True,
               "keepTime": True,
               "tags": ['vsan-overview-cmmds-%s' % bundlePostfix],
               "targetBlank": False,
               "title": "CMMDS",
               "type": "dashboards",
               "url": ""
            },
            {
               "asDropdown": True,
               "icon": "external link",
               "includeVars": True,
               "keepTime": True,
               "tags": ['vsan-overview-clom-%s' % bundlePostfix],
               "targetBlank": False,
               "title": "CLOM",
               "type": "dashboards",
               "url": ""
            },
            {
               "asDropdown": True,
               "icon": "external link",
               "includeVars": True,
               "keepTime": True,
               "tags": ['vsan-overview-network-%s' % bundlePostfix],
               "targetBlank": False,
               "title": "Network",
               "type": "dashboards",
               "url": ""
            },
            {
               "asDropdown": True,
               "icon": "external link",
               "includeVars": True,
               "keepTime": True,
               "tags": ['vsan-overview-rdt-%s' % bundlePostfix],
               "targetBlank": False,
               "title": "RDT",
               "type": "dashboards",
               "url": ""
            },
            {
               "asDropdown": True,
               "icon": "external link",
               "includeVars": True,
               "keepTime": True,
               "tags": ['vsan-overview-%s' % bundlePostfix],
               "targetBlank": False,
               "title": "Dashboards",
               "type": "dashboards",
               "url": ""
            },
         ]
         self._set_datasource(db)
         for temp in db['templating']['list']:
            if temp['name'] in ['entitySelected']:
               temp['regex'] = '/%s*/' % dbinfo['entityToShow']
               temp['query'] = 'show tag values from entities with key="object"'
            if temp['name'] in ['host']:
               temp['query'] = 'show tag values from entities with key="host"'
         dbs.append(db)
      return dbs

   def _createTitleRow(self, title, isNoRepeat=False):
      help = "To access Full Graphs, i.e. all graphs for a given entity, move mouse on the top left corner of any graph and click on Full Graphs";
      if isNoRepeat:
         help = "Please select a host from the top-left drop down\n%s" % help
      return {
         "collapse": False,
         "editable": False,
         "height": "20px",
         "showTitle": False,
         "title": title,
         "panels": [{
            "id": 1,
            "title": title,
            "span": 12,
            "type": "text",
            "mode": "markdown",
            "content": help,
            "links": [],
            "transparent": True,
            "height": "20px"
         }],
      }

   def _diskGroupEntities(self, entities, dashboards):
      dgs = {}
      for capDisk in entities:
         if capDisk['type'] != 'capacity-disk' or 'parent' not in capDisk:
            continue
         dgs.setdefault(capDisk['parent'], [])
         dgs[capDisk['parent']].append(capDisk['obj'])

      cacheDb = dashboards['cache_disk']
      capDb = dashboards['capacity_disk']

      dbEntities = []
      for cacheDisk in sorted(dgs.keys()):
         capDisks = list(set(dgs[cacheDisk]))
         dbEntities.append(
            (cacheDisk, 'cache-disk', cacheDb['metrics'], cacheDb['title']))
         dbEntities.extend(
            [(d, 'capacity-disk', capDb['metrics'], capDb['title']) for d in
             capDisks])
      return dbEntities

   def _getCurrentEntity(self, entities, entityType, entityObj='', entityDiskUuid=''):
      entitiesRequested = []
      for e in entities:
         if entityType in e['type']:
            entitiesRequested.append(e)

      for e in entitiesRequested:
         if entityObj and entityDiskUuid:
            if entityObj in e['obj'] and entityDiskUuid in e.get('diskUuid'):
               return e
         elif entityDiskUuid:
            diskuuid = e.get('diskUuid') or ''
            entityVal = e.get('val', '') or ''
            if entityDiskUuid in diskuuid or entityDiskUuid in e.get('obj', '') or entityDiskUuid in entityVal:
               return e
         elif entityObj:
            if entityObj in e['obj']:
               return e
         else:
            return e


   def _createDasboardsWithRepeats(self, bundle, bundlePostfix, dashboards, origdb, entities):
      dbs = []
      for dbid, dbinfo in dashboards.iteritems():
         if not dbinfo['repeat']:
            continue
         db = copy.deepcopy(origdb)

         logging.info("entityToShow => %s" % dbinfo['entityToShow'])
         if dbinfo['entityToShow'] == 'meta-disk-groups':
            dbEntities = self._diskGroupEntities(entities, dashboards)
         elif dbinfo['entityToShow'] == 'upit':
            dbEntities = [(e['obj'], e['type']) for e in entities
                          if 'upit' in e['type'] and "cpu" not in e['type']]
            dbEntities = [(e[0], e[1], dbinfo['metrics'], dbinfo['title'])
                          for e in list(set(dbEntities))]
         elif dbinfo['entityToShow'] == 'domclient':
            dbEntities = [(e['obj'], e['type']) for e in entities
                          if (dbinfo['entityToShow'] in ("%s-" % e['type']) and e['type']!='cluster-remotedomclient')]
            dbEntities = [(e[0], e[1], dbinfo['metrics'], dbinfo['title'])
                          for e in list(set(dbEntities))]
         else:
            dbEntities = [(e['obj'], e['type']) for e in entities
                          if dbinfo['entityToShow'] in ("%s-" % e['type'])]
            dbEntities = [(e[0], e[1], dbinfo['metrics'], dbinfo['title'])
                          for e in list(set(dbEntities))]

         # db['title'] = '%s %s' % (dbinfo['title'], postfix)
         db['title'] = '%s %s' % (dbinfo['title'], bundlePostfix)
         dbTag = dbinfo.get("tag")
         if dbTag:
            db['tags'] = ['vsan-overview-%s-%s' % (dbTag, bundlePostfix)]
         else:
            db['tags'] = ['vsan-overview-%s' % bundlePostfix]
         if dbid in ['dom_owner', 'vsan_client', 'dom_comp_mgr', 'cache_disk']:
            db['tags'].append('vsan-overview-top-%s' % bundlePostfix)
         db['timezone'] = 'utc'
         # Formats: µs, iops, short, Bps, KBps
         firstMetric = None
         templateRow = db['rows'][0]
         db['rows'] = [
            self._createTitleRow(dbinfo['title'])
         ]
         # sort dbEntities to put cluster stats first, ignore the disk-group entities sorting
         if dbinfo['entityToShow'] != 'meta-disk-groups':
            dbEntities.sort(key=lambda tup: 0 if tup[0].startswith('cluster') else tup[0])
         for entity, entityType, dbMetrics, dbTitle in dbEntities:
            if dbinfo['entityToShow'] != 'meta-disk-groups':
               dbinfo['entityType'] = entityType
            row = copy.deepcopy(templateRow)
            panelTemplate = row['panels'][0]
            row['title'] = "Entity: %s" % entity
            row['panels'] = []
            idx = panelTemplate['id']
            for panelConf in dbMetrics:
               if not isinstance(panelConf, dict):
                  panelConf = {
                     'title': panelConf[0],
                     'metrics': [panelConf[0]],
                     'unit': panelConf[1][0],
                  }
               if panelConf.get('detailOnly', False) == True:
                  continue
               panel = copy.deepcopy(panelTemplate)
               panel['id'] = idx
               target = panel['targets'][0]
               panel['targets'] = []
               panel['seriesOverrides'] = []
               # metrics in the right Y-axis
               panelMetricsRY = panelConf.get('metrics_ry', [])
               for metric in panelConf['metrics'] + panelMetricsRY:
                  origMetric = metric
                  newTarget = copy.deepcopy(target)
                  if type(metric) is tuple:
                     metricAlias = metric[1]
                     newTarget['alias'] = metricAlias
                     metric = metric[0]

                  if origMetric in panelMetricsRY:
                     if newTarget.get('alias') is None:
                        newTarget['alias'] = metric
                     panel['seriesOverrides'].append(
                        {
                           'alias': newTarget['alias'],
                           'yaxis': 2,
                        }
                     )

                  panelEntityType = panelConf.get("entity")
                  requestedEntity = None
                  if panelEntityType:
                     currentEntity = self._getCurrentEntity(entities, entityType, entity)
                     currentEntityVal = currentEntity.get("val")
                     currentEntityDiskUuid = currentEntity.get("diskUuid")
                     requestedEntity = self._getCurrentEntity(entities, panelEntityType, None, currentEntityDiskUuid)

                  panelGroup = panelConf.get("group", False)
                  if panelGroup:
                     newTarget['groupBy'] = [
                        {
                           "type": "tag",
                           "params": [
                              "objKey"
                              ]
                           }
                        ]
                     newTarget["alias"] = "$measurement : [[tag_objKey]]"

                  if DashboardGenerator.ENABLE_NEW_INFLUX_LAYOUT:
                     newTarget.setdefault('alias', metric)
                     newTarget['measurement'] = entityType
                     newTarget['select'][0][0]['params'][0] = metric
                     newTarget['tags'][0] = {
                        'key': "object",
                        'operator': "=",
                        'value': "\"%s\"" % entity
                     }
                  else:
                     panelEntity = entity
                     if requestedEntity:
                        panelEntity =requestedEntity.get("obj")
                     newTarget['measurement'] = metric
                     newTarget['select'][0][0]['params'][0] = 'value'
                     newTarget['tags'][0] = {
                        'key': "object",
                        'operator': "=",
                        'value': "\"%s\"" % panelEntity
                     }
                  panel['targets'].append(newTarget)
                  if firstMetric is None:
                     firstMetric = metric

               self._adjustPanel(panel, panelConf)

               # We can add links to panels, e.g. to our full graphs
               panel["links"] = [
                  {
                     "type": "dashboard",
                     "dashboard": "%s Details %s" % (dbTitle, bundlePostfix),
                     "title": "Full graphs",
                     "keepTime": True,
                     "includeVars": False,
                     "targetBlank": True,
                     "params": "var-SupportBundle=%s&var-entitySelected=%s" % (
                     bundle, entity)
                  }
               ]

               row['panels'].append(panel)
               idx += 1

            db['rows'].append(row)
         db["links"] = [
            {
               "asDropdown": False,
               "icon": "external link",
               "includeVars": True,
               "keepTime": True,
               "tags": ['vsan-overview-top-%s' % bundlePostfix],
               "targetBlank": False,
               "title": "Dashboards",
               "type": "dashboards",
               "url": ""
            },{
                  "asDropdown": True,
                  "icon": "external link",
                  "includeVars": True,
                  "keepTime": True,
                  "tags": ['vsan-overview-dom-%s' % bundlePostfix],
                  "targetBlank": False,
                  "title": "DOM vSAN & vSAN ESA",
                  "type": "dashboards",
                  "url": ""
                  },
               {
                  "asDropdown": True,
                  "icon": "external link",
                  "includeVars": True,
                  "keepTime": True,
                  "tags": ['vsan-overview-dom_vsan1-%s' % bundlePostfix],
                  "targetBlank": False,
                  "title": "zDOM",
                  "type": "dashboards",
                  "url": ""
                  },
               {
                  "asDropdown": True,
                  "icon": "external link",
                  "includeVars": True,
                  "keepTime": True,
                  "tags": ['vsan-overview-dom_vsan-esa-%s' % bundlePostfix],
                  "targetBlank": False,
                  "title": "DOM vSAN ESA Specific",
                  "type": "dashboards",
                  "url": ""
                  },
               {
                  "asDropdown": True,
                  "icon": "external link",
                  "includeVars": True,
                  "keepTime": True,
                  "tags": ['vsan-overview-zdom-%s' % bundlePostfix],
                  "targetBlank": False,
                  "title": "zDOM",
                  "type": "dashboards",
                  "url": ""
                  },
               {
                  "asDropdown": True,
                  "icon": "external link",
                  "includeVars": True,
                  "keepTime": True,
                  "tags": ['vsan-overview-lsom-%s' % bundlePostfix],
                  "targetBlank": False,
                  "title": "LSOM",
                  "type": "dashboards",
                  "url": ""
                  },
               {
                  "asDropdown": True,
                  "icon": "external link",
                  "includeVars": True,
                  "keepTime": True,
                  "tags": ['vsan-overview-lsom2-%s' % bundlePostfix],
                  "targetBlank": False,
                  "title": "LSOM2",
                  "type": "dashboards",
                  "url": ""
                  },
               {
                  "asDropdown": True,
                  "icon": "external link",
                  "includeVars": True,
                  "keepTime": True,
                  "tags": ['vsan-overview-cmmds-%s' % bundlePostfix],
                  "targetBlank": False,
                  "title": "CMMDS",
                  "type": "dashboards",
                  "url": ""
                  },
               {
                  "asDropdown": True,
                  "icon": "external link",
                  "includeVars": True,
                  "keepTime": True,
                  "tags": ['vsan-overview-clom-%s' % bundlePostfix],
                  "targetBlank": False,
                  "title": "CLOM",
                  "type": "dashboards",
                  "url": ""
                  },
               {
                  "asDropdown": True,
                  "icon": "external link",
                  "includeVars": True,
                  "keepTime": True,
                  "tags": ['vsan-overview-network-%s' % bundlePostfix],
                  "targetBlank": False,
                  "title": "Network",
                  "type": "dashboards",
                  "url": ""
                  },
               {
                  "asDropdown": True,
                  "icon": "external link",
                  "includeVars": True,
                  "keepTime": True,
                  "tags": ['vsan-overview-rdt-%s' % bundlePostfix],
                  "targetBlank": False,
                  "title": "RDT",
                  "type": "dashboards",
                  "url": ""
               },
               {
                  "asDropdown": True,
                  "icon": "external link",
                  "includeVars": True,
                  "keepTime": True,
                  "tags": ['vsan-overview-%s' % bundlePostfix],
                  "targetBlank": False,
                  "title": "Dashboards",
                  "type": "dashboards",
                  "url": ""
               },
         ]
         self._set_datasource(db)
         for temp in db['templating']['list']:
            if temp['name'] in ['entitySelected']:
               temp['regex'] = '/%s*/' % dbinfo['entityToShow']
               temp['query'] = 'show tag values from entities with key="object"'
         # print json.dumps(db, indent=2)
         dbs.append(db)

      for dbid, dbinfo in dashboards.iteritems():
         if not dbinfo['repeat']:
            continue
         if dbinfo['entityToShow'] == 'meta-disk-groups':
            continue
         db = copy.deepcopy(origdb)
         # db['title'] = '%s %s' % (dbinfo['title'], postfix)
         db['title'] = '%s Details %s' % (dbinfo['title'], bundlePostfix)
         db['timezone'] = 'utc'
         db['tags'] = []
         # Formats: µs, iops, short, Bps, KBps
         rowTemplate = db['rows'][0]
         idx = rowTemplate['panels'][0]['id']
         db['rows'] = []
         db['rows'].append({
            "collapse": False,
            "editable": True,
            "height": "100px",
            "panels": [
               {
                  "content": "# Full graphs for: $entitySelected",
                  "editable": True,
                  "error": False,
                  "id": 0,
                  "isNew": True,
                  "links": [],
                  "mode": "markdown",
                  "span": 12,
                  "title": "",
                  "transparent": True,
                  "type": "text"
               }
            ],
            "title": "New row"
         })
         for panelConf in dbinfo['metrics']:
            panelTemplate = rowTemplate['panels'][0]
            row = copy.deepcopy(rowTemplate)
            row['panels'] = []
            row['title'] = ''
            row['repeat'] = None
            panel = copy.deepcopy(panelTemplate)
            panel['id'] = idx
            panel['points'] = True
            panel['pointradius'] = 2
            panel['legend']['max'] = True
            panel['legend']['min'] = True
            panel['legend']['avg'] = True
            panel['legend']['values'] = True
            panel['legend']['alignAsTable'] = True
            panel['legend']['rightSide'] = True
            panel['legend']['sideWidth'] = 500
            idx += 1

            target = panel['targets'][0]
            if not isinstance(panelConf, dict):
               panelConf = {
                  'title': panelConf[0],
                  'metrics': [panelConf[0]],
                  'unit': panelConf[1][0],
               }
            panel['targets'] = []
            panel['seriesOverrides'] = []

            panelMetrics = panelConf.get(
               'detailMetrics', panelConf['metrics'])
            panelMetricsRY = panelConf.get('metrics_ry', [])

            for metric in panelMetrics + panelMetricsRY:
               origMetric = metric
               newTarget = copy.deepcopy(target)
               if type(metric) is tuple:
                  metricAlias = metric[1]
                  newTarget['alias'] = metricAlias
                  metric = metric[0]

               if origMetric in panelMetricsRY:
                  if newTarget.get('alias') is None:
                     newTarget['alias'] = metric
                  panel['seriesOverrides'].append(
                     {
                        'alias': newTarget['alias'],
                        'yaxis': 2,
                     }
                  )
               panelGroup = panelConf.get("group", False)
               if panelGroup:
                  newTarget['groupBy'] = [
                     {
                        "type": "tag",
                        "params": [
                           "objKey"
                           ]
                        }
                     ]
                  newTarget["alias"] = "$measurement : [[tag_objKey]]"
               if DashboardGenerator.ENABLE_NEW_INFLUX_LAYOUT:
                  newTarget['measurement'] = dbinfo.get('entityType',
                                                        dbinfo['entityToShow'])
                  newTarget['select'][0][0]['params'][0] = metric
                  newTarget['tags'][0] = {
                     'key': "object",
                     'operator': "=",
                     'value': '"$entitySelected"'
                  }
               else:
                  newTarget['measurement'] = metric
                  newTarget['select'][0][0]['params'][0] = 'value'
                  newTarget['tags'][0] = {
                     'key': "object",
                     'operator': "=~",
                     'value': '/^"$entitySelected"$/'
                  }
               panel['targets'].append(newTarget)

            self._adjustPanel(panel, panelConf, thresholdLine=False)
            row['panels'].append(panel)
            del row['scopedVars']
            del panel['scopedVars']
            del row['repeat']
            panel['span'] = 12
            db['rows'].append(row)
         # We are not adding any links, because we couldn't figure out
         # a solution to a problem: If we pass "includeVars" to keep
         # the support bundle context, grafana will also pass
         # var-selectedEntity, which will mess up the overview
         # dashboard.
         #      db["links"] = [{
         #         "asDropdown": True,
         #         "icon": "external link",
         #         "includeVars": True,
         #         "keepTime": True,
         #         "tags": ['vsan-overview'],
         #         "targetBlank": False,
         #         "title": "Dashboards",
         #         "type": "dashboards",
         #         "params": "var-SupportBundle",
         #         #"url": "var-entitySelected="
         #      }]
         self._set_datasource(db)
         tempList = db['templating']['list']
         db['templating']['list'] = []
         for temp in tempList:
            if temp['name'] not in ['SupportBundle', 'entitySelected']:
               continue
            temp['hide'] = 2
            if temp['name'] in ['entitySelected']:
               temp['name'] = 'entitySelected'
               temp['type'] = 'constant'
               temp['regex'] = None
               temp['includeAll'] = False
               temp['query'] = '${VAR_ENTITYSELECTED}'
            db['templating']['list'].append(temp)
         # print json.dumps(db, indent=2)
         dbs.append(db)
      return dbs
