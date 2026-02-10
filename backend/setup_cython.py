"""
Setup script for Cythonizing spellbook.variants modules.

This script compiles the Python modules in backend/spellbook/variants
using Cython for performance optimization.

Usage:
    python setup_cython.py build_ext --inplace
"""
from setuptools import setup, Extension
from Cython.Build import cythonize

# Define the modules to be cythonized
extensions = [
    Extension("spellbook.variants.multiset", ["spellbook/variants/multiset.py"]),
    Extension("spellbook.variants.minimal_set_of_multisets", ["spellbook/variants/minimal_set_of_multisets.py"]),
    Extension("spellbook.variants.variant_set", ["spellbook/variants/variant_set.py"]),
    Extension("spellbook.variants.variant_data", ["spellbook/variants/variant_data.py"]),
    Extension("spellbook.variants.combo_graph", ["spellbook/variants/combo_graph.py"]),
    Extension("spellbook.variants.variants_generator", ["spellbook/variants/variants_generator.py"]),
]

setup(
    name="spellbook-variants-cython",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': '3',
            'boundscheck': False,
            'wraparound': False,
            'cdivision': True,
            'initializedcheck': False,
            'embedsignature': True,
            'optimize.use_switch': True,
            'optimize.unpack_method_calls': True,
        },
        annotate=True,  # Generate HTML annotation files
    ),
)
