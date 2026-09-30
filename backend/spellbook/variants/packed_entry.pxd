# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=False
# cython: initializedcheck=False
# cython: embedsignature=True
# cython: optimize.use_switch=True
# cython: optimize.unpack_method_calls=True
# cython: infer_types=True
# cython: overflowcheck=False
# cython: profile=False
# cython: annotation_typing=True

# cdivision stays off: template elements are negative and need floor division

cimport cython


@cython.locals(limit=cython.longlong, total=cython.Py_ssize_t, packed_item=cython.longlong)
cpdef Py_ssize_t total_count(tuple packed)


cdef class PackedEntry:
    cdef readonly tuple _packed
    cdef readonly Py_ssize_t _total
    cdef Py_hash_t _hash

    cpdef list items(self)
    @cython.locals(limit=cython.longlong, elements=list, packed_item=cython.longlong)
    cpdef list distinct_elements(self)
    cpdef Py_ssize_t distinct_count(self)
    @cython.locals(first=tuple, second=tuple, first_length=cython.Py_ssize_t, second_length=cython.Py_ssize_t, limit=cython.longlong, i=cython.Py_ssize_t, j=cython.Py_ssize_t, packed_first=cython.longlong, packed_second=cython.longlong, element_first=cython.longlong, element_second=cython.longlong)
    cpdef bint issubset(self, PackedEntry other)
    cpdef bint issuperset(self, PackedEntry other)
    @cython.locals(first=tuple, second=tuple, first_length=cython.Py_ssize_t, second_length=cython.Py_ssize_t, limit=cython.longlong, result=list, i=cython.Py_ssize_t, j=cython.Py_ssize_t, packed_first=cython.longlong, packed_second=cython.longlong, element_first=cython.longlong, element_second=cython.longlong)
    cpdef PackedEntry union(self, PackedEntry other)
    @cython.locals(first=tuple, second=tuple, first_length=cython.Py_ssize_t, second_length=cython.Py_ssize_t, limit=cython.longlong, result=list, i=cython.Py_ssize_t, j=cython.Py_ssize_t, packed_first=cython.longlong, packed_second=cython.longlong, element_first=cython.longlong, element_second=cython.longlong)
    cpdef PackedEntry combine(self, PackedEntry other)
    @cython.locals(limit=cython.longlong, packed_item=cython.longlong)
    cpdef bint has_repeated_positive_elements(self)
