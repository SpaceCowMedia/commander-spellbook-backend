from unittest import TestCase
from spellbook.variants.packed_entry import PackedEntry, COUNT_LIMIT


class PackedEntryTests(TestCase):
    def test_from_items_and_items(self):
        self.assertEqual(PackedEntry.from_items([]).items(), [])
        self.assertEqual(PackedEntry.from_items([(1, 2), (3, 1)]).items(), [(1, 2), (3, 1)])
        self.assertEqual(PackedEntry.from_items([(3, 1), (1, 2)]).items(), [(1, 2), (3, 1)])
        self.assertEqual(PackedEntry.from_items([(-2, 5), (1, 2)]).items(), [(-2, 5), (1, 2)])
        self.assertEqual(PackedEntry.from_items([(1, 0), (2, 3)]).items(), [(2, 3)])
        with self.assertRaises(ValueError):
            PackedEntry.from_items([(1, -1)])
        with self.assertRaises(ValueError):
            PackedEntry.from_items([(1, COUNT_LIMIT)])

    def test_distinct_elements_and_counts(self):
        entry = PackedEntry.from_items([(-7, 3), (2, 1), (5, 4)])
        self.assertEqual(entry.distinct_elements(), [-7, 2, 5])
        self.assertEqual(entry.distinct_count(), 3)
        self.assertEqual(len(entry), 8)
        self.assertEqual(len(PackedEntry()), 0)
        self.assertFalse(PackedEntry())
        self.assertTrue(entry)

    def test_issubset(self):
        empty = PackedEntry()
        small = PackedEntry.from_items([(1, 1), (2, 2)])
        large = PackedEntry.from_items([(1, 1), (2, 3), (3, 1)])
        self.assertTrue(empty.issubset(empty))
        self.assertTrue(empty.issubset(small))
        self.assertFalse(small.issubset(empty))
        self.assertTrue(small.issubset(small))
        self.assertTrue(small.issubset(large))
        self.assertFalse(large.issubset(small))
        self.assertTrue(large.issuperset(small))
        self.assertFalse(PackedEntry.from_items([(1, 2), (2, 2)]).issubset(large))
        self.assertFalse(PackedEntry.from_items([(4, 1)]).issubset(large))
        self.assertTrue(PackedEntry.from_items([(-1, 1)]).issubset(PackedEntry.from_items([(-1, 2), (1, 1)])))
        self.assertFalse(PackedEntry.from_items([(-1, 3)]).issubset(PackedEntry.from_items([(-1, 2), (1, 1)])))

    def test_union(self):
        first = PackedEntry.from_items([(1, 1), (2, 3)])
        second = PackedEntry.from_items([(2, 2), (3, 4)])
        self.assertEqual((first | second).items(), [(1, 1), (2, 3), (3, 4)])
        self.assertEqual((second | first).items(), [(1, 1), (2, 3), (3, 4)])
        self.assertEqual((first | PackedEntry()).items(), first.items())
        self.assertEqual((PackedEntry() | first).items(), first.items())

    def test_combine(self):
        first = PackedEntry.from_items([(-1, 1), (2, 3)])
        second = PackedEntry.from_items([(2, 2), (3, 4)])
        self.assertEqual((first + second).items(), [(-1, 1), (2, 5), (3, 4)])
        self.assertEqual((second + first).items(), [(-1, 1), (2, 5), (3, 4)])
        self.assertEqual((first + PackedEntry()).items(), first.items())
        self.assertEqual((PackedEntry() + first).items(), first.items())

    def test_has_repeated_positive_elements(self):
        self.assertFalse(PackedEntry().has_repeated_positive_elements())
        self.assertFalse(PackedEntry.from_items([(1, 1), (2, 1)]).has_repeated_positive_elements())
        self.assertTrue(PackedEntry.from_items([(1, 1), (2, 2)]).has_repeated_positive_elements())
        self.assertFalse(PackedEntry.from_items([(-1, 5), (1, 1)]).has_repeated_positive_elements())

    def test_equality_and_hash(self):
        first = PackedEntry.from_items([(1, 1), (2, 2)])
        second = PackedEntry.from_items([(2, 2), (1, 1)])
        third = PackedEntry.from_items([(1, 1), (2, 3)])
        self.assertEqual(first, second)
        self.assertEqual(hash(first), hash(second))
        self.assertNotEqual(first, third)
        self.assertNotEqual(first, PackedEntry())
        self.assertEqual(len({first, second, third}), 2)

    def test_str(self):
        self.assertEqual(str(PackedEntry()), '{}')
        self.assertEqual(str(PackedEntry.from_items([(1, 2), (-1, 1)])), '{-1: 1, 1: 2}')
