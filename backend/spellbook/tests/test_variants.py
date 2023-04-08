from unittest import skip
from django.test import TestCase
from spellbook.variants.variant_set import VariantSet
from spellbook.variants.list_utils import merge_identities, includes_any


def list_of_tuples_of_lists_to_set(list_of_tuples_of_lists: list[tuple[list]]) -> set[tuple[tuple]]:
    return set([tuple([tuple(x) for x in y]) for y in list_of_tuples_of_lists])


class ListUtilsTests(TestCase):

    def test_merge_identities(self):
        self.assertEqual(merge_identities(['', '']), 'C')
        for c in 'CWUBRG':
            self.assertEqual(merge_identities([c, '']), c)
            self.assertEqual(merge_identities(['', c]), c)
            self.assertEqual(merge_identities([c, c]), c)
        self.assertEqual(merge_identities(['W', 'U']), 'WU')
        self.assertEqual(merge_identities(['W', 'U', 'B']), 'WUB')
        self.assertEqual(merge_identities(['W', 'U', 'B', 'R']), 'WUBR')
        self.assertEqual(merge_identities(['W', 'U', 'B', 'R', 'G']), 'WUBRG')
        self.assertEqual(merge_identities(sorted(['W', 'U', 'B', 'R', 'G'])), 'WUBRG')
        self.assertEqual(merge_identities(['W', 'U', 'B', 'R', 'G', 'W']), 'WUBRG')
        self.assertEqual(merge_identities(['WU', 'BR', 'G', 'WG']), 'WUBRG')
        self.assertEqual(merge_identities(['S']), 'C')
        self.assertEqual(merge_identities(['S', 'R']), 'R')
        self.assertEqual(merge_identities(['r', 'g']), 'RG')
        self.assertEqual(merge_identities(['g', 'r']), 'RG')

    def test_includes_any(self):
        self.assertTrue(includes_any({1, 2, 3}, [{1, 2, 3}]))
        self.assertTrue(includes_any({1, 2, 3}, [{1, 2, 3}, {1, 2, 3, 4}]))
        self.assertTrue(includes_any({1, 2, 3}, [{1, 2, 3, 4}, {2}]))
        self.assertTrue(includes_any(set(), [set()]))
        self.assertTrue(includes_any({1}, [{2}, {1}]))


class VariantSetTests(TestCase):
    def test_ingredients_to_key(self):
        variant_set = VariantSet()
        self.assertEqual(variant_set.key_to_ingredients(variant_set.ingredients_to_key([1, 2, 3, 4], [])), ([1, 2, 3, 4], []))
        self.assertEqual(variant_set.key_to_ingredients(variant_set.ingredients_to_key([1, 2, 3, 4], [1, 2, 3])), ([1, 2, 3, 4], [1, 2, 3]))
        self.assertEqual(variant_set.key_to_ingredients(variant_set.ingredients_to_key([], [1, 2, 3])), ([], [1, 2, 3]))
        self.assertEqual(variant_set.key_to_ingredients(variant_set.ingredients_to_key([], [])), ([], []))
        self.assertEqual(variant_set.key_to_ingredients(variant_set.ingredients_to_key([1], [1])), ([1], [1]))

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

        self.assertIsNotNone(VariantSet.or_sets([]))
        variant_set5 = VariantSet.or_sets([variant_set])
        self.assertIsNotNone(variant_set5)
        self.assertFalse(variant_set5 is variant_set)

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

        self.assertIsNotNone(VariantSet.and_sets([]))
        variant_set5 = VariantSet.and_sets([variant_set])
        self.assertIsNotNone(variant_set5)
        self.assertFalse(variant_set5 is variant_set)
