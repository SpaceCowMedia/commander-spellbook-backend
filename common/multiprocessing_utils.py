import logging
import multiprocessing
import multiprocessing.pool
import os
import signal
from contextlib import contextmanager
from typing import Generator, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Sizes the task worker pools. The work they fan out waits on the database far more than
# on a core, so how wide it is worth spreading is a deployment decision rather than
# something to read off the hardware.
WORKERS_ENV_VAR = 'TASK_WORKERS'

# Pool.terminate() retires its workers with SIGTERM, so it has to stay lethal for them
WORKER_LETHAL_SIGNALS = (signal.SIGTERM,)

# A terminal broadcasts these to the whole foreground process group, and a worker acting
# on one dies holding a result its parent is still waiting for, so only the parent reacts
WORKER_IGNORED_SIGNALS = tuple(
    s for s in (getattr(signal, name, None) for name in ('SIGINT', 'SIGQUIT'))
    if s is not None
)


def resolve_workers(workers: int | None) -> int:
    '''Returns the given worker count, defaulting to `TASK_WORKERS` and then to the cores available.

    Falling back on the cores is a guess: it is the count of a host the deployment never
    sized the pool against, so it is worth a warning wherever it happens.
    '''
    if workers is not None:
        return max(1, workers)
    configured = os.environ.get(WORKERS_ENV_VAR, '').strip()
    if configured:
        try:
            return max(1, int(configured))
        except ValueError:
            reason = f'{WORKERS_ENV_VAR} is set to {configured!r}, which is not a worker count'
    else:
        reason = f'{WORKERS_ENV_VAR} is unset'
    cores = max(1, getattr(os, 'process_cpu_count', os.cpu_count)() or 1)
    logger.warning('%s: sizing the worker pool on the %d cores available instead', reason, cores)
    return cores


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
    '''Drops the shutdown handlers a forked worker inherits from its parent.

    django-tasks' `db_worker` traps SIGINT/SIGTERM/SIGQUIT to let the task in flight
    finish before exiting. A pool worker inheriting that handler logs a bogus shutdown
    line and, since the handler returns instead of exiting, sits deaf through the SIGTERM
    of `Pool.terminate()`, hanging the parent in the unbounded join that follows it.
    '''
    for sig in WORKER_LETHAL_SIGNALS:
        signal.signal(sig, signal.SIG_DFL)
    for sig in WORKER_IGNORED_SIGNALS:
        signal.signal(sig, signal.SIG_IGN)


@contextmanager
def fork_pool(processes: int) -> Generator[multiprocessing.pool.Pool]:
    '''Runs a pool of forked workers, retiring them through the queue sentinel on success.

    `Pool.__exit__` reaches for `terminate()` instead, whose SIGTERM is both noise in the
    logs of a signal trapping parent and a way to lose a worker still writing a result.
    '''
    pool = multiprocessing.get_context('fork').Pool(
        processes=processes,
        initializer=reset_inherited_signal_handlers,
    )
    try:
        yield pool
    except BaseException:
        pool.terminate()
        raise
    else:
        pool.close()
    finally:
        pool.join()


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
