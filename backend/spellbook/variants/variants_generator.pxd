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

# Type definitions for variants_generator.py to enable Cython optimization
#
# Performance improvements for:
# - Variant generation from combo graphs
# - Large-scale iteration over variants
# - Feature processing and matching
# - Recipe definition and result computation
