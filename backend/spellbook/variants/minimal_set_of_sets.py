from typing import TypeVar, Generic, Iterator
from settrie import SetTrie
from copy import deepcopy


T = TypeVar('T')


class MinimalSetOfSets(Generic[T]):
    """
    A class representing a minimal set of sets.

    This class provides functionality to store and manipulate sets of elements.
    It ensures that the stored sets are minimal, meaning that no subset of another set
    in the collection is also present.
    """

    def __init__(self, sets: set[frozenset[T]] | None = None):
        """
        Initializes a new minimal set of sets.

        Args:
            sets (set[frozenset[T]] | None): Optional initial sets to be added to the collection,
            discarding all sets that are supersets of other sets in the collection.
        """
        self._sets = SetTrie()
        if sets is not None:
            for s in sets:
                self.add(s)

    def contains_subset_of(self, aset: frozenset[T] | set[T]) -> bool:
        """
        Checks if the collection contains a subset of the given set.
        """
        return len(self._sets.subsets(aset)) > 0

    def _remove_superset_of(self, aset: frozenset[T]):
        purge = False
        for ss in self._sets.supersets(aset):
            self._sets.remove(ss)
            purge = True
        if purge:
            self._sets.purge()

    def add(self, aset: frozenset[T]):
        """
        Adds a set to the collection if it is not a superset of any set in the collection.
        If the set is a subset of any set in the collection, every superset of the set is removed,
        and the set is added to the collection.
        """
        if not self.contains_subset_of(aset):
            self._remove_superset_of(aset)
            self._sets.insert(aset, str(hash(aset)))

    def __iter__(self) -> Iterator[frozenset[T]]:
        return iter(frozenset(ts.elements) for ts in iter(self._sets))  # type: ignore

    def __len__(self):
        return len(self._sets)

    def __contains__(self, set: frozenset[T]):
        return self._sets.find(set) != ''

    def __str__(self):
        return str(self._sets)

    def __repr__(self):
        return repr(self._sets)

    def __copy__(self):
        m = MinimalSetOfSets()
        m._sets = deepcopy(self._sets)
        return m

    def copy(self):
        """
        Creates a deep copy of this minimal set of sets.
        """
        return self.__copy__()

    def __eq__(self, other):
        if isinstance(other, MinimalSetOfSets):
            return frozenset(self) == frozenset(other)
        return False

    @classmethod
    def union(cls, *sets: 'MinimalSetOfSets[T]'):
        """
        Creates a new minimal set of sets containing all sets of the given collections,
        discarding all sets that are supersets of other sets in any of the collections.
        """
        set_union = cls()
        for s in sets:
            for item in s:
                set_union.add(item)
        return set_union
