from django.test import TestCase
from spellbook.variants.minimal_set_of_sets import MinimalSetOfSets


class MinimalSetOfSetsTests(TestCase):
    def setUp(self) -> None:
        self.subject = MinimalSetOfSets({
            frozenset({1, 2, 3}),
            frozenset({1, 2, 3, 4}),
            frozenset({3, 4, 5}),
            frozenset({3, 4, 5, 6}),
            frozenset(range(10)),
        })
        return super().setUp()

    def test_init(self):
        self.assertEqual(set(MinimalSetOfSets()), set())
        self.assertEqual(set(MinimalSetOfSets({frozenset({1})})), {frozenset({1})})
        self.assertEqual(set(MinimalSetOfSets({frozenset({1}), frozenset({2})})), {frozenset({1}), frozenset({2})})
        self.assertEqual(set(MinimalSetOfSets({frozenset({1, 2, 3})})), {frozenset({1, 2, 3})})
        self.assertEqual(set(self.subject), {
            frozenset({1, 2, 3}),
            frozenset({3, 4, 5}),
        })

    def test_contains_subset(self):
        self.assertFalse(MinimalSetOfSets().contains_subset_of({1}))
        self.assertTrue(MinimalSetOfSets({frozenset({1})}).contains_subset_of({1}))
        self.assertFalse(MinimalSetOfSets({frozenset({1, 2})}).contains_subset_of({1}))
        self.assertTrue(MinimalSetOfSets({frozenset({1, 2})}).contains_subset_of({1, 2}))
        self.assertTrue(MinimalSetOfSets({frozenset({1, 2})}).contains_subset_of({1, 2, 3}))
        self.assertTrue(MinimalSetOfSets({frozenset({1, 2}), frozenset({1, 2, 4})}).contains_subset_of({1, 2, 3}))
        self.assertTrue(MinimalSetOfSets({frozenset({1, 2}), frozenset({1, 2, 4})}).contains_subset_of({1, 2, 3, 4}))
        self.assertFalse(MinimalSetOfSets({frozenset({1, 2, 6}), frozenset({1, 2, 4})}).contains_subset_of({1, 2, 3, 5}))
        self.assertTrue(MinimalSetOfSets({frozenset({2}), frozenset({1, 2, 4})}).contains_subset_of({1, 2, 3}))
        self.assertTrue(MinimalSetOfSets({frozenset({2}), frozenset({1, 2, 4})}).contains_subset_of({1, 2, 3, 4}))
        self.assertTrue(self.subject.contains_subset_of(frozenset(range(100))))
        self.assertFalse(self.subject.contains_subset_of(frozenset(range(7, 10))))

    def test_add(self):
        self.subject.add(frozenset({1, 2, 3, 4, 5}))
        self.assertEqual(set(self.subject), {frozenset({1, 2, 3}), frozenset({3, 4, 5})})
        self.subject.add(frozenset(range(50, 100)))
        self.assertEqual(set(self.subject), {frozenset({1, 2, 3}), frozenset({3, 4, 5}), frozenset(range(50, 100))})
        self.subject.add(frozenset(range(50, 100)))
        self.assertEqual(set(self.subject), {frozenset({1, 2, 3}), frozenset({3, 4, 5}), frozenset(range(50, 100))})
        self.subject.add(frozenset({1, 2, 3, 4}))
        self.assertEqual(set(self.subject), {frozenset({1, 2, 3}), frozenset({3, 4, 5}), frozenset(range(50, 100))})
        self.subject.add(frozenset({3}))
        self.subject.add(frozenset({69}))
        self.assertEqual(set(self.subject), {frozenset({3}), frozenset({69})})
        self.subject.add(frozenset({}))
        self.assertEqual(set(self.subject), {frozenset({})})

    def test_union(self):
        self.assertEqual(self.subject, MinimalSetOfSets.union(MinimalSetOfSets(), self.subject))
        self.assertEqual(self.subject, MinimalSetOfSets.union(self.subject, MinimalSetOfSets()))
        self.assertEqual(self.subject, MinimalSetOfSets.union(self.subject, self.subject))
        other = MinimalSetOfSets({
            frozenset({1, 2, 3, 4, 5}),
            frozenset(range(50, 100)),
            frozenset({3}),
        })
        self.assertEqual(set(MinimalSetOfSets.union(self.subject, other)), {
            frozenset({3}),
            frozenset(range(50, 100)),
        })

    def test_len(self):
        self.subject.add(frozenset({1, 2, 3, 4, 5}))
        self.assertEqual(len(self.subject), 2)
        self.subject.add(frozenset(range(50, 100)))
        self.assertEqual(len(self.subject), 3)
        self.subject.add(frozenset(range(50, 100)))
        self.assertEqual(len(self.subject), 3)
        self.subject.add(frozenset({1, 2, 3, 4}))
        self.assertEqual(len(self.subject), 3)
        self.subject.add(frozenset({3}))
        self.subject.add(frozenset({69}))
        self.assertEqual(len(self.subject), 2)
        self.subject.add(frozenset({}))
        self.assertEqual(len(self.subject), 1)

    def test_iter(self):
        self.assertEqual(set(self.subject), {frozenset({1, 2, 3}), frozenset({3, 4, 5})})
        self.assertListEqual(list(self.subject), [frozenset({1, 2, 3}), frozenset({3, 4, 5})])
        self.assertEqual(frozenset(self.subject), frozenset({frozenset({1, 2, 3}), frozenset({3, 4, 5})}))

    def test_contains(self):
        self.assertIn(frozenset({1, 2, 3}), self.subject)
        self.assertIn(frozenset({3, 4, 5}), self.subject)
        self.assertNotIn(frozenset({1, 2, 3, 4}), self.subject)
        self.assertNotIn(frozenset({1, 2, 3, 4, 5}), self.subject)
        self.assertNotIn(frozenset({1}), self.subject)

    def test_copy(self):
        self.assertEqual(self.subject, self.subject.copy())
        c = self.subject.copy()
        c.add(frozenset({}))
        self.assertNotEqual(self.subject, c)
        self.assertNotEqual(len(self.subject), len(c))
