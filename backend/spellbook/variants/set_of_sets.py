from typing import TypeVar, Generic, Iterable

T = TypeVar('T')


class SetOfSets(Generic[T]):
    def __init__(self, sets: set[frozenset[T]] = set[frozenset[T]]()):
        self.sets = sets

    def contains_subset_of(self, set: frozenset[T]) -> bool:
        for subset in self:
            if subset.issubset(set):
                return True
        return False

    def contains_superset_of(self, set: frozenset[T]) -> bool:
        for superset in self:
            if superset.issuperset(set):
                return True
        return False

    def remove_subset_of(self, set: frozenset[T]):
        self.sets = {s for s in self.sets if not s.issubset(set)}

    def remove_superset_of(self, set: frozenset[T]):
        self.sets = {s for s in self.sets if not s.issuperset(set)}

    def add(self, set: frozenset[T]):
        self.sets.add(set)

    def remove(self, set: frozenset[T]):
        self.sets.remove(set)

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
        return SetOfSets(self.sets.copy())

    def copy(self):
        return self.__copy__()

    def __or__(self, other: 'SetOfSets'):
        return SetOfSets(self.sets | other.sets)

    def __add__(self, other):
        return self.__or__(other)

    def __and__(self, other: 'SetOfSets'):
        return SetOfSets(self.sets & other.sets)

    def __mul__(self, other):
        return self.__and__(other)

    def __sub__(self, other: 'SetOfSets'):
        return SetOfSets(self.sets - other.sets)

    def __xor__(self, other: 'SetOfSets'):
        return SetOfSets(self.sets ^ other.sets)

    def __eq__(self, other: 'SetOfSets'):
        return self.sets == other.sets

    def __ne__(self, other: 'SetOfSets'):
        return self.sets != other.sets
