from itertools import product
from .minimal_set_of_sets import MinimalSetOfSets

cardid = int
templateid = int


class VariantSet():
    def __init__(self, limit: int | float | None = None):
        self.sets = MinimalSetOfSets[str]()
        self.max_depth = limit if limit is not None else float('inf')

    @classmethod
    def ingredients_to_key(cls, cards: list[cardid], templates: list[templateid]) -> frozenset[str]:
        return frozenset([f'C{c_id}' for c_id in cards] + [f'T{t_id}' for t_id in templates])

    @classmethod
    def key_to_ingredients(cls, key: frozenset[str]) -> tuple[list[cardid], list[templateid]]:
        cards = list[cardid]()
        templates = list[templateid]()
        for item in key:
            if item[0] == 'C':
                cards.append(int(item[1:]))
            elif item[0] == 'T':
                templates.append(int(item[1:]))
        return (sorted(cards), sorted(templates))

    def add(self, cards: list[cardid], templates: list[templateid]):
        base_key = self.ingredients_to_key(cards, templates)
        if len(base_key) > self.max_depth:
            return
        self._add(base_key)

    def _add(self, key: frozenset[str]):
        if len(key) == 0 or len(key) > self.max_depth:
            return
        self.sets.add(key)

    def is_satisfied_by(self, cards: list[cardid], templates: list[templateid]) -> bool:
        key = self.ingredients_to_key(cards, templates)
        if len(key) > self.max_depth:
            return False
        return self.sets.contains_subset_of(key)

    def __copy__(self) -> 'VariantSet':
        result = VariantSet(limit=self.max_depth)
        result.sets = self.sets.copy()
        return result

    def _keys(self) -> frozenset[frozenset[str]]:
        return frozenset(self.sets)

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
            key = left_key | right_key
            if len(key) > self.max_depth:
                continue
            result._add(key)
        return result

    def __mul__(self, other):
        return self.__and__(other)

    def variants(self) -> list[tuple[list[cardid], list[templateid]]]:
        result = list[tuple[list[cardid], list[templateid]]]()
        for key in self._keys():
            cards, templates = self.key_to_ingredients(key)
            result.append((sorted(cards), sorted(templates)))
        return result

    def copy(self):
        return self.__copy__()

    @classmethod
    def or_sets(cls, sets: list['VariantSet'], limit: int | None = None) -> 'VariantSet':
        return VariantSet.aggregate_sets(sets, limit=limit, strategy=lambda x, y: x | y)

    @classmethod
    def and_sets(cls, sets: list['VariantSet'], limit: int | None = None) -> 'VariantSet':
        return VariantSet.aggregate_sets(sets, limit=limit, strategy=lambda x, y: x & y)

    @classmethod
    def aggregate_sets(cls, sets: list['VariantSet'], strategy, limit: int | None = None) -> 'VariantSet':
        match len(sets):
            case 0: return VariantSet(limit=limit)
            case _:
                result = sets[0].copy()
                if limit is not None:
                    result.max_depth = limit
                for variant_set in sets[1:]:
                    result = strategy(result, variant_set)
                return result
