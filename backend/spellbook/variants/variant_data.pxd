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

# Type definitions for variant_data.py to enable Cython optimization
#
# Performance improvements for:
# - Dictionary lookups and iterations
# - List comprehensions
# - Data structure initialization and population
