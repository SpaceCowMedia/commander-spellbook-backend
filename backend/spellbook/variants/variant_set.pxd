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

from spellbook.variants.multiset cimport FrozenMultiset
from spellbook.variants.minimal_set_of_multisets cimport MinimalSetOfMultisets


cdef class VariantSetParameters:
    cdef readonly object max_depth
    cdef readonly bint allow_multiple_copies
    cdef readonly FrozenMultiset filter

    cpdef bint _check_entry(self, FrozenMultiset entry)


cdef class VariantSet:
    cdef VariantSetParameters __parameters
    cdef MinimalSetOfMultisets __sets

    cpdef MinimalSetOfMultisets entries(self)
    cpdef VariantSet filter(self, FrozenMultiset entry)
    cpdef list variants(self)
