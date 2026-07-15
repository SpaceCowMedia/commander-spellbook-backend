from typing import Iterable
from spellbook.models.constants import MAX_INGREDIENT_QUANTITY

# Each element count must stay below this limit, leaving the rest of the packed integer to the element.
# Ingredient quantities are capped at MAX_INGREDIENT_QUANTITY, but per-element counts can compound as
# combos compose (a card needed q times, a feature needed q times, ...), so we square the cap to leave
# generous headroom while keeping the encoding tied to the model bound.
COUNT_LIMIT = MAX_INGREDIENT_QUANTITY * MAX_INGREDIENT_QUANTITY

# Sentinel value for the lazily computed hash, equal to the zero-initialized value of compiled class attributes
_HASH_NOT_COMPUTED = 0


class PackedEntry:
    '''
    An immutable multiset of integer elements, packed as a sorted tuple of
    element * COUNT_LIMIT + count integers.

    Packing keeps subset checks and merges cache-friendly walks over sorted integers,
    and makes hashing and equality plain tuple operations.
    Elements can be negative: Python floor division and modulo decode them correctly.
    '''

    __slots__ = ('_packed', '_total', '_hash')
    _packed: tuple
    _total: int
    _hash: int

    def __init__(self, _internal: tuple = ()):
        self._packed = _internal
        total = 0
        for packed_item in _internal:
            total += packed_item % COUNT_LIMIT
        self._total = total

    @classmethod
    def from_items(cls, items: Iterable) -> 'PackedEntry':
        '''
        Builds an entry from (element, count) pairs. Elements must be distinct.
        Pairs with a zero count are skipped.
        '''
        packed_items = []
        for element, count in items:
            if count == 0:
                continue
            if count < 0:
                raise ValueError('Counts must not be negative.')
            if count >= COUNT_LIMIT:
                raise ValueError(f'Counts must be lower than {COUNT_LIMIT}.')
            packed_items.append(element * COUNT_LIMIT + count)
        packed_items.sort()
        return cls(tuple(packed_items))

    def items(self) -> list:
        return [divmod(packed_item, COUNT_LIMIT) for packed_item in self._packed]

    def distinct_elements(self) -> list:
        return [packed_item // COUNT_LIMIT for packed_item in self._packed]

    def distinct_count(self) -> int:
        return len(self._packed)

    def __len__(self) -> int:
        return self._total

    def issubset(self, other: 'PackedEntry') -> bool:
        first = self._packed
        second = other._packed
        first_length: int = len(first)
        second_length: int = len(second)
        if first_length > second_length or self._total > other._total:
            return False
        i: int = 0
        j: int = 0
        while i < first_length:
            if second_length - j < first_length - i:
                return False
            packed_first = first[i]
            packed_second = second[j]
            if packed_first == packed_second:
                i += 1
                j += 1
                continue
            element_first = packed_first // COUNT_LIMIT
            element_second = packed_second // COUNT_LIMIT
            if element_first == element_second:
                # same element: the packed comparison is a count comparison
                if packed_first > packed_second:
                    return False
                i += 1
                j += 1
            elif element_first > element_second:
                j += 1
            else:
                return False
        return True

    def issuperset(self, other: 'PackedEntry') -> bool:
        return other.issubset(self)

    def union(self, other: 'PackedEntry') -> 'PackedEntry':
        first = self._packed
        second = other._packed
        first_length: int = len(first)
        second_length: int = len(second)
        result = []
        i: int = 0
        j: int = 0
        while i < first_length and j < second_length:
            packed_first = first[i]
            packed_second = second[j]
            element_first = packed_first // COUNT_LIMIT
            element_second = packed_second // COUNT_LIMIT
            if element_first == element_second:
                # same element: the greater packed value carries the greater count
                result.append(packed_first if packed_first >= packed_second else packed_second)
                i += 1
                j += 1
            elif element_first < element_second:
                result.append(packed_first)
                i += 1
            else:
                result.append(packed_second)
                j += 1
        result.extend(first[i:])
        result.extend(second[j:])
        return PackedEntry(tuple(result))

    def combine(self, other: 'PackedEntry') -> 'PackedEntry':
        first = self._packed
        second = other._packed
        first_length: int = len(first)
        second_length: int = len(second)
        result = []
        i: int = 0
        j: int = 0
        while i < first_length and j < second_length:
            packed_first = first[i]
            packed_second = second[j]
            element_first = packed_first // COUNT_LIMIT
            element_second = packed_second // COUNT_LIMIT
            if element_first == element_second:
                result.append(packed_first + packed_second - element_first * COUNT_LIMIT)
                i += 1
                j += 1
            elif element_first < element_second:
                result.append(packed_first)
                i += 1
            else:
                result.append(packed_second)
                j += 1
        result.extend(first[i:])
        result.extend(second[j:])
        return PackedEntry(tuple(result))

    def has_repeated_positive_elements(self) -> bool:
        for packed_item in self._packed:
            if packed_item >= COUNT_LIMIT and packed_item % COUNT_LIMIT > 1:
                return True
        return False

    def __or__(self, other: 'PackedEntry') -> 'PackedEntry':
        return self.union(other)

    def __add__(self, other: 'PackedEntry') -> 'PackedEntry':
        return self.combine(other)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PackedEntry):
            return self._packed == other._packed
        return False

    def __hash__(self):
        try:
            h = self._hash
        except AttributeError:
            h = _HASH_NOT_COMPUTED
        if h == _HASH_NOT_COMPUTED:
            h = hash(self._packed)
            self._hash = h
        return h

    def __str__(self) -> str:
        items = ', '.join('%r: %r' % divmod(packed_item, COUNT_LIMIT) for packed_item in self._packed)
        return '{%s}' % items

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self})'
