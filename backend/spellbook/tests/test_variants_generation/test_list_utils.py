from django.test import TestCase
from spellbook.variants.list_utils import includes_any
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
