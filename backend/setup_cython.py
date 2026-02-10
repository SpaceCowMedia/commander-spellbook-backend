"""
Setup script for Cythonizing spellbook.variants modules.

This script compiles the Python modules in backend/spellbook/variants
using Cython for performance optimization.
"""
from setuptools import setup, Extension
from Cython.Build import cythonize

# Define the modules to be cythonized
extensions = [
    Extension("spellbook.variants.multiset", ["backend/spellbook/variants/multiset.py"]),
    Extension("spellbook.variants.minimal_set_of_multisets", ["backend/spellbook/variants/minimal_set_of_multisets.py"]),
    Extension("spellbook.variants.variant_set", ["backend/spellbook/variants/variant_set.py"]),
    Extension("spellbook.variants.variant_data", ["backend/spellbook/variants/variant_data.py"]),
    Extension("spellbook.variants.combo_graph", ["backend/spellbook/variants/combo_graph.py"]),
    Extension("spellbook.variants.variants_generator", ["backend/spellbook/variants/variants_generator.py"]),
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
            'nonecheck': False,
            'embedsignature': True,
            'optimize.use_switch': True,
            'optimize.unpack_method_calls': True,
        },
        annotate=True,  # Generate HTML annotation files
    ),
)
