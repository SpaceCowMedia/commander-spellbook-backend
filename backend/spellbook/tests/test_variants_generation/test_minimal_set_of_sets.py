from django.test import TestCase
from spellbook.variants.minimal_set_of_multisets import MinimalSetOfMultisets
from spellbook.variants.multiset import FrozenMultiset


class MinimalSetOfMultisetsTests(TestCase):
    def setUp(self) -> None:
        self.subject = MinimalSetOfMultisets[int]({
            FrozenMultiset([1, 1, 2, 3]),
            FrozenMultiset([1, 1, 2, 3, 4]),
            FrozenMultiset([3, 4, 5, 5, 5]),
            FrozenMultiset([3, 4, 5, 5, 5, 6]),
            FrozenMultiset(list(range(10)) * 2),
        })
        return super().setUp()

    def test_init(self):
        self.assertEqual(set(MinimalSetOfMultisets()), set())
        self.assertEqual(set(MinimalSetOfMultisets({FrozenMultiset([1])})), {FrozenMultiset([1])})
        self.assertEqual(set(MinimalSetOfMultisets({FrozenMultiset([1]), FrozenMultiset([2])})), {FrozenMultiset([1]), FrozenMultiset([2])})
        self.assertEqual(set(MinimalSetOfMultisets({FrozenMultiset([1, 2, 3])})), {FrozenMultiset([1, 2, 3])})
        self.assertEqual(set(self.subject), {
            FrozenMultiset([1, 1, 2, 3]),
            FrozenMultiset([3, 4, 5, 5, 5]),
        })

    def test_add(self):
        self.subject.add(FrozenMultiset([1, 1, 2, 3, 4, 5]))
        self.assertEqual(set(self.subject), {FrozenMultiset([1, 1, 2, 3]), FrozenMultiset([3, 4, 5, 5, 5])})
        self.subject.add(FrozenMultiset(range(50, 100)))
        self.assertEqual(set(self.subject), {FrozenMultiset([1, 1, 2, 3]), FrozenMultiset([3, 4, 5, 5, 5]), FrozenMultiset(range(50, 100))})
        self.subject.add(FrozenMultiset(range(50, 100)))
        self.assertEqual(set(self.subject), {FrozenMultiset([1, 1, 2, 3]), FrozenMultiset([3, 4, 5, 5, 5]), FrozenMultiset(range(50, 100))})
        self.subject.add(FrozenMultiset([1, 1, 2, 3, 4]))
        self.assertEqual(set(self.subject), {FrozenMultiset([1, 1, 2, 3]), FrozenMultiset([3, 4, 5, 5, 5]), FrozenMultiset(range(50, 100))})
        self.subject.add(FrozenMultiset([1, 1]))
        self.subject.add(FrozenMultiset([5]))
        self.subject.add(FrozenMultiset([69]))
        self.assertEqual(set(self.subject), {FrozenMultiset([1, 1]), FrozenMultiset([69]), FrozenMultiset([5])})
        self.subject.add(FrozenMultiset([]))
        self.assertEqual(set(self.subject), {FrozenMultiset([])})

    def test_union(self):
        self.assertEqual(self.subject, MinimalSetOfMultisets() | self.subject)
        self.assertEqual(self.subject, self.subject | MinimalSetOfMultisets())
        self.assertEqual(self.subject, self.subject | self.subject)
        other = MinimalSetOfMultisets({
            FrozenMultiset([1, 2, 3, 4, 5]),
            FrozenMultiset(range(50, 100)),
            FrozenMultiset([3, 3, 3]),
            FrozenMultiset([3]),
        })
        self.assertEqual(set(self.subject | other), {
            FrozenMultiset([3]),
            FrozenMultiset(range(50, 100)),
        })

    def test_len(self):
        self.subject.add(FrozenMultiset([1, 1, 2, 3, 4, 5]))
        self.assertEqual(len(self.subject), 2)
        self.subject.add(FrozenMultiset(range(50, 100)))
        self.assertEqual(len(self.subject), 3)
        self.subject.add(FrozenMultiset(range(50, 100)))
        self.assertEqual(len(self.subject), 3)
        self.subject.add(FrozenMultiset([1, 1, 2, 3, 4]))
        self.assertEqual(len(self.subject), 3)
        self.subject.add(FrozenMultiset([3]))
        self.subject.add(FrozenMultiset([69]))
        self.assertEqual(len(self.subject), 2)
        self.subject.add(FrozenMultiset([]))
        self.assertEqual(len(self.subject), 1)

    def test_iter(self):
        self.assertSetEqual(set(self.subject), {FrozenMultiset([1, 1, 2, 3]), FrozenMultiset([3, 4, 5, 5, 5])})
        self.assertEqual(set(self.subject), {FrozenMultiset([1, 1, 2, 3]), FrozenMultiset([3, 4, 5, 5, 5])})

    def test_contains(self):
        self.assertIn(FrozenMultiset([1, 1, 2, 3]), self.subject)
        self.assertIn(FrozenMultiset([3, 4, 5, 5, 5]), self.subject)
        self.assertNotIn(FrozenMultiset([1, 2, 3, 4]), self.subject)
        self.assertNotIn(FrozenMultiset([1, 2, 3, 4, 5]), self.subject)
        self.assertNotIn(FrozenMultiset([1]), self.subject)

    def test_subtree(self):
        self.assertEqual(self.subject.subtree(FrozenMultiset([1, 1])), MinimalSetOfMultisets())
        self.assertEqual(self.subject.subtree(FrozenMultiset([1, 1, 2, 3])), MinimalSetOfMultisets({FrozenMultiset([1, 1, 2, 3])}))
        self.assertEqual(self.subject.subtree(FrozenMultiset([1, 1, 2, 3, 3])), MinimalSetOfMultisets({FrozenMultiset([1, 1, 2, 3])}))
        self.assertEqual(self.subject.subtree(FrozenMultiset([1, 1, 1, 2, 3, 4])), MinimalSetOfMultisets({FrozenMultiset([1, 1, 2, 3])}))
        self.assertEqual(self.subject.subtree(FrozenMultiset([3, 4, 5, 5, 5])), MinimalSetOfMultisets({FrozenMultiset([3, 4, 5, 5, 5])}))
        self.assertEqual(self.subject.subtree(FrozenMultiset([1, 1, 2, 3, 4, 5, 5, 5])), MinimalSetOfMultisets({
            FrozenMultiset([1, 1, 2, 3]),
            FrozenMultiset([3, 4, 5, 5, 5]),
        }))

    def test_copy(self):
        self.assertEqual(self.subject, self.subject.copy())
        c = self.subject.copy()
        c.add(FrozenMultiset({}))
        self.assertNotEqual(self.subject, c)
        self.assertNotEqual(len(self.subject), len(c))
