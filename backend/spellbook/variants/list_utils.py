from typing import TypeVar

T = TypeVar('T', int, str, float, complex)


def rotate(li: list[T], x: int) -> list[T]:
    return li[-x % len(li):] + li[:-x % len(li)]


def all_rotations(li: list[T]) -> list[list[T]]:
    return [rotate(li, x) for x in range(len(li))]


def merge_sort_unique(left: list[T], right: list[T]) -> list[T]:
    return sorted(set(left + right))
