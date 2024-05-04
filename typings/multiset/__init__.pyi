from typing import TypeVar, Generic, Iterable, Any, Set, FrozenSet, Self, Iterator


T = TypeVar('T', default=Any)


class BaseMultiset(Generic[T], Iterable[T]):

    def __init__(self, iterable: Iterable[T] = ...) -> None:
        ...

    def __new__(cls, iterable: Iterable[T] = ...):
        ...

    def __contains__(self, element: T) -> bool:
        ...

    def __getitem__(self, element: T) -> int:
        ...

    def __len__(self) -> int:
        ...

    def __bool__(self) -> bool:
        ...

    def __iter__(self) -> Iterator[T]:
        ...

    def isdisjoint(self, other: Iterable[T]) -> bool:
        ...

    def difference(self, *others: Iterable[T]) -> Self:
        ...

    def __sub__(self, other: 'BaseMultiset[T]' | Set[T] | FrozenSet[T]) -> Self:
        ...

    def __rsub__(self, other: 'BaseMultiset[T]' | Set[T] | FrozenSet[T]) -> Self:
        ...

    def union(self, *others: Iterable[T]) -> Self:
        ...

    def __or__(self, other: 'BaseMultiset[T]' | Set[T] | FrozenSet[T]) -> Self:
        ...

    __ror__ = __or__

    def combine(self, *others: Iterable[T]) -> Self:
        ...

    def __add__(self, other: 'BaseMultiset[T]' | Set[T] | FrozenSet[T]) -> Self:
        ...

    __radd__ = __add__

    def intersection(self, *others: Iterable[T]) -> Self:
        ...

    def __and__(self, other: 'BaseMultiset[T]' | Set[T] | FrozenSet[T]) -> Self:
        ...

    __rand__ = __and__

    def symmetric_difference(self, other: Iterable[T]) -> Self:
        ...

    def __xor__(self, other: 'BaseMultiset[T]' | Set[T] | FrozenSet[T]) -> Self:
        ...

    __rxor__ = __xor__

    def times(self, factor: int) -> Self:
        ...

    def __mul__(self, factor: int) -> Self:
        ...

    __rmul__ = __mul__

    def issubset(self, other: Iterable[T]) -> bool:
        ...

    def __le__(self, other: 'BaseMultiset[T]' | Set[T] | FrozenSet[T]) -> bool:
        ...

    def __lt__(self, other: 'BaseMultiset[T]' | Set[T] | FrozenSet[T]) -> bool:
        ...

    def issuperset(self, other: Iterable[T]) -> bool:
        ...

    def __ge__(self, other: 'BaseMultiset[T]' | Set[T] | FrozenSet[T]) -> bool:
        ...

    def __gt__(self, other: 'BaseMultiset[T]' | Set[T] | FrozenSet[T]) -> bool:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def __ne__(self, other: object) -> bool:
        ...

    def get(self, element: T, default: int) -> int:
        ...

    @classmethod
    def from_elements(cls, elements: Iterable[T], multiplicity: int) -> Self:
        ...

    def copy(self) -> Self:
        ...

    __copy__ = copy

    def items(self) -> Iterable[tuple[T, int]]:
        ...

    def distinct_elements(self) -> set[T]:
        ...

    def multiplicities(self) -> list[int]:
        ...

    values = multiplicities


class Multiset(BaseMultiset[T]):

    def __setitem__(self, element: T, multiplicity: int) -> None:
        ...

    def __delitem__(self, element: T) -> None:
        ...

    def update(self, *others: Iterable[T], **kwargs: int) -> None:
        ...

    def union_update(self, *others: Iterable[T]) -> None:
        ...

    def __ior__(self, other: 'Multiset[T]' | Set[T] | FrozenSet[T]) -> None:
        ...

    def intersection_update(self, *others: Iterable[T]) -> None:
        ...

    def __iand__(self, other: 'Multiset[T]' | Set[T] | FrozenSet[T]) -> None:
        ...

    def difference_update(self, *others: Iterable[T]) -> None:
        ...

    def __isub__(self, other: 'Multiset[T]' | Set[T] | FrozenSet[T]) -> None:
        ...

    def symmetric_difference_update(self, other: Iterable[T]) -> None:
        ...

    def __ixor__(self, other: 'Multiset[T]' | Set[T] | FrozenSet[T]) -> None:
        ...

    def times_update(self, factor: int) -> None:
        ...

    def __imul__(self, factor: int) -> None:
        ...

    def add(self, element: T, multiplicity: int = ...) -> None:
        ...

    def remove(self, element: T, multiplicity: int | None = ...) -> None:
        ...

    def discard(self, element: T, multiplicity: int | None = ...) -> None:
        ...

    def pop(self, element: T, default: int) -> int:
        ...

    def setdefault(self, element: T, default: int) -> int:
        ...

    def clear(self) -> None:
        ...


class FrozenMultiset(BaseMultiset[T]):
    def __hash__(self) -> int:
        ...
