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


cdef class BaseMultiset:
    cdef readonly dict _elements
    cdef readonly Py_ssize_t _total

    cpdef bint isdisjoint(self, BaseMultiset other)
    cpdef BaseMultiset difference(self, BaseMultiset other)
    cpdef BaseMultiset union(self, BaseMultiset other)
    cpdef BaseMultiset combine(self, BaseMultiset other)
    cpdef BaseMultiset intersection(self, BaseMultiset other)
    cpdef bint issubset(self, BaseMultiset other)
    cpdef bint issuperset(self, BaseMultiset other)
    cpdef BaseMultiset copy(self)
    cpdef object items(self)
    cpdef object distinct_elements(self)
    cpdef object multiplicities(self)


cdef class Multiset(BaseMultiset):
    pass


cdef class FrozenMultiset(BaseMultiset):
    cdef Py_hash_t _hash
