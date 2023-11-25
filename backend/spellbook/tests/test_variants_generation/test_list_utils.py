from django.test import TestCase
from spellbook.variants.list_utils import includes_any


class ListUtilsTests(TestCase):
    def test_includes_any(self):
        self.assertTrue(includes_any({1, 2, 3}, [{1, 2, 3}]))
        self.assertTrue(includes_any({1, 2, 3}, [{1, 2, 3}, {1, 2, 3, 4}]))
        self.assertTrue(includes_any({1, 2, 3}, [{1, 2, 3, 4}, {2}]))
        self.assertTrue(includes_any(set(), [set()]))
        self.assertTrue(includes_any({1}, [{2}, {1}]))
        self.assertFalse(includes_any({1, 2, 3}, [{1, 4}, {4, 3}]))
        self.assertFalse(includes_any(set(), [{1, 2, 3}]))
