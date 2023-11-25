from typing import TypeVar, Iterable


T = TypeVar('T')


def includes_any(v: frozenset[T] | set[T], others: Iterable[frozenset[T] | set[T]]) -> bool:
    return any(v.issuperset(o) for o in others)
