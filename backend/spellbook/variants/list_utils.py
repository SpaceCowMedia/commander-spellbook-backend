from typing import TypeVar, Iterable


T = TypeVar('T')


def includes_any(v: frozenset[T] | set[T], others: Iterable[frozenset[T] | set[T]]) -> bool:
    for o in others:
        if v.issuperset(o):
            return True
    return False


def list_of_tuples_of_lists_to_set(list_of_tuples_of_lists: list[tuple[list[T], ...]]) -> set[tuple[tuple[T, ...], ...]]:
    return set(tuple(tuple(x) for x in y) for y in list_of_tuples_of_lists)
