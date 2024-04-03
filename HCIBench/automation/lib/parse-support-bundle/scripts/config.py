class HumbugConfig(object):
   config = None
   
   @classmethod
   def configParams(cls, internalIp, externalIp, port):
      out = {}
      out['HUMBUG_HOST'] = "http://%s" % internalIp
      out['GRAFANA_HOST'] = "http://%s" % internalIp
      out['GRAFANA_PORT'] = port
      out['GRAFANA_EXT_HOST'] = "http://%s" % externalIp
      out['GRAFANA_EXT_PORT'] = port
      out['GRAFANA_USER'] = "admin"
      out['GRAFANA_PASS'] = "vmware"
      out['INFLUXDB_HOST'] = "http://%s" % internalIp #externalIp
      out['INFLUXDB_PORT'] = 8086
      out['INFLUXDB_EXT_HOST'] = "http://%s" % internalIp # externalIp
      out['INFLUXDB_EXT_PORT'] = 8086
      out['INFLUXDB_USER'] = "smly"
      out['INFLUXDB_PASS'] = "my_secret_password"
      out['GRAFANA_URL'] = "%s:%d" % (
         out['GRAFANA_HOST'], out['GRAFANA_PORT'])
      out['GRAFANA_EXT_URL'] = "%s:%d" % (
         out['GRAFANA_EXT_HOST'], out['GRAFANA_EXT_PORT'])
      out['INFLUXDB_URL'] = "%s:%d" % (
         out['INFLUXDB_HOST'], out['INFLUXDB_PORT'])
      out['INFLUXDB_EXT_URL'] = "%s:%d" % (
         out['INFLUXDB_EXT_HOST'], out['INFLUXDB_EXT_PORT'])
      cls.config = out
      return out
