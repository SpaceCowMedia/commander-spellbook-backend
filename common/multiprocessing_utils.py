import multiprocessing
import multiprocessing.pool
import os
import signal
from typing import TypeVar

T = TypeVar('T')

# The signals a long running parent process is likely to trap for a graceful shutdown
SHUTDOWN_SIGNALS = tuple(
    s for s in (getattr(signal, name, None) for name in ('SIGINT', 'SIGTERM', 'SIGQUIT'))
    if s is not None
)


def resolve_workers(workers: int | None) -> int:
    '''Returns the given worker count, defaulting to the number of available processor cores.'''
    if workers is not None:
        return max(1, workers)
    return max(1, getattr(os, 'process_cpu_count', os.cpu_count)() or 1)


def fork_is_available() -> bool:
    '''Whether the fork process start method is supported on this platform.'''
    return 'fork' in multiprocessing.get_all_start_methods()


def parallelism_is_available() -> bool:
    '''Whether the current process can fork child worker processes.

    Besides requiring platform support for the fork start method, the current
    process must be allowed to have children: a daemonic process (e.g. a
    parallel test-runner worker or a Celery worker with daemon processes)
    cannot spawn children, so parallelism must degrade to serial there.
    '''
    return fork_is_available() and not multiprocessing.current_process().daemon


def reset_inherited_signal_handlers() -> None:
    '''Restores the default disposition of the shutdown signals in a forked worker.

    A fork child inherits the signal handlers of its parent, and that parent may be a
    task worker (django-tasks' `db_worker`) trapping SIGINT/SIGTERM/SIGQUIT to finish
    the task it is running before exiting. Inherited by a pool worker, that handler both
    logs a bogus "shutting down gracefully" line when `Pool.terminate()` signals the
    worker at teardown, and - since it returns instead of exiting while a task is
    running - lets the worker ignore the signal, hanging the parent in the unbounded
    join that `Pool.terminate()` ends with.
    '''
    for sig in SHUTDOWN_SIGNALS:
        signal.signal(sig, signal.SIG_DFL)


def fork_pool(processes: int) -> multiprocessing.pool.Pool:
    '''Creates a pool of forked workers that no longer trap the shutdown signals of the parent.'''
    return multiprocessing.get_context('fork').Pool(
        processes=processes,
        initializer=reset_inherited_signal_handlers,
    )


def split_into_chunks(items: list[T], workers: int) -> list[list[T]]:
    '''Splits the items into evenly sized chunks, about four per worker, preserving order.'''
    chunk_count = min(len(items), workers * 4)
    if chunk_count <= 0:
        return []
    chunk_size, remainder = divmod(len(items), chunk_count)
    chunks: list[list[T]] = []
    start = 0
    for i in range(chunk_count):
        end = start + chunk_size + (1 if i < remainder else 0)
        chunks.append(items[start:end])
        start = end
    return chunks
