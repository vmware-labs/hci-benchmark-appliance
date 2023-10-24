# bazel-out/k8-dbg-obj/bin/bora/vpx/java/vsm/pythonCodeGen/ha_schema.py
# PyXB bindings for NamespaceModule
# NSM:79526013c265021f61758466505a6aa82fb6598e
# Generated 2022-05-17 19:53:28.918100 by PyXB version 1.1.1
import pyxb
import pyxb.binding
import pyxb.binding.saxer
import StringIO
import pyxb.utils.utility
import pyxb.utils.domutils
import sys

# Unique identifier for bindings created at the same time
_GenerationUID = pyxb.utils.utility.UniqueIdentifier('urn:uuid:b12ab9be-d655-11ec-a1b3-005056811909')

# Import bindings for namespaces imported into schema
import pyxb.binding.datatypes

Namespace = pyxb.namespace.NamespaceForURI(u'http://vmware.com/vService/demo/Availability', create_if_missing=True)
Namespace.configureCategories(['typeBinding', 'elementBinding'])
ModuleRecord = Namespace.lookupModuleRecordByUID(_GenerationUID, create_if_missing=True)
ModuleRecord._setModule(sys.modules[__name__])

def CreateFromDocument (xml_text, default_namespace=None, location_base=None):
    """Parse the given XML and use the document element to create a Python instance."""
    if pyxb.XMLStyle_saxer != pyxb._XMLStyle:
        dom = pyxb.utils.domutils.StringToDOM(xml_text)
        return CreateFromDOM(dom.documentElement)
    saxer = pyxb.binding.saxer.make_parser(fallback_namespace=Namespace.fallbackNamespace(), location_base=location_base)
    handler = saxer.getContentHandler()
    saxer.parse(StringIO.StringIO(xml_text))
    instance = handler.rootObject()
    return instance

def CreateFromDOM (node, default_namespace=None):
    """Create a Python instance from the given DOM node.
    The node tag must correspond to an element declaration in this module.

    @deprecated: Forcing use of DOM interface is unnecessary; use L{CreateFromDocument}."""
    if default_namespace is None:
        default_namespace = Namespace.fallbackNamespace()
    return pyxb.binding.basis.element.AnyCreateFromDOM(node, _fallback_namespace=default_namespace)


# Complex type Availability_Type with content type ELEMENT_ONLY
class Availability_Type (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'Availability_Type')
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {http://vmware.com/vService/demo/Availability}HostIsolationResponse uses Python identifier HostIsolationResponse
    __HostIsolationResponse = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'HostIsolationResponse'), 'HostIsolationResponse', '__httpvmware_comvServicedemoAvailability_Availability_Type_httpvmware_comvServicedemoAvailabilityHostIsolationResponse', False)

    
    HostIsolationResponse = property(__HostIsolationResponse.value, __HostIsolationResponse.set, None, None)

    
    # Element {http://vmware.com/vService/demo/Availability}VmRestartPriority uses Python identifier VmRestartPriority
    __VmRestartPriority = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'VmRestartPriority'), 'VmRestartPriority', '__httpvmware_comvServicedemoAvailability_Availability_Type_httpvmware_comvServicedemoAvailabilityVmRestartPriority', False)

    
    VmRestartPriority = property(__VmRestartPriority.value, __VmRestartPriority.set, None, None)


    _ElementMap = {
        __HostIsolationResponse.name() : __HostIsolationResponse,
        __VmRestartPriority.name() : __VmRestartPriority
    }
    _AttributeMap = {
        
    }
Namespace.addCategoryObject('typeBinding', u'Availability_Type', Availability_Type)


Availability = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Availability'), Availability_Type)
Namespace.addCategoryObject('elementBinding', Availability.name().localName(), Availability)



Availability_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'HostIsolationResponse'), pyxb.binding.datatypes.string, scope=Availability_Type))

Availability_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'VmRestartPriority'), pyxb.binding.datatypes.string, scope=Availability_Type))
Availability_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, element_use=Availability_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'VmRestartPriority'))),
    ])
    , 2 : pyxb.binding.content.ContentModelState(state=2, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=3, element_use=Availability_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'HostIsolationResponse'))),
    ])
    , 3 : pyxb.binding.content.ContentModelState(state=3, is_final=True, transitions=[
    ])
})
