from typing import TypeVar
from typing import Iterable

T = TypeVar('T', int, str, float, complex)


def merge_identities(identities: Iterable[str]):
    i = set(''.join(identities).upper())
    i.discard('C')
    return ''.join([color for color in 'WUBRG' if color in i]) or 'C'


def includes_any(v: set[int], others: Iterable[set[int]]) -> bool:
    for o in others:
        if v.issuperset(o):
            return True
    return False
