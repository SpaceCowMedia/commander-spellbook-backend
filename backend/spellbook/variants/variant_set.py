from typing import Iterable
from itertools import product
from multiset import FrozenMultiset
from django.conf import settings
from .minimal_set_of_multisets import MinimalSetOfMultisets

cardid = int
templateid = int


class VariantSet:
    def __init__(self, limit: int | float | None = None):
        self.sets = MinimalSetOfMultisets[str]()
        self.max_depth = limit if limit is not None else float('inf')

    @classmethod
    def ingredients_to_key(cls, cards: FrozenMultiset, templates: FrozenMultiset) -> FrozenMultiset:
        return FrozenMultiset(
            {f'C{c_id}': c_q for c_id, c_q in cards.items()} | {f'T{t_id}': t_q for t_id, t_q in templates.items()}
        )

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

    def add(self, cards: FrozenMultiset, templates: FrozenMultiset):
        base_key = self.ingredients_to_key(cards, templates)
        if len(base_key.distinct_elements()) > self.max_depth:
            return
        self._add(base_key)

    def _add(self, key: FrozenMultiset):
        if len(key) == 0 or len(key.distinct_elements()) > self.max_depth:
            return
        self.sets.add(key)

    def is_satisfied_by(self, cards: FrozenMultiset, templates: FrozenMultiset) -> bool:
        key = self.ingredients_to_key(cards, templates)
        if len(key.distinct_elements()) > self.max_depth:
            return False
        return self.sets.contains_subset_of(key)

    def satisfied_by(self, cards: FrozenMultiset, templates: FrozenMultiset) -> list[tuple[FrozenMultiset, FrozenMultiset]]:
        key = self.ingredients_to_key(cards, templates)
        if len(key.distinct_elements()) > self.max_depth:
            return []
        return [self.key_to_ingredients(subset) for subset in self.sets.subsets_of(key)]

    def __copy__(self) -> 'VariantSet':
        result = VariantSet(limit=self.max_depth)
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

    def __add__(self, other):
        return self.__or__(other)

    def __and__(self, other: 'VariantSet'):
        result = VariantSet(limit=self.max_depth)
        left_keys = list(self._keys())
        right_keys = list(other._keys())
        for left_key, right_key in product(left_keys, right_keys):
            key = left_key + right_key
            if len(key.distinct_elements()) > self.max_depth:
                continue
            result._add(key)
        return result

    def __mul__(self, other):
        return self.__and__(other)

    def __pow__(self, power: int):
        if not isinstance(power, int):
            raise ValueError('Exponent must be an integer.')
        if power < 0:
            raise ValueError('Exponent must be a non-negative integer.')
        if settings.SINGLETON_COMBO_MODE:
            result = VariantSet(limit=self.max_depth)
            keys = list(self._keys())
            for key_combinations in product(*[keys] * power):
                if len(key_combinations) == len(set(key_combinations)):
                    key = sum(key_combinations, FrozenMultiset())
                    if len(key.distinct_elements()) > self.max_depth:
                        continue
                    result._add(key)
            return result
        else:
            return self.and_sets([self] * power, limit=self.max_depth)

    def variants(self) -> list[tuple[FrozenMultiset, FrozenMultiset]]:
        result = list[tuple[FrozenMultiset, FrozenMultiset]]()
        for key in self._keys():
            cards, templates = self.key_to_ingredients(key)
            result.append((cards, templates))
        return result

    def copy(self):
        return self.__copy__()

    @classmethod
    def or_sets(cls, sets: list['VariantSet'], limit: int | float | None = None) -> 'VariantSet':
        return VariantSet.aggregate_sets(sets, limit=limit, strategy=lambda x, y: x | y)

    @classmethod
    def and_sets(cls, sets: list['VariantSet'], limit: int | float | None = None) -> 'VariantSet':
        return VariantSet.aggregate_sets(sets, limit=limit, strategy=lambda x, y: x & y)

    @classmethod
    def aggregate_sets(cls, sets: list['VariantSet'], strategy, limit: int | float | None = None) -> 'VariantSet':
        match len(sets):
            case 0: return VariantSet(limit=limit)
            case _:
                result = sets[0].copy()
                if limit is not None:
                    result.max_depth = limit
                for variant_set in sets[1:]:
                    result = strategy(result, variant_set)
                return result
