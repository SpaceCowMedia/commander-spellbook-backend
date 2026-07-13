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


cdef class AttributesMatcher:
    cdef readonly frozenset any_of
    cdef readonly frozenset all_of
    cdef readonly frozenset none_of

    cpdef bint matches(self, frozenset attributes)


cdef class Data:
    cdef public dict id_to_card
    cdef public dict id_to_template
    cdef public dict id_to_feature_of_card
    cdef public dict id_to_combo
    cdef public dict id_to_variant
    cdef public dict id_to_feature
    cdef public list generator_combos
    cdef public dict combo_to_cards
    cdef public dict combo_to_templates
    cdef public dict combo_to_produced_features
    cdef public dict combo_to_needed_features
    cdef public dict combo_to_removed_features
    cdef public dict feature_needed_in_combo_to_attributes_matcher
    cdef public dict feature_produced_in_combo_to_attributes
    cdef public dict card_to_features
    cdef public dict features_to_cards
    cdef public dict feature_of_card_to_attributes
    cdef public dict variant_to_cards
    cdef public dict variant_uses_card_dict
    cdef public dict variant_to_templates
    cdef public dict variant_requires_template_dict
    cdef public dict variant_to_of_sets
    cdef public dict variant_of_combo_dict
    cdef public dict variant_to_includes_sets
    cdef public dict variant_includes_combo_dict
    cdef public dict variant_to_produces
    cdef public dict variant_produces_feature_dict
    cdef public frozenset utility_features_ids
