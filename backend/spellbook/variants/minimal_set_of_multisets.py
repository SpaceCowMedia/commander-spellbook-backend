from typing import Generator, Iterable, TypeVar, Generic, TYPE_CHECKING
from bisect import bisect_left
from multiset import FrozenMultiset, Multiset
from anytree import Node, RenderTree

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison
    _T = TypeVar('_T', bound=SupportsRichComparison)
else:
    _T = TypeVar('_T')


class MinimalSetOfMultisets(Generic[_T]):
    """
    A class representing a minimal set of sets.

    This class provides functionality to store and manipulate sets of elements.
    It ensures that the stored sets are minimal, meaning that no subset of another set
    in the collection is also present.
    """

    __slots__ = ('__tree', '__alphabet', '__count')
    __tree: Node
    __alphabet: list[_T]
    __count: int

    def __init__(self, sets: Iterable[FrozenMultiset[_T]] | None = None):
        """
        Initializes a new minimal set of sets.

        Args:
            sets (set[FrozenMultiset] | None): Optional initial sets to be added to the collection,
            discarding all sets that are supersets of other sets in the collection.
        """
        self.__count = 0
        self.__tree = Node(name=0)
        self.__alphabet = []
        if sets is not None:
            self.extend(sets)

    def __subtree_subsets_of(self, sequence: tuple[int, ...], index: int, node: Node) -> Generator[tuple[int, ...], None, None]:
        if sequence[index] < node.name:
            return
        if node.is_leaf and not node.is_root:
            yield ()
            return
        for child in node.children:
            for subset in self.__subtree_subsets_of(sequence, index + 1, child):
                yield (child.name, *subset)

    def subtree(self, under: FrozenMultiset[_T] | Multiset[_T]) -> 'MinimalSetOfMultisets[_T]':
        """
        Creates a new minimal set of sets containing all sets in the collection that are subsets of the given set.
        """
        return MinimalSetOfMultisets[_T](
            FrozenMultiset(
                {
                    self.__alphabet[i]: count
                    for i, count in enumerate(subset)
                    if count > 0
                }
            )
            for subset in self.__subtree_subsets_of(
                (0, *(under.get(x, 0) for x in self.__alphabet)),
                0,
                self.__tree,
            )
        )

    def __subtree_contains_subset_of(self, sequence: tuple[int, ...], index: int, node: Node) -> bool:
        if sequence[index] < node.name:
            return False
        if node.is_leaf and not node.is_root:
            return True
        return any(
            self.__subtree_contains_subset_of(sequence, index + 1, child)
            for child in node.children
        )

    def __contains_subset_of(self, aset: FrozenMultiset[_T] | Multiset[_T]) -> bool:
        return self.__subtree_contains_subset_of(
            (0, *(aset.get(x, 0) for x in self.__alphabet)),
            0,
            self.__tree,
        )

    def __subtree_remove_supersets_of(self, sequence: tuple[int, ...], index: int, node: Node) -> bool:
        if node.name < sequence[index]:
            return False
        if node.is_leaf:
            if node.is_root:
                return False
            node.parent = None
            self.__count -= 1
            return True
        if all(tuple(
            self.__subtree_remove_supersets_of(sequence, index + 1, child)
            for child in node.children
        )):
            node.parent = None
            return True
        return False

    def __remove_supersets_of(self, aset: FrozenMultiset[_T]):
        if any(x not in self.__alphabet for x in aset.distinct_elements()):
            return
        self.__subtree_remove_supersets_of(
            (0, *(aset.get(x, 0) for x in self.__alphabet)),
            0,
            self.__tree,
        )

    def __subtree_insert_level(self, depth: int, node: Node):
        if depth == 0:
            new_node = Node(name=0)
            for child in node.children:
                child.parent = new_node
            new_node.parent = node
            return
        for child in node.children:
            self.__subtree_insert_level(depth - 1, child)

    def __align_alphabet(self, seq: Iterable[_T]):
        for x in seq:
            i: int = bisect_left(self.__alphabet, x)
            if i == len(self.__alphabet) or self.__alphabet[i] != x:
                self.__alphabet.insert(i, x)
                if self.__count > 0:
                    self.__subtree_insert_level(i, self.__tree)

    def __subtree_insert(self, sequence: tuple[int, ...], index: int, node: Node):
        if index == len(sequence):
            self.__count += 1
            return
        q = sequence[index]
        for child in node.children:
            if child.name == q:
                self.__subtree_insert(sequence, index + 1, child)
                return
        new_node = Node(name=q, parent=node)
        self.__subtree_insert(sequence, index + 1, new_node)

    def __add(self, aset: FrozenMultiset[_T]):
        self.__align_alphabet(sorted(aset.distinct_elements(), reverse=True))
        self.__subtree_insert(
            tuple(aset.get(x, 0) for x in self.__alphabet),
            0,
            self.__tree,
        )

    def add(self, aset: FrozenMultiset[_T]):
        """
        Adds a set to the collection if it is not a superset of any set in the collection.
        If the set is a subset of any set in the collection, every superset of the set is removed,
        and the set is added to the collection.
        """
        if not self.__contains_subset_of(aset):
            self.__remove_supersets_of(aset)
            self.__add(aset)

    def extend(self, sets: Iterable[FrozenMultiset[_T]]):
        """
        Adds multiple sets to the collection, discarding all sets that are supersets of other sets in the collection.
        """
        for s in sets:
            self.add(s)

    def __iter__(self):
        return iter(
            FrozenMultiset(
                {
                    self.__alphabet[i - 1]: node.name
                    for i, node in enumerate(leaf.path)
                    if node.name > 0
                }
            )
            for leaf in self.__tree.leaves
            if not leaf.is_root
        )

    def __len__(self):
        return self.__count

    def __subtree_contains(self, sequence: tuple[int, ...], index: int, node: Node) -> bool:
        if sequence[index] != node.name:
            return False
        if node.is_leaf:
            return True
        return any(
            self.__subtree_contains(sequence, index + 1, child)
            for child in node.children
        )

    def __contains__(self, aset: FrozenMultiset[_T]):
        multiplicities = [0] * len(self.__alphabet)
        for key in aset.distinct_elements():
            i = bisect_left(self.__alphabet, key)
            if i == len(self.__alphabet) or self.__alphabet[i] != key:
                return False
            multiplicities[i] = aset[key]
        return self.__subtree_contains(
            (0, *multiplicities),
            0,
            self.__tree,
        )

    def __str__(self):
        return str(RenderTree(self.__tree))

    def __repr__(self):
        return f'MinimalSetOfMultisets({{#{self.__count}}}, alphabet={self.__alphabet})'

    def __eq__(self, other):
        if isinstance(other, MinimalSetOfMultisets):
            return self.__count == other.__count and set(self) == set(other)
        return False

    @classmethod
    def union(cls, a: 'MinimalSetOfMultisets[_T]', b: 'MinimalSetOfMultisets[_T]'):
        """
        Creates a new minimal set of sets containing all sets of the given collections,
        discarding all sets that are supersets of other sets in any of the collections.
        """
        # TODO: optimize
        result = MinimalSetOfMultisets[_T]()
        result.extend(a)
        result.extend(b)
        return result
