from django.test import TestCase
from spellbook.variants.list_utils import includes_any
from spellbook.models import merge_identities


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
