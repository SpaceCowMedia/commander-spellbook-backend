from typing import Iterable, Self
from .packed_entry import PackedEntry


_EMPTY_ENTRY = PackedEntry()


class MinimalSetOfMultisets:
    '''
    A class representing a minimal set of multisets.

    This class provides functionality to store and manipulate sets of elements.
    It ensures that the stored sets are minimal, meaning that no subset of another set
    in the collection is also present.

    An index from element to the entries containing it keeps subset and superset
    searches proportional to the entries sharing elements with the probed entry,
    instead of the whole collection.
    '''

    __slots__ = ('__sets', '__element_to_entries')
    __sets: set[PackedEntry]
    __element_to_entries: dict

    def __init__(
        self,
        sets: Iterable[PackedEntry] | None = None,
        _internal: set[PackedEntry] | None = None,
    ):
        '''
        Initializes a new minimal set of multisets.

        Args:
            sets (Iterable[PackedEntry] | None): Optional initial sets to be added to the collection,
            discarding all sets that are supersets of other sets in the collection.
            _internal (set[PackedEntry] | None): Already-minimal sets adopted without dominance checks.
        '''
        self.__sets = set()
        self.__element_to_entries = {}
        if _internal is not None:
            for entry in _internal:
                self.__sets.add(entry)
                self._index_add(entry)
        if sets is not None:
            self.extend(sets)

    def _index_add(self, entry: PackedEntry):
        element_to_entries = self.__element_to_entries
        for element in entry.distinct_elements():
            bucket = element_to_entries.get(element)
            if bucket is None:
                element_to_entries[element] = {entry}
            else:
                bucket.add(entry)

    def _index_remove(self, entry: PackedEntry):
        element_to_entries = self.__element_to_entries
        for element in entry.distinct_elements():
            bucket = element_to_entries.get(element)
            if bucket is not None:
                bucket.discard(entry)
                if not bucket:
                    del element_to_entries[element]

    def _candidates_sharing_elements(self, entry: PackedEntry) -> set:
        '''
        Returns the entries in the collection sharing at least one element with the given entry.
        Every subset and every superset of the entry is among them, except for the empty entry.
        '''
        candidates = set()
        element_to_entries = self.__element_to_entries
        for element in entry.distinct_elements():
            bucket = element_to_entries.get(element)
            if bucket is not None:
                candidates.update(bucket)
        return candidates

    def subtree(self, under: PackedEntry) -> 'MinimalSetOfMultisets':
        '''
        Creates a new minimal set of multisets containing all sets in the collection that are subsets of the given set.
        '''
        result = set()
        if _EMPTY_ENTRY in self.__sets:
            result.add(_EMPTY_ENTRY)
        for entry in self._candidates_sharing_elements(under):
            if entry.issubset(under):
                result.add(entry)
        return MinimalSetOfMultisets(_internal=result)

    def add(self, aset: PackedEntry):
        '''
        Adds a set to the collection if it is not a superset of any set in the collection.
        If the set is a subset of any set in the collection, every superset of the set is removed,
        and the set is added to the collection.
        '''
        sets = self.__sets
        if _EMPTY_ENTRY in sets:
            return
        if not aset:
            sets.clear()
            self.__element_to_entries.clear()
            sets.add(aset)
            return
        candidates = self._candidates_sharing_elements(aset)
        s: PackedEntry
        for s in candidates:
            if s.issubset(aset):
                return
        for s in candidates:
            if aset.issubset(s):
                sets.remove(s)
                self._index_remove(s)
        sets.add(aset)
        self._index_add(aset)

    def extend(self, sets: Iterable[PackedEntry]):
        '''
        Adds multiple sets to the collection, discarding all sets that are supersets of other sets in the collection.
        '''
        for s in sets:
            self.add(s)

    def __iter__(self):
        return iter(self.__sets)

    def __len__(self):
        return len(self.__sets)

    def __contains__(self, aset: PackedEntry):
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
        result = self.__class__()
        result.__sets = self.__sets.copy()
        result.__element_to_entries = {element: bucket.copy() for element, bucket in self.__element_to_entries.items()}
        return result

    def copy(self):
        'Returns a shallow copy of the collection.'
        return self.__copy__()

    def __or__(self, other: Self):
        result = self.copy()
        result.extend(other)
        return result
