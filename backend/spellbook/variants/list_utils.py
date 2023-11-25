from typing import TypeVar, Iterable


T = TypeVar('T')


def includes_any(v: frozenset[T] | set[T], others: Iterable[frozenset[T] | set[T]]) -> bool:
    for o in others:
        if v.issuperset(o):
            return True
    return False
