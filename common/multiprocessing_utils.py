import multiprocessing
import os
from typing import TypeVar

T = TypeVar('T')


def resolve_workers(workers: int | None) -> int:
    '''Returns the given worker count, defaulting to the number of available processor cores.'''
    if workers is None:
        workers = getattr(os, 'process_cpu_count', os.cpu_count)() or 1
    return max(1, workers)


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
