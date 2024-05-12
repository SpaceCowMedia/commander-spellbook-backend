from typing import TypeVar, Iterable, Set
from multiset import BaseMultiset


T = TypeVar('T')


def includes_any(v: BaseMultiset, others: Iterable[BaseMultiset | Set[T]]) -> bool:
    return any(v.issuperset(o) for o in others)


def count_contains(v: BaseMultiset, other: BaseMultiset) -> int:
    if len(other) == 0:
        raise ValueError('Cannot count the number of times an empty multiset is contained in another multiset')
    if v.issuperset(other):
        return min(
            v[x] // other[x]
            for x in other.distinct_elements()
        )
    return 0
