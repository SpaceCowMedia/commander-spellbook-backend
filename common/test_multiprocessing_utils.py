import signal
from unittest import TestCase
from multiprocessing_utils import SHUTDOWN_SIGNALS, fork_pool, resolve_workers, fork_is_available, split_into_chunks


def _shutdown_signal_handlers() -> list[object]:
    '''Reports how the worker process it runs in handles the shutdown signals.'''
    return [signal.getsignal(sig) for sig in SHUTDOWN_SIGNALS]


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

    def test_fork_pool_workers_do_not_inherit_the_shutdown_handlers(self):
        if not fork_is_available():
            self.skipTest('the fork start method is unavailable on this platform')

        def trap(signum, frame):
            '''Stands in for the graceful shutdown handler of a task worker.'''

        previous = [signal.signal(sig, trap) for sig in SHUTDOWN_SIGNALS]
        try:
            with fork_pool(1) as pool:
                handlers = pool.apply(_shutdown_signal_handlers)
            # The parent keeps its own graceful shutdown handlers
            self.assertEqual([signal.getsignal(sig) for sig in SHUTDOWN_SIGNALS], [trap] * len(SHUTDOWN_SIGNALS))
        finally:
            for sig, handler in zip(SHUTDOWN_SIGNALS, previous):
                signal.signal(sig, handler)
        self.assertEqual(handlers, [signal.SIG_DFL] * len(SHUTDOWN_SIGNALS))

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
