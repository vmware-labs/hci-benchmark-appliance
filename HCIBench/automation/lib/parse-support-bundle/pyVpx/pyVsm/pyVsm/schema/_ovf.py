# bazel-out/k8-dbg-obj/bin/bora/vpx/java/vsm/pythonCodeGen/_ovf.py
# PyXB bindings for NamespaceModule
# NSM:2c779c7b0adaa1494d56cbfd7abf17862bde02db
# Generated 2022-05-17 19:16:59.058160 by PyXB version 1.1.1
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
import pyxb.binding.datatypes

Namespace = pyxb.namespace.NamespaceForURI(u'http://schemas.dmtf.org/ovf/envelope/1', create_if_missing=True)
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


# Complex type Msg_Type with content type SIMPLE
class Msg_Type (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = pyxb.binding.datatypes.string
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_SIMPLE
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'Msg_Type')
    # Base type is pyxb.binding.datatypes.string
    
    # Attribute {http://schemas.dmtf.org/ovf/envelope/1}msgid uses Python identifier msgid
    __msgid = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'msgid'), 'msgid', '__httpschemas_dmtf_orgovfenvelope1_Msg_Type_httpschemas_dmtf_orgovfenvelope1msgid', pyxb.binding.datatypes.string, unicode_default=u'')
    
    msgid = property(__msgid.value, __msgid.set, None, u'Identifier for lookup in string\n                     resource bundle\n                     for alternate locale\n                  ')

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)

    _ElementMap = {
        
    }
    _AttributeMap = {
        __msgid.name() : __msgid
    }
Namespace.addCategoryObject('typeBinding', u'Msg_Type', Msg_Type)


# Complex type Section_Type with content type ELEMENT_ONLY
class Section_Type (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = True
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'Section_Type')
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {http://schemas.dmtf.org/ovf/envelope/1}Info uses Python identifier Info
    __Info = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Info'), 'Info', '__httpschemas_dmtf_orgovfenvelope1_Section_Type_httpschemas_dmtf_orgovfenvelope1Info', False)

    
    Info = property(__Info.value, __Info.set, None, u'Info element describes the meaning of\n                  the Section,\n                  this is typically shown if the Section is\n                  not understood by an\n                  application')

    
    # Attribute {http://schemas.dmtf.org/ovf/envelope/1}required uses Python identifier required
    __required = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'required'), 'required', '__httpschemas_dmtf_orgovfenvelope1_Section_Type_httpschemas_dmtf_orgovfenvelope1required', pyxb.binding.datatypes.boolean, unicode_default=u'true')
    
    required = property(__required.value, __required.set, None, u'Determines whether import should fail if the\n            Section is\n            not understood')

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)

    _ElementMap = {
        __Info.name() : __Info
    }
    _AttributeMap = {
        __required.name() : __required
    }
Namespace.addCategoryObject('typeBinding', u'Section_Type', Section_Type)




Section_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Info'), Msg_Type, scope=Section_Type, documentation=u'Info element describes the meaning of\n                  the Section,\n                  this is typically shown if the Section is\n                  not understood by an\n                  application'))
Section_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, element_use=Section_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Info'))),
    ])
    , 2 : pyxb.binding.content.ContentModelState(state=2, is_final=True, transitions=[
    ])
})
