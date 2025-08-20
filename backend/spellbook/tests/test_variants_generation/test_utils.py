from django.test import TestCase
from spellbook.variants.utils import count_contains
from multiset import FrozenMultiset


class ListUtilsTests(TestCase):
    def test_count_contains(self):
        self.assertEqual(count_contains(FrozenMultiset([1, 2, 3]), FrozenMultiset([1, 2, 3])), 1)
        for i in range(1, 11):
            self.assertEqual(count_contains(FrozenMultiset([1, 2, 3] * i), FrozenMultiset([1, 2, 3])), i)
            self.assertEqual(count_contains(FrozenMultiset([1] * 2 * i + [2] * 3 * i + [3] * i), FrozenMultiset([1, 2, 3])), i)
            self.assertEqual(count_contains(FrozenMultiset([1, 2, 3] * i * i), FrozenMultiset([1, 2, 3] * i)), i)
