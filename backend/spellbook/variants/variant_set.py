from typing import Iterable, Callable
from itertools import product, combinations
from functools import reduce
from dataclasses import dataclass
from multiset import FrozenMultiset
from .minimal_set_of_multisets import MinimalSetOfMultisets

cardid = int
templateid = int


@dataclass
class _VariantSetParameters:
    max_depth: int | float
    allow_multiple_copies: bool


class VariantSet:
    def __init__(self, limit: int | float | None = None, allow_multiple_copies: bool = False, _parameters: _VariantSetParameters | None = None):
        self.sets = MinimalSetOfMultisets()
        if _parameters is not None:
            self.parameters = _parameters
        else:
            self.parameters = _VariantSetParameters(
                max_depth=limit if limit is not None else float('inf'),
                allow_multiple_copies=allow_multiple_copies
            )

    @classmethod
    def ingredients_to_key(cls, cards: FrozenMultiset, templates: FrozenMultiset) -> FrozenMultiset:
        return FrozenMultiset({f'C{c_id}': c_q for c_id, c_q in cards.items()} | {f'T{t_id}': t_q for t_id, t_q in templates.items()})

    @classmethod
    def key_to_ingredients(cls, key: FrozenMultiset) -> tuple[FrozenMultiset, FrozenMultiset]:
        cards = dict[cardid, int]()
        templates = dict[templateid, int]()
        for item, quantity in key.items():
            if item[0] == 'C':
                cards[int(item[1:])] = quantity
            elif item[0] == 'T':
                templates[int(item[1:])] = quantity
        return (FrozenMultiset(cards), FrozenMultiset(templates))

    def filter(self, cards: FrozenMultiset, templates: FrozenMultiset) -> 'VariantSet':
        result = VariantSet(_parameters=self.parameters)
        for subset in self.sets.subsets_of(self.ingredients_to_key(cards, templates)):
            result._add(subset)
        return result

    def add(self, cards: FrozenMultiset, templates: FrozenMultiset):
        base_key = self.ingredients_to_key(cards, templates)
        if len(base_key.distinct_elements()) > self.parameters.max_depth:
            return
        self._add(base_key)

    def _add(self, key: FrozenMultiset):
        if len(key) == 0 or len(key.distinct_elements()) > self.parameters.max_depth:
            return
        self.sets.add(key)

    def is_satisfied_by(self, cards: FrozenMultiset, templates: FrozenMultiset) -> bool:
        key = self.ingredients_to_key(cards, templates)
        if len(key.distinct_elements()) > self.parameters.max_depth:
            return False
        return self.sets.contains_subset_of(key)

    def satisfied_by(self, cards: FrozenMultiset, templates: FrozenMultiset) -> list[tuple[FrozenMultiset, FrozenMultiset]]:
        key = self.ingredients_to_key(cards, templates)
        if len(key.distinct_elements()) > self.parameters.max_depth:
            return []
        return [self.key_to_ingredients(subset) for subset in self.sets.subsets_of(key)]

    def __copy__(self) -> 'VariantSet':
        result = VariantSet(_parameters=self.parameters)
        result.sets = self.sets.copy()
        return result

    def _keys(self) -> Iterable[FrozenMultiset]:
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
        result = VariantSet(_parameters=self.parameters)
        left_keys = list(self._keys())
        right_keys = list(other._keys())
        for left_key, right_key in product(left_keys, right_keys):
            key = left_key | right_key
            if len(key.distinct_elements()) > self.parameters.max_depth:
                continue
            result._add(key)
        return result

    def _check_if_multiset_contains_multiple_copies(self, key: FrozenMultiset) -> bool:
        return any(key[item] > 1 for item in key if item[0] == 'C')

    def __add__(self, other: 'VariantSet'):
        result = VariantSet(_parameters=self.parameters)
        left_keys = list(self._keys())
        right_keys = list(other._keys())
        for left_key, right_key in product(left_keys, right_keys):
            key = left_key + right_key
            if len(key.distinct_elements()) > self.parameters.max_depth:
                continue
            result._add(key)
        return result

    def __pow__(self, power: int):
        if power < 0:
            raise ValueError('Exponent must be a non-negative integer.')
        if self.parameters.allow_multiple_copies:
            return self.sum_sets([self] * power, limit=self.parameters.max_depth, allow_multiple_copies=self.parameters.allow_multiple_copies)
        else:
            result = VariantSet(_parameters=self.parameters)
            keys = list(self._keys())
            for key_combination in product(*[keys] * power):
                cards_sets = [frozenset(c for c in key if c[0] == 'C') for key in key_combination]
                cards_sets = [s for s in cards_sets if len(s) > 0]
                if len(cards_sets) != len(set(cards_sets)):
                    continue
                key = sum(key_combination, FrozenMultiset())
                if len(key.distinct_elements()) > self.parameters.max_depth:
                    continue
                result._add(key)
            return result

    def variants(self) -> list[tuple[FrozenMultiset, FrozenMultiset]]:
        return [self.key_to_ingredients(key) for key in self._keys()]

    def copy(self):
        return self.__copy__()

    @classmethod
    def or_sets(cls, sets: list['VariantSet'], limit: int | float | None = None, allow_multiple_copies: bool = False) -> 'VariantSet':
        return VariantSet.aggregate_sets(sets, strategy=lambda x, y: x | y, limit=limit, allow_multiple_copies=allow_multiple_copies)

    @classmethod
    def and_sets(cls, sets: list['VariantSet'], limit: int | float | None = None, allow_multiple_copies: bool = False) -> 'VariantSet':
        return VariantSet.aggregate_sets(sets, strategy=lambda x, y: x & y, limit=limit, allow_multiple_copies=allow_multiple_copies)

    @classmethod
    def sum_sets(cls, sets: list['VariantSet'], limit: int | float | None = None, allow_multiple_copies: bool = False) -> 'VariantSet':
        return VariantSet.aggregate_sets(sets, strategy=lambda x, y: x + y, limit=limit, allow_multiple_copies=allow_multiple_copies)

    @classmethod
    def aggregate_sets(cls, sets: list['VariantSet'], strategy: Callable[['VariantSet', 'VariantSet'], 'VariantSet'], limit: int | float | None = None, allow_multiple_copies: bool = False) -> 'VariantSet':
        match len(sets):
            case 0: return VariantSet(limit=limit, allow_multiple_copies=allow_multiple_copies)
            case _: return reduce(strategy, sets)
