from unittest import TestCase
from multiprocessing_utils import resolve_workers, fork_is_available, split_into_chunks


class TestMultiprocessingUtils(TestCase):
    def test_resolve_workers_defaults_to_cpu_count(self):
        self.assertGreaterEqual(resolve_workers(None), 1)

    def test_resolve_workers_keeps_explicit_value(self):
        self.assertEqual(resolve_workers(3), 3)

    def test_resolve_workers_enforces_a_minimum_of_one(self):
        self.assertEqual(resolve_workers(0), 1)
        self.assertEqual(resolve_workers(-5), 1)

    def test_fork_is_available_returns_a_boolean(self):
        self.assertIsInstance(fork_is_available(), bool)

    def test_split_into_chunks_of_empty_list(self):
        self.assertEqual(split_into_chunks([], 4), [])

    def test_split_into_chunks_with_fewer_items_than_chunks(self):
        self.assertEqual(split_into_chunks([1, 2], 4), [[1], [2]])

    def test_split_into_chunks_preserves_order_and_items(self):
        for workers in (1, 2, 3, 8):
            for size in (1, 5, 16, 100):
                with self.subTest(workers=workers, size=size):
                    items = list(range(size))
                    chunks = split_into_chunks(items, workers)
                    self.assertEqual([item for chunk in chunks for item in chunk], items)
                    self.assertLessEqual(len(chunks), workers * 4)
                    self.assertLessEqual(max(map(len, chunks)) - min(map(len, chunks)), 1)
