from typing import TypeVar
from typing import Iterable

T = TypeVar('T', int, str, float, complex)


def includes_any(v: set[int], others: Iterable[set[int]]) -> bool:
    for o in others:
        if v.issuperset(o):
            return True
    return False
