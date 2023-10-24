#############################################################
# Copyright (c) 2005-2021 VMware, Inc.  All rights reserved.
# -- VMware Confidential
#############################################################

## @file connect.py
## @brief Connect to a VMOMI ServiceInstance.
##
## Detailed description (for Doxygen goes here)
"""
Connect to a VMOMI ServiceInstance.

Detailed description (for [e]pydoc goes here).
"""

import re
import ssl

from sys import version_info
from xml.parsers.expat import ExpatError

from six.moves import http_client

from pyVmomi import SessionOrientedStub, SoapStubAdapter, vim, vmodl
from pyVmomi.SoapAdapter import CONNECTION_POOL_IDLE_TIMEOUT_SEC
from pyVmomi.VmomiSupport import (GetServiceVersions, IsChildVersion, nsMap,
                                  versionIdMap, versionMap)

try:
    from xml.etree.ElementTree import ElementTree
except ImportError:
    from elementtree.ElementTree import ElementTree

if version_info[0] >= 3:
    from urllib.request import urlopen
else:
    # Python 2 fallback.
    from urllib import urlopen

"""
Global regular expression for parsing host and port connection
See http://www.ietf.org/rfc/rfc3986.txt sec 3.2.2
"""
_rx = re.compile(r"(^\[.+\]|[^:]+)(:\d+)?$")

_si = None
"""
Global (thread-shared) ServiceInstance

@todo: Get rid of me?
"""


def getSslContext(host, sslContext, disableSslCertValidation):
    """
    Connections to 'localhost' do not need SSL verification as a certificate
    will never match. The OS provides security by only allowing root to bind
    to low-numbered ports.
    """
    """
    TODO: the entire 127.0.0.0/8 network is allocated for loopback addresses.
    Therefore, the check should be for a valid ip4 address, beginning with 127.
    """
    if disableSslCertValidation or (not sslContext and host in ['localhost', '127.0.0.1', '::1']):
        sslContext = ssl._create_unverified_context()
    return sslContext


class closing(object):
    """
    Helper class for using closable objects in a 'with' statement,
    similar to the one provided by contextlib.
    """
    def __init__(self, obj):
        self.obj = obj

    def __enter__(self):
        return self.obj

    def __exit__(self, *exc_info):
        self.obj.close()


class VimSessionOrientedStub(SessionOrientedStub):
    '''A vim-specific SessionOrientedStub.  See the SessionOrientedStub class
    in pyVmomi/SoapAdapter.py for more information.
    '''

    # The set of exceptions that should trigger a relogin by the session stub.
    SESSION_EXCEPTIONS = (vim.fault.NotAuthenticated, )

    @staticmethod
    def makeUserLoginMethod(username, password, locale=None):
        '''Return a function that will call the vim.SessionManager.Login() method
        with the given parameters.  The result of this function can be passed as
        the "loginMethod" to a SessionOrientedStub constructor.
        '''
        def _doLogin(soapStub):
            si = vim.ServiceInstance("ServiceInstance", soapStub)
            sm = si.content.sessionManager
            if not sm.currentSession:
                si.content.sessionManager.Login(username, password, locale)

        return _doLogin

    @staticmethod
    def makeExtensionLoginMethod(extensionKey):
        '''Return a function that will call the vim.SessionManager.Login() method
        with the given parameters.  The result of this function can be passed as
        the "loginMethod" to a SessionOrientedStub constructor.
        '''
        def _doLogin(soapStub):
            si = vim.ServiceInstance("ServiceInstance", soapStub)
            sm = si.content.sessionManager
            if not sm.currentSession:
                si.content.sessionManager.LoginExtensionByCertificate(
                    extensionKey)

        return _doLogin

    @staticmethod
    def makeCertHokTokenLoginMethod(stsUrl, stsCert=None):
        '''Return a function that will call the vim.SessionManager.LoginByToken()
        after obtaining a HoK SAML token from the STS. The result of this function
        can be passed as the "loginMethod" to a SessionOrientedStub constructor.

        @param stsUrl: URL of the SAML Token issuing service. (i.e. SSO server).
        @param stsCert: public key of the STS service.
        '''
        assert (stsUrl)

        def _doLogin(soapStub):
            from . import sso
            cert = soapStub.schemeArgs['cert_file']
            key = soapStub.schemeArgs['key_file']
            authenticator = sso.SsoAuthenticator(sts_url=stsUrl,
                                                 sts_cert=stsCert)

            samlAssertion = authenticator.get_hok_saml_assertion(cert, key)

            def _requestModifier(request):
                return sso.add_saml_context(request, samlAssertion, key)

            si = vim.ServiceInstance("ServiceInstance", soapStub)
            sm = si.content.sessionManager
            if not sm.currentSession:
                with soapStub.requestModifier(_requestModifier):
                    try:
                        soapStub.samlToken = samlAssertion
                        si.content.sessionManager.LoginByToken()
                    finally:
                        soapStub.samlToken = None

        return _doLogin

    @staticmethod
    def makeCredBearerTokenLoginMethod(username,
                                       password,
                                       stsUrl,
                                       stsCert=None):
        '''Return a function that will call the vim.SessionManager.LoginByToken()
        after obtaining a Bearer token from the STS. The result of this function
        can be passed as the "loginMethod" to a SessionOrientedStub constructor.

        @param username: username of the user/service registered with STS.
        @param password: password of the user/service registered with STS.
        @param stsUrl: URL of the SAML Token issueing service. (i.e. SSO server).
        @param stsCert: public key of the STS service.
        '''
        assert (username)
        assert (password)
        assert (stsUrl)

        def _doLogin(soapStub):
            from . import sso
            cert = soapStub.schemeArgs['cert_file']
            key = soapStub.schemeArgs['key_file']
            authenticator = sso.SsoAuthenticator(sts_url=stsUrl,
                                                 sts_cert=stsCert)
            samlAssertion = authenticator.get_bearer_saml_assertion(
                username, password, cert, key)
            si = vim.ServiceInstance("ServiceInstance", soapStub)
            sm = si.content.sessionManager
            if not sm.currentSession:
                try:
                    soapStub.samlToken = samlAssertion
                    si.content.sessionManager.LoginByToken()
                finally:
                    soapStub.samlToken = None

        return _doLogin


def Connect(host='localhost',
            port=443,
            user='root',
            pwd='',
            service="hostd",
            adapter="SOAP",
            namespace=None,
            path="/sdk",
            version=None,
            keyFile=None,
            certFile=None,
            thumbprint=None,
            sslContext=None,
            httpConnectionTimeout=None,
            connectionPoolTimeout=CONNECTION_POOL_IDLE_TIMEOUT_SEC,
            token=None,
            disableSslCertValidation=False,
            customHeaders=None):
    """
    Connect to the specified server, login and return the service
    instance object.

    Throws any exception back to caller. The service instance object is
    also saved in the library for easy access.

    Clients should modify the service parameter only when connecting to
    a VMOMI server other than hostd/vpxd. For both of the latter, the
    default value is fine.

    @param host: Which host to connect to.
    @type  host: string
    @param port: Port
    @type  port: int
    @param user: User
    @type  user: string
    @param pwd: Password
    @type  pwd: string
    @param service: Service
    @type  service: string
    @param adapter: Adapter
    @type  adapter: string
    @param namespace: Namespace *** Deprecated: Use version instead ***
    @type  namespace: string
    @param path: Path
    @type  path: string
    @param version: Version
    @type  version: string
    @param keyFile: ssl key file path
    @type  keyFile: string
    @param certFile: ssl cert file path
    @type  certFile: string
    @param thumbprint: host cert thumbprint
    @type  thumbprint: string
    @param sslContext: SSL Context describing the various SSL options. It is only
                        supported in Python 2.7.9 or higher.
    @type  sslContext: SSL.Context
    @param httpConnectionTimeout: Timeout in secs for http requests.
    @type  httpConnectionTimeout: int
    @param connectionPoolTimeout: Timeout in secs for idle connections to close, specify
                                    negative numbers for never closing the connections
    @type  connectionPoolTimeout: int
    @type  token: string
    @param token: Authentication and Authorization token to use for the connection.
                    The presence of this token overrides the user and pwd parameters.
    @type  disableSslCertValidation: bool
    @param disableSslCertValidation: Creates an unverified SSL context when True.
    @type  customHeaders: dictionary
    @param customHeaders: Dictionary with custom HTTP headers.
    """
    try:
        info = re.match(_rx, host)
        if info is not None:
            host = info.group(1)
            if host[0] == '[':
                host = info.group(1)[1:-1]
            if info.group(2) is not None:
                port = int(info.group(2)[1:])
    except ValueError as ve:
        pass

    sslContext = getSslContext(host, sslContext, disableSslCertValidation)

    if namespace:
        assert (version is None)
        version = versionMap[namespace]
    elif not version:
        version = "vim.version.version9"
    si, stub = __Login(host,
                       port,
                       user,
                       pwd,
                       service,
                       adapter,
                       version,
                       path,
                       keyFile,
                       certFile,
                       thumbprint,
                       sslContext,
                       httpConnectionTimeout,
                       connectionPoolTimeout,
                       token=token,
                       customHeaders=customHeaders)
    SetSi(si)

    return si


def Disconnect(si):
    """
    Disconnect (logout) service instance
    @param si: Service instance (returned from Connect)
    """
    # Logout
    __Logout(si)
    SetSi(None)


## Method that gets a local ticket for the specified user
def GetLocalTicket(si, user):
    try:
        sessionManager = si.content.sessionManager
    except Exception as e:
        if type(e).__name__ == 'ExpatError':
            msg = 'Malformed response while querying for local ticket: "%s"' % e
            raise vim.fault.HostConnectFault(msg=msg)
        else:
            msg = 'Failed to query for local ticket: "%s"' % e
            raise vim.fault.HostConnectFault(msg=msg)
    localTicket = sessionManager.AcquireLocalTicket(userName=user)
    with open(localTicket.passwordFilePath) as f:
        content = f.read()
    return localTicket.userName, content


## Private method that performs the actual Connect and returns a
## connected service instance object.


def __Login(host,
            port,
            user,
            pwd,
            service,
            adapter,
            version,
            path,
            keyFile,
            certFile,
            thumbprint,
            sslContext,
            httpConnectionTimeout,
            connectionPoolTimeout,
            token,
            customHeaders):
    """
    Private method that performs the actual Connect and returns a
    connected service instance object.

    @param host: Which host to connect to.
    @type  host: string
    @param port: Port
    @type  port: int
    @param user: User
    @type  user: string
    @param pwd: Password
    @type  pwd: string
    @param service: Service
    @type  service: string
    @param adapter: Adapter
    @type  adapter: string
    @param version: Version
    @type  version: string
    @param path: Path
    @type  path: string
    @param keyFile: ssl key file path
    @type  keyFile: string
    @param certFile: ssl cert file path
    @type  certFile: string
    @param thumbprint: host cert thumbprint
    @type  thumbprint: string
    @param sslContext: SSL Context describing the various SSL options. It is only
                        supported in Python 2.7.9 or higher.
    @type  sslContext: SSL.Context
    @param httpConnectionTimeout: Timeout in secs for http requests.
    @type  httpConnectionTimeout: int
    @param connectionPoolTimeout: Timeout in secs for idle connections to close, specify
                                    negative numbers for never closing the connections
    @type  connectionPoolTimeout: int
    @type  token: string
    @param token: Authentication and Authorization token to use for the connection.
                    The presence of this token overrides the user and pwd parameters.
    @type  customHeaders: dictionary
    @param customHeaders: Dictionary with custom HTTP headers.
    """

    # XXX remove the adapter and service arguments once dependent code is fixed
    if adapter != "SOAP":
        raise ValueError(adapter)

    # Add an HTTP authorization header if a token is provided
    if token:
        if customHeaders is None:
            customHeaders = {}
        customHeaders.update({"Authorization": "Bearer {}".format(token)})

    # Create the SOAP stub adapter
    stub = SoapStubAdapter(
        host,
        port,
        version=version,
        path=path,
        certKeyFile=keyFile,
        certFile=certFile,
        thumbprint=thumbprint,
        sslContext=sslContext,
        httpConnectionTimeout=httpConnectionTimeout,
        connectionPoolTimeout=connectionPoolTimeout,
        customHeaders=customHeaders)

    # Get Service instance
    si = vim.ServiceInstance("ServiceInstance", stub)
    try:
        content = si.RetrieveContent()
    except vmodl.MethodFault:
        raise
    except Exception as e:
        raise vim.fault.HostConnectFault(msg=str(e))

    # Get a ticket if we're connecting to localhost and password is not specified
    if host == 'localhost' and not pwd and not token:
        try:
            (user, pwd) = GetLocalTicket(si, user)
        except:
            pass  # This is not supported against vCenter, and connecting
            # with an empty password is fine in debug builds

    # Login
    if token:
        content.sessionManager.LoginByToken()
    else:
        content.sessionManager.Login(user, pwd, None)
    return si, stub


## Private method that performs the actual Disonnect


def __Logout(si):
    """
    Disconnect (logout) service instance
    @param si: Service instance (returned from Connect)
    """
    try:
        if si:
            content = si.RetrieveContent()
            content.sessionManager.Logout()
    except Exception as e:
        pass


## Get the saved service instance.


def GetSi():
    """ Get the saved service instance. """
    return _si


## Set the saved service instance.


def SetSi(si):
    """ Set the saved service instance. """

    global _si
    _si = si


## Get the global saved stub


def GetStub():
    """ Get the global saved stub. """
    si = GetSi()
    if si:
        return si._GetStub()
    return None


## RAII-style class for managing connections


class Connection(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.si = None

    def __enter__(self):
        self.si = Connect(*self.args, **self.kwargs)
        return self.si

    def __exit__(self, *exc_info):
        if self.si:
            Disconnect(self.si)
            self.si = None


class SmartConnection(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.si = None

    def __enter__(self):
        self.si = SmartConnect(*self.args, **self.kwargs)
        return self.si

    def __exit__(self, *exc_info):
        if self.si:
            Disconnect(self.si)
            self.si = None


## Deprecated, use __GetElementTree method instead
def __GetElementTreeFromUrl(url, sslContext):
    """
    Private method that returns an ElementTree for the XML document referenced by
    the url.

    @param url: URL
    @type  url: string
    @param sslContext: SSL Context describing the various SSL options. It is only
                        supported in Python 2.7.9 or higher.
    @type  sslContext: SSL.Context
    """

    tree = ElementTree()

    try:
        urlopen_kwargs = {}
        if sslContext:
            # We need to pass the ssl context as kwargs because 'context' parameter
            # was added in Python 2.7.9, so passing it as a normal parameter would
            # fail in earlier versions. Please see
            # https://www.python.org/dev/peps/pep-0476/ for more details.
            urlopen_kwargs['context'] = sslContext
        with closing(urlopen(url, **urlopen_kwargs)) as sock:
            if sock.getcode() == 200:
                tree.parse(sock)
                return tree
    except ExpatError:
        pass
    return None


def __GetElementTree(protocol, server, port, path, sslContext):
    """
    Private method that returns ElementTree for a remote XML document.

    @param protocol: What protocol to use for the connection (e.g. https or http).
    @type  protocol: string
    @param server: Which server to connect to.
    @type  server: string
    @param port: Port
    @type  port: int
    @param path: Path
    @type  path: string
    @param sslContext: SSL Context describing the various SSL options. It is only
                        supported in Python 2.7.9 or higher.
    @type  sslContext: SSL.Context
    """
    tree = ElementTree()

    if protocol == "https":
        kwargs = {"context": sslContext} if sslContext else {}
        conn = http_client.HTTPSConnection(server, port=port, **kwargs)
    elif protocol == "http":
        conn = http_client.HTTPConnection(server, port=port)
    else:
        raise Exception("Protocol " + protocol + " not supported.")
    conn.request("GET", path)
    try:
        response = conn.getresponse()
        if response.status == 200:
            try:
                tree.parse(response)
                return tree
            except ExpatError:
                pass
        return None
    finally:
        conn.close()


## Private method that returns an ElementTree describing the API versions
## supported by the specified server.  The result will be vimServiceVersions.xml
## if it exists, otherwise vimService.wsdl if it exists, otherwise None.


def __GetServiceVersionDescription(protocol, server, port, path, sslContext):
    """
    Private method that returns an ElementTree describing the API versions
    supported by the specified server.  The result will be vimServiceVersions.xml
    if it exists, otherwise vimService.wsdl if it exists, otherwise None.

    @param protocol: What protocol to use for the connection (e.g. https or http).
    @type  protocol: string
    @param server: Which server to connect to.
    @type  server: string
    @param port: Port
    @type  port: int
    @param path: Path
    @type  path: string
    @param sslContext: SSL Context describing the various SSL options. It is only
                        supported in Python 2.7.9 or higher.
    @type  sslContext: SSL.Context
    """

    tree = __GetElementTree(protocol, server, port,
                            path + "/vimServiceVersions.xml", sslContext)
    if tree is not None:
        return tree

    tree = __GetElementTree(protocol, server, port, path + "/vimService.wsdl",
                            sslContext)
    return tree


## Private method that returns true if the service version description document
##  indicates that the desired version is supported


def __VersionIsSupported(desiredVersion, serviceVersionDescription):
    """
    Private method that returns true if the service version description document
    indicates that the desired version is supported

    @param desiredVersion: The version we want to see if the server supports
                            (eg. vim.version.version9.
    @type  desiredVersion: string
    @param serviceVersionDescription: An ElementTree for vimServiceVersions.xml
                                        or vimService.wsdl.
    @type  serviceVersionDescription: ElementTree
    """

    root = serviceVersionDescription.getroot()
    if root.tag == 'namespaces':
        # serviceVersionDescription appears to be a vimServiceVersions.xml document
        if root.get('version') != '1.0':
            raise RuntimeError('vimServiceVersions.xml has version %s,' \
                ' which is not understood' % (root.get('version')))
        desiredVersionId = versionIdMap[desiredVersion]
        supportedVersion = None
        for namespace in root.findall('namespace'):
            versionId = namespace.findtext('version')
            if versionId == desiredVersionId:
                return True
            else:
                for versionId in namespace.findall('priorVersions/version'):
                    if versionId.text == desiredVersionId:
                        return True
    else:
        # serviceVersionDescription must be a vimService.wsdl document
        wsdlNS = 'http://schemas.xmlsoap.org/wsdl/'
        importElement = serviceVersionDescription.find('.//{%s}import' %
                                                       wsdlNS)
        supportedVersion = versionMap[importElement.get('namespace')[4:]]
        if IsChildVersion(supportedVersion, desiredVersion):
            return True
    return False


## Private method that returns the most preferred API version supported by the
## specified server,


def __FindSupportedVersion(protocol, server, port, path, preferredApiVersions,
                           sslContext):
    """
    Private method that returns the most preferred API version supported by the
    specified server,

    @param protocol: What protocol to use for the connection (e.g. https or http).
    @type  protocol: string
    @param server: Which server to connect to.
    @type  server: string
    @param port: Port
    @type  port: int
    @param path: Path
    @type  path: string
    @param preferredApiVersions: Acceptable API version(s) (e.g. vim.version.version9)
                                    If a list of versions is specified the versions should
                                    be ordered from most to least preferred.
    @type  preferredApiVersions: string or string list
    @param sslContext: SSL Context describing the various SSL options. It is only
                        supported in Python 2.7.9 or higher.
    @type  sslContext: SSL.Context
    """

    serviceVersionDescription = __GetServiceVersionDescription(
        protocol, server, port, path, sslContext)
    if serviceVersionDescription is None:
        return None

    if not isinstance(preferredApiVersions, list):
        preferredApiVersions = [preferredApiVersions]

    for desiredVersion in preferredApiVersions:
        if __VersionIsSupported(desiredVersion, serviceVersionDescription):
            return desiredVersion
    return None


def SmartStubAdapter(host='localhost',
                     port=443,
                     path='/sdk',
                     url=None,
                     sock=None,
                     poolSize=5,
                     certFile=None,
                     certKeyFile=None,
                     httpProxyHost=None,
                     httpProxyPort=80,
                     sslProxyPath=None,
                     thumbprint=None,
                     cacertsFile=None,
                     preferredApiVersions=None,
                     acceptCompressedResponses=True,
                     samlToken=None,
                     sslContext=None,
                     httpConnectionTimeout=None,
                     connectionPoolTimeout=CONNECTION_POOL_IDLE_TIMEOUT_SEC,
                     disableSslCertValidation=False):
    """
    Determine the most preferred API version supported by the specified server,
    then create a soap stub adapter using that version

    The parameters are the same as for pyVmomi.SoapStubAdapter except for
    version which is renamed to prefferedApiVersions

    @param preferredApiVersions: Acceptable API version(s) (e.g. vim.version.version9)
                                    If a list of versions is specified the versions should
                                    be ordered from most to least preferred.  If None is
                                    specified, the list of versions support by pyVmomi will
                                    be used.
    @type  preferredApiVersions: string or string list
    @type disableSslCertValidation: bool
    @param disableSslCertValidation: Creates an unverified SSL context when True.
    """
    if preferredApiVersions is None:
        preferredApiVersions = GetServiceVersions('vim25')

    sslContext = getSslContext(host, sslContext, disableSslCertValidation)

    supportedVersion = __FindSupportedVersion('https' if port > 0 else 'http',
                                              host, port, path,
                                              preferredApiVersions, sslContext)
    if supportedVersion is None:
        raise Exception("%s:%s is not a VIM server" % (host, port))

    return SoapStubAdapter(host=host,
                           port=port,
                           path=path,
                           url=url,
                           sock=sock,
                           poolSize=poolSize,
                           certFile=certFile,
                           certKeyFile=certKeyFile,
                           httpProxyHost=httpProxyHost,
                           httpProxyPort=httpProxyPort,
                           sslProxyPath=sslProxyPath,
                           thumbprint=thumbprint,
                           cacertsFile=cacertsFile,
                           version=supportedVersion,
                           acceptCompressedResponses=acceptCompressedResponses,
                           samlToken=samlToken,
                           sslContext=sslContext,
                           httpConnectionTimeout=httpConnectionTimeout,
                           connectionPoolTimeout=connectionPoolTimeout)


def SmartConnect(protocol='https',
                 host='localhost',
                 port=443,
                 user='root',
                 pwd='',
                 service="hostd",
                 path="/sdk",
                 preferredApiVersions=None,
                 keyFile=None,
                 certFile=None,
                 thumbprint=None,
                 sslContext=None,
                 httpConnectionTimeout=None,
                 connectionPoolTimeout=CONNECTION_POOL_IDLE_TIMEOUT_SEC,
                 token=None,
                 disableSslCertValidation=False,
                 customHeaders=None):
    """
    Determine the most preferred API version supported by the specified server,
    then connect to the specified server using that API version, login and return
    the service instance object.

    Throws any exception back to caller. The service instance object is
    also saved in the library for easy access.

    Clients should modify the service parameter only when connecting to
    a VMOMI server other than hostd/vpxd. For both of the latter, the
    default value is fine.

    @param protocol: What protocol to use for the connection (e.g. https or http).
    @type  protocol: string
    @param host: Which host to connect to.
    @type  host: string
    @param port: Port
    @type  port: int
    @param user: User
    @type  user: string
    @param pwd: Password
    @type  pwd: string
    @param service: Service
    @type  service: string
    @param path: Path
    @type  path: string
    @param preferredApiVersions: Acceptable API version(s) (e.g. vim.version.version9)
                                If a list of versions is specified the versions should
                                be ordered from most to least preferred.  If None is
                                specified, the list of versions support by pyVmomi will
                                be used.
    @type  preferredApiVersions: string or string list
    @param keyFile: ssl key file path
    @type  keyFile: string
    @param certFile: ssl cert file path
    @type  certFile: string
    @param thumbprint: host cert thumbprint
    @type  thumbprint: string
    @param sslContext: SSL Context describing the various SSL options. It is only
                        supported in Python 2.7.9 or higher.
    @type  sslContext: SSL.Context
    @param httpConnectionTimeout: Timeout in secs for http requests.
    @type  httpConnectionTimeout: int
    @param connectionPoolTimeout: Timeout in secs for idle connections to close, specify
                                    negative numbers for never closing the connections
    @type  connectionPoolTimeout: int
    @type  token: string
    @param token: Authentication and Authorization token to use for the connection.
                    The presence of this token overrides the user and pwd parameters.
    @type disableSslCertValidation: bool
    @param disableSslCertValidation: Creates an unverified SSL context when True.
    """

    if preferredApiVersions is None:
        preferredApiVersions = GetServiceVersions('vim25')

    sslContext = getSslContext(host, sslContext, disableSslCertValidation)

    supportedVersion = __FindSupportedVersion(protocol, host, port, path,
                                              preferredApiVersions, sslContext)
    if supportedVersion is None:
        raise Exception("%s:%s is not a VIM server" % (host, port))

    portNumber = protocol == "http" and -int(port) or int(port)

    return Connect(host=host,
                   port=portNumber,
                   user=user,
                   pwd=pwd,
                   service=service,
                   adapter='SOAP',
                   version=supportedVersion,
                   path=path,
                   keyFile=keyFile,
                   certFile=certFile,
                   thumbprint=thumbprint,
                   sslContext=sslContext,
                   httpConnectionTimeout=httpConnectionTimeout,
                   connectionPoolTimeout=connectionPoolTimeout,
                   token=token,
                   disableSslCertValidation=disableSslCertValidation,
                   customHeaders=customHeaders)


def OpenUrlWithBasicAuth(url, user='root', pwd=''):
    """
    Open the specified URL, using HTTP basic authentication to provide
    the specified credentials to the server as part of the request.
    Returns the response as a file-like object.
    """
    import urllib2
    pwMgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    pwMgr.add_password(None, url, user, pwd)
    handler = urllib2.HTTPBasicAuthHandler(pwMgr)
    opener = urllib2.build_opener(handler)
    return opener.open(url)


def OpenPathWithStub(path, stub):
    """
    Open the specified path using HTTP, using the host/port/protocol
    associated with the specified stub.  If the stub has a session cookie,
    it is included with the HTTP request.  Returns the response as a
    file-like object.
    """
    import urllib2
    if not hasattr(stub, 'scheme'):
        raise vmodl.fault.NotSupported()
    elif stub.scheme == http_client.HTTPConnection:
        protocol = 'http'
    elif stub.scheme == http_client.HTTPSConnection:
        protocol = 'https'
    else:
        raise vmodl.fault.NotSupported()
    hostPort = stub.host
    url = '%s://%s%s' % (protocol, hostPort, path)
    request = urllib2.Request(url)
    if stub.cookie:
        request.add_header('Cookie', stub.cookie)
    return urllib2.urlopen(request)


def IsManagedHost():
    """
    Check whether the host is managed by vCenter
    """
    try:
        SmartConnect()
        return False
    except Exception as e:
        # connect to local server will be refused when host managed by vCenter
        return True
