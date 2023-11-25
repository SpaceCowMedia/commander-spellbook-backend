from typing import TypeVar


T = TypeVar('T')


def list_of_tuples_of_lists_to_set(list_of_tuples_of_lists: list[tuple[list[T], ...]]) -> set[tuple[tuple[T, ...], ...]]:
    return set(tuple(tuple(x) for x in y) for y in list_of_tuples_of_lists)
