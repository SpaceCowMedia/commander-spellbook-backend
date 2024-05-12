from django.test import TestCase
from spellbook.variants.utils import includes_any, count_contains
from multiset import FrozenMultiset


class ListUtilsTests(TestCase):
    def test_includes_any(self):
        self.assertTrue(includes_any(FrozenMultiset([1, 2, 3]), [FrozenMultiset([1, 2, 3])]))
        self.assertTrue(includes_any(FrozenMultiset([1, 2, 3]), [FrozenMultiset([1, 2, 3]), FrozenMultiset([1, 2, 3, 4])]))
        self.assertTrue(includes_any(FrozenMultiset([1, 2, 3]), [FrozenMultiset([1, 2, 3, 4]), FrozenMultiset([2])]))
        self.assertTrue(includes_any(FrozenMultiset(), [FrozenMultiset()]))
        self.assertTrue(includes_any(FrozenMultiset([1]), [FrozenMultiset([2]), FrozenMultiset([1])]))
        self.assertFalse(includes_any(FrozenMultiset([1, 2, 3]), [FrozenMultiset([1, 4]), FrozenMultiset([4, 3])]))
        self.assertFalse(includes_any(FrozenMultiset(), [FrozenMultiset([1, 2, 3])]))

    def test_count_contains(self):
        self.assertEqual(count_contains(FrozenMultiset([1, 2, 3]), FrozenMultiset([1, 2, 3])), 1)
        for i in range(1, 11):
            self.assertEqual(count_contains(FrozenMultiset([1, 2, 3] * i), FrozenMultiset([1, 2, 3])), i)
            self.assertEqual(count_contains(FrozenMultiset([1] * 2 * i + [2] * 3 * i + [3] * i), FrozenMultiset([1, 2, 3])), i)
            self.assertEqual(count_contains(FrozenMultiset([1, 2, 3] * i * i), FrozenMultiset([1, 2, 3] * i)), i)
