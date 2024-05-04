from typing import TypeVar, Iterable, Set
from multiset import BaseMultiset


T = TypeVar('T')


def includes_any(v: BaseMultiset, others: Iterable[BaseMultiset | Set[T]]) -> bool:
    return any(v.issuperset(o) for o in others)
