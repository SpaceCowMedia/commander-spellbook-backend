from typing import TypeVar, Generic, Iterator
from multiset import FrozenMultiset, Multiset


_T = TypeVar('_T')


class MinimalSetOfMultisets(Generic[_T]):
    """
    A class representing a minimal set of sets.

    This class provides functionality to store and manipulate sets of elements.
    It ensures that the stored sets are minimal, meaning that no subset of another set
    in the collection is also present.
    """

    def __init__(self, sets: set[FrozenMultiset[_T]] | None = None):
        """
        Initializes a new minimal set of sets.

        Args:
            sets (set[FrozenMultiset] | None): Optional initial sets to be added to the collection,
            discarding all sets that are supersets of other sets in the collection.
        """
        self._sets = set[FrozenMultiset[_T]]()
        if sets is not None:
            for s in sets:
                self.add(s)

    def contains_subset_of(self, aset: FrozenMultiset[_T] | Multiset[_T]) -> bool:
        """
        Checks if the collection contains a subset of the given set.
        """
        for s in self._sets:
            if s.issubset(aset):
                return True
        return False

    def subsets_of(self, aset: FrozenMultiset[_T] | Multiset[_T]) -> Iterator[FrozenMultiset[_T]]:
        """
        Yields all subsets of the given set that are present in the collection.
        """
        for s in self._sets:
            if s.issubset(aset):
                yield s

    def _remove_superset_of(self, aset: FrozenMultiset[_T]):
        self._sets = {s for s in self._sets if not s.issuperset(aset)}

    def add(self, aset: FrozenMultiset[_T]):
        """
        Adds a set to the collection if it is not a superset of any set in the collection.
        If the set is a subset of any set in the collection, every superset of the set is removed,
        and the set is added to the collection.
        """
        if not self.contains_subset_of(aset):
            self._remove_superset_of(aset)
            self._sets.add(aset)

    def __iter__(self):
        return iter(self._sets)

    def __len__(self):
        return len(self._sets)

    def __contains__(self, set: FrozenMultiset[_T]):
        return set in self._sets

    def __str__(self):
        return str(self._sets)

    def __repr__(self):
        return repr(self._sets)

    def __copy__(self):
        m = MinimalSetOfMultisets[_T]()
        m._sets = self._sets.copy()
        return m

    def copy(self):
        """
        Creates a shallow copy of this minimal set of sets.
        """
        return self.__copy__()

    def __eq__(self, other):
        if isinstance(other, MinimalSetOfMultisets):
            return self._sets == other._sets
        return False

    @classmethod
    def union(cls, *sets: 'MinimalSetOfMultisets[_T]'):
        """
        Creates a new minimal set of sets containing all sets of the given collections,
        discarding all sets that are supersets of other sets in any of the collections.
        """
        set_union = cls()
        for s in sets:
            for item in s:
                set_union.add(item)
        return set_union
