from pyxb.xmlschema.structures import Schema, ElementDeclaration, ComplexTypeDefinition, Particle, ModelGroup, SimpleTypeDefinition, Wildcard, AttributeUse, AttributeDeclaration

def _xsd_isinstance(type, base_type):
    """Returns True if the type (ComplexTypeDefinition) derives from the base_type"""
    while type.baseTypeDefinition() != type:
        if type == base_type:
            return True
        type = type.baseTypeDefinition()
    return False

def _find_element_declarations(obj, ns_map, min_occurs = 1, max_occurs = 1):
    """Returns a flatten list of (ElementDeclaration, abstract ElementDeclaration, minOccurs, maxOccurs) from the given node"""
    if isinstance(obj, ElementDeclaration):
        if isinstance(obj.typeDefinition(), ComplexTypeDefinition) and obj.typeDefinition().abstract():
            types = []
            # look for concrete types that derives from this abstract type
            for ns in ns_map.values():
                for ed in ns.elementDeclarations().values():
                    if _xsd_isinstance(ed.typeDefinition(), obj.typeDefinition()):
                        types.append((ed, obj, min_occurs, max_occurs))
            return types
        return [(obj, obj, min_occurs, max_occurs)]        
    elif isinstance(obj, ComplexTypeDefinition):
        return _find_element_declarations(obj.contentType()[1], ns_map, min_occurs, max_occurs)
    elif isinstance(obj, Particle):
        return  _find_element_declarations(obj.term(), ns_map, obj.minOccurs(), obj.maxOccurs())
    elif isinstance(obj, ModelGroup):
        r = []
        for p in obj.particles():
            r += _find_element_declarations(p, ns_map, min_occurs, max_occurs)
        return r
    return []

def no_prefix(tag):
    """Remove the namespace prefix from the given name"""
    if tag.startswith('{'):
        return tag[tag.rfind('}')+1:]
    return tag

def prefix(tag):
    """Return the namespace prefix from the given name"""
    if tag.startswith('{'):
        return tag[1:tag.rfind('}')]
    return ""

def split_tag(tag):
    """Return a pair (ns prefix, tag) from a tag name"""
    if tag.startswith('{'):
        i = tag.rfind('}')
        return (tag[1:i], tag[i+1:])
    return ("", tag)

def type_definition_name(td):
    std = None
    if isinstance(td, ComplexTypeDefinition):
        if td.contentType()[0] == 'SIMPLE':
            # complex type with simple content
            std = td.contentType()[1]
    elif isinstance(td, SimpleTypeDefinition):
        std = td
    type_name = ""
    if std:
        if std.variety() == SimpleTypeDefinition.VARIETY_list:
            std = std.itemTypeDefinition()
            type_name += "list of "
        if std.variety() == SimpleTypeDefinition.VARIETY_atomic and std.primitiveTypeDefinition() != std:
            type_name += "{}({})".format(std.name(), std.primitiveTypeDefinition().name())
        else:
            type_name += std.name()
    else:
        type_name = td.name() or "<unnamed_complex>"
    return type_name

class TypeInfo(object):

    def __init__(self, type_info, attribute_type_info_map, min_occurs = 1, max_occurs = 1, abstract_type_info = None):
        self.__type_info = type_info
        self.__abstract_type_info = abstract_type_info
        self.__attribute_type_info_map = attribute_type_info_map
        self.__min_occurs = min_occurs
        self.__max_occurs = max_occurs # None for unbounded

    def type_info(self):
        return self.__type_info

    def abstract_type_info(self):
        return self.__abstract_type_info

    def min_occurs(self):
        return self.__min_occurs

    def max_occurs(self):
        return self.__max_occurs

    def attribute_type_info_map(self):
        return self.__attribute_type_info_map

    def attribute_type_info(self, attribute_key):
        return self.__attribute_type_info_map[attribute_key]
        
def _resolve_types(etree_node, ns_map, declaration, abstract_declaration, min_occurs, max_occurs, type_info_dict):
    """
    :param etree_node: a node of a tree, following the etree API
    :param ns_map: namespace map
    :param cadrinality: cardinality of the node
    :param type_info_dict: a dict {Element : TypeInfo} to augment
    """
    node_ns, node_tag = split_tag(etree_node.tag)
    type_info_dict[etree_node] = TypeInfo(declaration, {}, min_occurs, max_occurs, abstract_declaration)

    if len(etree_node.attrib) > 0:
        attrs_uses = declaration.typeDefinition().attributeUses()
        for attr_name in etree_node.attrib.keys():
            if prefix(attr_name) == "http://www.w3.org/2001/XMLSchema-instance":
                continue
            n_attr_name = no_prefix(attr_name)
            attr_use = [au for au in attrs_uses if au.attributeDeclaration().name() == n_attr_name]
            if attr_use:
                type_info_dict[etree_node].attribute_type_info_map()[attr_name] = attr_use[0]
            else:
                raise RuntimeError("Can't find declaration for attribute {}".format(n_attr_name))

    child_declarations = _find_element_declarations(declaration.typeDefinition(), ns_map)
    for child in etree_node:
        c_name = no_prefix(child.tag)
        child_decl = [(ed, abs_ed, min_o, max_o) for ed, abs_ed, min_o, max_o in child_declarations if ed.name() == c_name]
        if len(child_decl) > 0:
            ed, abs_ed, min_o, max_o = child_decl[0]
            _resolve_types(child, ns_map, ed, abs_ed if abs_ed.abstract() else None, min_o, max_o, type_info_dict)
        else:
            import ipdb; ipdb.set_trace()
            raise RuntimeError("Can't find declaration for element {}".format(c_name))

def resolve_types(root_node, ns_map):
    """
    Augment the ElementTree with type informations for each element and each attribute.

    :param etree_node: An XML node following the ElementTree API
    :param ns_map: A PyXB's Namespace dict {namespace uri : namespace}
    :returns: a dict {Element : TypeInfo}
    """
    type_info_dict = {}
    root_ns, root_tag = split_tag(root_node.tag)
    decl = ns_map[root_ns].elementDeclarations()[root_tag]
    _resolve_types(root_node, ns_map, decl, None, 1, 1, type_info_dict)
    return type_info_dict
