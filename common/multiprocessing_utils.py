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
