#!/usr/bin/env python

## @file configSerialize.py
## @brief Format a python VMOMI object in config serializer format.
##
## Detailed description (for Doxygen goes here)
"""
Format a python VMOMI object in config serializer format.

Detailed description (for [e]pydoc goes here)
"""

from pyVmomi import VmomiSupport
from pyVmomi.VmomiSupport import GetVmodlName
from six.moves import range

INDENT = "  "


def SerializeToConfig(val,
                      info=VmomiSupport.Object(name="",
                                               index=-1,
                                               type=object,
                                               flags=0),
                      indent=0,
                      tag=None):
    """
    Format a python VMOMI object in config serializer format.

    @param val:     the object
    @param info:    the field
    @type  indent:  int
    @param indent:  the level of indentation
    @rtype:         str
    @return:        the formatted string

    @warning:       This function is not well tested.
    @note:          Deserialization code has not been implemented.
    """

    # Unset properties should not be serialized
    if val == None or (isinstance(val, list) and len(val) == 0):
        return None
    valType = GetVmodlName(val.__class__)
    start = indent * INDENT
    if info.name:
        start = start + ("<%s>" % info.name)
        end = "</%s>" % info.name
        indent = indent + 1
        # Need to emit additional information for properties declared Any
        if info.type == object:
            start = start + "\n%s<_type>%s</_type>" % (indent * INDENT,
                                                       valType)
            start = start + "\n%s<_value>" % (indent * INDENT)
            end = "</_value>\n%s" % ((indent - 1) * INDENT) + end
            indent = indent + 1
    elif info.index != -1:
        start = start + "<e id=\"%d\">" % info.index
        end = "</e>\n"
        indent = indent + 1
    else:
        start = start + "<ConfigRoot>"
        end = "</ConfigRoot>"
        indent = indent + 1
        if tag:
            start += "\n%s<%s>" % (indent * INDENT, tag)
            end = "</%s>\n%s" % (tag, (indent - 1) * INDENT) + end
            indent = indent + 1

    if isinstance(val, VmomiSupport.DataObject):
        if info.flags & VmomiSupport.F_LINK:
            result = "\n%s<_type>%s</_type>\n%s<_key>%s</_key>\n" % \
                     (indent * INDENT, valType, indent * INDENT, val.key)
        else:
            result = "\n%s<_type>%s</_type>\n%s\n%s" % \
                     (indent * INDENT,
                      valType,
                      '\n'.join([x for x in [SerializeToConfig(getattr(val, prop.name),
                                                          prop, indent)
                                        for prop in sorted(val._GetPropertyList(),
                                                           lambda x, y:
                                                              cmp(x.name, y.name))] if x != None]),
                                (indent - 1) * INDENT)
    elif isinstance(val, VmomiSupport.ManagedObject):
        result = "\n%s<_type>%s</_type>\n%s<moid>%s</moid>\n" % \
                 (indent * INDENT, valType, indent * INDENT, val._moId)
    elif isinstance(val, list):
        itemType = GetVmodlName(
            getattr(val, 'Item', getattr(info.type, 'Item', object)))
        result = "\n%s<_length>%d</_length>\n%s<_type>%s[]</_type>\n" % \
            (indent * INDENT, len(val), indent * INDENT, itemType)
        results = []
        for i in range(len(val)):
            item = VmomiSupport.Object(name="",
                                       index=i,
                                       type=itemType,
                                       flags=info.flags)
            results.append(SerializeToConfig(val[i], item, indent))
        result = result + ''.join(results) + ((indent - 1) * INDENT)
    elif isinstance(val, type):
        result = val.__name__
    elif isinstance(val, VmomiSupport.ManagedMethod):
        result = '%s' % (val.info.name)
    elif isinstance(val, bool):
        result = val and "true" or "false"
    else:
        result = val
    return start + str(result) + end


def main():
    print(SerializeToConfig(3))
    print(SerializeToConfig([3, 4, 5]))


if __name__ == "__main__":
    main()
