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
# - infer_types=True: Enables automatic type inference for better optimization
# - overflowcheck=False: Disables integer overflow checking (faster arithmetic)
# - profile=False: Disables profiling hooks for maximum speed
# - annotation_typing=True: Uses PEP 484 annotations for type inference
#
# These directives provide significant performance improvements for:
# - Dictionary operations in Counter
# - Arithmetic operations on multiset elements
# - Iteration over multiset items
# - Set operations (union, intersection, difference)
