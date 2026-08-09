import multiprocessing_utils
import signal
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from multiprocessing_utils import WORKER_IGNORED_SIGNALS, WORKER_LETHAL_SIGNALS, cgroup_cpu_quota, fork_pool, parallelism_is_available, resolve_workers, fork_is_available, split_into_chunks


def worker_signal_handlers(signals: tuple[signal.Signals, ...]) -> list[object]:
    '''Reports how the worker process it runs in handles the given signals.'''
    return [signal.getsignal(sig) for sig in signals]


def trap(signum, frame) -> None:
    '''Stands in for the graceful shutdown handler of a task worker.'''


class TestMultiprocessingUtils(TestCase):
    def cpu_quota_from(self, *contents: str) -> int | None:
        with TemporaryDirectory() as directory:
            paths = []
            for index, content in enumerate(contents):
                path = Path(directory) / f'cpu{index}'
                path.write_text(content)
                paths.append(str(path))
            with patch.object(multiprocessing_utils, 'CGROUP_CPU_QUOTA_FILES', (tuple(paths),)):
                return cgroup_cpu_quota()

    def trapping_shutdown_signals(self):
        signals = WORKER_LETHAL_SIGNALS + WORKER_IGNORED_SIGNALS
        previous = [signal.signal(sig, trap) for sig in signals]
        self.addCleanup(lambda: [signal.signal(sig, handler) for sig, handler in zip(signals, previous)])

    def requires_forking(self):
        # A daemonic process, as Django's --parallel test runner uses, cannot fork at all
        if not parallelism_is_available():
            self.skipTest('forking a pool requires the fork start method and a non-daemonic process')

    def test_resolve_workers_defaults_to_cpu_count(self):
        self.assertGreaterEqual(resolve_workers(None), 1)

    def test_resolve_workers_keeps_explicit_value(self):
        self.assertEqual(resolve_workers(3), 3)

    def test_resolve_workers_enforces_a_minimum_of_one(self):
        self.assertEqual(resolve_workers(0), 1)
        self.assertEqual(resolve_workers(-5), 1)

    def test_resolve_workers_never_exceeds_the_cgroup_quota(self):
        quota = cgroup_cpu_quota()
        if quota is None:
            self.skipTest('this process runs without a cgroup cpu quota')
        self.assertLessEqual(resolve_workers(None), quota)

    def test_cgroup_cpu_quota_reads_a_cgroup_v2_limit(self):
        self.assertEqual(self.cpu_quota_from('200000 100000\n'), 2)

    def test_cgroup_cpu_quota_rounds_a_fractional_limit_up_to_one_core(self):
        self.assertEqual(self.cpu_quota_from('50000 100000\n'), 1)

    def test_cgroup_cpu_quota_of_an_unlimited_cgroup_v2(self):
        self.assertIsNone(self.cpu_quota_from('max 100000\n'))

    def test_cgroup_cpu_quota_reads_a_cgroup_v1_limit(self):
        self.assertEqual(self.cpu_quota_from('400000\n', '100000\n'), 4)

    def test_cgroup_cpu_quota_of_an_unlimited_cgroup_v1(self):
        self.assertIsNone(self.cpu_quota_from('-1\n', '100000\n'))

    def test_cgroup_cpu_quota_without_any_cgroup_file(self):
        with patch.object(multiprocessing_utils, 'CGROUP_CPU_QUOTA_FILES', (('/nonexistent/cpu.max',),)):
            self.assertIsNone(cgroup_cpu_quota())

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
        with self.assertRaises(RuntimeError):
            with fork_pool(1) as pool:
                workers = list(pool._pool)  # type: ignore[attr-defined]
                pool.apply_async(time.sleep, (30,))
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
