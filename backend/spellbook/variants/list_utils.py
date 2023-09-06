from typing import TypeVar, Iterable, Set

T = TypeVar('T', int, str, float, complex)


def includes_any(v: frozenset[T], others: Iterable[frozenset[T]]) -> bool:
    for o in others:
        if v.issuperset(o):
            return True
    return False
