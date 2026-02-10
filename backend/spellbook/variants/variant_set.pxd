# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
# cython: embedsignature=True
# cython: optimize.use_switch=True
# cython: optimize.unpack_method_calls=True

# Type definitions for variant_set.py to enable Cython optimization
#
# Performance improvements for:
# - Product operations over multiple variant sets
# - Entry checking and filtering
# - Set union, intersection, and sum operations
# - Iteration over variant entries
