from django.test import TestCase
from spellbook.variants.variant_set import VariantSet
from spellbook.tests.utils import list_of_tuples_of_lists_to_set


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
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key([1, 2, 3, 4], [])), ([1, 2, 3, 4], []))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key([1, 2, 3, 4], [1, 2, 3])), ([1, 2, 3, 4], [1, 2, 3]))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key([], [1, 2, 3])), ([], [1, 2, 3]))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key([], [])), ([], []))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key([1], [1])), ([1], [1]))

    def test_key_to_ingredients(self):
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(frozenset())), frozenset())
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(frozenset({'C1', 'C2', 'T1'}))), frozenset({'C1', 'C2', 'T1'}))
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(frozenset({'C1', 'C2', 'T1', 'T2'}))), frozenset({'C1', 'C2', 'T1', 'T2'}))
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(frozenset({'C1', 'C2', 'T1', 'T3'}))), frozenset({'C1', 'C2', 'T1', 'T3'}))

    def test_variant_set_add(self):
        variant_set = VariantSet()
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4), (1, 2, 3))})
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4), (1, 2, 3))})
        variant_set.add([1, 2, 3, 4], [1, 2, 3, 4])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4), (1, 2, 3))})
        variant_set.add([1, 2, 3, 4, 5], [1, 2, 3])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4), (1, 2, 3))})
        variant_set.add([1, 2, 3, 4, 5, 6], [1, 2])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4), (1, 2, 3)), ((1, 2, 3, 4, 5, 6), (1, 2))})
        variant_set.add([1, 2, 3, 4, 5], [1, 2])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4), (1, 2, 3)), ((1, 2, 3, 4, 5), (1, 2))})
        variant_set.add([2, 3, 4], [1, 2, 3])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4, 5), (1, 2)), ((2, 3, 4), (1, 2, 3))})
        variant_set.add([2, 4], [])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((2, 4), ())})

    def test_is_satisfied_by(self):
        variant_set = VariantSet()
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        variant_set.add([1, 2, 3, 4, 5], [1, 2])
        self.assertTrue(variant_set.is_satisfied_by([1, 2, 3, 4], [1, 2, 3]))
        self.assertTrue(variant_set.is_satisfied_by([1, 2, 3, 4, 5], [1, 2]))
        self.assertFalse(variant_set.is_satisfied_by([1, 2, 3, 4], [1, 2]))
        self.assertTrue(variant_set.is_satisfied_by([1, 2, 3, 4, 5], [1, 2, 3]))
        self.assertTrue(variant_set.is_satisfied_by([0, 1, 2, 3, 4, 5], [1, 2, 3, 4]))
        self.assertFalse(variant_set.is_satisfied_by([], []))

    def test_len(self):
        variant_set = VariantSet()
        self.assertEqual(len(variant_set), 0)
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        self.assertEqual(len(variant_set), 1)
        variant_set.add([1, 2, 3, 4, 5], [1, 2])
        self.assertEqual(len(variant_set), 2)
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        self.assertEqual(len(variant_set), 2)
        variant_set.add([1, 2, 3, 4], [1, 2])
        self.assertEqual(len(variant_set), 1)

    def test_variant_set_or(self):
        variant_set = VariantSet()
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        variant_set.add([1, 2, 3, 4, 5], [1, 2])
        variant_set2 = VariantSet()
        variant_set2.add([1, 2, 3], [1, 2, 3, 4])
        variant_set2.add([1, 2, 3, 4, 5], [1])

        variant_set3 = variant_set | variant_set2
        self.assertSetEqual(list_of_tuples_of_lists_to_set(variant_set3.variants()), list_of_tuples_of_lists_to_set([([1, 2, 3, 4], [1, 2, 3]), ([1, 2, 3, 4, 5], [1]), ([1, 2, 3], [1, 2, 3, 4])]))
        variant_set4 = variant_set2 | variant_set
        self.assertSetEqual(list_of_tuples_of_lists_to_set(variant_set3.variants()), list_of_tuples_of_lists_to_set(variant_set4.variants()))

        variant_set2.add([2, 3], [2])
        variant_set3 = variant_set | variant_set2
        self.assertSetEqual(list_of_tuples_of_lists_to_set(variant_set3.variants()), list_of_tuples_of_lists_to_set([([2, 3], [2]), ([1, 2, 3, 4, 5], [1])]))

        with self.subTest('edge cases test'):
            self.assertIsNotNone(VariantSet.or_sets([]))
            variant_set5 = VariantSet.or_sets([variant_set])
            self.assertIsNotNone(variant_set5)
            self.assertFalse(variant_set5 is variant_set)

        with self.subTest('test commutativity and operator overloading'):
            self.assertEqual(list_of_tuples_of_lists_to_set((variant_set | variant_set2).variants()), list_of_tuples_of_lists_to_set((variant_set2 + variant_set).variants()))
            self.assertEqual(list_of_tuples_of_lists_to_set(VariantSet.or_sets([variant_set, variant_set2, variant_set3]).variants()), list_of_tuples_of_lists_to_set((variant_set2 + variant_set + variant_set3).variants()))

    def test_variant_set_and(self):
        variant_set = VariantSet()
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        variant_set.add([1, 2, 3, 4, 5], [1, 2])
        variant_set2 = VariantSet()
        variant_set2.add([1, 2, 3], [1, 2, 3, 4])
        variant_set2.add([1, 2, 3, 4, 5], [1])

        variant_set3 = variant_set & variant_set2
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set3.variants()), list_of_tuples_of_lists_to_set([([1, 2, 3, 4], [1, 2, 3, 4]), ([1, 2, 3, 4, 5], [1, 2])]))
        variant_set4 = variant_set2 & variant_set
        self.assertSetEqual(list_of_tuples_of_lists_to_set(variant_set3.variants()), list_of_tuples_of_lists_to_set(variant_set4.variants()))

        variant_set2.add([2, 3], [2])
        variant_set3 = variant_set & variant_set2
        self.assertSetEqual(list_of_tuples_of_lists_to_set(variant_set3.variants()), list_of_tuples_of_lists_to_set([([1, 2, 3, 4], [1, 2, 3]), ([1, 2, 3, 4, 5], [1, 2])]))

        with self.subTest('edge cases test'):
            self.assertIsNotNone(VariantSet.and_sets([]))
            variant_set5 = VariantSet.and_sets([variant_set])
            self.assertIsNotNone(variant_set5)
            self.assertFalse(variant_set5 is variant_set)

        with self.subTest('test commutativity and operator overloading'):
            self.assertEqual(list_of_tuples_of_lists_to_set((variant_set & variant_set2).variants()), list_of_tuples_of_lists_to_set((variant_set2 * variant_set).variants()))
            self.assertEqual(list_of_tuples_of_lists_to_set(VariantSet.and_sets([variant_set, variant_set2, variant_set3]).variants()), list_of_tuples_of_lists_to_set((variant_set2 * variant_set * variant_set3).variants()))

    def test_copy(self):
        variant_set = VariantSet()
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        variant_set.add([1, 2, 3, 4, 5], [1, 2])
        variant_set2 = variant_set.copy()
        self.assertIsNotNone(variant_set2)
        self.assertFalse(variant_set2 is variant_set)
        self.assertEqual(variant_set2.variants(), variant_set.variants())
        variant_set2.add([1, 2], [1, 2])
        self.assertNotEqual(variant_set2.variants(), variant_set.variants())
