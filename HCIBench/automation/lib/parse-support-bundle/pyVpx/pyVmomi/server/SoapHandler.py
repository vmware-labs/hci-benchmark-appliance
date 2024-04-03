#!/usr/bin/env python
"""
Copyright 2008-2022 VMware, Inc.  All rights reserved. -- VMware Confidential

This module is the pyVmomi SOAP handler module. This handle SOAP request,
call server object and returns response
"""
__author__ = "VMware, Inc"

from abc import ABC, abstractmethod
import traceback
import threading
import logging
import random

# For xml parsing
import xml
from .XMLExpatHelper import XMLExpatHelper

from pyVmomi import VmomiSupport, SoapAdapter, Vmodl
from . import MoManager


# XML header string
_STR_XML_ENCODING = SoapAdapter.XML_ENCODING
_STR_XML_HEADER = SoapAdapter.XML_HEADER

NS_SEP = SoapAdapter.NS_SEP

_STR_ENVELOPE = SoapAdapter.XMLNS_SOAPENV + NS_SEP + "Envelope"
_STR_ENVELOPE_START = SoapAdapter.SOAP_ENVELOPE_START
_STR_ENVELOPE_END = "</" + SoapAdapter.SOAP_ENVELOPE_TAG + ">"

_STR_HEADER = SoapAdapter.XMLNS_SOAPENV + NS_SEP + "Header"

_STR_BODY = SoapAdapter.XMLNS_SOAPENV + NS_SEP + "Body"
_STR_BODY_START = "<" + SoapAdapter.SOAP_BODY_TAG + ">"
_STR_BODY_END = "</" + SoapAdapter.SOAP_BODY_TAG + ">"

_STR_FAULT = SoapAdapter.XMLNS_SOAPENV + NS_SEP + "Fault"
_STR_FAULT_START = "<" + SoapAdapter.SOAP_FAULT_TAG + ">"
_STR_FAULT_END = "</" + SoapAdapter.SOAP_FAULT_TAG + ">"

# SOAP accessor tag "Fetch"
_STR_FETCH = "Fetch"

# SOAP request parameter tag "_this"
_STR_THIS = "_this"

# SOAP accessor parameter tag "prop"
_STR_PROP = "prop"

# SOAP response tag "returnval"
_STR_RETURNVAL = "returnval"
_STR_RETURNVAL_START = "<" + _STR_RETURNVAL + ">"
_STR_RETURNVAL_END = "</" + _STR_RETURNVAL + ">"

_STR_SOAPENV_MUST_UNDERSTAND = SoapAdapter.XMLNS_SOAPENV + NS_SEP + 'mustUnderstand'

_XSD_STRING = VmomiSupport.GetQualifiedWsdlName(str)

ANONYMOUS_API_PRIVILEGE = "System.Anonymous"
_unauthFaultFactoryMap = {}


# Get property accessor parameters
#
# @return accessor parameters
def GetAccessorParams():
    """Get property accessor parameters"""
    params = tuple([
        VmomiSupport.Object(name="prop",
                            type=str,
                            version=VmomiSupport.BASE_VERSION,
                            flags=0)
    ])
    return params


# Get property accessor method
#
# @param  mo managed object
# @param  prop accessor property name
# @return accessor method
def GetAccessorMethod(mo, prop):
    """Get property accessor method"""

    # Technically objType should be the parent type with the prop. But don't
    # need the type yet. We are ok
    objType = type(mo)
    propInfo = VmomiSupport.GetPropertyInfo(objType, prop)
    info = VmomiSupport.Object(name=_STR_FETCH,
                               type=objType,
                               wsdlName=_STR_FETCH,
                               version=propInfo.version,
                               params=GetAccessorParams(),
                               isTask=False,
                               resultFlags=propInfo.flags,
                               result=propInfo.type,
                               methodResult=propInfo.type)
    return VmomiSupport.ManagedMethod(info)


# Get message from exception
#
# @param err the exception
# @return the error message
def ExceptionMsg(err):
    """Get exception message"""
    try:
        if err.msg is not None:
            msg = err.msg
        else:
            msg = ""
    except AttributeError:
        if len(err.args) > 0:
            msg = err.args[0]
        else:
            msg = err
    return msg


# Split xml tag with NS_SEP
def SplitTag(tag):
    """Split tag into ns, name"""
    tags = tag.split(NS_SEP, 1)
    if len(tags) > 1:
        return tags[0], tags[1]
    else:
        return "", tags[0]


# Context manager for renaming a thread for the duration of the given scope.
class _ThreadName:
    def __init__(self, name):
        self.name = name
        self.oldName = None

    def __enter__(self):
        self.oldName = threading.current_thread().name
        threading.current_thread().name = self.name
        return self

    def __exit__(self, *args):
        threading.current_thread().name = self.oldName
        # we don't handle exceptions
        return False


def _AuthCheck(authChecker, msg):
    method = msg.method
    if getattr(method.info, "privId", None) != ANONYMOUS_API_PRIVILEGE:
        if not authChecker.isAuthenticated(msg.context):
            nsId = VmomiSupport.GetVmodlNs(msg.version)
            factory = _unauthFaultFactoryMap.get(nsId)
            unauthnFault = factory.getUnauthnFault(msg) if factory else \
                Vmodl.Fault.SecurityError(
                    msg="Rejecting unauthenticated access to non-anonymous API method.")
            raise unauthnFault


# Authorizes method calls and property accesses.
#
# Subclasses should implement the validateMethodCall and validatePropertyAccess
# to check that the current user session has sufficient access privileges.
#
# @see SoapHandler.RegisterValidator
class Validator(ABC):
    # Validate a method call.  An exception should be raised if the current
    # session not have sufficient privileges.
    #
    # @param soapContext The SOAP context from VmomiSupport.
    # @param methodInfo The information about the method.
    # @param mo The managed object that the method is being invoked on.
    # @param params The parameters to the method.
    @abstractmethod
    def validateMethodCall(self, soapContext, methodInfo, mo, params):
        return

    # Validate access to a property.  An exception should be raised if the
    # current session does not have sufficient privileges.
    #
    # @param soapContext The SOAP context from VmomiSupport.
    # @param propInfo The information about the property.
    # @param mo The managed object that the property belongs to.
    @abstractmethod
    def validatePropertyAccess(self, soapContext, propInfo, mo):
        return


# SOAP server stub class
class SoapServerStubAdapter:
    """SOAP server stub adapter"""

    # Constructor
    #
    # @param  version the server version
    # @param  moMgr the managed object manager
    def __init__(self, version, moMgr):
        """SoapServerStubAdapter constructor"""
        # .version is required (used by SoapDeserializer)
        self.version = version
        self._moMgr = moMgr
        self.validatorList = []

    # Invoke a managed object method
    #
    # @param  mo this
    # @param  info method info
    # @param  args method arguments
    # @return method returned object
    def InvokeMethod(self, mo, info, args):
        """Call method"""

        # Lookup managed object
        obj = self._LookupObject(mo, info)

        # Get method from object
        method = getattr(obj, info.name)

        # Get arguments name from method info
        vmodlArgs = [param.name for param in info.params]

        # Validate method signature
        # 1. Method implementation argument list must match vmodl arguments
        #    list, in exact same order.
        # 2. Method implementation can have 'self' as first argument.
        #    Validation starts after 'self'.
        #    Note: no 'self' for static class method.
        # 3. Method implementation are allowed to have additional variable
        #    arguments following vmodl argument list.
        # TODO: Only do this in debug mode
        validateMethodSignature = getattr(obj, '_validateMethodSignature',
                                          True)
        numParams = len(info.params)
        if validateMethodSignature and numParams > 0:
            # Get method arguments
            methodArgs = method.__code__.co_varnames[:method.__code__.
                                                     co_argcount]

            # See 2 above
            methodIdx = 0
            if methodArgs[0] == 'self':
                methodIdx = 1

            # See 1 & 3 above
            if vmodlArgs != list(
                    methodArgs[methodIdx:(methodIdx + numParams)]):
                msg = "Method signature mismatch"
                reason = "Vmodl definition is %s while method %s is defined as %s" \
                         % (vmodlArgs, method.__name__, methodArgs[methodIdx:])
                logging.error("%s: %s" % (msg, reason))
                raise Vmodl.Fault.SystemError(msg=msg, reason=reason)
            del methodArgs

        # Call method
        params = dict(list(zip(vmodlArgs, args)))
        context = VmomiSupport.GetRequestContext()
        for validator in self.validatorList:
            validator.validateMethodCall(context, info, mo, params)
        response = method(**params)
        del params
        del obj

        return response

    # Invoke a managed object accessor
    #
    # @param  mo this
    # @param  info method info
    # @return property value
    def InvokeAccessor(self, mo, info):
        """Get property"""
        obj = self._LookupObject(mo, info)
        context = VmomiSupport.GetRequestContext()
        for validator in self.validatorList:
            validator.validatePropertyAccess(context, info, mo)
        val = getattr(obj, info.name)
        return val

    # Lookup a managed object
    #
    # @param  mo this
    # @param  info method info
    # @return managed object
    def _LookupObject(self, mo, info):
        """Lookup managed object from object id"""

        # Check version
        if not VmomiSupport.IsChildVersion(self.version, info.version):
            logging.error(self.version + " not child version of " +
                          info.version)
            raise Vmodl.Fault.MethodNotFound(receiver=mo, method=info.name)

        try:
            # Lookup objects
            serverGuid = getattr(mo, "_serverGuid", None)
            obj = self._moMgr.LookupObject(mo._moId, serverGuid)
        except Exception:
            message = "Failed to find (" + mo._moId + ")" + \
                      " serverGuid (" + str(serverGuid) + ")"
            logging.error(message)
            raise Vmodl.Fault.ManagedObjectNotFound(msg=message, obj=mo)

        # TODO: Verify object type
        return obj


# SOAP msg class (hold info for deserialized soap msg)
class SoapMsg:
    """SOAP message class"""
    def __init__(self):
        pass


# SOAP response msg class
class SoapMsgResponse(SoapMsg):
    """SOAP response message class"""

    # Constructor
    #
    # @param  version the message version
    # @param  method the managed method
    # @param  retVal the return value
    def __init__(self, version, method, retVal):
        SoapMsg.__init__(self)
        self.version = version
        self.method = method
        self.retVal = retVal


# SOAP fault msg class
class SoapMsgFault(SoapMsg):
    """Soap fault message class"""
    def __init__(self):
        SoapMsg.__init__(self)


class SoapMsgRequest(SoapMsg):
    """SOAP request message class"""

    # Constructor
    #
    # @param  version the message version
    # @param  isTask true for task, false otherwise
    # @param  mo the managed object
    # @param  method the managed method
    # @param  params the managed method parameters
    def __init__(self, version, isTask, mo, method, params):
        SoapMsg.__init__(self)
        self.version = version
        self.isTask = isTask
        self.mo = mo
        self.method = method
        self.params = params


class SoapMsgAccessor(SoapMsgRequest):
    """SOAP accessor message class"""

    # Constructor
    #
    # @param  version the message version
    # @param  mo the managed object
    # @param  method the managed method
    # @param  prop the managed property name
    def __init__(self, version, mo, method, prop):
        SoapMsgRequest.__init__(self, version, False, mo, method, prop)


# class to deserialize managed method parameters
class SoapMethodParamsDeserializer(SoapAdapter.ExpatDeserializerNSHandlers):
    """SOAP method parameters serializer"""

    # Constructor
    #
    # @param  helper the XMLExpatHelper
    # @param  version the server mo version
    # @param  params the method params [list of obj with attr name and type]
    # @param  nsMap a dict of ns prefix -> [xml ns stack]
    def __init__(self, helper, version, params, nsMap):
        SoapAdapter.ExpatDeserializerNSHandlers.__init__(self, nsMap)
        self.helper = helper
        self.params = params
        self.version = version
        self.soapDeserializer = None
        self.data = ""
        self.objType = None
        self.serverGuid = None
        self.allResults = {}
        self.element = 0
        self.thisTag = VmomiSupport.GetWsdlNamespace(
            version) + NS_SEP + _STR_THIS

    # Get accumulated results
    #
    # @return SOAP parameter result. A dict of tag str mapped to parameter obj
    def GetResult(self):
        """Get accumulated results"""
        # Set default val for optional array
        if self.params:
            for param in self.params:
                if param.flags & VmomiSupport.F_OPTIONAL \
                and not param.name in self.allResults \
                and issubclass(param.type, list):
                    self.allResults[param.name] = param.type()
        return self.allResults

    # Handle an opening XML tag
    #
    # @param  tag the XML tag
    # @param  attr the XML attribute
    def StartElementHandler(self, tag, attr):
        """Start XML element"""

        if not self.soapDeserializer:
            self.data = ""
            if tag == self.thisTag or tag == _STR_THIS:
                try:
                    typeAttr = attr[u'type']
                    ns, name = self.GetNSAndWsdlname(typeAttr)
                    self.objType = VmomiSupport.GetWsdlType(ns, name)
                except KeyError:
                    try:
                        # Do a second attempt at finding the type.
                        # XXX: We need a cleaner fix for this.
                        # Problem description:
                        # If vpxd3 is a child namespace of vim25, if we pass
                        # vpxd3 as a default namespace, resolution fails for
                        # objects in vim25 namespace even though vpxd3 is a
                        # child namespace of vim25.  This fix is a temporary
                        # one to deal with that failure.
                        typeAttr = attr[u'type']
                        self.objType = VmomiSupport.GuessWsdlType(typeAttr)
                    except KeyError:
                        message = "Unknown type (" + attr.get(u"type") + ")"
                        logging.error(message)
                        raise Vmodl.Fault.InvalidRequest(msg=message)
                self.serverGuid = attr.get(u"serverGuid")
            elif self.params:
                # Check for known function parameters
                _, name = SplitTag(tag)
                for param in self.params:
                    if param.name == name:
                        # Deserialize if parameter exists in this version
                        parser = self.helper.GetParser()

                        # Save hijacked handlers as soapDeserializer
                        # overrides them.
                        origHandlers = SoapAdapter.GetHandlers(parser)

                        # Setup SOAP deserializer
                        self.soapDeserializer = SoapAdapter.SoapDeserializer(
                            version=self.version)
                        self.soapDeserializer.Deserialize(
                            parser,
                            param.type,
                            False,  # isFault
                            self.nsMap)

                        # Restore original handlers
                        SoapAdapter.SetHandlers(parser, origHandlers)

                        # Call SOAP deserializer for current tag
                        self.soapDeserializer.StartElementHandler(tag, attr)
                        self.element = 1
                        break

                # Unknown paramters
        else:
            self.element += 1
            self.soapDeserializer.StartElementHandler(tag, attr)

    # Handle text data
    #
    # @param  data the XML node data
    def CharacterDataHandler(self, data):
        """Character handler"""

        if not self.soapDeserializer:
            self.data += data
        else:
            self.soapDeserializer.CharacterDataHandler(data)

    # Handle a closing XML tag
    #
    # @param  tag the XML tag
    def EndElementHandler(self, tag):
        """End XML element"""

        if not self.soapDeserializer:
            if tag == self.thisTag or tag == _STR_THIS:
                # Construct this object from object type
                self._SaveResult(
                    _STR_THIS,
                    self.objType(self.data, serverGuid=self.serverGuid))
            else:
                # Unknown paramters
                pass
        else:
            self.soapDeserializer.EndElementHandler(tag)
            self.element -= 1
            if self.element == 0:
                _, name = SplitTag(tag)
                self._SaveResult(name, self.soapDeserializer.GetResult())
                self.soapDeserializer = None

    # Get/Set expat handlers fn for this class
    # Callback required by XMLExpatHelper
    #
    # @param  dst Expat parser to copy handlers to
    # @param  src Expat parser to copy handlers from
    # @return an object with overwritten handlers
    @staticmethod
    def ExpatHandlers(dst, src):
        ret = VmomiSupport.Object(
            StartElementHandler=dst.StartElementHandler,
            EndElementHandler=dst.EndElementHandler,
            CharacterDataHandler=dst.CharacterDataHandler,
            StartNamespaceDeclHandler=dst.StartNamespaceDeclHandler,
            EndNamespaceDeclHandler=dst.EndNamespaceDeclHandler)
        dst.StartElementHandler = src.StartElementHandler
        dst.EndElementHandler = src.EndElementHandler
        dst.CharacterDataHandler = src.CharacterDataHandler
        dst.StartNamespaceDeclHandler = src.StartNamespaceDeclHandler
        dst.EndNamespaceDeclHandler = src.EndNamespaceDeclHandler
        return ret

    # Save result obj associated with tag
    #
    # @param  tag the XML tag (without ns info)
    # @param  obj the obj associated with the XML tag
    def _SaveResult(self, tag, obj):
        """Save result object"""
        assert (tag.find(NS_SEP) == -1)
        # Note: tag could be in unicode. Always convert it to ascii
        tag = str(tag)
        if tag in self.allResults:
            origObj = self.allResults[tag]
            if not isinstance(origObj, list) or not isinstance(obj, list):
                message = "Duplicated tag " + tag
                logging.error(message)
                raise Vmodl.Fault.InvalidRequest(msg=message)
            origObj.extend(obj)
        else:
            self.allResults[tag] = obj


# class to deserialize SOAP header
class SoapHeaderDeserializer(SoapAdapter.ExpatDeserializerNSHandlers):
    """SOAP header deserializer"""

    # Constructor
    #
    # @param  helper the XMLExpatHelper
    # @param  nsMap a dict of ns prefix -> [xml ns stack]
    def __init__(self, helper, nsMap):
        SoapAdapter.ExpatDeserializerNSHandlers.__init__(self, nsMap)
        self.helper = helper
        self.level = 0
        self.value = ''
        self.result = {}

    # Get result string
    #
    # @return SOAP body result str
    def GetResult(self):
        """Get result (request context dict)"""
        return self.result

    # Handle an opening XML tag
    #
    # @param  tag the XML tag
    # @param  attr the XML attribute
    def StartElementHandler(self, tag, attr):
        """Start XML element"""
        if self.level == 0:
            self.tag = tag
            self.mustUnderstand = attr.get(_STR_SOAPENV_MUST_UNDERSTAND)
            self.xsiType = attr.get(SoapAdapter.XSI_TYPE)
            self.complex = False
        else:
            self.complex = True
        self.level += 1

    # Handle text data
    #
    # @param  data the XML node data
    def CharacterDataHandler(self, data):
        """Character handler"""
        if self.level == 1:
            self.value = data

    # Handle a closing XML tag
    #
    # @param  tag the XML tag
    def EndElementHandler(self, tag):
        """End XML element"""
        self.level -= 1
        if self.level == 0:
            assert (self.tag == tag)
            # VMOMI request context (currently) only supports values of type
            # string, so if the SOAP header element was complex, or didn't have
            # type string we ignore it.  If no xsi:type was specified and it
            # wasn't complex, we just assume it was a string.  If we want to
            # ignore an element, but it had a mustUnderstand attribute with
            # value "1", we raise an exception instead.
            if not self.complex and (
                    not self.xsiType
                    or self.xsiType == 'string'  # workaround bug 553406
                    or self.GetNSAndWsdlname(self.xsiType) == _XSD_STRING):
                _, name = SplitTag(tag)
                self.result[name] = self.value
            elif self.mustUnderstand == '1':
                fmt = 'Unsupported type for SOAP header %s, but mustUnderstand is specified'
                raise Exception(fmt % tag)
            self.tag = None

    # Get/Set expat handlers fn for this class
    # Callback required by XMLExpatHelper
    #
    # @param  dst Expat parser to copy handlers to
    # @param  src Expat parser to copy handlers from
    # @return an object with overwritten handlers
    @staticmethod
    def ExpatHandlers(dst, src):
        ret = VmomiSupport.Object(
            StartElementHandler=dst.StartElementHandler,
            EndElementHandler=dst.EndElementHandler,
            CharacterDataHandler=dst.CharacterDataHandler,
            StartNamespaceDeclHandler=dst.StartNamespaceDeclHandler,
            EndNamespaceDeclHandler=dst.EndNamespaceDeclHandler)
        dst.StartElementHandler = src.StartElementHandler
        dst.EndElementHandler = src.EndElementHandler
        dst.CharacterDataHandler = src.CharacterDataHandler
        dst.StartNamespaceDeclHandler = src.StartNamespaceDeclHandler
        dst.EndNamespaceDeclHandler = src.EndNamespaceDeclHandler
        return ret


# class to deserialize managed method
class SoapBodyDeserializer(SoapAdapter.ExpatDeserializerNSHandlers):
    """SOAP body serializer"""

    # Constructor
    #
    # @param  helper the XMLExpatHelper
    # @param  nsMap a dict of ns prefix -> [xml ns stack]
    def __init__(self, helper, nsMap):
        SoapAdapter.ExpatDeserializerNSHandlers.__init__(self, nsMap)
        self.helper = helper
        self.data = ""
        self.method = None
        if self.helper.soapVersion:
            version = self.helper.soapVersion
        else:
            version = None
        self.SetVersion(version)
        self.soapMethodParamsDeserializer = None
        self.result = None
        self.isTask = False

    # Get result string
    #
    # @return SOAP method result str
    def GetResult(self):
        """Get result string"""
        return self.result

    # version setter
    def SetVersion(self, version):
        self.version = version
        if version:
            ns = VmomiSupport.GetWsdlNamespace(version)
            self.fetchTag = ns + NS_SEP + _STR_FETCH

    # Handle an opening XML tag
    #
    # @param  tag the XML tag
    # @param  attr the XML attribute
    def StartElementHandler(self, tag, attr):
        """Start XML element"""

        # Check method name
        if tag == _STR_FAULT:
            pass
        else:
            # Get version from default namespace if version is not known
            if not self.version:
                try:
                    ns = self.GetCurrDefNS()
                    self.SetVersion(ns)
                except KeyError:
                    message = "Unknown namespace " + ns
                    logging.error(message)
                    raise Vmodl.Fault.InvalidRequest(msg=message)

            # Deserialize requests and responses
            try:
                if tag == self.fetchTag or tag == _STR_FETCH:
                    params = GetAccessorParams()
                else:
                    isResponse = False
                    if tag.endswith("Response"):
                        name = tag[:-8]
                        isResponse = True
                    elif tag.endswith("_Task"):
                        name = tag
                        self.isTask = True
                    else:
                        name = tag
                    ns, name = SplitTag(name)
                    if not ns:
                        ns = self.GetCurrDefNS()
                    try:
                        self.method = VmomiSupport.GetWsdlMethod(ns, name)
                    except KeyError:
                        # Do a second attempt at finding the methodName.
                        # XXX: We need a cleaner fix for this.
                        # Problem description:
                        # If vpxd3 is a child namespace of vim25, if we pass
                        # vpxd3 as a default namespace, resolution fails for
                        # methods in vim25 namespace even though vpxd3 is a
                        # child namespace of vim25.  This fix is a temporary
                        # one to deal with that failure.
                        self.method = VmomiSupport.GuessWsdlMethod(name)
                    if not isResponse:
                        params = self.method.info.params
                    else:
                        # TODO: Make info.result same as param object
                        params = [
                            VmomiSupport.Object(name=_STR_RETURNVAL,
                                                type=self.method.info.result,
                                                version=self.version,
                                                flags=0)
                        ]
            except Exception:
                logging.error("Unknown method " + tag)
                params = None
                # We cannot raise MethodNotFound here, as we don't know
                # _this yet!
                # raise Vmodl.Fault.MethodNotFound(receiver=None, method=tag)

            # Start parameters parsing
            self.soapMethodParamsDeserializer = \
                    SoapMethodParamsDeserializer(self.helper, self.version,
                                                 params, self.nsMap)
            self.helper.SubHandler(self.soapMethodParamsDeserializer)

    # Handle a closing XML tag
    #
    # @param  tag the XML tag
    def EndElementHandler(self, tag):
        """End XML element"""
        if tag == _STR_FAULT:
            pass
        elif tag.endswith("Response"):
            result = self.soapMethodParamsDeserializer.GetResult()
            try:
                retVal = result[_STR_RETURNVAL]
            except KeyError:
                message = "Missing return value"
                logging.error(message)
                raise Vmodl.Fault.InvalidType(msg=message)

            self.result = SoapMsgResponse(self.version, self.method, retVal)
        else:
            # Assign to a callable method class
            _, name = SplitTag(tag)
            paramDict = self.soapMethodParamsDeserializer.GetResult()
            mo = paramDict.pop(_STR_THIS, None)
            if not mo:
                message = "Method (" + name + ") missing parameter: _this"
                logging.error(message)
                raise Vmodl.Fault.InvalidRequest(msg=message)

            # Fill in missing method info
            if tag == self.fetchTag or tag == _STR_FETCH:
                prop = ""
                try:
                    prop = paramDict[_STR_PROP]
                    # Fill in missing accessor info
                    accessor = GetAccessorMethod(mo, prop)
                except Exception:
                    message = "Property not found: " + name + " (" + prop + ")"
                    logging.error(message)
                    raise Vmodl.Fault.MethodNotFound(msg=message,
                                                     receiver=mo,
                                                     method=name)

                self.result = SoapMsgAccessor(self.version, mo, accessor, prop)
            else:
                if not self.method:
                    message = "Method not found: " + name
                    logging.error(message)
                    raise Vmodl.Fault.MethodNotFound(msg=message,
                                                     receiver=mo,
                                                     method=name)

                self.result = SoapMsgRequest(self.version, self.isTask, mo,
                                             self.method, paramDict)

    # Get/Set expat handlers fn for this class
    # Callback required by XMLExpatHelper
    #
    # @param  dst Expat parser to copy handlers to
    # @param  src Expat parser to copy handlers from
    # @return an object with overwritten handlers
    @staticmethod
    def ExpatHandlers(dst, src):
        ret = VmomiSupport.Object(
            StartElementHandler=dst.StartElementHandler,
            EndElementHandler=dst.EndElementHandler,
            StartNamespaceDeclHandler=dst.StartNamespaceDeclHandler,
            EndNamespaceDeclHandler=dst.EndNamespaceDeclHandler)
        dst.StartElementHandler = src.StartElementHandler
        dst.EndElementHandler = src.EndElementHandler
        dst.StartNamespaceDeclHandler = src.StartNamespaceDeclHandler
        dst.EndNamespaceDeclHandler = src.EndNamespaceDeclHandler
        return ret


# class to deserialize SOAP header or body
class SoapHeaderBodyDeserializer(SoapAdapter.ExpatDeserializerNSHandlers):
    """SOAP header and body serializer"""

    # Constructor
    #
    # @param  helper the XMLExpatHelper
    # @param  nsMap a dict of ns prefix -> [xml ns stack]
    def __init__(self, helper, nsMap):
        SoapAdapter.ExpatDeserializerNSHandlers.__init__(self, nsMap)
        self.helper = helper
        self.soapHeaderDeserializer = None
        self.soapBodyDeserializer = None

    # Get result string
    #
    # @return SOAP body result str
    def GetResult(self):
        """Get result string"""
        if self.soapBodyDeserializer:
            result = self.soapBodyDeserializer.GetResult()
            if self.soapHeaderDeserializer:
                result.context = self.soapHeaderDeserializer.GetResult()
            else:
                result.context = {}
        else:
            result = None
        return result

    # Handle an opening XML tag
    #
    # @param  tag the XML tag
    # @param  attr the XML attribute
    def StartElementHandler(self, tag, attr):
        """Start XML element"""
        if tag == _STR_HEADER:
            if self.soapBodyDeserializer is not None:
                message = "Unexpected Header tag following Body tag"
                logging.error(message)
                raise Vmodl.Fault.InvalidRequest(msg=message)
            if self.soapHeaderDeserializer is not None:
                message = "Duplicated tag " + tag
                logging.error(message)
                raise Vmodl.Fault.InvalidRequest(msg=message)
            self.soapHeaderDeserializer = \
               self.helper.SubHandler(SoapHeaderDeserializer(self.helper,
                                                             self.nsMap))
        elif tag == _STR_BODY:
            if self.soapBodyDeserializer is not None:
                message = "Duplicated tag " + tag
                logging.error(message)
                raise Vmodl.Fault.InvalidRequest(msg=message)
            self.soapBodyDeserializer = \
               self.helper.SubHandler(SoapBodyDeserializer(self.helper,
                                                           self.nsMap))
        else:
            # Disallow unknown tag?
            # raise Vmodl.Fault.InvalidRequest(msg="Unexpected tag " + tag)
            pass

    # Handle a closing XML tag
    #
    # @param  tag the XML tag
    def EndElementHandler(self, tag):
        """End XML element"""
        if tag == _STR_HEADER or tag == _STR_BODY:
            pass
        else:
            # Disallow unknown tag?
            # raise Vmodl.Fault.InvalidRequest(msg="Unexpected tag " + tag)
            pass

    # Get/Set expat handlers fn for this class
    # Callback required by XMLExpatHelper
    #
    # @param  dst Expat parser to copy handlers to
    # @param  src Expat parser to copy handlers from
    # @return an object with overwritten handlers
    @staticmethod
    def ExpatHandlers(dst, src):
        ret = VmomiSupport.Object(
            StartElementHandler=dst.StartElementHandler,
            EndElementHandler=dst.EndElementHandler,
            StartNamespaceDeclHandler=dst.StartNamespaceDeclHandler,
            EndNamespaceDeclHandler=dst.EndNamespaceDeclHandler)
        dst.StartElementHandler = src.StartElementHandler
        dst.EndElementHandler = src.EndElementHandler
        dst.StartNamespaceDeclHandler = src.StartNamespaceDeclHandler
        dst.EndNamespaceDeclHandler = src.EndNamespaceDeclHandler
        return ret


# class to deserialize SOAP envelope
class SoapEnvelopeDeserializer(SoapAdapter.ExpatDeserializerNSHandlers):
    """SOAP envelope serializer"""
    def __init__(self):
        SoapAdapter.ExpatDeserializerNSHandlers.__init__(self)
        self.parser = None
        self.helper = None
        self.soapHeaderBodyDeserializer = None

    # Reset this obj back to clean state
    #
    # @param version the SOAP message vmomi version
    def Reset(self, version=None):
        """Reset this obj back to clean state"""
        # We cannot use the same xml parser to parse multiple documents.
        # Have to reset
        del self.parser
        self.parser = xml.parsers.expat.ParserCreate(
            namespace_separator=NS_SEP)
        self.parser.buffer_text = True

        del self.helper
        self.helper = XMLExpatHelper(self.parser)
        self.helper.SubHandler(self)

        # Put version into helper
        assert (not hasattr(self.helper, "soapVersion"))
        setattr(self.helper, "soapVersion", version)

        # Reset deserializer
        self.soapHeaderBodyDeserializer = None

    # Get result string
    #
    # @return SOAP envelope result str
    def GetResult(self):
        """Get result string"""
        if self.soapHeaderBodyDeserializer:
            result = self.soapHeaderBodyDeserializer.GetResult()
        else:
            result = None
        return result

    # Parse SOAP envelope
    #
    # @param envelope the envelope to parse
    # @param version the SOAP message vmomi version
    def Parse(self, envelope, version=None):
        """Parse SOAP envelope"""
        self.Reset(version)
        # Many existing tests pass in str directly in python2 for testing
        # purpose.  But in python3 the input become unicode and the handling
        # will fall into ParseFile case.  Adding unicode input support to make
        # it more test friendly.
        if isinstance(envelope, str) or isinstance(envelope, bytes):
            self.parser.Parse(envelope)
        else:
            self.parser.ParseFile(envelope)

    # Handle an opening XML tag
    #
    # @param  tag the XML tag
    # @param  attr the XML attribute
    def StartElementHandler(self, tag, attr):
        """Start XML element"""
        if tag == _STR_ENVELOPE:
            if self.soapHeaderBodyDeserializer is None:
                self.soapHeaderBodyDeserializer = \
                   self.helper.SubHandler(SoapHeaderBodyDeserializer(self.helper,
                                                                     self.nsMap))
            else:
                message = "Duplicated tag " + tag
                logging.error(message)
                raise Vmodl.Fault.InvalidRequest(msg=message)
        else:
            # Disallow unknown tag?
            # raise Vmodl.Fault.InvalidRequest(msg="Unexpected tag " + tag)
            pass

    # Handle a closing XML tag
    #
    # @param  tag the XML tag
    def EndElementHandler(self, tag):
        """End XML element"""
        if tag == _STR_ENVELOPE:
            pass
        else:
            # Disallow unknown tag?
            # raise Vmodl.Fault.InvalidRequest(msg="Unexpected tag " + tag)
            pass

    # Get/Set expat handlers fn for this class
    #  Callback required by XMLExpatHelper
    #
    # @param  dst Expat parser to copy handlers to
    # @param  src Expat parser to copy handlers from
    # @return an object with overwritten handlers
    @staticmethod
    def ExpatHandlers(dst, src):
        """Get/Set expat handlers fn for this class"""
        ret = VmomiSupport.Object(
            StartElementHandler=dst.StartElementHandler,
            EndElementHandler=dst.EndElementHandler,
            StartNamespaceDeclHandler=dst.StartNamespaceDeclHandler,
            EndNamespaceDeclHandler=dst.EndNamespaceDeclHandler)
        dst.StartElementHandler = src.StartElementHandler
        dst.EndElementHandler = src.EndElementHandler
        dst.StartNamespaceDeclHandler = src.StartNamespaceDeclHandler
        dst.EndNamespaceDeclHandler = src.EndNamespaceDeclHandler
        return ret


# SOAP serializer class
#
class SoapSerializer:
    """SOAP serializer"""

    _SOAP_BEGIN = _STR_XML_HEADER + _STR_ENVELOPE_START + _STR_BODY_START
    _SOAP_END = _STR_BODY_END + _STR_ENVELOPE_END

    _anyType = VmomiSupport.GetVmodlType("anyType")

    def __init__(self, encoding=_STR_XML_ENCODING):
        self.encoding = encoding

    # Serialize SOAP response
    #
    # @param  version the response version (client version)
    # @param  method the managed object method
    # @param  value the response object to serialize
    # @return serialized SOAP response msg
    def SerializeResponse(self, version, method, value):
        """Serialize SOAP response"""
        ns = VmomiSupport.GetWsdlNamespace(version)
        responseTag = method.info.wsdlName + "Response"
        resultType = method.info.result
        returnval = ""
        if resultType is VmomiSupport.NoneType:
            # void return value
            if value:
                # TODO: throw invalid return value?
                pass
        else:
            if value != None:
                # Fetch result are serialized as any since ESX 3.5
                if method.info.name == _STR_FETCH:
                    resultType = self._anyType
                info = VmomiSupport.Object(name=_STR_RETURNVAL,
                                           type=resultType,
                                           version=version,
                                           flags=method.info.resultFlags)
                nsMap = SoapAdapter.SOAP_NSMAP.copy()
                # Set default ns
                nsMap[ns] = ''
                returnval = SoapAdapter.SerializeToStr(
                    value, info, version, nsMap)
            else:
                # Throw if return value is not optional
                if not method.info.resultFlags & VmomiSupport.F_OPTIONAL:
                    raise Vmodl.RuntimeFault(msg="Missing return value")

        result = "".join([
            self._SOAP_BEGIN, "<", responseTag, " xmlns='", ns, "'>",
            returnval, "</", responseTag, ">", self._SOAP_END
        ])
        return result

    # Serialize SOAP header fault (fault not related to SOAP body processing).
    # Should not contain detail tag.
    #
    # @param  faultCode the fault code
    # @param  message the fault message
    def SerializeHeaderFault(self, faultCode, message):
        """Serialize SOAP header fault"""
        escapedMsg = message and SoapAdapter.XmlEscape(message) or ""
        result = "".join([
            self._SOAP_BEGIN, _STR_FAULT_START, "<faultcode>", faultCode,
            "</faultcode>", "<faultstring>", escapedMsg, "</faultstring>",
            _STR_FAULT_END, self._SOAP_END
        ])
        return result

    # Serialize SOAP fault
    #
    # @param  faultCode the fault code
    # @param  fault the fault object
    # @param  version the response version (client version)
    # @return serialized SOAP fault msg
    def SerializeFault(self, faultCode, fault, version):
        """Serialize SOAP fault"""
        if not version:
            version = fault._version
        info = VmomiSupport.Object(name=fault._wsdlName + "Fault",
                                   type=VmomiSupport.Type(fault),
                                   version=version,
                                   flags=0)
        message = fault.msg
        fault.msg = None
        escapedMsg = message and SoapAdapter.XmlEscape(message) or ""
        nsMap = SoapAdapter.SOAP_NSMAP.copy()
        faultDetail = SoapAdapter.SerializeFaultDetail(fault,
                                                       info,
                                                       version,
                                                       nsMap,
                                                       encoding=self.encoding)
        result = "".join([
            self._SOAP_BEGIN, _STR_FAULT_START, "<faultcode>", faultCode,
            "</faultcode>", "<faultstring>", escapedMsg, "</faultstring>",
            "<detail>", faultDetail, "</detail>", _STR_FAULT_END,
            self._SOAP_END
        ])
        return result

    # Serialize server SOAP fault
    #
    # @param  fault the fault object
    # @param  version the response version (client version)
    # @return serialized SOAP fault msg
    def SerializeServerFault(self, fault, version=None):
        """Serialize server SOAP fault"""
        return self.SerializeFault("ServerFaultCode", fault, version)


# class to deserialize SOAP message
class SoapHandler:
    """SOAP handler"""

    _setupCompleted = False
    _authChecker = None

    # Create server stubs
    _moMgr = MoManager.GetMoManager()
    _moStubs = {}

    @classmethod
    def isSetupCompleted(cls):
        return cls._setupCompleted

    @classmethod
    def Setup(cls):
        if cls.isSetupCompleted():
            raise RuntimeError("SoapHandler is already setup")

        from .Security import GetAuthChecker
        cls._authChecker = GetAuthChecker()
        for version in VmomiSupport.nsMap:
            stub = SoapServerStubAdapter(version, cls._moMgr)
            cls._moStubs[version] = [(cls._moMgr, stub)]
        cls._setupCompleted = True

    @classmethod
    def RegisterValidator(cls, validator):
        if not cls.isSetupCompleted():
            raise RuntimeError("Setup SoapHandler before registering validators")

        for stubList in list(cls._moStubs.values()):
            for _mgr, stub in stubList:
                stub.validatorList.append(validator)


    @classmethod
    # Register a namespace-specific "not authenticated" faults.
    # These faults will be returned to non-authenticated clients
    # making remote calls to privileged methods.
    def SetUnauthenticatedFaultFactory(cls, namespaceId, faultFactory):
        _unauthFaultFactoryMap[namespaceId] = faultFactory

    # Create SOAP fault
    _soapSystemError = SoapSerializer().SerializeServerFault(
        Vmodl.Fault.SystemError(msg="System Error", reason="System Error"))

    # Default (dummy) managed objects manager.
    # Overrides base to make LookupObject always return a managed object
    class DefaultManagedObjectsManager(MoManager.ManagedObjectsManager):
        """Default managed objects manager"""
        def __init__(self, stub):
            MoManager.ManagedObjectsManager.__init__(self)
            self.stub = stub

        def LookupObject(self, moId, serverGuid=None):
            """Return a fake object"""
            return VmomiSupport.ManagedObject(moId, self.stub, serverGuid)

    # Constructor
    #
    # @param  stubs a dict of {version: (moMgr, stub)}
    #       - moMgr must implement LookupObject (to lookup a moid)
    #       - stub will be used for calling method if LookupObject succeed
    #       - If the version name is 'default', the corresponding stubs will be
    #         used for all known versions
    #       - If moMgr is None, a default mo manager will be created, and
    #         simply return a valid object for all moId
    def __init__(self, stubs=None):
        if not self.isSetupCompleted():
            raise Exception("The SoapHandler setup is not completed")
        if stubs:
            # Default stub
            defaultMoMgr, defaultStub = stubs.get('default')
            if not defaultMoMgr:
                defaultMoMgr = self.DefaultManagedObjectsManager(defaultStub)
            for version in VmomiSupport.nsMap:
                moMgr, stub = stubs.get(version, (defaultMoMgr, defaultStub))
                if stub:
                    if not moMgr:
                        moMgr = self.DefaultManagedObjectsManager(stub)
                    self._moStubs[version].append((moMgr, stub))
        elif len(VmomiSupport.nsMap) != len(self._moStubs):
            # The _moStubs array is created by walking nsMap when this module
            # is loaded.  If new entries have been added to
            # nsMap (e.g. by the DTM) since then, we need to rebuild _moStubs.
            for version in VmomiSupport.nsMap:
                stub = SoapServerStubAdapter(version, self._moMgr)
                self._moStubs[version] = [(self._moMgr, stub)]
        self._soapSerializer = SoapSerializer()


    # Handle a SOAP request
    #
    # @param request a SOAP request (str or file)
    # @param wireVersion the request version (namespace/versionId)
    # @return tuple(isFault, SOAP response str)
    def HandleRequest(self, request, wireVersion=None):
        """Handle a SOAP request"""
        try:
            version = None
            if wireVersion:
                version = self._GetHeaderVersion(wireVersion)
                if not version:
                    # namespace not found. Not able to handle it at all
                    message = "Unsupported version URI urn:" + wireVersion
                    logging.error(message)
                    isFault = True
                    return isFault, self._soapSerializer.SerializeHeaderFault(
                        "ClientFaultCode", message)

            return self._HandleRequest(request, version)
        except Exception as err:
            message = ExceptionMsg(err)
            if message:
                logging.error(message)
            stackTrace = traceback.format_exc()
            if stackTrace:
                logging.error(stackTrace)

            # Return something if SerializeServerFault throw exception
            isFault = True
            return isFault, self._soapSystemError

    # Get vmomi version from request version (namespace/versionId)
    #
    # @param wireVersion the request version (namespace/versionId)
    # @return vmomi version
    def _GetHeaderVersion(self, wireVersion):
        """Get vmomi version from request version (namespace/versionId)"""

        # Get vmomi version from incoming namespace/versionId
        reqVersion = VmomiSupport.versionMap.get(wireVersion)
        if not reqVersion:
            # namespace/versionId not found. Try namespace alone
            reqNS = wireVersion.split('/')[0]
            reqVersion = VmomiSupport.versionMap.get(reqNS)
            if reqVersion:
                # Get the latest version within that namespace
                # TODO: This is not right to walk down the tree. Need some
                #       other way to get to the current version
                for version, ns in VmomiSupport.nsMap.items():
                    if reqNS == ns and VmomiSupport.IsChildVersion(
                            version, reqVersion):
                        reqVersion = version
        return reqVersion

    # Get managed object stub
    #
    # @param version the request version
    # @param mo managed object
    # @return stub
    def _GetMoStub(self, version, mo):
        """Get stub for this version of managed object"""
        moStub = None
        moMgrStubs = self._moStubs.get(version)
        for moMgr, stub in moMgrStubs:
            try:
                # Throws key error if not found
                moMgr.LookupObject(mo._moId, mo._serverGuid)
                moStub = stub
                break
            except KeyError:
                try:
                    # Try looking up a MoFactory
                    logging.info("Looking up mo factory for %s" %
                                 mo.__class__._wsdlName)
                    factory = moMgr.LookupMoFactory(mo.__class__)
                    factory.CreateInstance(mo._moId, mo._serverGuid)
                    # If successful, set the stub
                    moStub = stub
                    break
                except KeyError:
                    logging.error("Failed to find object using mofactory")
                    pass

        return moStub

    # Handle a SOAP request, internal
    #
    # @param request a SOAP request (str or file)
    # @param version the request vmomi version
    # @return tuple(isFault, SOAP response str)
    # @throw Vmodl.MethodFault (and its subclass)
    def _HandleRequest(self, request, version=None):
        """Handle a SOAP request, internal"""
        try:
            msg = self._DeserializeMessage(request, version)
            _AuthCheck(self._authChecker, msg)
            return self._InvokeMethod(msg)
        except Exception as err:
            message = ExceptionMsg(err)
            if message:
                logging.error(message)
            stackTrace = traceback.format_exc()
            if stackTrace:
                logging.error(stackTrace)
            return self.ProcessException(err, message, version)

    def _DeserializeMessage(self, request, version):
        # Parse incoming SOAP request
        soapDeserializer = SoapEnvelopeDeserializer()
        try:
            soapDeserializer.Parse(request, version)
        except xml.parsers.expat.ExpatError as expatErr:
            # Handle expat error
            message = "Parse error at line " + str(expatErr.lineno) + \
                      ": " + xml.parsers.expat.ErrorString(expatErr.code)
            logging.error(message)
            raise Vmodl.Fault.InvalidRequest(msg=message)
        msg = soapDeserializer.GetResult()

        # Only handle request
        if not isinstance(msg, SoapMsgRequest):
            # Invalid request
            message = "Expecting SOAP request"
            logging.error(message)
            raise Vmodl.Fault.InvalidRequest(msg=message)

        # In the future, version could have changed after parsing soap msg
        version, mo, method = msg.version, msg.mo, msg.method

        # Make sure method is available to this version
        if not VmomiSupport.IsChildVersion(version, method.info.version):
            message = version + " not child verison of " + method.info.version
            logging.error(message)
            raise Vmodl.Fault.MethodNotFound(receiver=mo,
                                             method=method.info.name)

        return msg

    def _InvokeMethod(self, msg):
        try:
            version, mo, method = msg.version, msg.mo, msg.method

            # Get managed object stub
            stub = self._GetMoStub(version, mo)
            if not stub:
                message = "Failed to find (" + mo._moId + ")" + \
                          " serverGuid (" + str(mo._serverGuid) + ")"
                logging.error(message)
                raise Vmodl.Fault.ManagedObjectNotFound(msg=message, obj=mo)
            mo._stub = stub

            # Put the VMOMI request context in thread-local storage
            context = VmomiSupport.GetRequestContext()
            context.clear()
            context.update(msg.context)

            callerVersion = context.get("callerVersion")
            if not callerVersion:
                context['callerVersion'] = msg.version

            opID = context.get("operationID")
            if not opID:
                opID = format(random.SystemRandom().randrange(0, 0xFFFF), '04x')
                context['operationID'] = opID

            with _ThreadName(opID):
                # Call method according to SOAP msg
                if isinstance(msg, SoapMsgAccessor):
                    value = getattr(mo, msg.params)
                else:
                    # TODO: Task method
                    value = method.f(method.info, mo, **msg.params)

            # Serialize response
            isFault = False
            result = self._soapSerializer.SerializeResponse(
                version, method, value)
            return isFault, result
        except Exception as err:
            message = ExceptionMsg(err)
            if message:
                logging.error(message)
            stackTrace = traceback.format_exc()
            if stackTrace:
                logging.error(stackTrace)
            return self.ProcessException(err, message, version, method.info)

    def _ValidateException(self, err, mInfo):
        # All methods are allowed to throw RuntimeFault and its descendants.
        if isinstance(err, Vmodl.RuntimeFault):
            return err

        # Otherwise, the fault must be an instance of one of the faults the
        # method declares that it throws.
        for fault in mInfo.faults:
            if isinstance(err, VmomiSupport.GetVmodlType(fault)):
                return err

        # If its not, log a message and throw a SystemError instead.
        msg = 'Method %s threw undeclared fault of type %s' % (
            mInfo.wsdlName, type(err).__name__)
        logging.error(msg)
        return Vmodl.Fault.SystemError(msg='Invalid Fault',
                                       faultCause=err,
                                       reason=msg)

    def ProcessException(self, err, message, version, mInfo=None):
        if issubclass(err.__class__, Vmodl.MethodFault) or \
           issubclass(err.__class__, Vmodl.RuntimeFault):
            if err.__class__ == Vmodl.MethodFault or \
               err.__class__ == Vmodl.RuntimeFault:
                # Method fault or Runtime fault
                err = Vmodl.Fault.SystemError(msg=message,
                                              reason=ExceptionMsg(err))
        else:
            err = Vmodl.Fault.SystemError(msg=message, reason="Runtime fault")

        if mInfo:
            err = self._ValidateException(err, mInfo)

        isFault = True
        return isFault, self._soapSerializer.SerializeServerFault(err, version)
