from typing import Iterable, Callable
from itertools import product, chain
from functools import reduce
from dataclasses import dataclass, replace
from multiset import FrozenMultiset
from .minimal_set_of_multisets import MinimalSetOfMultisets

cardid = int
templateid = int
Key = FrozenMultiset[int]


@dataclass(frozen=True)
class VariantSetParameters:
    max_depth: int | float = float('inf')
    allow_multiple_copies: bool = True
    filter: Key | None = None

    def _check_key(self, key: Key) -> bool:
        if not key:
            return False
        if len(key.distinct_elements()) > self.max_depth:
            return False
        cards_multiplicities = (q for c, q in key.items() if c > 0)
        if not self.allow_multiple_copies and any(q > 1 for q in cards_multiplicities):
            return False
        if self.filter is not None and not self.filter.issuperset(key):
            return False
        return True


class VariantSet:
    __slots__ = ('__parameters', '__sets')

    def __init__(self, parameters: VariantSetParameters | None = None, keys: Iterable[Key] = (), internal: 'MinimalSetOfMultisets[int] | None' = None):
        self.__parameters = parameters if parameters is not None else VariantSetParameters()
        self.__sets = internal if internal is not None else MinimalSetOfMultisets[int](k for k in keys if self.parameters._check_key(k))

    @property
    def parameters(self) -> VariantSetParameters:
        return self.__parameters

    @property
    def sets(self) -> MinimalSetOfMultisets[int]:
        return self.__sets

    @classmethod
    def ingredients_to_key(cls, cards: FrozenMultiset[cardid], templates: FrozenMultiset[templateid]) -> Key:
        return FrozenMultiset(dict(chain(((c_id, c_q) for c_id, c_q in cards.items()), ((-t_id, t_q) for t_id, t_q in templates.items()))))

    @classmethod
    def key_to_ingredients(cls, key: Key) -> tuple[FrozenMultiset[cardid], FrozenMultiset[templateid]]:
        cards = dict[cardid, int]()
        templates = dict[templateid, int]()
        for item, quantity in key.items():
            if item > 0:
                cards[item] = quantity
            else:
                templates[-item] = quantity
        return (FrozenMultiset(cards), FrozenMultiset(templates))

    def keys(self) -> Iterable[Key]:
        return self.sets

    def filter(self, key: Key) -> 'VariantSet':
        return VariantSet(parameters=replace(self.parameters, filter=key), internal=self.sets.subtree(key))

    def __str__(self) -> str:
        return str(self.sets)

    def __len__(self) -> int:
        return len(self.sets)

    def __or__(self, other: 'VariantSet'):
        assert self.parameters == other.parameters, "Cannot union VariantSets with different parameters"
        return VariantSet(parameters=self.parameters, internal=MinimalSetOfMultisets.union(self.sets, other.sets))

    def __and__(self, other: 'VariantSet'):
        assert self.parameters == other.parameters, "Cannot intersect VariantSets with different parameters"
        result = MinimalSetOfMultisets[int]()
        for left_key, right_key in product(self.keys(), other.keys()):
            key = left_key | right_key
            if not self.parameters._check_key(key):
                continue
            result.add(key)
        return VariantSet(parameters=self.parameters, internal=result)

    def __add__(self, other: 'VariantSet'):
        assert self.parameters == other.parameters, "Cannot sum VariantSets with different parameters"
        result = MinimalSetOfMultisets[int]()
        for left_key, right_key in product(self.keys(), other.keys()):
            key = left_key + right_key
            if not self.parameters._check_key(key):
                continue
            result.add(key)
        return VariantSet(parameters=self.parameters, internal=result)

    def variants(self) -> list[tuple[FrozenMultiset[cardid], FrozenMultiset[templateid]]]:
        return [self.key_to_ingredients(key) for key in self.keys()]

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
        result = MinimalSetOfMultisets[int]()
        for key_combination in product(*(s.keys() for s in sets)):
            # TODO: check performance gain
            cards_sets = [
                s
                for s in (
                    frozenset(c for c in key if c > 0)
                    for key in key_combination
                )
                if len(s) > 0
            ]
            if len(cards_sets) != len(set(cards_sets)):
                continue
            key = sum(key_combination, Key())
            if not parameters._check_key(key):
                continue
            result.add(key)
        return VariantSet(parameters=parameters, internal=result)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, VariantSet):
            return self.sets == other.sets and self.parameters == other.parameters
        return False
