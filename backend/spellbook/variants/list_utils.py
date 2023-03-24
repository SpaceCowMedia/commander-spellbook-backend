from typing import TypeVar
from typing import Iterable

T = TypeVar('T', int, str, float, complex)


def rotate(li: list[T], x: int) -> list[T]:
    return li[-x % len(li):] + li[:-x % len(li)]


def all_rotations(li: list[T]) -> list[list[T]]:
    return [rotate(li, x) for x in range(len(li))]


def merge_sort_unique(left: list[T], right: list[T]) -> list[T]:
    return sorted(set(left + right))


def merge_identities(identities: Iterable[str]):
    i = set(''.join(identities).upper())
    i.discard('C')
    return ''.join([color for color in 'WUBRG' if color in i]) or 'C'


def includes_any(v: set[int], others: Iterable[set[int]]) -> bool:
    for o in others:
        if v.issuperset(o):
            return True
    return False
