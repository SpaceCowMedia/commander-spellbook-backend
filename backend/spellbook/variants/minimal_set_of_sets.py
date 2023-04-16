from typing import TypeVar, Generic


T = TypeVar('T')


class MinimalSetOfSets(Generic[T]):
    def __init__(self, sets: set[frozenset[T]] = None):
        if sets is None:
            sets = set[frozenset[T]]()
        self._sets = sets

    def contains_subset_of(self, aset: frozenset[T]) -> bool:
        for s in self._sets:
            if s.issubset(aset):
                return True
        return False

    def remove_superset_of(self, aset: frozenset[T]):
        self._sets = {s for s in self._sets if not s.issuperset(aset)}

    def add(self, aset: frozenset[T]):
        if not self.contains_subset_of(aset):
            self.remove_superset_of(aset)
            self._sets.add(aset)

    def remove(self, aset: frozenset[T]):
        self._sets.remove(aset)

    def __iter__(self):
        return iter(self._sets)

    def __len__(self):
        return len(self._sets)

    def __contains__(self, set: frozenset[T]):
        return set in self._sets

    def __str__(self):
        return str(self._sets)

    def __repr__(self):
        return repr(self._sets)

    def __copy__(self):
        return MinimalSetOfSets(self._sets.copy())

    def copy(self):
        return self.__copy__()

    @classmethod
    def union(cls, *sets: 'MinimalSetOfSets[T]'):
        set_union = cls()
        for s in sets:
            for item in s:
                set_union.add(item)
        return set_union
