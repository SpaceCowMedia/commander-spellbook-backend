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


cdef class MinimalSetOfMultisets:
    cdef readonly set __sets

    cpdef MinimalSetOfMultisets subtree(self, FrozenMultiset under)
    cpdef add(self, FrozenMultiset aset)
    cpdef extend(self, object sets)
    cpdef MinimalSetOfMultisets copy(self)
