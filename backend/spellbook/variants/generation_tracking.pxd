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

from spellbook.variants.variant_data cimport Data


cpdef str _hash_parts(object parts)
cpdef dict _meta_payload()
cpdef plan_full_generation(Data data, str reason=*)
# compute_fingerprints and plan_incremental_generation are intentionally left as
# plain compiled defs: the former contains bare generator expressions Cython cannot
# turn into a cpdef, the latter is annotated with the Python-only Fingerprints alias.
