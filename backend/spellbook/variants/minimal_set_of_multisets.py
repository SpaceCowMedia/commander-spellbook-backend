from typing import Iterable, Self
from .packed_entry import PackedEntry


_EMPTY_ENTRY = PackedEntry()


class MinimalSetOfMultisets:
    '''
    A class representing a minimal set of multisets.

    This class provides functionality to store and manipulate sets of elements.
    It ensures that the stored sets are minimal, meaning that no subset of another set
    in the collection is also present.

    Every entry is indexed under each of its elements, so that its supersets are found among
    the entries holding its least shared element, and under a single key, the element of it that
    was least shared when it was added, so that its subsets are found among the entries keyed by
    its elements. Elements every entry holds, like the cards a combo always needs, then never make
    a search go through the whole collection.
    '''

    __slots__ = ('__sets', '__element_to_entries', '__key_to_entries', '__entry_to_key')
    __sets: set[PackedEntry]
    __element_to_entries: dict
    __key_to_entries: dict
    __entry_to_key: dict

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
        self.__key_to_entries = {}
        self.__entry_to_key = {}
        if _internal is not None:
            for entry in _internal:
                self.__sets.add(entry)
                self._index_add(entry)
        if sets is not None:
            self.extend(sets)

    def _index_add(self, entry: PackedEntry):
        element_to_entries = self.__element_to_entries
        key = None
        key_sharing = -1
        for element in entry.distinct_elements():
            bucket = element_to_entries.get(element)
            if bucket is None:
                element_to_entries[element] = {entry}
                sharing = 0
            else:
                sharing = len(bucket)
                bucket.add(entry)
            if key_sharing < 0 or sharing < key_sharing:
                key = element
                key_sharing = sharing
        if key_sharing < 0:
            return
        self.__entry_to_key[entry] = key
        bucket = self.__key_to_entries.get(key)
        if bucket is None:
            self.__key_to_entries[key] = {entry}
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
        if entry in self.__entry_to_key:
            key = self.__entry_to_key.pop(entry)
            bucket = self.__key_to_entries[key]
            bucket.discard(entry)
            if not bucket:
                del self.__key_to_entries[key]

    def subtree(self, under: PackedEntry) -> 'MinimalSetOfMultisets':
        '''
        Creates a new minimal set of multisets containing all sets in the collection that are subsets of the given set.
        '''
        result = set()
        if _EMPTY_ENTRY in self.__sets:
            result.add(_EMPTY_ENTRY)
        key_to_entries = self.__key_to_entries
        entry: PackedEntry
        for element in under.distinct_elements():
            bucket = key_to_entries.get(element)
            if bucket is not None:
                for entry in bucket:
                    if entry.issubset(under):
                        result.add(entry)
        return MinimalSetOfMultisets(_internal=result)

    def contains_subset_of(self, aset: PackedEntry) -> bool:
        '''
        Returns whether some set in the collection is a subset of the given set.
        '''
        if _EMPTY_ENTRY in self.__sets:
            return True
        key_to_entries = self.__key_to_entries
        s: PackedEntry
        for element in aset.distinct_elements():
            bucket = key_to_entries.get(element)
            if bucket is not None:
                for s in bucket:
                    if s.issubset(aset):
                        return True
        return False

    def _supersets_of(self, aset: PackedEntry) -> list:
        '''
        Returns the sets in the collection that are supersets of the given non-empty set.
        '''
        element_to_entries = self.__element_to_entries
        smallest = None
        for element in aset.distinct_elements():
            bucket = element_to_entries.get(element)
            if bucket is None:
                return []
            if smallest is None or len(bucket) < len(smallest):
                smallest = bucket
        if smallest is None:
            return []
        result = []
        s: PackedEntry
        for s in smallest:
            if aset.issubset(s):
                result.append(s)
        return result

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
            self.__key_to_entries.clear()
            self.__entry_to_key.clear()
            sets.add(aset)
            return
        if self.contains_subset_of(aset):
            return
        s: PackedEntry
        for s in self._supersets_of(aset):
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
        result = MinimalSetOfMultisets()
        result.__sets = self.__sets.copy()
        result.__element_to_entries = {element: bucket.copy() for element, bucket in self.__element_to_entries.items()}
        result.__key_to_entries = {key: bucket.copy() for key, bucket in self.__key_to_entries.items()}
        result.__entry_to_key = self.__entry_to_key.copy()
        return result

    def copy(self):
        'Returns a shallow copy of the collection.'
        return self.__copy__()

    def __or__(self, other: Self):
        result = self.copy()
        result.extend(other)
        return result
