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

from spellbook.variants.packed_entry cimport PackedEntry


cdef class MinimalSetOfMultisets:
    cdef readonly set __sets
    cdef dict __element_to_entries

    cpdef _index_add(self, PackedEntry entry)
    cpdef _index_remove(self, PackedEntry entry)
    cpdef set _candidates_sharing_elements(self, PackedEntry entry)
    cpdef MinimalSetOfMultisets subtree(self, PackedEntry under)
    cpdef add(self, PackedEntry aset)
    cpdef extend(self, object sets)
    cpdef MinimalSetOfMultisets copy(self)
