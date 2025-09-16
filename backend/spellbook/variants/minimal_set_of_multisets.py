from typing import Iterable, TypeVar, Generic
from multiset import FrozenMultiset, Multiset

_T = TypeVar('_T')


class MinimalSetOfMultisets(Generic[_T]):
    """
    A class representing a minimal set of sets.

    This class provides functionality to store and manipulate sets of elements.
    It ensures that the stored sets are minimal, meaning that no subset of another set
    in the collection is also present.
    """

    __slots__ = ('__sets')
    __sets: set[FrozenMultiset[_T]]

    def __init__(
        self,
        sets: Iterable[FrozenMultiset[_T]] | None = None,
        _internal: set[FrozenMultiset[_T]] | None = None,
    ):
        """
        Initializes a new minimal set of sets.

        Args:
            sets (set[FrozenMultiset] | None): Optional initial sets to be added to the collection,
            discarding all sets that are supersets of other sets in the collection.
        """
        self.__sets = _internal if _internal is not None else set()
        if sets is not None:
            self.extend(sets)

    def subtree(self, under: FrozenMultiset[_T] | Multiset[_T]) -> 'MinimalSetOfMultisets[_T]':
        """
        Creates a new minimal set of sets containing all sets in the collection that are subsets of the given set.
        """
        return MinimalSetOfMultisets(
            _internal={s for s in self.__sets if s.issubset(under)}
        )

    def __contains_subset_of(self, aset: FrozenMultiset[_T]) -> bool:
        return any(s.issubset(aset) for s in self.__sets)

    def __remove_supersets_of(self, aset: FrozenMultiset[_T]):
        self.__sets.difference_update([s for s in self.__sets if s.issuperset(aset)])

    def add(self, aset: FrozenMultiset[_T]):
        """
        Adds a set to the collection if it is not a superset of any set in the collection.
        If the set is a subset of any set in the collection, every superset of the set is removed,
        and the set is added to the collection.
        """
        if not self.__contains_subset_of(aset):
            self.__remove_supersets_of(aset)
            self.__sets.add(aset)

    def extend(self, sets: Iterable[FrozenMultiset[_T]]):
        """
        Adds multiple sets to the collection, discarding all sets that are supersets of other sets in the collection.
        """
        for s in sets:
            self.add(s)

    def __iter__(self):
        return iter(self.__sets)

    def __len__(self):
        return len(self.__sets)

    def __contains__(self, aset: FrozenMultiset[_T]):
        return aset in self.__sets

    def __str__(self):
        return str(self.__sets)

    def __repr__(self):
        return f'MinimalSetOfMultisets({self.__sets})'

    def __eq__(self, other):
        if isinstance(other, MinimalSetOfMultisets):
            return self.__sets == other.__sets
        return False

    def __copy__(self):
        return MinimalSetOfMultisets(_internal=self.__sets.copy())

    def copy(self):
        "Returns a shallow copy of the collection."
        return self.__copy__()

    @classmethod
    def union(cls, a: 'MinimalSetOfMultisets[_T]', b: 'MinimalSetOfMultisets[_T]'):
        """
        Creates a new minimal set of sets containing all sets of the given collections,
        discarding all sets that are supersets of other sets in any of the collections.
        """
        result = a.copy()
        result.extend(b)
        return result
