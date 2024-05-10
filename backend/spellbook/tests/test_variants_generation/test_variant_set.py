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
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 1, 3: 1, 4: 1}), FrozenMultiset({}))), (FrozenMultiset({1: 1, 2: 1, 3: 1, 4: 1}), FrozenMultiset()))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 1, 3: 1, 4: 1}), FrozenMultiset({1: 1, 2: 1, 3: 1}))), (FrozenMultiset({1: 1, 2: 1, 3: 1, 4: 1}), FrozenMultiset({1: 1, 2: 1, 3: 1})))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 3, 4: 4}), FrozenMultiset({1: 5, 2: 6, 3: 7}))), (FrozenMultiset({1: 1, 2: 2, 3: 3, 4: 4}), FrozenMultiset({1: 5, 2: 6, 3: 7})))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key(FrozenMultiset({}), FrozenMultiset({1: 1, 2: 1, 3: 1}))), (FrozenMultiset(), FrozenMultiset({1: 1, 2: 1, 3: 1})))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key(FrozenMultiset({}), FrozenMultiset({}))), (FrozenMultiset(), FrozenMultiset()))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key(FrozenMultiset({1: 1}), FrozenMultiset({1: 2}))), (FrozenMultiset({1: 1}), FrozenMultiset({1: 2})))

    def test_key_to_ingredients(self):
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(FrozenMultiset())), FrozenMultiset())
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(FrozenMultiset({'C1': 7, 'C2': 14, 'T1': 21}))), FrozenMultiset({'C1': 7, 'C2': 14, 'T1': 21}))
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(FrozenMultiset({'C1': 1, 'C2': 2, 'T1': 1, 'T2': 1}))), FrozenMultiset({'C1': 1, 'C2': 2, 'T1': 1, 'T2': 1}))
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(FrozenMultiset({'C1': 10, 'C2': 10, 'T1': 10, 'T3': 10}))), FrozenMultiset({'C1': 10, 'C2': 10, 'T1': 10, 'T3': 10}))

    def test_variant_set_add(self):
        variant_set = VariantSet()
        variant_set.add(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129}))
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129}))]))
        variant_set.add(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129}))
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129}))]))
        variant_set.add(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}))
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129}))]))
        variant_set.add(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4, 5: 5}), FrozenMultiset({1: 1, 2: 2, 3: 129}))
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129}))]))
        variant_set.add(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4, 5: 5, 6: 6}), FrozenMultiset({1: 1, 2: 2}))
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129})), (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4, 5: 5, 6: 6}), FrozenMultiset({1: 1, 2: 2}))]))
        variant_set.add(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4, 5: 5}), FrozenMultiset({1: 1, 2: 2}))
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129})), (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4, 5: 5}), FrozenMultiset({1: 1, 2: 2}))]))
        variant_set.add(FrozenMultiset({2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129}))
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4, 5: 5}), FrozenMultiset({1: 1, 2: 2})), (FrozenMultiset({2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129}))]))
        variant_set.add(FrozenMultiset({2: 2, 4: 4}), FrozenMultiset({}))
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([(FrozenMultiset({2: 2, 4: 4}), FrozenMultiset({}))]))
