from typing import Self
from pygtrie import Trie
from itertools import product
from .list_utils import all_rotations, merge_sort_unique

cardid = int
templateid = int


DEFAULT_MAX_DEPTH = 100


class VariantTrie():
    def __init__(self, limit: int = DEFAULT_MAX_DEPTH):
        self.trie = Trie()
        self.max_depth = limit

    def ingredients_to_key(self, cards: list[cardid], templates: list[templateid]) -> list[str]:
        return merge_sort_unique([f'C{c_id}' for c_id in cards], [f'T{t_id}' for t_id in templates])

    def key_to_ingredients(self, key: list[str]) -> tuple[list[cardid], list[templateid]]:
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
        keys = all_rotations(base_key)
        self._add(keys)

    def _add(self, all_rotations: list[list[str]]):
        if len(all_rotations) == 0:
            return
        if any(len(r) > self.max_depth for r in all_rotations):
            return
        for key in all_rotations:
            prefix = self.trie.longest_prefix(key)
            if prefix.is_set:
                return
        for key in all_rotations:
            if self.trie.has_subtrie(key):
                for subkey in self.trie.keys(prefix=key):
                    for rotated_subkey in self.trie[subkey]:
                        del self.trie[rotated_subkey]
            self.trie[key] = all_rotations

    def __or__(self, other):
        result = VariantTrie(limit=self.max_depth)
        for value in self.trie.values() + other.trie.values():
            result._add(value)
        return result

    def __add__(self, other):
        return self.__or__(other)

    def __and__(self, other):
        result = VariantTrie(limit=self.max_depth)
        for left_part, right_part in product(self.trie.keys(), other.trie.keys()):
            key = merge_sort_unique(left_part, right_part)
            if len(key) > self.max_depth:
                continue
            result._add(all_rotations(key))
        return result

    def __mul__(self, other):
        return self.__and__(other)

    def variants(self, preserve=False) -> list[tuple[list[cardid], list[templateid]]]:
        result = list[tuple[list[cardid], list[templateid]]]()
        trie = self.trie.copy() if preserve else self.trie
        while len(trie) > 0:
            key, value = trie.popitem()
            cards, templates = self.key_to_ingredients(key)
            result.append((cards, templates))
            for rotation in value:
                if trie.has_key(rotation):
                    del trie[rotation]
        return result

    def __str__(self):
        return str(self.trie)

    @classmethod
    def or_tries(cls, tries: list[Self], limit: int = DEFAULT_MAX_DEPTH) -> Self:
        return VariantTrie.aggregate_tries(tries, limit=limit, strategy=lambda x, y: x | y)

    @classmethod
    def and_tries(cls, tries: list[Self], limit: int = DEFAULT_MAX_DEPTH) -> Self:
        return VariantTrie.aggregate_tries(tries, limit=limit, strategy=lambda x, y: x & y)

    @classmethod
    def aggregate_tries(cls, tries: list[Self], strategy, limit: int = DEFAULT_MAX_DEPTH) -> Self:
        match len(tries):
            case 0: return VariantTrie(limit=limit)
            case 1: return tries[0]
            case _:
                result = tries[0]
                for trie in tries[1:]:
                    result = strategy(result, trie)
                return result
