from typing import Iterable, Callable
from itertools import product, chain
from functools import reduce
from dataclasses import dataclass
from multiset import FrozenMultiset
from .minimal_set_of_multisets import MinimalSetOfMultisets

cardid = int
templateid = int


@dataclass(frozen=True)
class VariantSetParameters:
    max_depth: int | float = float('inf')
    allow_multiple_copies: bool = False


class VariantSet:
    def __init__(self, parameters: VariantSetParameters | None = None):
        self.sets = MinimalSetOfMultisets[int]()
        self.parameters = parameters if parameters is not None else VariantSetParameters()

    @classmethod
    def ingredients_to_key(cls, cards: FrozenMultiset[cardid], templates: FrozenMultiset[templateid]) -> FrozenMultiset[int]:
        return FrozenMultiset(dict(chain(((c_id, c_q) for c_id, c_q in cards.items()), ((-t_id, t_q) for t_id, t_q in templates.items()))))

    @classmethod
    def key_to_ingredients(cls, key: FrozenMultiset[int]) -> tuple[FrozenMultiset[cardid], FrozenMultiset[templateid]]:
        cards = dict[cardid, int]()
        templates = dict[templateid, int]()
        for item, quantity in key.items():
            if item > 0:
                cards[item] = quantity
            else:
                templates[-item] = quantity
        return (FrozenMultiset(cards), FrozenMultiset(templates))

    def filter(self, cards: FrozenMultiset[cardid], templates: FrozenMultiset[templateid]) -> 'VariantSet':
        result = VariantSet(parameters=self.parameters)
        for subset in self.sets.subsets_of(self.ingredients_to_key(cards, templates)):
            result._add(subset)
        return result

    def add(self, cards: FrozenMultiset[cardid], templates: FrozenMultiset[templateid]):
        base_key = self.ingredients_to_key(cards, templates)
        if len(base_key.distinct_elements()) > self.parameters.max_depth:
            return
        self._add(base_key)

    def _add(self, key: FrozenMultiset[int]):
        if len(key) == 0 or len(key.distinct_elements()) > self.parameters.max_depth:
            return
        self.sets.add(key)

    def is_satisfied_by(self, cards: FrozenMultiset[cardid], templates: FrozenMultiset[templateid]) -> bool:
        key = self.ingredients_to_key(cards, templates)
        if len(key.distinct_elements()) > self.parameters.max_depth:
            return False
        return self.sets.contains_subset_of(key)

    def satisfied_by(self, cards: FrozenMultiset[cardid], templates: FrozenMultiset[templateid]) -> list[tuple[FrozenMultiset[cardid], FrozenMultiset[templateid]]]:
        key = self.ingredients_to_key(cards, templates)
        if len(key.distinct_elements()) > self.parameters.max_depth:
            return []
        return [self.key_to_ingredients(subset) for subset in self.sets.subsets_of(key)]

    def __copy__(self) -> 'VariantSet':
        result = VariantSet(parameters=self.parameters)
        result.sets = self.sets.copy()
        return result

    def _keys(self) -> Iterable[FrozenMultiset[int]]:
        return self.sets

    def __str__(self) -> str:
        return str(self.sets)

    def __len__(self) -> int:
        return len(self.sets)

    def __or__(self, other: 'VariantSet'):
        result = self.copy()
        for key in other._keys():
            result._add(key)
        return result

    def __and__(self, other: 'VariantSet'):
        result = VariantSet(parameters=self.parameters)
        for left_key, right_key in product(self._keys(), other._keys()):
            key = left_key | right_key
            if len(key.distinct_elements()) > self.parameters.max_depth:
                continue
            result._add(key)
        return result

    def _check_if_multiset_contains_multiple_copies(self, key: FrozenMultiset[int]) -> bool:
        return any(key[item] > 1 for item in key if item > 0)

    def __add__(self, other: 'VariantSet'):
        result = VariantSet(parameters=self.parameters)
        for left_key, right_key in product(self._keys(), other._keys()):
            key = left_key + right_key
            if len(key.distinct_elements()) > self.parameters.max_depth:
                continue
            result._add(key)
        return result

    def variants(self) -> list[tuple[FrozenMultiset[cardid], FrozenMultiset[templateid]]]:
        return [self.key_to_ingredients(key) for key in self._keys()]

    def copy(self):
        return self.__copy__()

    @classmethod
    def or_sets(cls, sets: list['VariantSet'], parameters: VariantSetParameters | None = None) -> 'VariantSet':
        return VariantSet.aggregate_sets(sets, strategy=lambda x, y: x | y, parameters=parameters)

    @classmethod
    def and_sets(cls, sets: list['VariantSet'], parameters: VariantSetParameters | None = None) -> 'VariantSet':
        return VariantSet.aggregate_sets(sets, strategy=lambda x, y: x & y, parameters=parameters)

    @classmethod
    def sum_sets(cls, sets: list['VariantSet'], parameters: VariantSetParameters | None = None) -> 'VariantSet':
        return VariantSet.aggregate_sets(sets, strategy=lambda x, y: x + y, parameters=parameters)

    @classmethod
    def aggregate_sets(cls, sets: list['VariantSet'], strategy: Callable[['VariantSet', 'VariantSet'], 'VariantSet'], parameters: VariantSetParameters | None = None) -> 'VariantSet':
        match len(sets):
            case 0: return VariantSet(parameters=parameters)
            case _: return reduce(strategy, sets)

    @classmethod
    def product_sets(cls, sets: list['VariantSet'], parameters: VariantSetParameters | None = None) -> 'VariantSet':
        parameters = parameters if parameters is not None else VariantSetParameters()
        if parameters.allow_multiple_copies:
            return VariantSet.sum_sets(sets, parameters=parameters)
        result = VariantSet(parameters=parameters)
        for key_combination in product(*(s._keys() for s in sets)):
            cards_sets = [frozenset(c for c in key if c > 0) for key in key_combination]
            cards_sets = [s for s in cards_sets if len(s) > 0]
            if len(cards_sets) != len(set(cards_sets)):
                continue
            key = sum(key_combination, FrozenMultiset[int]())
            if len(key.distinct_elements()) > result.parameters.max_depth:
                continue
            result._add(key)
        return result

    def __eq__(self, other: object) -> bool:
        if isinstance(other, VariantSet):
            return self.sets == other.sets and self.parameters == other.parameters
        return False
