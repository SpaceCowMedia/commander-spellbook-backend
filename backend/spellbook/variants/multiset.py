from typing import MutableMapping, Generic, TypeVar, Hashable, Mapping as MappingType, Union, Optional, Iterable as IterableType, \
    ItemsView, KeysView, ValuesView
from collections import Counter
from collections.abc import Mapping

_T = TypeVar('_T', bound=Hashable)
_Other = Union['BaseMultiset[_T]', IterableType[_T], MappingType[_T, int]]


class BaseMultiset(Generic[_T]):
    """A multiset implementation.

    A multiset is similar to the builtin :class:`set`, but elements can occur multiple times in the multiset.
    It is also similar to a :class:`list` without ordering of the values and hence no index-based operations.

    :see: https://en.wikipedia.org/wiki/Multiset
    """

    __slots__ = ('_elements', '_total')
    _elements: Counter[_T]
    _total: int

    def __init__(self, iterable: Optional[_Other] = None, _internal: Optional[Counter[_T]] = None):
        assert iterable is None or _internal is None, "Either 'iterable' or '_internal' must be provided, not both."
        if isinstance(iterable, BaseMultiset):
            self._elements = iterable._elements.copy()
            self._total = iterable._total
        elif _internal is not None:
            self._elements = _internal
            self._total = self._elements.total()
        else:
            self._elements = Counter[_T](iterable)
            self._total = self._elements.total()

    def __contains__(self, element: object) -> bool:
        return element in self._elements

    def __getitem__(self, element: _T) -> int:
        return self._elements[element]

    def __str__(self) -> str:
        items = ', '.join('%r: %r' % item for item in self._elements.items())
        return '{%s}' % items

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self})'

    def __len__(self) -> int:
        return self._total

    def isdisjoint(self, other: 'BaseMultiset[_T]') -> bool:
        return self._elements.keys().isdisjoint(other._elements.keys())

    def difference(self, other: 'BaseMultiset[_T]'):
        return self.__class__(_internal=self._elements - other._elements)

    def union(self, other: 'BaseMultiset[_T]'):
        return self.__class__(_internal=self._elements | other._elements)

    def combine(self, other: 'BaseMultiset[_T]'):
        return self.__class__(_internal=self._elements + other._elements)

    def intersection(self, other: 'BaseMultiset[_T]'):
        return self.__class__(_internal=self._elements & other._elements)

    def times(self, factor: int):
        if factor == 0:
            return self.__class__()
        if factor < 0:
            raise ValueError('The factor must no be negative.')
        _elements = self._elements.copy()
        for element in _elements:
            _elements[element] *= factor
        return self.__class__(_internal=_elements)

    def count_contains(self, other: 'BaseMultiset[_T]') -> int:
        if len(other) == 0:
            raise ZeroDivisionError('Cannot count the number of times an empty multiset is contained in another multiset')
        if other._total > self._total:
            return 0
        return min(
            self[k] // v
            for k, v in other.items()
            if v > 0
        )

    def issubset(self, other: 'BaseMultiset[_T]') -> bool:
        self_len = self._total
        if self_len == 0:
            return True
        other_len = other._total
        if self_len > other_len:
            return False
        return all(q <= other[element] for element, q in self._elements.items())

    def issuperset(self, other: 'BaseMultiset[_T]') -> bool:
        return other.issubset(self)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BaseMultiset):
            return self._total == other._total and self._elements == other._elements
        return False

    def get(self, element: _T, default: int) -> int:
        return self._elements.get(element, default)

    def copy(self):
        return self.__class__(_internal=self._elements.copy())

    __copy__ = copy

    def items(self) -> ItemsView[_T, int]:
        return self._elements.items()

    def distinct_elements(self) -> KeysView[_T]:
        return self._elements.keys()

    def multiplicities(self) -> ValuesView[int]:
        return self._elements.values()

    def __le__(self, other: 'BaseMultiset[_T]') -> bool:
        return self.issubset(other)

    def __lt__(self, other: 'BaseMultiset[_T]') -> bool:
        return self._total < other._total and self.issubset(other)

    def __ge__(self, other: 'BaseMultiset[_T]') -> bool:
        return self.issuperset(other)

    def __gt__(self, other: 'BaseMultiset[_T]') -> bool:
        return self._total > other._total and self.issuperset(other)

    def __add__(self, other: 'BaseMultiset[_T]'):
        return self.combine(other)

    def __sub__(self, other: 'BaseMultiset[_T]'):
        return self.difference(other)

    def __mul__(self, factor: int):
        return self.times(factor)

    def __rmul__(self, factor: int):
        return self.times(factor)

    def __or__(self, other: 'BaseMultiset[_T]'):
        return self.union(other)

    def __and__(self, other: 'BaseMultiset[_T]'):
        return self.intersection(other)

    def __floordiv__(self, other: 'BaseMultiset[_T]') -> int:
        return self.count_contains(other)

    __iter__ = None


class Multiset(Generic[_T], BaseMultiset[_T]):
    def __setitem__(self, element: _T, quantity: int) -> None:
        if quantity < 0:
            raise ValueError('The quantity must not be negative.')
        elif quantity == 0:
            del self[element]
            return
        current_quantity = self._elements[element]
        self._elements[element] = quantity
        self._total += quantity - current_quantity

    def __delitem__(self, element: _T) -> None:
        current_quantity = self._elements.get(element, 0)
        if current_quantity:
            del self._elements[element]
            self._total -= current_quantity

    def add(self, element: _T, quantity: int = 1) -> None:
        if quantity < 0:
            raise ValueError('The quantity must not be negative.')
        self._elements[element] += quantity
        self._total += quantity


class FrozenMultiset(Generic[_T], BaseMultiset[_T]):
    def __hash__(self):
        return hash(frozenset(self._elements.items()))


Mapping.register(FrozenMultiset)  # type: ignore
MutableMapping.register(Multiset)  # type: ignore
