import multiprocessing
import os
import signal
import time
from unittest import TestCase
from unittest.mock import patch
from multiprocessing_utils import WORKER_IGNORED_SIGNALS, WORKER_LETHAL_SIGNALS, WORKERS_ENV_VAR, fork_pool, parallelism_is_available, resolve_workers, fork_is_available, split_into_chunks


def worker_signal_handlers(signals: tuple[signal.Signals, ...]) -> list[object]:
    '''Reports how the worker process it runs in handles the given signals.'''
    return [signal.getsignal(sig) for sig in signals]


def trap(signum, frame) -> None:
    '''Stands in for the graceful shutdown handler of a task worker.'''


# Inherited by the forked worker, which reports through it that it has started working
worker_started = multiprocessing.Event()


def block_until_retired() -> None:
    '''Occupies the worker it runs in until the pool retires it.'''
    worker_started.set()
    time.sleep(60)


class TestMultiprocessingUtils(TestCase):
    def trapping_shutdown_signals(self):
        signals = WORKER_LETHAL_SIGNALS + WORKER_IGNORED_SIGNALS
        previous = [signal.signal(sig, trap) for sig in signals]
        self.addCleanup(lambda: [signal.signal(sig, handler) for sig, handler in zip(signals, previous)])

    def requires_forking(self):
        # A daemonic process, as Django's --parallel test runner uses, cannot fork at all
        if not parallelism_is_available():
            self.skipTest('forking a pool requires the fork start method and a non-daemonic process')

    def test_resolve_workers_keeps_explicit_value(self):
        self.assertEqual(resolve_workers(3), 3)

    def test_resolve_workers_enforces_a_minimum_of_one(self):
        self.assertEqual(resolve_workers(0), 1)
        self.assertEqual(resolve_workers(-5), 1)

    def test_resolve_workers_reads_the_environment(self):
        with patch.dict(os.environ, {WORKERS_ENV_VAR: ' 6 '}):
            self.assertEqual(resolve_workers(None), 6)

    def test_resolve_workers_enforces_a_minimum_of_one_from_the_environment(self):
        with patch.dict(os.environ, {WORKERS_ENV_VAR: '0'}):
            self.assertEqual(resolve_workers(None), 1)

    def test_resolve_workers_prefers_an_explicit_value_over_the_environment(self):
        with patch.dict(os.environ, {WORKERS_ENV_VAR: '6'}):
            self.assertEqual(resolve_workers(2), 2)

    def test_resolve_workers_warns_when_falling_back_on_the_cores(self):
        cores = max(1, getattr(os, 'process_cpu_count', os.cpu_count)() or 1)
        for value in ('', '   ', 'two'):
            with self.subTest(value=value):
                with patch.dict(os.environ, {WORKERS_ENV_VAR: value}):
                    with self.assertLogs('multiprocessing_utils', level='WARNING') as logs:
                        self.assertEqual(resolve_workers(None), cores)
                self.assertIn(WORKERS_ENV_VAR, logs.output[0])

    def test_resolve_workers_warns_when_the_environment_is_unset(self):
        cores = max(1, getattr(os, 'process_cpu_count', os.cpu_count)() or 1)
        with patch.dict(os.environ):
            os.environ.pop(WORKERS_ENV_VAR, None)
            with self.assertLogs('multiprocessing_utils', level='WARNING'):
                self.assertEqual(resolve_workers(None), cores)

    def test_fork_is_available_returns_a_boolean(self):
        self.assertIsInstance(fork_is_available(), bool)

    def test_fork_pool_workers_do_not_inherit_the_shutdown_handlers(self):
        self.requires_forking()
        self.trapping_shutdown_signals()
        with fork_pool(1) as pool:
            lethal = pool.apply(worker_signal_handlers, (WORKER_LETHAL_SIGNALS,))
            ignored = pool.apply(worker_signal_handlers, (WORKER_IGNORED_SIGNALS,))
        self.assertEqual(lethal, [signal.SIG_DFL] * len(WORKER_LETHAL_SIGNALS))
        self.assertEqual(ignored, [signal.SIG_IGN] * len(WORKER_IGNORED_SIGNALS))

    def test_fork_pool_leaves_the_handlers_of_the_parent_alone(self):
        self.requires_forking()
        self.trapping_shutdown_signals()
        with fork_pool(1) as pool:
            pool.apply(worker_signal_handlers, (WORKER_LETHAL_SIGNALS,))
        signals = WORKER_LETHAL_SIGNALS + WORKER_IGNORED_SIGNALS
        self.assertEqual([signal.getsignal(sig) for sig in signals], [trap] * len(signals))

    def test_fork_pool_retires_its_workers_without_signalling_them(self):
        self.requires_forking()
        with fork_pool(2) as pool:
            workers = list(pool._pool)  # type: ignore[attr-defined]
            pool.map(abs, range(4))
        self.assertEqual([worker.exitcode for worker in workers], [0, 0])

    def test_fork_pool_terminates_its_workers_when_the_body_fails(self):
        self.requires_forking()
        worker_started.clear()
        with self.assertRaises(RuntimeError):
            with fork_pool(1) as pool:
                workers = list(pool._pool)  # type: ignore[attr-defined]
                pool.apply_async(block_until_retired)
                # An idle worker is retired by the queue sentinel instead, never signalled
                self.assertTrue(worker_started.wait(30), 'the worker never started the task')
                raise RuntimeError('the body of the pool failed')
        self.assertEqual([worker.exitcode for worker in workers], [-signal.SIGTERM])

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
