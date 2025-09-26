from typing import Callable
from unittest import TestCase
from spellbook.variants.multiset import BaseMultiset, FrozenMultiset, Multiset


class BaseMultisetTests(TestCase):
    MultisetClass: type[BaseMultiset]

    def test_contains_and_getitem(self):
        ms = self.MultisetClass({1: 1, 2: 2, 3: 1})
        self.assertIn(1, ms)
        self.assertIn(2, ms)
        self.assertNotIn(4, ms)
        self.assertEqual(ms[2], 2)
        self.assertEqual(ms[3], 1)

    def test_str_and_repr(self):
        ms = self.MultisetClass({1: 1, 2: 2})
        s = str(ms)
        r = repr(ms)
        self.assertTrue(s.startswith('{'))
        self.assertIn('1', s)
        self.assertIn('2', s)
        self.assertIn('2', r)
        self.assertIn(self.MultisetClass.__name__, r)

    def test_len(self):
        ms = self.MultisetClass({1: 1, 2: 2, 3: 1})
        self.assertEqual(len(ms), 4)

    def test_isdisjoint(self):
        ms1 = self.MultisetClass({1: 1, 2: 1})
        ms2 = self.MultisetClass({3: 1, 4: 1})
        ms3 = self.MultisetClass({2: 1, 3: 1})
        self.assertTrue(ms1.isdisjoint(ms2))
        self.assertFalse(ms1.isdisjoint(ms3))

    def test_difference_union_combine_intersection(self):
        ms1 = self.MultisetClass({1: 1, 2: 2})
        ms2 = self.MultisetClass({2: 3, 3: 1})
        self.assertEqual(ms1.difference(ms2), self.MultisetClass({1: 1}))
        self.assertEqual(ms2.difference(ms1), self.MultisetClass({2: 1, 3: 1}))
        self.assertEqual(ms1.union(ms2), self.MultisetClass({1: 1, 2: 3, 3: 1}))
        self.assertEqual(ms2.union(ms1), self.MultisetClass({1: 1, 2: 3, 3: 1}))
        self.assertEqual(ms1.combine(ms2), self.MultisetClass({1: 1, 2: 5, 3: 1}))
        self.assertEqual(ms2.combine(ms1), self.MultisetClass({1: 1, 2: 5, 3: 1}))
        self.assertEqual(ms1.intersection(ms2), self.MultisetClass({2: 2}))
        self.assertEqual(ms2.intersection(ms1), self.MultisetClass({2: 2}))

    def test_times(self):
        ms = self.MultisetClass({1: 1, 2: 2})
        self.assertEqual(ms.times(3), self.MultisetClass({1: 3, 2: 6}))
        self.assertEqual(ms.times(0), self.MultisetClass())
        with self.assertRaises(ValueError):
            ms.times(-1)

    def test_issubset_issuperset(self):
        ms0 = self.MultisetClass()
        self.assertTrue(ms0.issubset(ms0))
        self.assertTrue(ms0.issuperset(ms0))
        ms1 = self.MultisetClass({1: 1, 2: 1})
        self.assertTrue(ms0.issubset(ms1))
        self.assertTrue(ms1.issuperset(ms0))
        ms2 = self.MultisetClass({1: 1, 2: 2})
        self.assertTrue(ms1.issubset(ms2))
        self.assertFalse(ms2.issubset(ms1))
        self.assertTrue(ms2.issuperset(ms1))
        self.assertFalse(ms1.issuperset(ms2))
        self.assertTrue(ms1.issubset(ms1))
        self.assertTrue(ms1.issuperset(ms1))

    def test_eq_and_copy(self):
        ms1 = self.MultisetClass({1: 1, 2: 2})
        ms2 = self.MultisetClass({1: 1, 2: 2})
        self.assertEqual(ms1, ms2)
        ms3 = ms1.copy()
        self.assertEqual(ms1, ms3)
        # Only mutate if add exists
        add_method = getattr(ms3, 'add', None)
        if callable(add_method):
            add_method(3)
            self.assertNotEqual(ms1, ms3)

    def test_get(self):
        ms = self.MultisetClass({1: 1, 2: 1})
        self.assertEqual(ms.get(1, 0), 1)
        self.assertEqual(ms.get(3, 42), 42)

    def test_items_distinct_elements_multiplicities(self):
        ms = self.MultisetClass({1: 1, 2: 2})
        items = dict(ms.items())
        self.assertEqual(items, {1: 1, 2: 2})
        self.assertEqual(ms.distinct_elements(), {1, 2})
        self.assertEqual(sorted(ms.multiplicities()), [1, 2])

    def test_comparison_operators(self):
        ms1 = self.MultisetClass({1: 1, 2: 1})
        ms2 = self.MultisetClass({1: 1, 2: 2})
        self.assertTrue(ms1 <= ms2)
        self.assertTrue(ms2 >= ms1)
        self.assertTrue(ms1 <= ms1)
        self.assertTrue(ms1 >= ms1)
        self.assertTrue(ms1 < ms2)
        self.assertTrue(ms2 > ms1)
        self.assertFalse(ms1 < ms1)
        self.assertFalse(ms1 > ms1)
        self.assertFalse(ms1 > ms2)
        self.assertFalse(ms2 < ms1)

    def test_arithmetic_operators(self):
        ms1 = self.MultisetClass({1: 1, 2: 2})
        ms2 = self.MultisetClass({2: 3, 3: 1})
        self.assertEqual(ms1 + ms2, self.MultisetClass({1: 1, 2: 5, 3: 1}))
        self.assertEqual(ms2 + ms1 + ms2, self.MultisetClass({1: 1, 2: 8, 3: 2}))
        self.assertEqual(ms1 - ms2, self.MultisetClass({1: 1}))
        self.assertEqual(ms2 - ms1, self.MultisetClass({2: 1, 3: 1}))
        self.assertEqual(ms2 - ms1 - ms2, self.MultisetClass())
        self.assertEqual(ms1 * 2, self.MultisetClass({1: 2, 2: 4}))
        self.assertEqual(2 * ms1, self.MultisetClass({1: 2, 2: 4}))
        self.assertEqual(ms1 | ms2, self.MultisetClass({1: 1, 2: 3, 3: 1}))
        self.assertEqual(ms2 | ms1, self.MultisetClass({1: 1, 2: 3, 3: 1}))
        self.assertEqual(ms1 & ms2, self.MultisetClass({2: 2}))
        self.assertEqual(ms2 & ms1, self.MultisetClass({2: 2}))
        self.assertEqual(ms1 // ms2, 0)
        self.assertEqual(ms2 // ms1, 0)
        self.assertEqual(ms1 // ms1, 1)
        self.assertEqual(ms2 // ms2, 1)

    def base_test_count_contains(self, sut: Callable[[BaseMultiset[int], BaseMultiset[int]], int]):
        self.assertEqual(sut(self.MultisetClass({1: 1, 2: 1, 3: 1}), self.MultisetClass({1: 1, 2: 1, 3: 1})), 1)
        self.assertEqual(sut(self.MultisetClass({-1: 1, 1: 1, 2: 1, 3: 1, 4: 1}), self.MultisetClass({1: 1, 2: 1, 3: 1})), 1)
        for i in range(1, 11):
            self.assertEqual(sut(self.MultisetClass({1: i, 2: i, 3: i}), self.MultisetClass({1: 1, 2: 1, 3: 1})), i)
            self.assertEqual(sut(self.MultisetClass({1: 2 * i, 2: 3 * i, 3: i}), self.MultisetClass({1: 1, 2: 1, 3: 1})), i)
            self.assertEqual(sut(self.MultisetClass({1: i * i, 2: i * i, 3: i * i}), self.MultisetClass({1: i, 2: i, 3: i})), i)
        self.assertEqual(sut(self.MultisetClass({1: 1, 2: 1, 3: 1}), self.MultisetClass({1: 1, 2: 1, 3: 1, 4: 1})), 0)

    def test_count_contains(self):
        self.base_test_count_contains(lambda a, b: a.count_contains(b))

    def test_operator_floordiv(self):
        self.base_test_count_contains(lambda a, b: a // b)


class MultisetTests(BaseMultisetTests):
    MultisetClass = Multiset

    def test_add(self):
        ms = Multiset()
        ms.add(1)
        ms.add(2, 3)
        self.assertEqual(ms[1], 1)
        self.assertEqual(ms[2], 3)
        self.assertEqual(len(ms), 4)

    def test_setitem_and_getitem(self):
        ms = Multiset({1: 1, 2: 2})
        ms[1] = 5
        self.assertEqual(ms[1], 5)
        ms[2] = 0
        self.assertEqual(ms[2], 0)
        self.assertNotIn(2, ms._elements)

    def test_setitem_negative_raises(self):
        ms = Multiset({1: 1})
        with self.assertRaises(ValueError):
            ms[1] = -1

    def test_delitem(self):
        ms = Multiset({1: 1, 2: 2})
        del ms[2]
        self.assertNotIn(2, ms._elements)
        self.assertEqual(ms._total, 1)

    def test_add_negative_raises(self):
        ms = Multiset()
        with self.assertRaises(ValueError):
            ms.add(1, -2)


class FrozenMultisetTests(BaseMultisetTests):
    MultisetClass = FrozenMultiset

    def test_hash(self):
        ms1 = self.MultisetClass([1, 2, 3, 1])
        ms2 = self.MultisetClass([3, 2, 1, 1])
        self.assertEqual(hash(ms1), hash(ms2))
        ms3 = self.MultisetClass([1, 2, 3])
        self.assertNotEqual(hash(ms1), hash(ms3))


del BaseMultisetTests
