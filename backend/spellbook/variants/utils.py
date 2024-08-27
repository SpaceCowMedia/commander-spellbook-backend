from typing import TypeVar, Iterable, Set
from multiset import BaseMultiset


_T = TypeVar('_T')


def includes_any(v: BaseMultiset[_T], others: Iterable[BaseMultiset[_T] | Set[_T]]) -> bool:
    return any(v.issuperset(o) for o in others)


def count_contains(v: BaseMultiset[_T], other: BaseMultiset[_T]) -> int:
    if len(other) == 0:
        raise ValueError('Cannot count the number of times an empty multiset is contained in another multiset')
    if v.issuperset(other):
        return min(
            v[x] // other[x]
            for x in other.distinct_elements()
        )
    return 0
