# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
# cython: embedsignature=True
# cython: optimize.use_switch=True
# cython: optimize.unpack_method_calls=True
# cython: infer_types=True
# cython: overflowcheck=False
# cython: profile=False
# cython: annotation_typing=True

cimport cython

from spellbook.variants.multiset cimport FrozenMultiset, Multiset
from spellbook.variants.variant_set cimport VariantSet, VariantSetParameters
from spellbook.variants.variant_data cimport Data


cdef class Node:
    cdef VariantSet _variant_set
    cdef VariantSet _filtered_variant_set
    cdef Graph _graph
    cdef readonly object item
    cdef Py_hash_t _hash
    cdef object _state
    cdef object _subgraph_state

    cpdef _reset_state(self)
    cpdef _reset_subgraph_state(self)
    cpdef _reset_filtered_variant_set(self)


cdef class NodeWithState(Node):
    pass


cdef class NodeWithoutState(Node):
    pass


cdef class CardNode(NodeWithoutState):
    cdef readonly list features
    cdef readonly dict combos


cdef class TemplateNode(NodeWithoutState):
    cdef readonly dict combos


cdef class FeatureOfCardNode(NodeWithoutState):
    cdef readonly Py_ssize_t quantity
    cdef readonly CardNode card
    cdef readonly FeatureWithAttributesNode feature


cdef class FeatureWithAttributesNode(NodeWithState):
    cdef readonly list produced_by_cards
    cdef readonly list produced_by_combos
    cdef readonly list matches


cdef class FeatureWithAttributesMatcherNode(NodeWithState):
    cdef readonly dict needed_by_combos
    cdef readonly set matches


cdef class ComboNode(NodeWithState):
    cdef readonly Multiset cards
    cdef readonly Multiset templates
    cdef readonly dict features_needed
    cdef readonly list features_produced


cpdef bint satisfies(object produced, object needed)


cdef class Graph:
    cdef readonly Py_ssize_t variant_limit
    cdef public VariantSetParameters variant_set_parameters
    cdef public bint subgraph
    cdef readonly Data data
    cdef readonly dict card_nodes
    cdef readonly dict template_nodes
    cdef readonly dict combo_nodes
    cdef set _to_reset_nodes_state
    cdef set _to_reset_nodes_subgraph_state
    cdef set _to_reset_nodes_filtered_variant_set

    cpdef _reset(self)
    cpdef list results(self, VariantSet variant_set)
    cpdef VariantSet _combo_nodes_down(self, ComboNode combo)
    cpdef VariantSet _feature_with_attribute_matchers_nodes_down(self, FeatureWithAttributesMatcherNode feature)
    cpdef VariantSet _feature_with_attributes_nodes_down(self, FeatureWithAttributesNode feature)
    cpdef bint _check_satisfiability_of_uncountable_features(self, ComboNode combo, set available)
    cpdef bint _check_satisfiability_of_countable_features(self, ComboNode combo, dict available)
