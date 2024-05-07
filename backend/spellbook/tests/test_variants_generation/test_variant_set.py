from typing import Iterable, Mapping
from multiset import FrozenMultiset
from django.test import TestCase
from spellbook.variants.variant_set import VariantSet


def use_hashable_dict(tuples: Iterable[tuple[Mapping[int, int], Mapping[int, int]]]) -> set[tuple[tuple[tuple[int, int], ...], ...]]:
    return set(tuple(tuple(sorted(dict.items())) for dict in t) for t in tuples)


class VariantSetTests(TestCase):
    def test_init(self):
        variant_set = VariantSet()
        self.assertIsNotNone(variant_set)
        self.assertEqual(variant_set.max_depth, float('inf'))
        self.assertEqual(variant_set.variants(), [])
        variant_set = VariantSet(limit=3)
        self.assertIsNotNone(variant_set)
        self.assertEqual(variant_set.max_depth, 3)
        self.assertEqual(variant_set.variants(), [])

    def test_ingredients_to_key(self):
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key({1: 1, 2: 1, 3: 1, 4: 1}, {})), ({1: 1, 2: 1, 3: 1, 4: 1}, {}))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key({1: 1, 2: 1, 3: 1, 4: 1}, {1: 1, 2: 1, 3: 1})), ({1: 1, 2: 1, 3: 1, 4: 1}, {1: 1, 2: 1, 3: 1}))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key({1: 1, 2: 2, 3: 3, 4: 4}, {1: 5, 2: 6, 3: 7})), ({1: 1, 2: 2, 3: 3, 4: 4}, {1: 5, 2: 6, 3: 7}))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key({}, {1: 1, 2: 1, 3: 1})), ({}, {1: 1, 2: 1, 3: 1}))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key({}, {})), ({}, {}))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key({1: 1}, {1: 2})), ({1: 1}, {1: 2}))

    def test_key_to_ingredients(self):
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(FrozenMultiset())), FrozenMultiset())
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(FrozenMultiset({'C1': 7, 'C2': 14, 'T1': 21}))), FrozenMultiset({'C1': 7, 'C2': 14, 'T1': 21}))
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(FrozenMultiset({'C1': 1, 'C2': 2, 'T1': 1, 'T2': 1}))), FrozenMultiset({'C1':1 , 'C2': 2, 'T1': 1, 'T2': 1}))
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(FrozenMultiset({'C1': 10, 'C2': 10, 'T1': 10, 'T3': 10}))), FrozenMultiset({'C1': 10, 'C2': 10, 'T1': 10, 'T3': 10}))

    def test_variant_set_add(self):
        variant_set = VariantSet()
        variant_set.add({1: 1, 2: 2, 3: 129, 4: 4}, {1: 1, 2: 2, 3: 129})
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([({1: 1, 2: 2, 3: 129, 4: 4}, {1: 1, 2: 2, 3: 129})]))
        variant_set.add({1: 1, 2: 2, 3: 129, 4: 4}, {1: 1, 2: 2, 3: 129})
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([({1: 1, 2: 2, 3: 129, 4: 4}, {1: 1, 2: 2, 3: 129})]))
        variant_set.add({1: 1, 2: 2, 3: 129, 4: 4}, {1: 1, 2: 2, 3: 129, 4: 4})
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([({1: 1, 2: 2, 3: 129, 4: 4}, {1: 1, 2: 2, 3: 129})]))
        variant_set.add({1: 1, 2: 2, 3: 129, 4: 4, 5: 5}, {1: 1, 2: 2, 3: 129})
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([({1: 1, 2: 2, 3: 129, 4: 4}, {1: 1, 2: 2, 3: 129})]))
        variant_set.add({1: 1, 2: 2, 3: 129, 4: 4, 5: 5, 6: 6}, {1: 1, 2: 2})
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([({1: 1, 2: 2, 3: 129, 4: 4}, {1: 1, 2: 2, 3: 129}), ({1: 1, 2: 2, 3: 129, 4: 4, 5: 5, 6: 6}, {1: 1, 2: 2})]))
        variant_set.add({1: 1, 2: 2, 3: 129, 4: 4, 5: 5}, {1: 1, 2: 2})
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([({1: 1, 2: 2, 3: 129, 4: 4}, {1: 1, 2: 2, 3: 129}), ({1: 1, 2: 2, 3: 129, 4: 4, 5: 5}, {1: 1, 2: 2})]))
        variant_set.add({2: 2, 3: 129, 4: 4}, {1: 1, 2: 2, 3: 129})
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([({1: 1, 2: 2, 3: 129, 4: 4, 5: 5}, {1: 1, 2: 2}), ({2: 2, 3: 129, 4: 4}, {1: 1, 2: 2, 3: 129})]))
        variant_set.add({2: 2, 4: 4}, {})
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([({2: 2, 4: 4}, {})]))

    def test_is_satisfied_by(self):
        variant_set = VariantSet()
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4}, {1: 1, 2: 2, 3: 3})
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2})
        self.assertTrue(variant_set.is_satisfied_by({1: 1, 2: 2, 3: 3, 4: 4}, {1: 1, 2: 2, 3: 3}))
        self.assertTrue(variant_set.is_satisfied_by({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2}))
        self.assertFalse(variant_set.is_satisfied_by({1: 1, 2: 2, 3: 3, 4: 4}, {1: 1, 2: 2}))
        self.assertFalse(variant_set.is_satisfied_by({1: 1, 2: 2, 3: 3, 4: 4, 5: 4}, {1: 1, 2: 2}))
        self.assertFalse(variant_set.is_satisfied_by({1: 1, 2: 2, 3: 3, 4: 1004, 5: 4}, {1: 1, 2: 2}))
        self.assertFalse(variant_set.is_satisfied_by({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 1}))
        self.assertTrue(variant_set.is_satisfied_by({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2, 3: 3}))
        self.assertTrue(variant_set.is_satisfied_by({0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2, 3: 3, 4: 4}))
        self.assertFalse(variant_set.is_satisfied_by({}, {}))
        variant_set = VariantSet(limit=1)
        variant_set.add({1: 1}, {})
        self.assertFalse(variant_set.is_satisfied_by({1: 1, 2: 2}, {}))

    def test_satisfied_by(self):
        variant_set = VariantSet()
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4}, {1: 1, 2: 2, 3: 3})
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2})
        self.assertSetEqual(use_hashable_dict(variant_set.satisfied_by({1: 1, 2: 2, 3: 3, 4: 4}, {1: 1, 2: 2, 3: 3})), use_hashable_dict([({1: 1, 2: 2, 3: 3, 4: 4}, {1: 1, 2: 2, 3: 3})]))
        self.assertSetEqual(use_hashable_dict(variant_set.satisfied_by({1: 1, 2: 1, 3: 3, 4: 4}, {1: 1, 2: 2, 3: 3})), use_hashable_dict([]))
        self.assertSetEqual(use_hashable_dict(variant_set.satisfied_by({1: 1000, 2: 2000, 3: 3000, 4: 4000}, {1: 1000, 2: 2000, 3: 3000})), use_hashable_dict([({1: 1, 2: 2, 3: 3, 4: 4}, {1: 1, 2: 2, 3: 3})]))
        self.assertSetEqual(use_hashable_dict(variant_set.satisfied_by({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2})), use_hashable_dict([({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2})]))
        self.assertSetEqual(use_hashable_dict(variant_set.satisfied_by({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2, 3: 3})), use_hashable_dict([({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2}), ({1: 1, 2: 2, 3: 3, 4: 4}, {1: 1, 2: 2, 3: 3})]))
        self.assertSetEqual(use_hashable_dict(variant_set.satisfied_by({}, {})), use_hashable_dict([]))
        variant_set = VariantSet(limit=1)
        variant_set.add({1: 1}, {})
        self.assertSetEqual(use_hashable_dict(variant_set.satisfied_by({1: 1, 2: 2}, {})), use_hashable_dict([]))

    def test_len(self):
        variant_set = VariantSet()
        self.assertEqual(len(variant_set), 0)
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4}, {1: 1, 2: 2, 3: 3})
        self.assertEqual(len(variant_set), 1)
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2})
        self.assertEqual(len(variant_set), 2)
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4}, {1: 1, 2: 2, 3: 3})
        self.assertEqual(len(variant_set), 2)
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4}, {1: 1, 2: 2})
        self.assertEqual(len(variant_set), 1)

    def test_variant_set_or(self):
        variant_set = VariantSet()
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4444}, {1: 1, 2: 2, 3: 3})
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2})
        variant_set2 = VariantSet()
        variant_set2.add({1: 1, 2: 2, 3: 3}, {1: 1, 2: 2, 3: 3, 4: 4444})
        variant_set2.add({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1})
        variant_set.add({1: 1, 2: 2, 3: 4, 4: 5444}, {1: 1, 2: 2, 3: 4})

        variant_set3 = variant_set | variant_set2
        self.assertSetEqual(use_hashable_dict(variant_set3.variants()), use_hashable_dict([({1: 1, 2: 2, 3: 3, 4: 4444}, {1: 1, 2: 2, 3: 3}), ({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1}), ({1: 1, 2: 2, 3: 3}, {1: 1, 2: 2, 3: 3, 4: 4444})]))
        variant_set4 = variant_set2 | variant_set
        self.assertSetEqual(use_hashable_dict(variant_set3.variants()), use_hashable_dict(variant_set4.variants()))

        variant_set2.add({2: 1, 3: 3}, {2: 1})
        variant_set3 = variant_set | variant_set2
        self.assertSetEqual(use_hashable_dict(variant_set3.variants()), use_hashable_dict([({2: 1, 3: 3}, {2: 1}), ({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1})]))

        with self.subTest('edge cases test'):
            self.assertIsNotNone(VariantSet.or_sets([]))
            variant_set5 = VariantSet.or_sets([variant_set])
            self.assertIsNotNone(variant_set5)
            self.assertFalse(variant_set5 is variant_set)

        with self.subTest('test commutativity and operator overloading'):
            self.assertEqual(use_hashable_dict((variant_set | variant_set2).variants()), use_hashable_dict((variant_set2 + variant_set).variants()))
            self.assertEqual(use_hashable_dict(VariantSet.or_sets([variant_set, variant_set2, variant_set3]).variants()), use_hashable_dict((variant_set2 + variant_set + variant_set3).variants()))

    def test_variant_set_and(self):
        variant_set = VariantSet()
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4000}, {1: 1, 2: 2, 3: 11})
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2})
        variant_set2 = VariantSet()
        variant_set2.add({1: 1, 2: 2, 3: 3}, {1: 1, 2: 2, 3: 3, 4: 4000})
        variant_set2.add({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1})

        variant_set3 = variant_set & variant_set2
        self.assertEqual(use_hashable_dict(variant_set3.variants()), use_hashable_dict([({1: 1, 2: 2, 3: 3, 4: 4000}, {1: 1, 2: 2, 3: 11, 4: 4000}), ({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2})]))
        variant_set4 = variant_set2 & variant_set
        self.assertSetEqual(use_hashable_dict(variant_set3.variants()), use_hashable_dict(variant_set4.variants()))

        variant_set2.add({2: 1, 3: 3}, {2: 1})
        variant_set3 = variant_set & variant_set2
        self.assertSetEqual(use_hashable_dict(variant_set3.variants()), use_hashable_dict([({1: 1, 2: 2, 3: 3, 4: 4000}, {1: 1, 2: 2, 3: 11}), ({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2})]))

        with self.subTest('edge cases test'):
            self.assertIsNotNone(VariantSet.and_sets([]))
            variant_set5 = VariantSet.and_sets([variant_set])
            self.assertIsNotNone(variant_set5)
            self.assertFalse(variant_set5 is variant_set)

        with self.subTest('test commutativity and operator overloading'):
            self.assertEqual(use_hashable_dict((variant_set & variant_set2).variants()), use_hashable_dict((variant_set2 * variant_set).variants()))
            self.assertEqual(use_hashable_dict(VariantSet.and_sets([variant_set, variant_set2, variant_set3]).variants()), use_hashable_dict((variant_set2 * variant_set * variant_set3).variants()))

    def test_copy(self):
        variant_set = VariantSet()
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4}, {1: 1, 2: 2, 3: 3})
        variant_set.add({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2})
        variant_set2 = variant_set.copy()
        self.assertIsNotNone(variant_set2)
        self.assertFalse(variant_set2 is variant_set)
        self.assertEqual(variant_set2.variants(), variant_set.variants())
        variant_set2.add({1: 1, 2: 2}, {1: 1, 2: 2})
        self.assertNotEqual(variant_set2.variants(), variant_set.variants())
