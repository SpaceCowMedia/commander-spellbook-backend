from typing import TypeVar, Generic


T = TypeVar('T')


class MinimalSetOfSets(Generic[T]):
    def __init__(self, sets: set[frozenset[T]] = None):
        pass

    def contains_subset_of(self, aset: frozenset[T]) -> bool:
        return False

    def add(self, aset: frozenset[T]):
        pass

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def __contains__(self, aset: frozenset[T]):
        return False

    def __str__(self):
        return ''

    def __repr__(self):
        return ''

    def __copy__(self):
        return self

    def copy(self):
        return self.__copy__()

    def __eq__(self, other):
        return False

    @classmethod
    def union(cls, *sets: 'MinimalSetOfSets[T]'):
        return cls()
