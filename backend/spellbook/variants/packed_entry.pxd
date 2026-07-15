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


cdef class PackedEntry:
    cdef readonly tuple _packed
    cdef readonly Py_ssize_t _total
    cdef Py_hash_t _hash

    cpdef list items(self)
    cpdef list distinct_elements(self)
    cpdef Py_ssize_t distinct_count(self)
    cpdef bint issubset(self, PackedEntry other)
    cpdef bint issuperset(self, PackedEntry other)
    cpdef PackedEntry union(self, PackedEntry other)
    cpdef PackedEntry combine(self, PackedEntry other)
    cpdef bint has_repeated_positive_elements(self)
