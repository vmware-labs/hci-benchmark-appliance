#!/usr/bin/python

# Required to make pyVim.connect.Connection work on Python 2.5
from __future__ import with_statement

import base64
import Cookie
import copy
import cgi
import re
import sys
import urllib
from cStringIO import StringIO
from optparse import OptionParser
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

from pyVmomi import vmodl, vim, SoapAdapter, DynamicTypeManagerHelper
from pyVmomi.VmomiSupport import GetWsdlType, GetWsdlName, \
    GetWsdlNamespace, GetQualifiedWsdlName, GuessWsdlType, \
    GetVmodlType, GetVmodlName, DataObject, ManagedObject, F_OPTIONAL
from pyVmomi.SoapAdapter import SoapStubAdapter, SoapResponseDeserializer
from pyVim.connect import Connect, Disconnect

css = '''
  body {
    font-family: Verdana, Arial, Helvetica, sans-serif;
    font-size: 12px;
    color: #000;
    background-color: #fff;
    margin-left: 2%;
    margin-right: 2%;
  }
  a {
    color: #036;
    text-decoration: underline;
  }
  a:visited {
    color: #036;
    text-decoration: underline;
  }
  a:hover {
    color: #3366AA;
    text-decoration: none;
  }
  p.table-title {
    font-weight: bold;
    margin: 10px 0 5px 5px;
  }
  table {
    border-collapse:collapse;
    border-top: 1px solid #999;
    border-left: 1px solid #999;
    width: 100%
  }
  td, th {
    font-size: 12px;
    padding: 5px 10px 5px 10px;
    border-bottom: 1px solid #999;
    border-right: 1px solid #999;
    vertical-align: top;
  }
  th {
    background-color: #555555;
    color: #fff;
    text-transform: uppercase;
    font-size: 10px;
    text-align: left;
    white-space: nowrap;
  }
  tr.title td {
    background-color: #F0F8FF;
  }
  span.object {
    font-size: 150%;
  }
  span.property {
    font-size: 125%;
    padding-left: 1em;
  }
  td.c1 {
    width: 1%;
    text-align: right;
  }
  td.c2 {
    width: 1%;
    text-align: right;
  }
  span.nav-button {
    border-top: 1px solid #999;
    border-left: 1px solid #999;
    border-right: 1px solid #999;
    padding-left: 1em;
    padding-right: 1em;
    margin-right: 5px;
    text-decoration: none;
    cursor: pointer;
    background-color: #FFF0F0;
    color: #036;
  }
  ul.noindent {
    margin-bottom: 0;
    margin-left: 1em;
  }
  h1 {
    font-size: 18px;
    font-weight: bold;
    color: #3366AA;
    margin-bottom: 25px;
    padding-bottom: 5px;
    border-bottom-width: 1px;
    border-bottom-style: dashed;
    border-bottom-color: #95a8a6;
  }
  input {
    font-family:verdana;width:100%;
    font-size: 12px;
  }
  textarea {
    font-family:verdana;
    width:100%;
    font-size: 12px;
  }
'''

navHtml = '''
<span class="nav-button" onclick="location='%s';">%s</span>
'''

methodScript = '''
<script type="text/javascript">
  /*<![CDATA[ */
  function openMethodWindow(moId, method) {
    var url = '%s?method=' + method + '&%s';
    window.open(url,'methodInvocation',
                'width=600,height=400,scrollbars=yes,toolbar=yes,resizable=yes');
  }
  function invokeMethod() {
    document.method.submit();
  }
  /* ]]>*/
</script>
'''

#
# Output formatting helper classes
#

# Helper class that formats VMODL objects as HTML
class VmodlHtmlFormatter:
   def __init__(self, path=None, query={}, docurl=None,
                wsdlNames=False, sorted=True, inline=False, fetchNames=True):
      self.path = path
      self.query = query
      self.wsdlNames = wsdlNames
      self.sorted = sorted
      self.inline = inline
      self.docurl = docurl
      self.fetchNames = fetchNames

   @staticmethod
   def StyleSheet():
      return '<style type="text/css"><!--%s--></style>' % css

   def CgiToUrl(self, params):
      paramList = []
      for (key, val) in params.iteritems():
         if isinstance(val, list):
            paramList.append('&'.join(['%s=%s' % (urllib.quote_plus(key),
                                                  urllib.quote_plus(elt))
                                       for elt in val]))
         else:
            paramList.append('%s=%s' % (urllib.quote_plus(key), urllib.quote_plus(val)))
      paramString = '&'.join(paramList)
      return '%s?%s' % (self.path, paramString)

   def CgiToHtml(self, params, label):
      # If no path was provided, punt and just return the label
      if not self.path:
         return label
      else:
         return '<a href="%s">%s</a>' % (self.CgiToUrl(params), label)

   def BannerHeader(self, summary=''):
      return '<table summary="%s"><tr class="title"><td>' % summary

   def BannerRow(self, label, value, cls='property'):
      return '<span class="%s">%s: <strong>%s</strong></span>' % (cls, label, value)

   def BannerFooter(self):
      return '</td></tr></table>'

   def TableHeader(self, *columns):
      return '<table><tr>%s</tr>' % ''.join(['<th>%s</th>' % c for c in columns])

   def TableFooter(self):
      return '</table>'

   def ArrayElementPropertyToHtml(self, arrayType, arrayName, arrayValue, idx):
      eltType = arrayType.Item
      eltValue = arrayValue[idx]
      if issubclass(eltType, DataObject) and 'key' in eltType._propInfo:
         if isinstance(eltValue.key, int):
            eltName = '%s[%d]' % (arrayName, eltValue.key)
         elif isinstance(eltValue.key, ManagedObject):
            eltName = '%s["%s"]' % (arrayName, eltValue.key._GetMoId())
         else:
            eltName = '%s["%s"]' % (arrayName, eltValue.key)
      else:
         eltName = '%s[%d]' % (arrayName, idx)
      return '<li>%s' % self.PropertyValueToHtml(eltType, eltName, eltValue)

   def ArrayPropertyToHtml(self, arrayType, arrayName, arrayValue):
      # Handle the case where the declaraed type is Any
      if not issubclass(arrayType, list):
         arrayType = type(arrayValue)
      listHeader = '<ul>'
      listRows = [self.ArrayElementPropertyToHtml(arrayType, arrayName, arrayValue, idx)
                  for idx in xrange(0, len(arrayValue))]
      listFooter = '</ul>'
      return '\n'.join([listHeader] + listRows + [listFooter])

   def DataObjectPropertyToHtml(self, propType, propName, value):
      if self.inline:
         # Render data objects as a nested table
         return self.DataObjectToHtml(value)
      else:
         # Render data objects as links
         params = copy.deepcopy(self.query)
         if 'doPath' in params:
            params['doPath'][0] += '.' + propName
         else:
            params['doPath'] = propName
         return self._AnnotatePropertyHtml(self.CgiToHtml(params, propName),
                                           propType,
                                           value)

   def ManagedObjectPropertyToHtml(self, propType, propName, value):
      # Preserve query params except for ones that only apply to this page
      params = dict([kv for kv in self.query.items()
                     if kv[0] not in ['method', 'doPath']])
      params['moid'] = value._GetMoId()
      # TODO: The pyMob meta-variable names could conflict with vmodl function
      #       parameter names (which is also embedded in the query)
      #       Adding prefix '_' to the meta variables fixed the problem.
      #       However, C++ MOB have the similar problem, but surprisingly no
      #       variables name conflict with non-internal vmodl funcation
      #       parameters, yet. Definitely need some cleanup
      params['_type'] = self.VmodlTypeNameToHtml(value.__class__, ref=False)
      if self.wsdlNames:
         params['_typens'], _ = GetQualifiedWsdlName(value.__class__)
      return self._AnnotatePropertyHtml(self.CgiToHtml(params, value._GetMoId()),
                                        propType,
                                        value)

   def _AnnotatePropertyHtml(self, propHtml, propType, value):
      annotations = []
      if isinstance(value, DataObject) or isinstance(value, ManagedObject):
         if self.fetchNames:
            if hasattr(value, 'name') and isinstance(value.name, str):
               annotations.append("name=%s" % cgi.escape(value.name))
         valueType = type(value)
         if valueType != propType:
            annotations.append("type=%s" % self.VmodlTypeToHtml(valueType))
      if len(annotations) == 0:
         return propHtml
      else:
         return '%s (%s)' % (propHtml, ", ".join(annotations))

   def VmodlTypeNameToHtml(self, typ, ref=True):
      if self.wsdlNames:
         (prefix, suffix) = ('', '')
         if hasattr(typ, 'Item'):
            # For array types: get corresponding base type and add array suffix
            typ = typ.Item
            suffix = '[]'
         if issubclass(typ, ManagedObject) and ref:
            prefix = 'ManagedObjectReference:'
         return prefix + GetWsdlName(typ) + suffix
      else:
         return GetVmodlName(typ)

   def VmodlTypeToHtml(self, propType):
      typeEntry = self.VmodlTypeNameToHtml(propType)
      # Link type name to ref guide entry (if available);
      # if type is an array, get the corresponsing scalar type
      docType = hasattr(propType, 'Item') and propType.Item or propType
      if self.docurl and (issubclass(docType, ManagedObject) or
                          issubclass(docType, DataObject)):
         vmodlTypeName = GetVmodlName(docType)
         return '<a href="%s/%s.html">%s</a>' % (self.docurl, vmodlTypeName, typeEntry)
      else:
         return typeEntry

   def PropertyValueToHtml(self, propType, propName, value):
      if value == None or (isinstance(value, list) and len(value) == 0):
         return 'Unset'
      elif isinstance(value, list):
         return self.ArrayPropertyToHtml(propType, propName, value)
      elif isinstance(value, vmodl.MethodFault) and \
             not issubclass(propType, vmodl.MethodFault):
         # Fault thrown trying to read the property from the server;
         # usually indicates a server-side bug.
         methodType = self.VmodlTypeNameToHtml(value.__class__)
         return '<b>EXCEPTION: %s: %s</b>' % (methodType, value.msg)
      elif isinstance(value, DataObject):
         return self.DataObjectPropertyToHtml(propType, propName, value)
      elif isinstance(value, ManagedObject):
         return self.ManagedObjectPropertyToHtml(propType, propName, value)
      elif isinstance(value, type):
         # Classic MOB always renders TypeName properties using VMODL names
         return GetVmodlName(value)
      elif isinstance(value, str):
         return '"%s"' % cgi.escape(value)
      else:
         return str(value)

   def PropertyToHtml(self, propType, propName, value):
      valueEntry = self.PropertyValueToHtml(propType, propName, value)
      typeEntry = self.VmodlTypeToHtml(propType)
      return '\n'.join([
            '<tr><td class="c2">%s</td>' % propName,
            '<td class="c1">%s</td>' % typeEntry,
            '<td>%s</td></tr>' % valueEntry,
            ])

   def PropertyListToHtml(self, obj, propValues):
      tableHeader = self.TableHeader('Name', 'Type', 'Value')
      tableRows = [self.PropertyToHtml(obj._GetPropertyInfo(name).type, name, value)
                   for (name, value) in propValues]
      tableFooter = self.TableFooter()
      return '\n'.join([tableHeader] + tableRows + [tableFooter])

   def DataObjectToHtml(self, obj):
      # Skip dynamicType and dynamicProperty since they're unimplemented
      skip = ['dynamicProperty', 'dynamicType']
      propList = [p.name for p in obj._GetPropertyList() if p.name not in skip]
      if self.sorted:
         propList.sort()
      propValues = [(p, getattr(obj, p)) for p in propList]
      return self.PropertyListToHtml(obj, propValues)

   def ParameterToHtml(self, paramInfo):
      opt = paramInfo.flags & F_OPTIONAL and '(optional)' or '(required)'
      typeName = self.VmodlTypeNameToHtml(paramInfo.type)
      if issubclass(paramInfo.type, (DataObject, list)):
         input = '<td><textarea cols=\"10\" rows=\"5\" name=\"%s\"></textarea></td></tr>'
      else:
         input = '<td><input name="%s" type="text" /></td></tr>'
      return '\n'.join([
            '<tr><td class="c1" nowrap="nowrap">',
            '<strong>%s</strong> %s</td>' % (paramInfo.name, opt),
            '<td class="c2" nowrap="nowrap">%s</td>' % typeName,
            input % paramInfo.name,
            ])

   def ParameterListToHtml(self, obj, methodName):
      action = self.CgiToUrl(self.query)
      formHeader = '<form name="method" action="%s" method="post"' % action
      tableHeader = self.TableHeader('Name', 'Type', 'Value')
      tableFooter = self.TableFooter()
      formFooter = '</form>'
      paramInfoList = obj._GetMethodInfo(methodName).params
      tableRows = [self.ParameterToHtml(p) for p in paramInfoList]
      return '\n'.join([formHeader, tableHeader] + tableRows + [tableFooter, formFooter])

   def MethodToHtml(self, moType, methodInfo):
      methodName = self.wsdlNames and methodInfo.wsdlName or methodInfo.name
      resultTypeName = self.VmodlTypeNameToHtml(methodInfo.result)
      href = '<a href=javascript:openMethodWindow("%s","%s")>%s</a>' % \
          (GetWsdlName(moType), methodInfo.name, methodName)
      return '\n'.join([
            '<tr><td class="c1" nowrap="nowrap">%s</td>' % resultTypeName,
            '<td nowrap="nowrap">%s</td></tr>' % href
            ])

   def MethodListToHtml(self, obj):
      moType = obj.__class__
      tableHeader = self.TableHeader('Return Type', 'Name')
      tableFooter = self.TableFooter()
      methodInfoList = moType._GetMethodList()
      if self.sorted:
         methodInfoList.sort(lambda x, y: cmp(x.name, y.name))
      tableRows = [self.MethodToHtml(moType, m) for m in methodInfoList]
      return '\n'.join([tableHeader] + tableRows + [tableFooter])

   def ResultToHtml(self, resultType, result):
      if result == None or (isinstance(result, list) and len(result) == 0):
         # void result -- nothing to display
         pass
      elif isinstance(result, list):
         # Array result -- print inline array element list
         inline = self.inline
         self.inline = True
         tableRow = self.ArrayPropertyToHtml(resultType, 'Return value', result)
         self.inline = inline
         # Hand craft a table with a single row/column to get a border around the list
         tableHeader = '<table><tr><td>'
         tableFooter = '</td></tr></table>'
         return '\n'.join([tableHeader, tableRow, tableFooter])
      elif isinstance(result, DataObject):
         # DataObject result -- print inline property table
         inline = self.inline
         self.inline = True
         result = self.DataObjectToHtml(result)
         self.inline = inline
         return result
      elif isinstance(result, ManagedObject):
         # MoRef result -- print as a single table entry
         tableHeader = self.TableHeader('Name', 'Type', 'Value')
         tableFooter = self.TableFooter()
         morefHtml = self.ManagedObjectPropertyToHtml(result.__class__, 'result', result)
         tableRow = '<tr><td>%s</td></tr>' % '</td><td>'.join(('result',
                                                                str(result.__class__),
                                                                morefHtml))
         return '\n'.join([tableHeader, tableRow, tableFooter])
      else:
         # Primitive result -- print as a single table entry
         tableHeader = self.TableHeader('Name', 'Type', 'Value')
         tableFooter = self.TableFooter()
         tableRow = self.PropertyToHtml(result.__class__, 'result', str(result))
         return '\n'.join([tableHeader, tableRow, tableFooter])

#
# Authentication helper classes
#

# No-op authentication class: performs no auth checks, allows all operations
class NullAuthenticator():
   def NeedSession(self):
      return False

   def GetSession(self, headers):
      return None

   def CreateSession(self, headers):
      return None

   def IsNotAuthenticatedFault(self, e):
      return False

# VIM authentication class: uses standard VI API authentication
class VimAuthenticator():
   cookieId = 'vmware_soap_session'

   def NeedSession(self):
      return True

   def IsNotAuthenticatedFault(self, e):
      return isinstance(e, vim.fault.NotAuthenticated)

   def GetSession(self, headers):
      # Check if the caller already has a session cookie
      cookieHeader = headers.getheader('Cookie')
      if not cookieHeader:
         return None
      cookie = Cookie.SimpleCookie(cookieHeader)
      if self.cookieId in cookie and cookie[self.cookieId].value:
         sessionCookie = '%s=%s' % (self.cookieId, cookie[self.cookieId].value)
         return sessionCookie

   def CreateSession(self, headers, soapHost, soapPort, namespace):
      (username, password) = self._GetHttpCredentials(headers)
      if not username:
         return None
      print "CreateSession: connecting as user '%s'" % username
      try:
         si = Connect(host=soapHost, port=soapPort, user=username,
                      pwd=password, namespace=namespace)
         sessionCookie = si._stub.cookie
         print "CreateSession: using new cookie '%s'" % sessionCookie
         return sessionCookie
      except Exception, e:
         print "CreateSession: connect failed -- '%s'" % str(e)
         return None

   def AuthChallenge(self, title):
      # XXX The dreaded hack I just removed from the C++ MOB....
      cookie = Cookie.SimpleCookie()
      cookie[self.cookieId] = ''
      return '%s\r\nWWW-Authenticate: Basic realm="%s"\r\n' % (cookie, title)

   def _GetHttpCredentials(self, headers):
      (username, password) = (None, None)
      try:
         authHeader = headers.getheader('Authorization')
         (authType, auth) = authHeader.split()
         if authType.lower() == 'basic':
            (username, password) = base64.decodestring(auth).split(':')
      except:
         pass
      return (username, password)

#
# HTTP request handler
#

class MyHandler(BaseHTTPRequestHandler):
   config = {}
   serviceInstanceType = None
   title = None
   fetchNames = True

   def UseWsdlNames(self):
      return 'wsdl' in self.__query

   def UsePropertyCollector(self):
      return 'pc' in self.__query

   def UseSort(self):
      return 'unsorted' not in self.__query

   def GetMoType(self, moTypeName, moTypeNS):
      if self.UseWsdlNames():
         return GetWsdlType(moTypeNS, moTypeName)
      else:
         return GetVmodlType(moTypeName)

   def LoadDynamicTypes(self, moAdapter):
      try:
         print 'Trying to import dynamic types...'
         dti = DynamicTypeManagerHelper.DynamicTypeImporter(moAdapter)
         dti.ImportTypes()
         print '...succeeded'
      except Exception, e:
         print '...failed:', e

   def GetManagedPropertyValuesPC(self, obj):
      PropertyCollector = vmodl.query.PropertyCollector
      filterSpec = PropertyCollector.FilterSpec(
         objectSet=[PropertyCollector.ObjectSpec(obj=obj, skip=False)],
         propSet=[PropertyCollector.PropertySpec(all=True, type=obj.__class__)],
         )
      si = vim.ServiceInstance(self.serviceInstanceId, obj._stub)
      pc = si.RetrieveContent().GetPropertyCollector()
      props = []
      for content in pc.RetrieveContents([filterSpec]):
         props.extend([(dp.name, dp.val) for dp in content.propSet])
         # Raise an exception if any of the missing properties
         # were caused by authentication failures
         authFailures = [mp.fault for mp in content.missingSet
                         if self.auth.IsNotAuthenticatedFault(mp.fault)]
         if authFailures:
            raise authFailures[0]
         props.extend([(mp.path, '<i>%s</i>' % str(mp.fault))
                       for mp in content.missingSet])
      return props

   def GetManagedPropertyValuesFetch(self, obj):
      props = []
      for prop in obj._GetPropertyList():
         try:
            props.append((prop.name, getattr(obj, prop.name)))
         except vmodl.fault.MethodNotFound:
            # This is thrown when requesting a property that's not available
            # on the server due to versioning; eat the exception until
            # versioning is handled in _GetPropertyList.
            pass
         except vmodl.MethodFault, e:
            if self.auth.IsNotAuthenticatedFault(e):
               # Propagate authentication faults so we can issue an auth challenge.
               raise e
            else:
               # Store the fault with the property so it can be displayed
               # to the user.  This should only happen due to server-side issues.
               sys.stderr.write('Got error parsing %s: %s' % (prop.name, e))
               props.append((prop.name, e))
      return props

   def GetManagedPropertyValues(self, obj):
      if self.UsePropertyCollector():
         values = self.GetManagedPropertyValuesPC(obj)
      else:
         values = self.GetManagedPropertyValuesFetch(obj)
      # Sort alphabetically by property name
      if self.UseSort():
         values.sort(lambda x, y: cmp(x[0], y[0]))
      return values

   @staticmethod
   def PropertyPathItems(path):
      """
      This generator returns information about the items in a property path.
      For each item it returns a pair (propName, index), where propName is
      the name of the property, and index is the array index or key (or None)
      if no array index or key was present.  For example, for the property path
      config.fileSystemVolume.mountInfo[0].volume.extent[0] it would return this
      sequence: (config, None) (fileSystemVolume, None) (mountInfo, 0)
      (volume, None) (extent, 0), while for the property path
      config.option["Irq.RoutingPolicy"] it would return the sequence:
      (config, None) (option, "Irq.RoutingPolicy")
      """
      propNamePat = r'\w+'
      intPat = r'\d+'
      stringPat = r'"[^"]+"'
      pathItemPat = r'(%s)(?:\[(%s|%s)\])?' % (propNamePat, intPat, stringPat)
      cre = re.compile(pathItemPat)
      match = cre.match(path)
      if match:
         yield((match.group(1), match.group(2)))
         pos = match.end()
         while pos < len(path) and path[pos] == '.':
            match = cre.match(path, pos + 1)
            if match:
               yield((match.group(1), match.group(2)))
               pos = match.end()
      return

   @staticmethod
   def KeysEqual(key1, key2):
      if isinstance(key1, ManagedObject):
         if isinstance(key2, ManagedObject):
            return key1._GetMoId() == key2._GetMoId()
         else:
             return False
      else:
         return key1 == key2

   def GetTargetObject(self, obj, doPath):
      if doPath:
         cre = re.compile(r'^(.*)\[(.*)\]$')
         for (propName, index) in self.PropertyPathItems(doPath):
            if index:
               elementType = type(obj)._GetPropertyInfo(propName).type.Item
               if 'key' in elementType._propInfo:
                  if index[0] == '"':
                     key = index[1:-1]
                  else:
                     key = index
                  keyType = elementType._GetPropertyInfo('key').type
                  keyValue = keyType(key)
                  matches = [elt for elt in getattr(obj, propName)
                                 if self.KeysEqual(elt.key, keyValue)]
                  obj = matches[0]
               else:
                  obj = getattr(obj, propName)[int(index)]
            else:
               obj = getattr(obj, propName)
      return obj

   #
   # XML formatting
   #

   def WriteXml(self, obj, file=None):
      file = file or self.wfile
      self.send_header('Content-type', 'text/xml')
      self.end_headers()
      xmlStr = SoapAdapter.Serialize(obj)
      tag = "MobData"
      xmlDoc = '<?xml version="1.0" encoding="UTF-8"?>' \
          '<%s xmlns:xsd="http://www.w3.org/2001/XMLSchema" ' \
          'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">' \
          '%s</%s>' % (tag, xmlStr, tag)
      file.write(xmlDoc)

   #
   # HTML formatting
   #

   def WriteHtmlHeader(self, obj, cookie, file=None):
      file = file or self.wfile
      file.write('Content-type: text/html\r\n')
      if self.auth.NeedSession():
         file.write('Set-Cookie: %s\r\n' % cookie)
      file.write('\r\n')
      file.write('<html><head>')
      file.write('<title>%s</title>' % self.title)
      file.write('<style type="text/css"><!--%s--></style>' % css)
      file.write('</head><body>')

   def WriteHtmlFooter(self, file=None):
      file = file or self.wfile
      file.write('</body></html>')

   def WriteDataObjectBanner(self, formatter, obj, moId, doPath, file=None):
      file = file or self.wfile
      typeName = formatter.VmodlTypeNameToHtml(obj.__class__)
      summary = 'Table of properties for this Data Object'
      self.wfile.write(formatter.BannerHeader(summary))
      self.wfile.write('<br />\n'.join([
            formatter.BannerRow('Data Object Type', typeName, cls='object'),
            formatter.BannerRow('Parent Managed Object ID', moId),
            formatter.BannerRow('Property Path', doPath),
            ]))
      self.wfile.write(formatter.BannerFooter())

   def WriteManagedObjectBanner(self, formatter, obj, moId, file=None):
      file = file or self.wfile
      typeName = formatter.VmodlTypeNameToHtml(obj.__class__, ref=False)
      summary = 'Table of properties for this Managed Object'
      self.wfile.write(formatter.BannerHeader(summary))
      self.wfile.write('<br />\n'.join([
            formatter.BannerRow('Managed Object Type', typeName, cls='object'),
            formatter.BannerRow('Managed Object ID', moId),
            formatter.BannerFooter(),
            ]))

   def WriteManagedMethodBanner(self, formatter, obj, moId, method, file=None):
      typeName = formatter.VmodlTypeNameToHtml(obj.__class__, ref=False)
      self.wfile.write(formatter.BannerHeader())
      self.wfile.write('<br />\n'.join([
               formatter.BannerRow('Managed Object Type', typeName, cls='object'),
               formatter.BannerRow('Managed Object ID', moId),
               formatter.BannerRow('Method', method),
               ]))
      self.wfile.write(formatter.BannerFooter())

   def WriteTableTitle(self, title, file=None):
      file = file or self.wfile
      file.write('<p class="table-title">%s</p>' % title)

   def WriteInvokeTable(self, file=None):
      file = file or self.wfile
      file.write('<table><tr><td class="c1" align="right">')
      file.write('<a href="javascript:invokeMethod()">Invoke Method</a>')
      file.write('</td></tr></table>')

   def HandleRequest(self, reqType):
      host = self.config['soapHost']
      port = self.config['soapPort']
      ns = self.config['namespace']

      #
      # Unmarshal CGI parameters
      #

      query = self.__query
      moTypeName = '_type' in query and query['_type'][0] or None
      moTypeNS = '_typens' in query and query['_typens'][0] or None
      moId = 'moid' in query and query['moid'][0] or self.serviceInstanceId
      sendXML = 'contentType' in query and query['contentType'][0] == "xml"

      doPath = 'doPath' in query and query['doPath'][0] or None
      method = 'method' in query and query['method'][0] or None

      #
      # Identify request type.  We handle four types of requests:
      #
      #                                reqType    obj  doPath  method
      # Data Object property page:         get     DO     str    None
      # Managed Object property page:      get     MO    None    None
      # Managed Object method form:        get     MO    None     str
      # Managed Object method call:       post     MO    None     str
      #

      DO_PROP = doPath != None
      MO_PROP = doPath == None and method == None
      MO_FORM = method != None and reqType == 'get'
      MO_CALL = method != None and reqType == 'post'

      #
      # Do authentication (if required)
      #

      sessionCookie = self.auth.GetSession(self.headers)
      if self.auth.NeedSession():
         if not sessionCookie:
            sessionCookie = self.auth.CreateSession(self.headers, host, port, ns)
         if not sessionCookie:
            self.send_response(401)
            self.wfile.write(self.auth.AuthChallenge(self.title))
            return

      #
      # Instantiate a managed object stub
      #

      moAdapter = SoapStubAdapter(host, port, ns)
      moAdapter.cookie = sessionCookie

      # Look up the managed object type
      if not moTypeName:
         moType = self.serviceInstanceType
      else:
         try:
            moType = self.GetMoType(moTypeName, moTypeNS)
         except Exception, e:
            if 'dynamic' in self.config and self.config['dynamic']:
               self.LoadDynamicTypes(moAdapter)
               # Clear the 'dynamic' flag since we only want to load types once
               self.config['dynamic'] = False
               moType = self.GetMoType(moTypeName, moTypeNS)
            else:
               raise e

      mo = moType(moId, moAdapter)
      obj = self.GetTargetObject(mo, doPath)

      #
      # Call server to fetch data and/or perform operations
      #

      if MO_PROP:
         # Managed object property page: retrieve property values
         try:
            moPropValues = self.GetManagedPropertyValues(obj)
         except Exception, e:
            if self.auth.IsNotAuthenticatedFault(e):
               self.send_response(401)
               self.wfile.write(self.auth.AuthChallenge(self.title))
               return
            else:
               excInfo = sys.exc_info()
               raise excInfo[1], None, excInfo[2]
      elif MO_CALL:
         # Method call: invoke method
         methodArgs = {}
         methodInfo = mo._GetMethodInfo(method)
         for param in methodInfo.params:
            if (param.name in self.__query.keys()):
               value = self.__query[param.name][0]
               if value == '' and (param.flags & F_OPTIONAL):
                  continue
               if issubclass(param.type, DataObject) or \
                      issubclass(param.type, ManagedObject) or \
                      issubclass(param.type, list):
                  # Attach namespace snippet for this param
                  tag = param.name + "Response"
                  response = "".join(
                     [ SoapAdapter.SOAP_START,
                       '<%s xmlns="%s">' % (tag,
                                            GetWsdlNamespace(param.version)),
                       value,
                       '</%s>' % tag,
                       SoapAdapter.SOAP_END ]
                  )
                  methodArgs[param.name] = \
                     SoapResponseDeserializer(moAdapter).Deserialize(response,
                                                                     param.type)
               elif param.type is type:
                  methodArgs[param.name] = self.UseWsdlNames() and \
                      GuessWsdlType(value) or GetVmodlType(value)
               elif param.type is bool:
                  if value.lower() in ('true', 'yes', 't', 'y', '1'):
                     methodArgs[param.name] = True
                  elif value.lower() in ('false', 'no', 'f', 'n', '0'):
                     methodArgs[param.name] = False
                  else:
                     # This should cause an TypeError
                     methodArgs[param.name] = value
               else:
                  methodArgs[param.name] = param.type(value)

         methodObj = getattr(mo, method)
         try:
            result = methodObj(**methodArgs)
            fault = None
         except vmodl.MethodFault, e:
            fault = e

      #
      # Send response
      #

      self.send_response(200)
      if sendXML:
         self.WriteXml(obj)
         return

      docurl = 'refGuide' in self.config and self.config['refGuide'] or None
      formatter = VmodlHtmlFormatter(path=self.path, query=self.__query, docurl=docurl,
                                     wsdlNames=self.UseWsdlNames(), sorted=self.UseSort(),
                                     inline=False, fetchNames=self.fetchNames)

      self.WriteHtmlHeader(obj, sessionCookie)
      self.wfile.write(methodScript % (self.path, self.query_string))
      if DO_PROP or MO_PROP:
         self.wfile.write(navHtml % (self.path, 'Home'))
         params = dict(self.__query)
         if self.UseSort():
            params['unsorted'] = '1'
            label = 'Declaration Order'
         else:
            del params['unsorted']
            label = 'Alphabetical Order'
         self.wfile.write(navHtml % (formatter.CgiToUrl(params), label))
         params = dict(self.__query)
         if self.UseWsdlNames():
            del params['wsdl']
            label = 'VMODL Names'
         else:
            params['wsdl'] = '1'
            label = 'WSDL Names'
         self.wfile.write(navHtml % (formatter.CgiToUrl(params), label))

      if DO_PROP:
         self.WriteDataObjectBanner(formatter, obj, moId, doPath)
      elif MO_PROP:
         self.WriteManagedObjectBanner(formatter, obj, moId)
      elif MO_FORM or MO_CALL:
         self.WriteManagedMethodBanner(formatter, obj, moId, method)
         methodInfo = obj._GetMethodInfo(method)
         resultTypeName = formatter.VmodlTypeNameToHtml(methodInfo.result)
         self.wfile.write('<h1>%s %s</h1>' % (resultTypeName, method))

      if DO_PROP:
         self.WriteTableTitle('Properties')
         table = formatter.DataObjectToHtml(obj)
         self.wfile.write(table)
      elif MO_PROP:
         self.WriteTableTitle('Properties')
         table = formatter.PropertyListToHtml(obj, moPropValues)
         self.wfile.write(table)
      elif MO_FORM or MO_CALL:
         self.WriteTableTitle('Parameters')
         table = formatter.ParameterListToHtml(obj, method)
         self.wfile.write(table)
         self.WriteInvokeTable()

      if MO_PROP:
         self.wfile.write('<br />')
         self.WriteTableTitle('Methods')
         table = formatter.MethodListToHtml(obj)
         self.wfile.write(table)

      if MO_CALL:
         self.wfile.write('<br />')
         if fault:
            faultType = fault.__class__
            faultTypeName = formatter.VmodlTypeNameToHtml(faultType)
            self.WriteTableTitle('Method Invocation Fault: %s' % faultTypeName)
            table = formatter.ResultToHtml(faultType, fault)
            self.wfile.write(table)
         else:
            resultType = methodInfo.result
            resultTypeName = formatter.VmodlTypeNameToHtml(resultType)
            self.WriteTableTitle('Method Invocation Result: %s' % resultTypeName)
            table = formatter.ResultToHtml(resultType, result)
            self.wfile.write(table)

      self.WriteHtmlFooter()

   def ParseCgiQuery(self):
      # Parse URL and read any CGI parameters specified there
      if self.path.find('?') != -1:
         self.path, self.query_string = self.path.split('?', 1)
         self.__query = cgi.parse_qs(self.query_string)
      else:
         self.__query = {}
         self.query_string = ''

      # Parse request contents (for POST) and get any additional parameters
      ctype = self.headers.get('content-type')
      if ctype:
         ctype, pdict = cgi.parse_header(ctype)
         if ctype == 'multipart/form-data':
            self.__query.update(cgi.parse_multipart(r.rfile, pdict))
         elif ctype == 'application/x-www-form-urlencoded':
            clength = int(self.headers.get('Content-length'))
            self.__query.update(cgi.parse_qs(self.rfile.read(clength), 1))

   def do_GET(self):
      self.ParseCgiQuery()
      try:
         self.HandleRequest('get')
      except IOError:
         self.send_error(404,'File Not Found: %s' % self.path)

   def do_POST(self):
      self.ParseCgiQuery()
      try:
         self.HandleRequest('post')
      except IOError:
         self.send_error(404,'File Not Found: %s' % self.path)

#
# Function that creates a MOB using the specified configuration
#

def ManagedObjectBrowser(httpPort, siId, siType, auth=None, title=None, fetchNames=True, **kwargs):
   try:
      address = ('', httpPort)
      MyHandler.serviceInstanceId = siId
      MyHandler.serviceInstanceType = siType
      MyHandler.config = kwargs
      MyHandler.auth = auth and auth or NullAuthenticator()
      MyHandler.title = title and title or 'VMware SDK Browser'
      MyHandler.fetchNames = fetchNames

      server = HTTPServer(address, MyHandler)
      print 'started httpserver on port %u ...' % httpPort
      server.serve_forever()
   except KeyboardInterrupt:
      print '^C received, shutting down server'
      server.socket.close()

#
# When run standalone, create a MOB instance configured for VI by default
#

def main():
   authMap = {'none': NullAuthenticator, 'vim': VimAuthenticator}
   parser = OptionParser()
   parser.add_option('-H', '--soapHost', dest='soapHost', default='localhost',
                     help='Hostname of SOAP server')
   parser.add_option('-S', '--soapPort', dest='soapPort', type='int', default=443,
                     help='Port of SOAP server (positive for https, negative for http)')
   parser.add_option('-P', '--httpPort', dest='httpPort', type='int', default=8008,
                     help='HTTP port')
   parser.add_option('-n', '--namespace', dest='namespace', default='vim25/5.5',
                     help='SOAP namespace')
   parser.add_option('-p', '--package', dest='package', default='vim',
                     help='VMODL package')
   parser.add_option('--defaultType', dest='defaultType', default='ServiceInstance',
                     help='The default type to show')
   parser.add_option('--defaultMoid', dest='defaultMoid', default='ServiceInstance',
                     help='Moid of the default object')
   parser.add_option('-d', '--dynamic', dest='dynamic', default=False,
                     help='Load dynamic types from server', action="store_true")
   parser.add_option('-a', '--authenticator', dest='auth', default='vim',
                     help='Authentication type %s' % authMap.keys())
   parser.add_option('-r', '--refguide', dest='refguide',
                     help='Reference guide base URL')
   parser.add_option('-f', '--doNotfetchName', dest = 'fetchNames', default = True,
                     help = 'Do not fetch names of managed and data objects', action = "store_false")
   (options, args) = parser.parse_args()

   if options.auth in authMap.keys():
      auth = authMap[options.auth]()
   else:
      parser.error('Unknown authenticator type "%s"' % options.auth)

   ManagedObjectBrowser(siId=options.defaultMoid,
                        siType=
                           GetVmodlType('%s.%s' %(options.package, options.defaultType)),
                        soapHost=options.soapHost,
                        soapPort=options.soapPort,
                        httpPort=options.httpPort,
                        namespace=options.namespace,
                        refGuide=options.refguide,
                        auth=auth,
                        fetchNames = options.fetchNames,
                        dynamic=options.dynamic,
                        )

# Start program
if __name__ == "__main__":
   main()

