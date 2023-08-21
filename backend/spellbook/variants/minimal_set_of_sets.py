from typing import TypeVar, Generic


T = TypeVar('T')


class MinimalSetOfSets(Generic[T]):
    def __init__(self, sets: set[frozenset[T]] | None = None):
        self._sets = set[frozenset[T]]()
        if sets is not None:
            for s in sets:
                self.add(s)

    def contains_subset_of(self, aset: frozenset[T]) -> bool:
        for s in self._sets:
            if s.issubset(aset):
                return True
        return False

    def _remove_superset_of(self, aset: frozenset[T]):
        self._sets = {s for s in self._sets if not s.issuperset(aset)}

    def add(self, aset: frozenset[T]):
        if not self.contains_subset_of(aset):
            self._remove_superset_of(aset)
            self._sets.add(aset)

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
        m = MinimalSetOfSets()
        m._sets = self._sets.copy()
        return m

    def copy(self):
        return self.__copy__()

    def __eq__(self, other):
        if isinstance(other, MinimalSetOfSets):
            return self._sets == other._sets
        return False

    @classmethod
    def union(cls, *sets: 'MinimalSetOfSets[T]'):
        set_union = cls()
        for s in sets:
            for item in s:
                set_union.add(item)
        return set_union
