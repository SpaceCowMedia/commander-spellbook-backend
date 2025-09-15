from typing import Iterable, Mapping
from multiset import FrozenMultiset
from django.test import TestCase
from spellbook.variants.variant_set import VariantSet, VariantSetParameters


def use_hashable_dict(tuples: Iterable[tuple[Mapping[int, int], Mapping[int, int]]]) -> set[tuple[tuple[tuple[int, int], ...], ...]]:
    return set(tuple(tuple(sorted(dict.items())) for dict in t) for t in tuples)


class VariantSetTests(TestCase):
    def test_init(self):
        variant_set = VariantSet()
        self.assertIsNotNone(variant_set)
        self.assertEqual(variant_set.parameters.max_depth, float('inf'))
        self.assertEqual(variant_set.variants(), [])
        variant_set = VariantSet(parameters=VariantSetParameters(max_depth=3))
        self.assertIsNotNone(variant_set)
        self.assertEqual(variant_set.parameters.max_depth, 3)
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
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(FrozenMultiset({1: 7, 2: 14, -1: 21}))), FrozenMultiset({1: 7, 2: 14, -1: 21}))
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(FrozenMultiset({1: 1, 2: 2, -1: 1, -2: 1}))), FrozenMultiset({1: 1, 2: 2, -1: 1, -2: 1}))
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(FrozenMultiset({1: 10, 2: 10, -1: 10, -3: 10}))), FrozenMultiset({1: 10, 2: 10, -1: 10, -3: 10}))

    def test_variant_set_add(self):
        variant_set = VariantSet(keys=[
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129})),
        ])
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129})),
        ]))
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129})),
        ])
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129})),
        ]))
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4})),
        ])
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129})),
        ]))
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4, 5: 5}), FrozenMultiset({1: 1, 2: 2, 3: 129})),
        ])
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129})),
        ]))
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4, 5: 5, 6: 6}), FrozenMultiset({1: 1, 2: 2})),
        ])
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129})),
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4, 5: 5, 6: 6}), FrozenMultiset({1: 1, 2: 2})),
        ]))
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4, 5: 5}), FrozenMultiset({1: 1, 2: 2})),
        ])
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129})),
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4, 5: 5}), FrozenMultiset({1: 1, 2: 2})),
        ]))
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129})),
        ])
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4, 5: 5}), FrozenMultiset({1: 1, 2: 2})),
            (FrozenMultiset({2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 1, 2: 2, 3: 129})),
        ]))
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({2: 2, 4: 4}), FrozenMultiset({})),
        ])
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([
            (FrozenMultiset({2: 2, 4: 4}), FrozenMultiset({})),
        ]))

    def test_len(self):
        variant_set = VariantSet()
        self.assertEqual(len(variant_set), 0)
        variant_set = VariantSet(keys=[
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset()),
        ])
        self.assertEqual(len(variant_set), 1)
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1}), FrozenMultiset()),
        ])
        self.assertEqual(len(variant_set), 1)
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4, 5: 5}), FrozenMultiset({1: 1, 2: 2, 3: 129})),
        ])
        self.assertEqual(len(variant_set), 1)
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({2: 1}), FrozenMultiset()),
            VariantSet.ingredients_to_key(FrozenMultiset(), FrozenMultiset({1: 1})),
        ])
        self.assertEqual(len(variant_set), 3)

    def test_or(self):
        variant_set_1 = VariantSet()
        variant_set_2 = VariantSet()
        self.assertEqual(use_hashable_dict((variant_set_1 | variant_set_2).variants()), use_hashable_dict([]))
        variant_set_1 = VariantSet(keys=[
            *variant_set_1.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset()),
        ])
        self.assertEqual(use_hashable_dict((variant_set_1 | variant_set_2).variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset()),
        ]))
        variant_set_2 = VariantSet(keys=[
            *variant_set_2.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({2: 1}), FrozenMultiset()),
        ])
        self.assertEqual(use_hashable_dict((variant_set_1 | variant_set_2).variants()), use_hashable_dict([
            (FrozenMultiset({2: 1}), FrozenMultiset()),
        ]))
        variant_set_1 = VariantSet(keys=[
            *variant_set_1.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1}), FrozenMultiset()),
        ])
        self.assertEqual(use_hashable_dict((variant_set_1 | variant_set_2).variants()), use_hashable_dict([
            (FrozenMultiset({1: 1}), FrozenMultiset()),
            (FrozenMultiset({2: 1}), FrozenMultiset()),
        ]))
        variant_set_2 = VariantSet(keys=[
            *variant_set_2.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1}), FrozenMultiset()),
        ])
        self.assertEqual(use_hashable_dict((variant_set_1 | variant_set_2).variants()), use_hashable_dict([
            (FrozenMultiset({1: 1}), FrozenMultiset()),
            (FrozenMultiset({2: 1}), FrozenMultiset()),
        ]))

    def test_and(self):
        variant_set_1 = VariantSet()
        variant_set_2 = VariantSet()
        self.assertEqual(use_hashable_dict((variant_set_1 & variant_set_2).variants()), use_hashable_dict([]))
        variant_set_1 = VariantSet(keys=[
            *variant_set_1.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset()),
        ])
        self.assertEqual(use_hashable_dict((variant_set_1 & variant_set_2).variants()), use_hashable_dict([]))
        variant_set_2 = VariantSet(keys=[
            *variant_set_2.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({2: 1}), FrozenMultiset()),
        ])
        self.assertEqual(use_hashable_dict((variant_set_1 & variant_set_2).variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset()),
        ]))
        variant_set_1 = VariantSet(keys=[
            *variant_set_1.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset(), FrozenMultiset({1: 1})),
        ])
        variant_set_2 = VariantSet(keys=[
            *variant_set_2.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({3: 100}), FrozenMultiset({2: 1})),
            VariantSet.ingredients_to_key(FrozenMultiset({4: 5}), FrozenMultiset({2: 1})),
            VariantSet.ingredients_to_key(FrozenMultiset({5: 1}), FrozenMultiset({1: 1, 2: 1})),
        ])
        self.assertEqual(use_hashable_dict((variant_set_1 & variant_set_2).variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset()),
            (FrozenMultiset({2: 1}), FrozenMultiset({1: 1})),
            (FrozenMultiset({3: 100}), FrozenMultiset({1: 1, 2: 1})),
            (FrozenMultiset({4: 5}), FrozenMultiset({1: 1, 2: 1})),
            (FrozenMultiset({5: 1}), FrozenMultiset({1: 1, 2: 1})),
        ]))

    def test_sum(self):
        variant_set_1 = VariantSet()
        variant_set_2 = VariantSet()
        self.assertEqual(use_hashable_dict((variant_set_1 + variant_set_2).variants()), use_hashable_dict([]))
        variant_set_1 = VariantSet(keys=[
            *variant_set_1.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset()),
        ])
        self.assertEqual(use_hashable_dict((variant_set_1 + variant_set_2).variants()), use_hashable_dict([]))
        variant_set_2 = VariantSet(keys=[
            *variant_set_2.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({2: 1}), FrozenMultiset()),
        ])
        self.assertEqual(use_hashable_dict((variant_set_1 + variant_set_2).variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 3, 3: 129, 4: 4}), FrozenMultiset()),
        ]))
        variant_set_1 = VariantSet(keys=[
            *variant_set_1.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset(), FrozenMultiset({1: 1})),
        ])
        variant_set_2 = VariantSet(keys=[
            *variant_set_2.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({3: 100}), FrozenMultiset({2: 1})),
            VariantSet.ingredients_to_key(FrozenMultiset({4: 5}), FrozenMultiset({2: 1})),
            VariantSet.ingredients_to_key(FrozenMultiset({5: 1}), FrozenMultiset({1: 1, 2: 1})),
        ])
        self.assertEqual(use_hashable_dict((variant_set_1 + variant_set_2).variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 3, 3: 129, 4: 4}), FrozenMultiset()),
            (FrozenMultiset({1: 1, 2: 2, 3: 229, 4: 4}), FrozenMultiset({2: 1})),
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 9}), FrozenMultiset({2: 1})),
            (FrozenMultiset({2: 1}), FrozenMultiset({1: 1})),
            (FrozenMultiset({3: 100}), FrozenMultiset({1: 1, 2: 1})),
            (FrozenMultiset({4: 5}), FrozenMultiset({1: 1, 2: 1})),
            (FrozenMultiset({5: 1}), FrozenMultiset({1: 2, 2: 1})),
        ]))
        disallow_multiple_copies = VariantSetParameters(allow_multiple_copies=False)
        variant_set_1 = VariantSet(disallow_multiple_copies, keys=[
            *variant_set_1.keys(),
        ])
        variant_set_2 = VariantSet(disallow_multiple_copies, keys=[
            *variant_set_2.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1}), FrozenMultiset({1: 500})),
        ])
        self.assertEqual(use_hashable_dict((variant_set_1 + variant_set_2).variants()), use_hashable_dict([
            (FrozenMultiset({2: 1}), FrozenMultiset({1: 1})),
            (FrozenMultiset({5: 1}), FrozenMultiset({1: 2, 2: 1})),
            (FrozenMultiset({1: 1}), FrozenMultiset({1: 501})),
        ]))

    def test_product_sets(self):
        variant_set = VariantSet(keys=[
            VariantSet.ingredients_to_key(FrozenMultiset({1: 2, 2: 2}), FrozenMultiset()),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 4}), FrozenMultiset()),
        ])
        self.assertEqual(use_hashable_dict(VariantSet.product_sets([]).variants()), use_hashable_dict([]))
        self.assertEqual(use_hashable_dict(VariantSet.product_sets([variant_set]).variants()), use_hashable_dict(variant_set.variants()))
        self.assertEqual(use_hashable_dict(VariantSet.product_sets([variant_set] * 2).variants()), use_hashable_dict([
            (FrozenMultiset({1: 4, 2: 4}), FrozenMultiset()),
            (FrozenMultiset({1: 6, 2: 2}), FrozenMultiset()),
            (FrozenMultiset({1: 8}), FrozenMultiset()),
        ]))
        self.assertEqual(use_hashable_dict(VariantSet.product_sets([variant_set] * 3).variants()), use_hashable_dict([
            (FrozenMultiset({1: 6, 2: 6}), FrozenMultiset()),
            (FrozenMultiset({1: 8, 2: 4}), FrozenMultiset()),
            (FrozenMultiset({1: 10, 2: 2}), FrozenMultiset()),
            (FrozenMultiset({1: 12}), FrozenMultiset()),
        ]))
        variant_set = VariantSet(keys=[
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 1}), FrozenMultiset({1: 2})),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 2}), FrozenMultiset({1: 1})),
            VariantSet.ingredients_to_key(FrozenMultiset({4: 1}), FrozenMultiset()),
            VariantSet.ingredients_to_key(FrozenMultiset({5: 1}), FrozenMultiset({1: 5})),
            VariantSet.ingredients_to_key(FrozenMultiset(), FrozenMultiset({2: 2})),
        ])
        disallow_multiple_copies = VariantSetParameters(allow_multiple_copies=False)
        self.assertEqual(use_hashable_dict(VariantSet.product_sets([], disallow_multiple_copies).variants()), use_hashable_dict([]))
        self.assertEqual(use_hashable_dict(VariantSet.product_sets([variant_set], disallow_multiple_copies).variants()), use_hashable_dict(VariantSet(keys=variant_set.keys(), parameters=disallow_multiple_copies).variants()))
        self.assertEqual(use_hashable_dict(VariantSet.product_sets([variant_set] * 2, disallow_multiple_copies).variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 1, 4: 1}), FrozenMultiset({1: 2})),
            (FrozenMultiset({1: 1, 2: 1, 5: 1}), FrozenMultiset({1: 7})),
            (FrozenMultiset({1: 1, 2: 1}), FrozenMultiset({1: 2, 2: 2})),
            (FrozenMultiset({4: 1, 5: 1}), FrozenMultiset({1: 5})),
            (FrozenMultiset({4: 1}), FrozenMultiset({2: 2})),
            (FrozenMultiset({5: 1}), FrozenMultiset({1: 5, 2: 2})),
            (FrozenMultiset(), FrozenMultiset({2: 4})),
        ]))
        self.assertEqual(use_hashable_dict(VariantSet.product_sets([variant_set] * 3, disallow_multiple_copies).variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 1, 4: 1, 5: 1}), FrozenMultiset({1: 7})),
            (FrozenMultiset({1: 1, 2: 1, 4: 1}), FrozenMultiset({1: 2, 2: 2})),
            (FrozenMultiset({1: 1, 2: 1, 5: 1}), FrozenMultiset({1: 7, 2: 2})),
            (FrozenMultiset({4: 1, 5: 1}), FrozenMultiset({1: 5, 2: 2})),
            (FrozenMultiset({1: 1, 2: 1}), FrozenMultiset({1: 2, 2: 4})),
            (FrozenMultiset({4: 1}), FrozenMultiset({2: 4})),
            (FrozenMultiset({5: 1}), FrozenMultiset({1: 5, 2: 4})),
            (FrozenMultiset(), FrozenMultiset({2: 6})),
        ]))

    def test_variants(self):
        variant_set = VariantSet()
        self.assertEqual(variant_set.variants(), [])
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset()),
        ])
        self.assertEqual(variant_set.variants(), [
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset()),
        ])
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1}), FrozenMultiset()),
        ])
        self.assertEqual(variant_set.variants(), [
            (FrozenMultiset({1: 1}), FrozenMultiset()),
        ])
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset(), FrozenMultiset({1: 1})),
        ])
        self.assertEqual(use_hashable_dict(variant_set.variants()), use_hashable_dict([
            (FrozenMultiset({1: 1}), FrozenMultiset()),
            (FrozenMultiset(), FrozenMultiset({1: 1})),
        ]))

    def test_filter(self):
        variant_set = VariantSet()
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset()),
        ])
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1}), FrozenMultiset({1: 2})),
        ])
        variant_set = VariantSet(keys=[
            *variant_set.keys(),
            VariantSet.ingredients_to_key(FrozenMultiset({1: 1000}), FrozenMultiset()),
        ])
        self.assertEqual(variant_set.filter(variant_set.ingredients_to_key(FrozenMultiset(), FrozenMultiset())).variants(), [])
        self.assertEqual(variant_set.filter(variant_set.ingredients_to_key(FrozenMultiset({1: 1}), FrozenMultiset())).variants(), [])
        self.assertEqual(variant_set.filter(variant_set.ingredients_to_key(FrozenMultiset({1: 1}), FrozenMultiset({1: 2}))).variants(), [
            (FrozenMultiset({1: 1}), FrozenMultiset({1: 2})),
        ])
        self.assertEqual(variant_set.filter(variant_set.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset())).variants(), [
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset()),
        ])
        self.assertEqual(use_hashable_dict(variant_set.filter(variant_set.ingredients_to_key(FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset({1: 2}))).variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset()),
            (FrozenMultiset({1: 1}), FrozenMultiset({1: 2})),
        ]))
        self.assertEqual(use_hashable_dict(variant_set.filter(variant_set.ingredients_to_key(FrozenMultiset({1: 2, 2: 3, 3: 129, 4: 4, 5: 11}), FrozenMultiset({1: 11, 2: 20}))).variants()), use_hashable_dict([
            (FrozenMultiset({1: 1, 2: 2, 3: 129, 4: 4}), FrozenMultiset()),
            (FrozenMultiset({1: 1}), FrozenMultiset({1: 2})),
        ]))
