# -*- coding: utf-8 -*-
import json
import logging
import requests
from dashboardUtil import DashboardGenerator


class GrafanaClient:
   CONTENT_TYPE_HEADER = {'content-type': 'application/json'}

   def __init__(self, host, port, user, password):
      self.session = requests.Session()
      self.url = '%s:%u' % (host, port)
      self.authentication = (user, password)

   def isNewGrafana(self):
      defaultVersion = '4.4.3'
      try:
         response = self.session.get('%s/api/health' % self.url,
            headers=GrafanaClient.CONTENT_TYPE_HEADER,
            auth=self.authentication
         )
         results = json.loads(response.content)
         logging.info("result for checking Grafana %s" % str(results))
         return results.get('version') != defaultVersion
      except:
         import traceback
         logging.info(traceback.format_exc())
         return False

   def createDatasource(self, dbname, dbuser, dbpass, ifdb_host, ifdb_port):
      post_data = {
         'access': 'proxy',
         'database': dbname,
         'name': dbname,
         'type': 'influxdb',
         'url': '%s:%u' % (ifdb_host, ifdb_port),
         'user': dbuser,
         'password': dbpass
      }

      logging.info("Creating influx datasource target in grafana: %s" % dbname)

      self.session.post(
         '%s/api/datasources' % self.url,
         data=json.dumps(post_data),
         headers=GrafanaClient.CONTENT_TYPE_HEADER,
         auth=self.authentication
      )

   def _find_dashboard_uri(self, title):
      try:
         response = self.session.get('%s/api/search?query=%s' % (self.url, title),
            headers=GrafanaClient.CONTENT_TYPE_HEADER,
            auth=self.authentication
         )

         results = json.loads(response.content)
         return results[0]['uri']
      except:
         return None

   def _delete_dashboard(self, uri):
      try:
         logging.info("Deleteing dashboard %s" % uri)
         resp = self.session.delete('%s/api/dashboards/%s' % (self.url, uri),
            headers=GrafanaClient.CONTENT_TYPE_HEADER,
            auth=self.authentication
         )

         if resp.status_code != 200:
            logging.error("Failed to delete dashboard %s, code: %d, text: %s" % (uri, resp.status_code, resp.text))
      except:
         return None

   def _delete_dashboard_if_exists(self, db_title):
      uri = self._find_dashboard_uri(db_title)
      if uri:
         self._delete_dashboard(uri)

   def createDashboard(self, dbDict):
      self._delete_dashboard_if_exists(dbDict['title'])
      self._ImportDashboard(dbDict)

   def _ImportDashboard(self, dbDict):
      body = {
         'inputs': [{
            "name": "DS_DASHBOARDDB",
            "type": "datasource",
            "pluginId": "influxdb",
            "value": "dashboardDB"
         }],
         'overwrite': True,
         'dashboard': dbDict
      }

      resp = self.session.post(
         "%s/api/dashboards/import" % self.url,
         auth=self.authentication,
         data=json.dumps(body),
         headers=self.CONTENT_TYPE_HEADER
      )

      logging.info("Result of create dashboard %s: %d (%s)" % (dbDict['title'], resp.status_code, resp.text))

      if resp.status_code / 100 != 2:
         logging.info("Failed to create dashboard %s: %d (%s)" % (dbDict['title'], resp.status_code, resp.text))
