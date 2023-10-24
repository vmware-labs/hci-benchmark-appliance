# bazel-out/k8-dbg-obj/bin/bora/vpx/java/vsm/pythonCodeGen/ovfenv_vmware_schema.py
# PyXB bindings for NamespaceModule
# NSM:d4597a17b495943a5f4a2eb9af3cd69e9f89aa04
# Generated 2022-05-17 19:16:59.058382 by PyXB version 1.1.1
import pyxb
import pyxb.binding
import pyxb.binding.saxer
import StringIO
import pyxb.utils.utility
import pyxb.utils.domutils
import sys

# Unique identifier for bindings created at the same time
_GenerationUID = pyxb.utils.utility.UniqueIdentifier('urn:uuid:9884139c-d650-11ec-a7f0-005056b4a83d')

# Import bindings for namespaces imported into schema
import _ovfenv
import pyxb.binding.datatypes

Namespace = pyxb.namespace.NamespaceForURI(u'http://www.vmware.com/schema/ovfenv', create_if_missing=True)
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


# Complex type vServiceEnvironmentSection_Type with content type ELEMENT_ONLY
class vServiceEnvironmentSection_Type (_ovfenv.Section_Type):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'vServiceEnvironmentSection_Type')
    # Base type is _ovfenv.Section_Type
    
    # Attribute {http://www.vmware.com/schema/ovfenv}id uses Python identifier id
    __id = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'id'), 'id', '__httpwww_vmware_comschemaovfenv_vServiceEnvironmentSection_Type_httpwww_vmware_comschemaovfenvid', pyxb.binding.datatypes.string)
    
    id = property(__id.value, __id.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/ovfenv}type uses Python identifier type
    __type = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'type'), 'type', '__httpwww_vmware_comschemaovfenv_vServiceEnvironmentSection_Type_httpwww_vmware_comschemaovfenvtype', pyxb.binding.datatypes.string)
    
    type = property(__type.value, __type.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/ovfenv}bound uses Python identifier bound
    __bound = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'bound'), 'bound', '__httpwww_vmware_comschemaovfenv_vServiceEnvironmentSection_Type_httpwww_vmware_comschemaovfenvbound', pyxb.binding.datatypes.boolean)
    
    bound = property(__bound.value, __bound.set, None, None)

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True

    _ElementMap = _ovfenv.Section_Type._ElementMap.copy()
    _ElementMap.update({
        
    })
    _AttributeMap = _ovfenv.Section_Type._AttributeMap.copy()
    _AttributeMap.update({
        __id.name() : __id,
        __type.name() : __type,
        __bound.name() : __bound
    })
Namespace.addCategoryObject('typeBinding', u'vServiceEnvironmentSection_Type', vServiceEnvironmentSection_Type)


vServiceEnvironmentSection = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'vServiceEnvironmentSection'), vServiceEnvironmentSection_Type)
Namespace.addCategoryObject('elementBinding', vServiceEnvironmentSection.name().localName(), vServiceEnvironmentSection)


vServiceEnvironmentSection_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=1, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
})
