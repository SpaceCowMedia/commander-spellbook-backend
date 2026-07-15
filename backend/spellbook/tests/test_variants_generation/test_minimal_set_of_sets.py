from collections import Counter
from unittest import TestCase
from spellbook.variants.minimal_set_of_multisets import MinimalSetOfMultisets
from spellbook.variants.packed_entry import PackedEntry


def packed(*elements: int) -> PackedEntry:
    return PackedEntry.from_items(Counter(elements).items())


class MinimalSetOfMultisetsTests(TestCase):
    def setUp(self):
        super().setUp()
        self.subject = MinimalSetOfMultisets({
            packed(1, 1, 2, 3),
            packed(1, 1, 2, 3, 4),
            packed(3, 4, 5, 5, 5),
            packed(3, 4, 5, 5, 5, 6),
            packed(*(list(range(10)) * 2)),
        })

    def test_init(self):
        self.assertEqual(set(MinimalSetOfMultisets()), set())
        self.assertEqual(set(MinimalSetOfMultisets({packed(1)})), {packed(1)})
        self.assertEqual(set(MinimalSetOfMultisets({packed(1), packed(2)})), {packed(1), packed(2)})
        self.assertEqual(set(MinimalSetOfMultisets({packed(1, 2, 3)})), {packed(1, 2, 3)})
        self.assertEqual(set(self.subject), {
            packed(1, 1, 2, 3),
            packed(3, 4, 5, 5, 5),
        })

    def test_add(self):
        self.subject.add(packed(1, 1, 2, 3, 4, 5))
        self.assertEqual(set(self.subject), {packed(1, 1, 2, 3), packed(3, 4, 5, 5, 5)})
        self.subject.add(packed(*range(50, 100)))
        self.assertEqual(set(self.subject), {packed(1, 1, 2, 3), packed(3, 4, 5, 5, 5), packed(*range(50, 100))})
        self.subject.add(packed(*range(50, 100)))
        self.assertEqual(set(self.subject), {packed(1, 1, 2, 3), packed(3, 4, 5, 5, 5), packed(*range(50, 100))})
        self.subject.add(packed(1, 1, 2, 3, 4))
        self.assertEqual(set(self.subject), {packed(1, 1, 2, 3), packed(3, 4, 5, 5, 5), packed(*range(50, 100))})
        self.subject.add(packed(1, 1))
        self.subject.add(packed(5))
        self.subject.add(packed(69))
        self.assertEqual(set(self.subject), {packed(1, 1), packed(69), packed(5)})
        self.subject.add(packed())
        self.assertEqual(set(self.subject), {packed()})

    def test_union(self):
        self.assertEqual(self.subject, MinimalSetOfMultisets() | self.subject)
        self.assertEqual(self.subject, self.subject | MinimalSetOfMultisets())
        self.assertEqual(self.subject, self.subject | self.subject)
        other = MinimalSetOfMultisets({
            packed(1, 2, 3, 4, 5),
            packed(*range(50, 100)),
            packed(3, 3, 3),
            packed(3),
        })
        self.assertEqual(set(self.subject | other), {
            packed(3),
            packed(*range(50, 100)),
        })

    def test_len(self):
        self.subject.add(packed(1, 1, 2, 3, 4, 5))
        self.assertEqual(len(self.subject), 2)
        self.subject.add(packed(*range(50, 100)))
        self.assertEqual(len(self.subject), 3)
        self.subject.add(packed(*range(50, 100)))
        self.assertEqual(len(self.subject), 3)
        self.subject.add(packed(1, 1, 2, 3, 4))
        self.assertEqual(len(self.subject), 3)
        self.subject.add(packed(3))
        self.subject.add(packed(69))
        self.assertEqual(len(self.subject), 2)
        self.subject.add(packed())
        self.assertEqual(len(self.subject), 1)

    def test_iter(self):
        self.assertSetEqual(set(self.subject), {packed(1, 1, 2, 3), packed(3, 4, 5, 5, 5)})
        self.assertEqual(set(self.subject), {packed(1, 1, 2, 3), packed(3, 4, 5, 5, 5)})

    def test_contains(self):
        self.assertIn(packed(1, 1, 2, 3), self.subject)
        self.assertIn(packed(3, 4, 5, 5, 5), self.subject)
        self.assertNotIn(packed(1, 2, 3, 4), self.subject)
        self.assertNotIn(packed(1, 2, 3, 4, 5), self.subject)
        self.assertNotIn(packed(1), self.subject)

    def test_subtree(self):
        self.assertEqual(self.subject.subtree(packed(1, 1)), MinimalSetOfMultisets())
        self.assertEqual(self.subject.subtree(packed(1, 1, 2, 3)), MinimalSetOfMultisets({packed(1, 1, 2, 3)}))
        self.assertEqual(self.subject.subtree(packed(1, 1, 2, 3, 3)), MinimalSetOfMultisets({packed(1, 1, 2, 3)}))
        self.assertEqual(self.subject.subtree(packed(1, 1, 1, 2, 3, 4)), MinimalSetOfMultisets({packed(1, 1, 2, 3)}))
        self.assertEqual(self.subject.subtree(packed(3, 4, 5, 5, 5)), MinimalSetOfMultisets({packed(3, 4, 5, 5, 5)}))
        self.assertEqual(self.subject.subtree(packed(1, 1, 2, 3, 4, 5, 5, 5)), MinimalSetOfMultisets({
            packed(1, 1, 2, 3),
            packed(3, 4, 5, 5, 5),
        }))

    def test_subtree_with_empty_entry(self):
        self.subject.add(packed())
        self.assertEqual(self.subject.subtree(packed(1, 1)), MinimalSetOfMultisets({packed()}))

    def test_copy(self):
        self.assertEqual(self.subject, self.subject.copy())
        c = self.subject.copy()
        c.add(packed())
        self.assertNotEqual(self.subject, c)
        self.assertNotEqual(len(self.subject), len(c))

    def test_copy_is_independent(self):
        c = self.subject.copy()
        c.add(packed(7))
        self.assertNotIn(packed(7), self.subject)
        self.assertEqual(c.subtree(packed(7)), MinimalSetOfMultisets({packed(7)}))
        self.assertEqual(self.subject.subtree(packed(7)), MinimalSetOfMultisets())
