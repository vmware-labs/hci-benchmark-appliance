# bazel-out/k8-dbg-obj/bin/bora/vpx/java/vsm/pythonCodeGen/ovf_vmware_schema.py
# PyXB bindings for NamespaceModule
# NSM:749129191fec4eefae2b6215e039be8d7390dd5b
# Generated 2022-05-17 19:16:59.058460 by PyXB version 1.1.1
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
import _ovf

Namespace = pyxb.namespace.NamespaceForURI(u'http://www.vmware.com/schema/ovf', create_if_missing=True)
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


# Atomic SimpleTypeDefinition
class ValidationResultEnum (pyxb.binding.datatypes.string, pyxb.binding.basis.enumeration_mixin):

    """An atomic simple type."""

    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'ValidationResultEnum')
    _Documentation = None
ValidationResultEnum._CF_enumeration = pyxb.binding.facets.CF_enumeration(value_datatype=ValidationResultEnum, enum_prefix=None)
ValidationResultEnum.red = ValidationResultEnum._CF_enumeration.addEnumeration(unicode_value=u'red')
ValidationResultEnum.yellow = ValidationResultEnum._CF_enumeration.addEnumeration(unicode_value=u'yellow')
ValidationResultEnum.green = ValidationResultEnum._CF_enumeration.addEnumeration(unicode_value=u'green')
ValidationResultEnum._InitializeFacetMap(ValidationResultEnum._CF_enumeration)
Namespace.addCategoryObject('typeBinding', u'ValidationResultEnum', ValidationResultEnum)

# Complex type CTD_ANON_1 with content type ELEMENT_ONLY
class CTD_ANON_1 (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = None
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {http://www.vmware.com/schema/ovf}Providers uses Python identifier Providers
    __Providers = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Providers'), 'Providers', '__httpwww_vmware_comschemaovf_CTD_ANON_1_httpwww_vmware_comschemaovfProviders', False)

    
    Providers = property(__Providers.value, __Providers.set, None, None)

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True

    _ElementMap = {
        __Providers.name() : __Providers
    }
    _AttributeMap = {
        
    }



# Complex type CTD_ANON_2 with content type ELEMENT_ONLY
class CTD_ANON_2 (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = None
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {http://www.vmware.com/schema/ovf}Provider uses Python identifier Provider
    __Provider = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Provider'), 'Provider', '__httpwww_vmware_comschemaovf_CTD_ANON_2_httpwww_vmware_comschemaovfProvider', True)

    
    Provider = property(__Provider.value, __Provider.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/ovf}selected uses Python identifier selected
    __selected = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'selected'), 'selected', '__httpwww_vmware_comschemaovf_CTD_ANON_2_httpwww_vmware_comschemaovfselected', pyxb.binding.datatypes.string)
    
    selected = property(__selected.value, __selected.set, None, None)

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)

    _ElementMap = {
        __Provider.name() : __Provider
    }
    _AttributeMap = {
        __selected.name() : __selected
    }



# Complex type vServiceProvider_Type with content type ELEMENT_ONLY
class vServiceProvider_Type (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'vServiceProvider_Type')
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {http://www.vmware.com/schema/ovf}Name uses Python identifier Name
    __Name = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Name'), 'Name', '__httpwww_vmware_comschemaovf_vServiceProvider_Type_httpwww_vmware_comschemaovfName', False)

    
    Name = property(__Name.value, __Name.set, None, None)

    
    # Element {http://www.vmware.com/schema/ovf}ValidationResult uses Python identifier ValidationResult
    __ValidationResult = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'ValidationResult'), 'ValidationResult', '__httpwww_vmware_comschemaovf_vServiceProvider_Type_httpwww_vmware_comschemaovfValidationResult', False)

    
    ValidationResult = property(__ValidationResult.value, __ValidationResult.set, None, None)

    
    # Element {http://www.vmware.com/schema/ovf}Description uses Python identifier Description
    __Description = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Description'), 'Description', '__httpwww_vmware_comschemaovf_vServiceProvider_Type_httpwww_vmware_comschemaovfDescription', False)

    
    Description = property(__Description.value, __Description.set, None, None)

    
    # Element {http://www.vmware.com/schema/ovf}ValidationMessage uses Python identifier ValidationMessage
    __ValidationMessage = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'ValidationMessage'), 'ValidationMessage', '__httpwww_vmware_comschemaovf_vServiceProvider_Type_httpwww_vmware_comschemaovfValidationMessage', False)

    
    ValidationMessage = property(__ValidationMessage.value, __ValidationMessage.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/ovf}id uses Python identifier id
    __id = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'id'), 'id', '__httpwww_vmware_comschemaovf_vServiceProvider_Type_httpwww_vmware_comschemaovfid', pyxb.binding.datatypes.string)
    
    id = property(__id.value, __id.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/ovf}autobind uses Python identifier autobind
    __autobind = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'autobind'), 'autobind', '__httpwww_vmware_comschemaovf_vServiceProvider_Type_httpwww_vmware_comschemaovfautobind', pyxb.binding.datatypes.boolean)
    
    autobind = property(__autobind.value, __autobind.set, None, None)

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True

    _ElementMap = {
        __Name.name() : __Name,
        __ValidationResult.name() : __ValidationResult,
        __Description.name() : __Description,
        __ValidationMessage.name() : __ValidationMessage
    }
    _AttributeMap = {
        __id.name() : __id,
        __autobind.name() : __autobind
    }
Namespace.addCategoryObject('typeBinding', u'vServiceProvider_Type', vServiceProvider_Type)


# Complex type vServiceConfiguration_Type with content type ELEMENT_ONLY
class vServiceConfiguration_Type (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'vServiceConfiguration_Type')
    # Base type is pyxb.binding.datatypes.anyType
    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True

    _ElementMap = {
        
    }
    _AttributeMap = {
        
    }
Namespace.addCategoryObject('typeBinding', u'vServiceConfiguration_Type', vServiceConfiguration_Type)


# Complex type vServiceDependencySection_Type with content type ELEMENT_ONLY
class vServiceDependencySection_Type (_ovf.Section_Type):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'vServiceDependencySection_Type')
    # Base type is _ovf.Section_Type
    
    # Element {http://www.vmware.com/schema/ovf}Type uses Python identifier Type
    __Type = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Type'), 'Type', '__httpwww_vmware_comschemaovf_vServiceDependencySection_Type_httpwww_vmware_comschemaovfType', False)

    
    Type = property(__Type.value, __Type.set, None, None)

    
    # Element {http://www.vmware.com/schema/ovf}Configuration uses Python identifier Configuration
    __Configuration = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Configuration'), 'Configuration', '__httpwww_vmware_comschemaovf_vServiceDependencySection_Type_httpwww_vmware_comschemaovfConfiguration', False)

    
    Configuration = property(__Configuration.value, __Configuration.set, None, None)

    
    # Element Info ({http://schemas.dmtf.org/ovf/envelope/1}Info) inherited from {http://schemas.dmtf.org/ovf/envelope/1}Section_Type
    
    # Element {http://www.vmware.com/schema/ovf}Name uses Python identifier Name
    __Name = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Name'), 'Name', '__httpwww_vmware_comschemaovf_vServiceDependencySection_Type_httpwww_vmware_comschemaovfName', False)

    
    Name = property(__Name.value, __Name.set, None, None)

    
    # Element {http://www.vmware.com/schema/ovf}Description uses Python identifier Description
    __Description = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Description'), 'Description', '__httpwww_vmware_comschemaovf_vServiceDependencySection_Type_httpwww_vmware_comschemaovfDescription', False)

    
    Description = property(__Description.value, __Description.set, None, None)

    
    # Element {http://www.vmware.com/schema/ovf}Annotations uses Python identifier Annotations
    __Annotations = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Annotations'), 'Annotations', '__httpwww_vmware_comschemaovf_vServiceDependencySection_Type_httpwww_vmware_comschemaovfAnnotations', False)

    
    Annotations = property(__Annotations.value, __Annotations.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/ovf}id uses Python identifier id
    __id = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'id'), 'id', '__httpwww_vmware_comschemaovf_vServiceDependencySection_Type_httpwww_vmware_comschemaovfid', pyxb.binding.datatypes.string)
    
    id = property(__id.value, __id.set, None, None)

    
    # Attribute required inherited from {http://schemas.dmtf.org/ovf/envelope/1}Section_Type
    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True

    _ElementMap = _ovf.Section_Type._ElementMap.copy()
    _ElementMap.update({
        __Type.name() : __Type,
        __Configuration.name() : __Configuration,
        __Name.name() : __Name,
        __Description.name() : __Description,
        __Annotations.name() : __Annotations
    })
    _AttributeMap = _ovf.Section_Type._AttributeMap.copy()
    _AttributeMap.update({
        __id.name() : __id
    })
Namespace.addCategoryObject('typeBinding', u'vServiceDependencySection_Type', vServiceDependencySection_Type)


vServiceDependencySection = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'vServiceDependencySection'), vServiceDependencySection_Type)
Namespace.addCategoryObject('elementBinding', vServiceDependencySection.name().localName(), vServiceDependencySection)



CTD_ANON_1._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Providers'), CTD_ANON_2, scope=CTD_ANON_1))
CTD_ANON_1._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, element_use=CTD_ANON_1._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Providers'))),
    ])
    , 2 : pyxb.binding.content.ContentModelState(state=2, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
})



CTD_ANON_2._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Provider'), vServiceProvider_Type, scope=CTD_ANON_2))
CTD_ANON_2._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=1, element_use=CTD_ANON_2._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Provider'))),
    ])
})



vServiceProvider_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Name'), pyxb.binding.datatypes.string, scope=vServiceProvider_Type))

vServiceProvider_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'ValidationResult'), ValidationResultEnum, scope=vServiceProvider_Type))

vServiceProvider_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Description'), pyxb.binding.datatypes.string, scope=vServiceProvider_Type))

vServiceProvider_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'ValidationMessage'), pyxb.binding.datatypes.string, scope=vServiceProvider_Type))
vServiceProvider_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=3, element_use=vServiceProvider_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Name'))),
    ])
    , 2 : pyxb.binding.content.ContentModelState(state=2, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
    , 3 : pyxb.binding.content.ContentModelState(state=3, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=4, element_use=vServiceProvider_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Description'))),
    ])
    , 4 : pyxb.binding.content.ContentModelState(state=4, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=5, element_use=vServiceProvider_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'ValidationResult'))),
    ])
    , 5 : pyxb.binding.content.ContentModelState(state=5, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, element_use=vServiceProvider_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'ValidationMessage'))),
    ])
})


vServiceConfiguration_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=1, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
})



vServiceDependencySection_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Type'), pyxb.binding.datatypes.string, scope=vServiceDependencySection_Type))

vServiceDependencySection_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Configuration'), vServiceConfiguration_Type, scope=vServiceDependencySection_Type))

vServiceDependencySection_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Name'), _ovf.Msg_Type, scope=vServiceDependencySection_Type))

vServiceDependencySection_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Description'), _ovf.Msg_Type, scope=vServiceDependencySection_Type))

vServiceDependencySection_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Annotations'), CTD_ANON_1, scope=vServiceDependencySection_Type))
vServiceDependencySection_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, element_use=vServiceDependencySection_Type._UseForTag(pyxb.namespace.ExpandedName(pyxb.namespace.NamespaceForURI(u'http://schemas.dmtf.org/ovf/envelope/1'), u'Info'))),
    ])
    , 2 : pyxb.binding.content.ContentModelState(state=2, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=3, element_use=vServiceDependencySection_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Type'))),
    ])
    , 3 : pyxb.binding.content.ContentModelState(state=3, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=4, element_use=vServiceDependencySection_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Name'))),
    ])
    , 4 : pyxb.binding.content.ContentModelState(state=4, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=5, element_use=vServiceDependencySection_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Description'))),
    ])
    , 5 : pyxb.binding.content.ContentModelState(state=5, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=6, element_use=vServiceDependencySection_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Annotations'))),
        pyxb.binding.content.ContentModelTransition(next_state=7, element_use=vServiceDependencySection_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Configuration'))),
    ])
    , 6 : pyxb.binding.content.ContentModelState(state=6, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=7, element_use=vServiceDependencySection_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Configuration'))),
    ])
    , 7 : pyxb.binding.content.ContentModelState(state=7, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=7, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
})
