from typing import TypeVar, Generic


T = TypeVar('T')


class MinimalSetOfSets(Generic[T]):
    def __init__(self, sets: set[frozenset[T]] = None):
        if sets is None:
            sets = set[frozenset[T]]()
        self.sets = sets

    def contains_subset_of(self, aset: frozenset[T]) -> bool:
        for s in self.sets:
            if s.issubset(aset):
                return True
        return False

    def remove_subset_of(self, aset: frozenset[T]):
        self.sets = {s for s in self.sets if not aset.issuperset(s)}

    def remove_superset_of(self, aset: frozenset[T]):
        self.sets = {s for s in self.sets if not s.issuperset(aset)}

    def add(self, aset: frozenset[T]):
        self.remove_superset_of(aset)
        if not self.contains_subset_of(aset):
            self.sets.add(aset)

    def remove(self, aset: frozenset[T]):
        self.sets.remove(aset)

    def __iter__(self):
        return iter(self.sets)

    def __len__(self):
        return len(self.sets)

    def __contains__(self, set: frozenset[T]):
        return set in self.sets

    def __str__(self):
        return str(self.sets)

    def __repr__(self):
        return repr(self.sets)

    def __copy__(self):
        return MinimalSetOfSets(self.sets.copy())

    def copy(self):
        return self.__copy__()

    @classmethod
    def union(cls, *sets: 'MinimalSetOfSets[T]'):
        set_union = cls()
        for s in sets:
            for item in s:
                set_union.add(item)
        return set_union
