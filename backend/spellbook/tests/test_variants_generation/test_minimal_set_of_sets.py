from django.test import TestCase
from spellbook.variants.minimal_set_of_multisets import MinimalSetOfMultisets
from multiset import FrozenMultiset


class MinimalSetOfSetsTests(TestCase):
    def setUp(self) -> None:
        self.subject = MinimalSetOfMultisets({
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

    def test_contains_subset(self):
        self.assertFalse(MinimalSetOfMultisets().contains_subset_of(FrozenMultiset([1])))
        self.assertTrue(MinimalSetOfMultisets({FrozenMultiset([1])}).contains_subset_of(FrozenMultiset([1])))
        self.assertFalse(MinimalSetOfMultisets({FrozenMultiset([1, 2])}).contains_subset_of(FrozenMultiset([1])))
        self.assertTrue(MinimalSetOfMultisets({FrozenMultiset([1, 2])}).contains_subset_of(FrozenMultiset([1, 2])))
        self.assertTrue(MinimalSetOfMultisets({FrozenMultiset([1, 2])}).contains_subset_of(FrozenMultiset([1, 2, 3])))
        self.assertTrue(MinimalSetOfMultisets({FrozenMultiset([1, 2]), FrozenMultiset([1, 2, 4])}).contains_subset_of(FrozenMultiset([1, 2, 3])))
        self.assertTrue(MinimalSetOfMultisets({FrozenMultiset([1, 2]), FrozenMultiset([1, 2, 4])}).contains_subset_of(FrozenMultiset([1, 2, 3, 4])))
        self.assertFalse(MinimalSetOfMultisets({FrozenMultiset([1, 2, 6]), FrozenMultiset([1, 2, 4])}).contains_subset_of(FrozenMultiset([1, 2, 3, 5])))
        self.assertTrue(MinimalSetOfMultisets({FrozenMultiset([2]), FrozenMultiset([1, 2, 4])}).contains_subset_of(FrozenMultiset([1, 2, 3])))
        self.assertTrue(MinimalSetOfMultisets({FrozenMultiset([2]), FrozenMultiset([1, 2, 4])}).contains_subset_of(FrozenMultiset([1, 2, 3, 4])))
        self.assertTrue(self.subject.contains_subset_of(FrozenMultiset(range(100))))
        self.assertFalse(self.subject.contains_subset_of(FrozenMultiset(range(7, 10))))

    def test_subsets_of(self):
        self.assertSetEqual(set(MinimalSetOfMultisets().subsets_of(FrozenMultiset([1]))), set())
        self.assertSetEqual(set(MinimalSetOfMultisets({FrozenMultiset([1])}).subsets_of(FrozenMultiset([1]))), {FrozenMultiset([1])})
        self.assertSetEqual(set(MinimalSetOfMultisets({FrozenMultiset([1, 2])}).subsets_of(FrozenMultiset([1]))), set())
        self.assertSetEqual(set(MinimalSetOfMultisets({FrozenMultiset([1, 2])}).subsets_of(FrozenMultiset([1, 2]))), {FrozenMultiset([1, 2])})
        self.assertSetEqual(set(MinimalSetOfMultisets({FrozenMultiset([1, 2])}).subsets_of(FrozenMultiset([1, 2, 3]))), {FrozenMultiset([1, 2])})
        self.assertSetEqual(set(MinimalSetOfMultisets({FrozenMultiset([1, 2]), FrozenMultiset([1, 2, 4])}).subsets_of(FrozenMultiset([1, 2, 3]))), {FrozenMultiset([1, 2])})
        self.assertSetEqual(set(MinimalSetOfMultisets({FrozenMultiset([1, 2]), FrozenMultiset([1, 2, 4])}).subsets_of(FrozenMultiset([1, 2, 3, 4]))), {FrozenMultiset([1, 2])})
        self.assertSetEqual(set(MinimalSetOfMultisets({FrozenMultiset([1, 2, 6]), FrozenMultiset([1, 2, 4]), FrozenMultiset([1, 1, 2, 4])}).subsets_of(FrozenMultiset([1, 2, 3, 4]))), {FrozenMultiset([1, 2, 4])})
        self.assertSetEqual(set(MinimalSetOfMultisets({FrozenMultiset([1, 2, 6]), FrozenMultiset([1, 2, 4]), FrozenMultiset([1, 1, 2, 4])}).subsets_of(FrozenMultiset([1, 1, 2, 3, 4, 6]))), {FrozenMultiset([1, 2, 4]), FrozenMultiset([1, 2, 6])})
        self.assertSetEqual(set(MinimalSetOfMultisets({FrozenMultiset([2]), FrozenMultiset([1, 2, 4])}).subsets_of(FrozenMultiset([1, 2, 3]))), {FrozenMultiset([2])})
        self.assertSetEqual(set(MinimalSetOfMultisets({FrozenMultiset([2]), FrozenMultiset([1, 3]), FrozenMultiset([1, 2, 4])}).subsets_of(FrozenMultiset([1, 2, 3, 4]))), {FrozenMultiset([2]), FrozenMultiset([1, 3])})
        self.assertSetEqual(set(self.subject.subsets_of(FrozenMultiset(range(100)) + FrozenMultiset(range(100)) + {5})), set(self.subject))
        self.assertSetEqual(set(self.subject.subsets_of(FrozenMultiset(range(7, 10)))), set())

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
        self.assertEqual(self.subject, MinimalSetOfMultisets.union(MinimalSetOfMultisets(), self.subject))
        self.assertEqual(self.subject, MinimalSetOfMultisets.union(self.subject, MinimalSetOfMultisets()))
        self.assertEqual(self.subject, MinimalSetOfMultisets.union(self.subject, self.subject))
        other = MinimalSetOfMultisets({
            FrozenMultiset([1, 2, 3, 4, 5]),
            FrozenMultiset(range(50, 100)),
            FrozenMultiset([3, 3, 3]),
            FrozenMultiset([3]),
        })
        self.assertEqual(set(MinimalSetOfMultisets.union(self.subject, other)), {
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

    def test_copy(self):
        self.assertEqual(self.subject, self.subject.copy())
        c = self.subject.copy()
        c.add(FrozenMultiset({}))
        self.assertNotEqual(self.subject, c)
        self.assertNotEqual(len(self.subject), len(c))
