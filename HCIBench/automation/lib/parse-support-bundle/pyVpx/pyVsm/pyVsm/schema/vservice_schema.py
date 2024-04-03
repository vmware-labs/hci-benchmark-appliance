# bazel-out/k8-dbg-obj/bin/bora/vpx/java/vsm/pythonCodeGen/vservice_schema.py
# PyXB bindings for NamespaceModule
# NSM:336522f159744b4953dc3442853fe02764ca9353
# Generated 2022-05-17 19:16:59.058565 by PyXB version 1.1.1
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
import ovfenv_vmware_schema
import ovf_vmware_schema

Namespace = pyxb.namespace.NamespaceForURI(u'http://www.vmware.com/schema/vserviceprovider', create_if_missing=True)
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
class BindDependencyResultEnum (pyxb.binding.datatypes.string, pyxb.binding.basis.enumeration_mixin):

    """An atomic simple type."""

    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'BindDependencyResultEnum')
    _Documentation = None
BindDependencyResultEnum._CF_enumeration = pyxb.binding.facets.CF_enumeration(value_datatype=BindDependencyResultEnum, enum_prefix=None)
BindDependencyResultEnum.red = BindDependencyResultEnum._CF_enumeration.addEnumeration(unicode_value=u'red')
BindDependencyResultEnum.yellow = BindDependencyResultEnum._CF_enumeration.addEnumeration(unicode_value=u'yellow')
BindDependencyResultEnum.green = BindDependencyResultEnum._CF_enumeration.addEnumeration(unicode_value=u'green')
BindDependencyResultEnum._InitializeFacetMap(BindDependencyResultEnum._CF_enumeration)
Namespace.addCategoryObject('typeBinding', u'BindDependencyResultEnum', BindDependencyResultEnum)

# Complex type Entity_Type with content type ELEMENT_ONLY
class Entity_Type (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'Entity_Type')
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {http://www.vmware.com/schema/vserviceprovider}Platform uses Python identifier Platform
    __Platform = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Platform'), 'Platform', '__httpwww_vmware_comschemavserviceprovider_Entity_Type_httpwww_vmware_comschemavserviceproviderPlatform', False)

    
    Platform = property(__Platform.value, __Platform.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/vserviceprovider}entityId uses Python identifier entityId
    __entityId = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'entityId'), 'entityId', '__httpwww_vmware_comschemavserviceprovider_Entity_Type_httpwww_vmware_comschemavserviceproviderentityId', pyxb.binding.datatypes.string)
    
    entityId = property(__entityId.value, __entityId.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/vserviceprovider}ovfId uses Python identifier ovfId
    __ovfId = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'ovfId'), 'ovfId', '__httpwww_vmware_comschemavserviceprovider_Entity_Type_httpwww_vmware_comschemavserviceproviderovfId', pyxb.binding.datatypes.string)
    
    ovfId = property(__ovfId.value, __ovfId.set, None, None)

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)

    _ElementMap = {
        __Platform.name() : __Platform
    }
    _AttributeMap = {
        __entityId.name() : __entityId,
        __ovfId.name() : __ovfId
    }
Namespace.addCategoryObject('typeBinding', u'Entity_Type', Entity_Type)


# Complex type VirtualApp_Type with content type ELEMENT_ONLY
class VirtualApp_Type (Entity_Type):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'VirtualApp_Type')
    # Base type is Entity_Type
    
    # Element {http://www.vmware.com/schema/vserviceprovider}Children uses Python identifier Children
    __Children = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Children'), 'Children', '__httpwww_vmware_comschemavserviceprovider_VirtualApp_Type_httpwww_vmware_comschemavserviceproviderChildren', False)

    
    Children = property(__Children.value, __Children.set, None, None)

    
    # Element Platform ({http://www.vmware.com/schema/vserviceprovider}Platform) inherited from {http://www.vmware.com/schema/vserviceprovider}Entity_Type
    
    # Attribute entityId inherited from {http://www.vmware.com/schema/vserviceprovider}Entity_Type
    
    # Attribute ovfId inherited from {http://www.vmware.com/schema/vserviceprovider}Entity_Type
    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True

    _ElementMap = Entity_Type._ElementMap.copy()
    _ElementMap.update({
        __Children.name() : __Children
    })
    _AttributeMap = Entity_Type._AttributeMap.copy()
    _AttributeMap.update({
        
    })
Namespace.addCategoryObject('typeBinding', u'VirtualApp_Type', VirtualApp_Type)


# Complex type InstanceSpec_Type with content type ELEMENT_ONLY
class InstanceSpec_Type (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'InstanceSpec_Type')
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {http://www.vmware.com/schema/vserviceprovider}Entity uses Python identifier Entity
    __Entity = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Entity'), 'Entity', '__httpwww_vmware_comschemavserviceprovider_InstanceSpec_Type_httpwww_vmware_comschemavserviceproviderEntity', False)

    
    Entity = property(__Entity.value, __Entity.set, None, None)

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True

    _ElementMap = {
        __Entity.name() : __Entity
    }
    _AttributeMap = {
        
    }
Namespace.addCategoryObject('typeBinding', u'InstanceSpec_Type', InstanceSpec_Type)


# Complex type CTD_ANON_1 with content type ELEMENT_ONLY
class CTD_ANON_1 (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = None
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {http://www.vmware.com/schema/vserviceprovider}Entity uses Python identifier Entity
    __Entity = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Entity'), 'Entity', '__httpwww_vmware_comschemavserviceprovider_CTD_ANON_1_httpwww_vmware_comschemavserviceproviderEntity', True)

    
    Entity = property(__Entity.value, __Entity.set, None, None)


    _ElementMap = {
        __Entity.name() : __Entity
    }
    _AttributeMap = {
        
    }



# Complex type BindDependencyResult_Type with content type ELEMENT_ONLY
class BindDependencyResult_Type (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'BindDependencyResult_Type')
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {http://www.vmware.com/schema/vserviceprovider}publicVServiceEnvironment uses Python identifier publicVServiceEnvironment
    __publicVServiceEnvironment = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'publicVServiceEnvironment'), 'publicVServiceEnvironment', '__httpwww_vmware_comschemavserviceprovider_BindDependencyResult_Type_httpwww_vmware_comschemavserviceproviderpublicVServiceEnvironment', False)

    
    publicVServiceEnvironment = property(__publicVServiceEnvironment.value, __publicVServiceEnvironment.set, None, None)

    
    # Element {http://www.vmware.com/schema/vserviceprovider}Message uses Python identifier Message
    __Message = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Message'), 'Message', '__httpwww_vmware_comschemavserviceprovider_BindDependencyResult_Type_httpwww_vmware_comschemavserviceproviderMessage', False)

    
    Message = property(__Message.value, __Message.set, None, None)

    
    # Element {http://www.vmware.com/schema/vserviceprovider}privateVServiceEnvironment uses Python identifier privateVServiceEnvironment
    __privateVServiceEnvironment = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'privateVServiceEnvironment'), 'privateVServiceEnvironment', '__httpwww_vmware_comschemavserviceprovider_BindDependencyResult_Type_httpwww_vmware_comschemavserviceproviderprivateVServiceEnvironment', False)

    
    privateVServiceEnvironment = property(__privateVServiceEnvironment.value, __privateVServiceEnvironment.set, None, None)

    
    # Element {http://www.vmware.com/schema/vserviceprovider}Result uses Python identifier Result
    __Result = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Result'), 'Result', '__httpwww_vmware_comschemavserviceprovider_BindDependencyResult_Type_httpwww_vmware_comschemavserviceproviderResult', False)

    
    Result = property(__Result.value, __Result.set, None, None)

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True

    _ElementMap = {
        __publicVServiceEnvironment.name() : __publicVServiceEnvironment,
        __Message.name() : __Message,
        __privateVServiceEnvironment.name() : __privateVServiceEnvironment,
        __Result.name() : __Result
    }
    _AttributeMap = {
        
    }
Namespace.addCategoryObject('typeBinding', u'BindDependencyResult_Type', BindDependencyResult_Type)


# Complex type ValidateBinding_Type with content type ELEMENT_ONLY
class ValidateBinding_Type (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'ValidateBinding_Type')
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {http://www.vmware.com/schema/vserviceprovider}InstanceSpec uses Python identifier InstanceSpec
    __InstanceSpec = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'InstanceSpec'), 'InstanceSpec', '__httpwww_vmware_comschemavserviceprovider_ValidateBinding_Type_httpwww_vmware_comschemavserviceproviderInstanceSpec', False)

    
    InstanceSpec = property(__InstanceSpec.value, __InstanceSpec.set, None, None)

    
    # Element {http://www.vmware.com/schema/vserviceprovider}Configuration uses Python identifier Configuration
    __Configuration = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Configuration'), 'Configuration', '__httpwww_vmware_comschemavserviceprovider_ValidateBinding_Type_httpwww_vmware_comschemavserviceproviderConfiguration', False)

    
    Configuration = property(__Configuration.value, __Configuration.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/vserviceprovider}locale uses Python identifier locale
    __locale = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'locale'), 'locale', '__httpwww_vmware_comschemavserviceprovider_ValidateBinding_Type_httpwww_vmware_comschemavserviceproviderlocale', pyxb.binding.datatypes.string)
    
    locale = property(__locale.value, __locale.set, None, None)

    _HasWildcardElement = True

    _ElementMap = {
        __InstanceSpec.name() : __InstanceSpec,
        __Configuration.name() : __Configuration
    }
    _AttributeMap = {
        __locale.name() : __locale
    }
Namespace.addCategoryObject('typeBinding', u'ValidateBinding_Type', ValidateBinding_Type)


# Complex type VirtualMachine_Type with content type ELEMENT_ONLY
class VirtualMachine_Type (Entity_Type):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'VirtualMachine_Type')
    # Base type is Entity_Type
    
    # Element Platform ({http://www.vmware.com/schema/vserviceprovider}Platform) inherited from {http://www.vmware.com/schema/vserviceprovider}Entity_Type
    
    # Attribute entityId inherited from {http://www.vmware.com/schema/vserviceprovider}Entity_Type
    
    # Attribute ovfId inherited from {http://www.vmware.com/schema/vserviceprovider}Entity_Type
    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True

    _ElementMap = Entity_Type._ElementMap.copy()
    _ElementMap.update({
        
    })
    _AttributeMap = Entity_Type._AttributeMap.copy()
    _AttributeMap.update({
        
    })
Namespace.addCategoryObject('typeBinding', u'VirtualMachine_Type', VirtualMachine_Type)


# Complex type UnbindDependency_Type with content type ELEMENT_ONLY
class UnbindDependency_Type (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'UnbindDependency_Type')
    # Base type is pyxb.binding.datatypes.anyType
    
    # Attribute {http://www.vmware.com/schema/vserviceprovider}locale uses Python identifier locale
    __locale = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'locale'), 'locale', '__httpwww_vmware_comschemavserviceprovider_UnbindDependency_Type_httpwww_vmware_comschemavserviceproviderlocale', pyxb.binding.datatypes.string)
    
    locale = property(__locale.value, __locale.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/vserviceprovider}entityId uses Python identifier entityId
    __entityId = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'entityId'), 'entityId', '__httpwww_vmware_comschemavserviceprovider_UnbindDependency_Type_httpwww_vmware_comschemavserviceproviderentityId', pyxb.binding.datatypes.string)
    
    entityId = property(__entityId.value, __entityId.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/vserviceprovider}dependencyId uses Python identifier dependencyId
    __dependencyId = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'dependencyId'), 'dependencyId', '__httpwww_vmware_comschemavserviceprovider_UnbindDependency_Type_httpwww_vmware_comschemavserviceproviderdependencyId', pyxb.binding.datatypes.string)
    
    dependencyId = property(__dependencyId.value, __dependencyId.set, None, None)

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True

    _ElementMap = {
        
    }
    _AttributeMap = {
        __locale.name() : __locale,
        __entityId.name() : __entityId,
        __dependencyId.name() : __dependencyId
    }
Namespace.addCategoryObject('typeBinding', u'UnbindDependency_Type', UnbindDependency_Type)


# Complex type Platform_Type with content type ELEMENT_ONLY
class Platform_Type (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'Platform_Type')
    # Base type is pyxb.binding.datatypes.anyType
    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True

    _ElementMap = {
        
    }
    _AttributeMap = {
        
    }
Namespace.addCategoryObject('typeBinding', u'Platform_Type', Platform_Type)


# Complex type ValidateBindingResult_type with content type ELEMENT_ONLY
class ValidateBindingResult_type (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'ValidateBindingResult_type')
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {http://www.vmware.com/schema/vserviceprovider}Result uses Python identifier Result
    __Result = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Result'), 'Result', '__httpwww_vmware_comschemavserviceprovider_ValidateBindingResult_type_httpwww_vmware_comschemavserviceproviderResult', False)

    
    Result = property(__Result.value, __Result.set, None, None)

    
    # Element {http://www.vmware.com/schema/vserviceprovider}Message uses Python identifier Message
    __Message = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Message'), 'Message', '__httpwww_vmware_comschemavserviceprovider_ValidateBindingResult_type_httpwww_vmware_comschemavserviceproviderMessage', False)

    
    Message = property(__Message.value, __Message.set, None, None)

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True

    _ElementMap = {
        __Result.name() : __Result,
        __Message.name() : __Message
    }
    _AttributeMap = {
        
    }
Namespace.addCategoryObject('typeBinding', u'ValidateBindingResult_type', ValidateBindingResult_type)


# Complex type BindDependency_Type with content type ELEMENT_ONLY
class BindDependency_Type (pyxb.binding.basis.complexTypeDefinition):
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = pyxb.namespace.ExpandedName(Namespace, u'BindDependency_Type')
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {http://www.vmware.com/schema/vserviceprovider}Configuration uses Python identifier Configuration
    __Configuration = pyxb.binding.content.ElementUse(pyxb.namespace.ExpandedName(Namespace, u'Configuration'), 'Configuration', '__httpwww_vmware_comschemavserviceprovider_BindDependency_Type_httpwww_vmware_comschemavserviceproviderConfiguration', False)

    
    Configuration = property(__Configuration.value, __Configuration.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/vserviceprovider}entityId uses Python identifier entityId
    __entityId = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'entityId'), 'entityId', '__httpwww_vmware_comschemavserviceprovider_BindDependency_Type_httpwww_vmware_comschemavserviceproviderentityId', pyxb.binding.datatypes.string)
    
    entityId = property(__entityId.value, __entityId.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/vserviceprovider}dependencyId uses Python identifier dependencyId
    __dependencyId = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'dependencyId'), 'dependencyId', '__httpwww_vmware_comschemavserviceprovider_BindDependency_Type_httpwww_vmware_comschemavserviceproviderdependencyId', pyxb.binding.datatypes.string)
    
    dependencyId = property(__dependencyId.value, __dependencyId.set, None, None)

    
    # Attribute {http://www.vmware.com/schema/vserviceprovider}locale uses Python identifier locale
    __locale = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(Namespace, u'locale'), 'locale', '__httpwww_vmware_comschemavserviceprovider_BindDependency_Type_httpwww_vmware_comschemavserviceproviderlocale', pyxb.binding.datatypes.string)
    
    locale = property(__locale.value, __locale.set, None, None)

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True

    _ElementMap = {
        __Configuration.name() : __Configuration
    }
    _AttributeMap = {
        __entityId.name() : __entityId,
        __dependencyId.name() : __dependencyId,
        __locale.name() : __locale
    }
Namespace.addCategoryObject('typeBinding', u'BindDependency_Type', BindDependency_Type)


VirtualApp = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'VirtualApp'), VirtualApp_Type)
Namespace.addCategoryObject('elementBinding', VirtualApp.name().localName(), VirtualApp)

BindDependencyResult = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'BindDependencyResult'), BindDependencyResult_Type)
Namespace.addCategoryObject('elementBinding', BindDependencyResult.name().localName(), BindDependencyResult)

ValidateBinding = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'ValidateBinding'), ValidateBinding_Type)
Namespace.addCategoryObject('elementBinding', ValidateBinding.name().localName(), ValidateBinding)

Entity = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Entity'), Entity_Type)
Namespace.addCategoryObject('elementBinding', Entity.name().localName(), Entity)

ResourcePool = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'ResourcePool'), pyxb.binding.datatypes.string)
Namespace.addCategoryObject('elementBinding', ResourcePool.name().localName(), ResourcePool)

VirtualMachine = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'VirtualMachine'), VirtualMachine_Type)
Namespace.addCategoryObject('elementBinding', VirtualMachine.name().localName(), VirtualMachine)

MoRef = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'MoRef'), pyxb.binding.datatypes.string)
Namespace.addCategoryObject('elementBinding', MoRef.name().localName(), MoRef)

UnbindDependency = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'UnbindDependency'), UnbindDependency_Type)
Namespace.addCategoryObject('elementBinding', UnbindDependency.name().localName(), UnbindDependency)

ValidateBindingResult = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'ValidateBindingResult'), ValidateBindingResult_type)
Namespace.addCategoryObject('elementBinding', ValidateBindingResult.name().localName(), ValidateBindingResult)

BindDependency = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'BindDependency'), BindDependency_Type)
Namespace.addCategoryObject('elementBinding', BindDependency.name().localName(), BindDependency)



Entity_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Platform'), Platform_Type, scope=Entity_Type))
Entity_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, element_use=Entity_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Platform'))),
    ])
    , 2 : pyxb.binding.content.ContentModelState(state=2, is_final=True, transitions=[
    ])
})



VirtualApp_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Children'), CTD_ANON_1, scope=VirtualApp_Type))
VirtualApp_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, element_use=VirtualApp_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Platform'))),
    ])
    , 2 : pyxb.binding.content.ContentModelState(state=2, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=3, element_use=VirtualApp_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Children'))),
    ])
    , 3 : pyxb.binding.content.ContentModelState(state=3, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=3, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
})



InstanceSpec_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Entity'), Entity_Type, scope=InstanceSpec_Type))
InstanceSpec_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, element_use=InstanceSpec_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Entity'))),
    ])
    , 2 : pyxb.binding.content.ContentModelState(state=2, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
})



CTD_ANON_1._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Entity'), Entity_Type, scope=CTD_ANON_1))
CTD_ANON_1._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=1, element_use=CTD_ANON_1._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Entity'))),
    ])
})



BindDependencyResult_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'publicVServiceEnvironment'), ovfenv_vmware_schema.vServiceEnvironmentSection_Type, scope=BindDependencyResult_Type))

BindDependencyResult_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Message'), pyxb.binding.datatypes.string, scope=BindDependencyResult_Type))

BindDependencyResult_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'privateVServiceEnvironment'), ovfenv_vmware_schema.vServiceEnvironmentSection_Type, scope=BindDependencyResult_Type))

BindDependencyResult_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Result'), BindDependencyResultEnum, scope=BindDependencyResult_Type))
BindDependencyResult_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=4, element_use=BindDependencyResult_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'privateVServiceEnvironment'))),
        pyxb.binding.content.ContentModelTransition(next_state=5, element_use=BindDependencyResult_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Result'))),
        pyxb.binding.content.ContentModelTransition(next_state=3, element_use=BindDependencyResult_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'publicVServiceEnvironment'))),
    ])
    , 2 : pyxb.binding.content.ContentModelState(state=2, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
    , 3 : pyxb.binding.content.ContentModelState(state=3, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=5, element_use=BindDependencyResult_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Result'))),
    ])
    , 4 : pyxb.binding.content.ContentModelState(state=4, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=3, element_use=BindDependencyResult_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'publicVServiceEnvironment'))),
        pyxb.binding.content.ContentModelTransition(next_state=5, element_use=BindDependencyResult_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Result'))),
    ])
    , 5 : pyxb.binding.content.ContentModelState(state=5, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, element_use=BindDependencyResult_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Message'))),
    ])
})



ValidateBinding_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'InstanceSpec'), InstanceSpec_Type, scope=ValidateBinding_Type))

ValidateBinding_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Configuration'), ovf_vmware_schema.vServiceConfiguration_Type, scope=ValidateBinding_Type))
ValidateBinding_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, element_use=ValidateBinding_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Configuration'))),
    ])
    , 2 : pyxb.binding.content.ContentModelState(state=2, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=3, element_use=ValidateBinding_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'InstanceSpec'))),
    ])
    , 3 : pyxb.binding.content.ContentModelState(state=3, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=3, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
})


VirtualMachine_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, element_use=VirtualMachine_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Platform'))),
    ])
    , 2 : pyxb.binding.content.ContentModelState(state=2, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
})


UnbindDependency_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=1, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
})


Platform_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=1, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
})



ValidateBindingResult_type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Result'), ovf_vmware_schema.ValidationResultEnum, scope=ValidateBindingResult_type))

ValidateBindingResult_type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Message'), pyxb.binding.datatypes.string, scope=ValidateBindingResult_type))
ValidateBindingResult_type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, element_use=ValidateBindingResult_type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Result'))),
    ])
    , 2 : pyxb.binding.content.ContentModelState(state=2, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=3, element_use=ValidateBindingResult_type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Message'))),
    ])
    , 3 : pyxb.binding.content.ContentModelState(state=3, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=3, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
})



BindDependency_Type._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'Configuration'), ovf_vmware_schema.vServiceConfiguration_Type, scope=BindDependency_Type))
BindDependency_Type._ContentModel = pyxb.binding.content.ContentModel(state_map = {
      1 : pyxb.binding.content.ContentModelState(state=1, is_final=False, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, element_use=BindDependency_Type._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'Configuration'))),
    ])
    , 2 : pyxb.binding.content.ContentModelState(state=2, is_final=True, transitions=[
        pyxb.binding.content.ContentModelTransition(next_state=2, term=pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)),
    ])
})

VirtualApp._setSubstitutionGroup(Entity)

VirtualMachine._setSubstitutionGroup(Entity)
