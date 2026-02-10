# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
# cython: embedsignature=True
# cython: optimize.use_switch=True
# cython: optimize.unpack_method_calls=True

# Type definitions for multiset.py to enable Cython optimization
# This .pxd file provides compiler directives for performance improvements:
#
# - boundscheck=False: Disables bounds checking on array/list access
# - wraparound=False: Disables negative indexing
# - cdivision=True: Uses C division semantics (faster)
# - initializedcheck=False: Assumes variables are initialized
# - embedsignature=True: Embeds function signatures in docstrings
# - optimize.use_switch=True: Uses switch statements for optimization
# - optimize.unpack_method_calls=True: Optimizes method calls
#
# These directives provide significant performance improvements for:
# - Dictionary operations in Counter
# - Arithmetic operations on multiset elements
# - Iteration over multiset items
# - Set operations (union, intersection, difference)
