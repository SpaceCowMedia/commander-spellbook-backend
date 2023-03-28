from pygtrie import Trie
from itertools import product, chain
from .list_utils import all_rotations, merge_sort_unique

cardid = int
templateid = int


DEFAULT_MAX_DEPTH = 100


class VariantTrie():
    def __init__(self, limit: int = DEFAULT_MAX_DEPTH):
        self.trie = Trie()
        self.shadow = Trie()
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
        self.shadow[all_rotations[0]] = all_rotations
        for key in all_rotations:
            if self.trie.has_subtrie(key):
                for subkey in self.trie.keys(prefix=key):
                    del self.shadow[self.trie[subkey][0]]
                    for rotated_subkey in self.trie[subkey]:
                        del self.trie[rotated_subkey]
            self.trie[key] = all_rotations

    def _keys(self) -> list[list[str]]:
        return self.shadow.keys()

    def _values(self) -> list[list[list[str]]]:
        return self.shadow.values()

    def __or__(self, other):
        result = VariantTrie(limit=self.max_depth)
        for value in chain(self._values(), other._values()):
            result._add(value)
        return result

    def __add__(self, other):
        return self.__or__(other)

    def __and__(self, other):
        result = VariantTrie(limit=self.max_depth)
        left_keys = list(self._keys())
        right_keys = list(other._keys())
        for left_key, right_key in product(left_keys, right_keys):
            key = merge_sort_unique(left_key, right_key)
            if len(key) > self.max_depth:
                continue
            result._add(all_rotations(key))
        return result

    def __mul__(self, other):
        return self.__and__(other)

    def variants(self) -> list[tuple[list[cardid], list[templateid]]]:
        result = list[tuple[list[cardid], list[templateid]]]()
        for key in self._keys():
            cards, templates = self.key_to_ingredients(key)
            result.append((sorted(cards), sorted(templates)))
        return result

    def __str__(self):
        return str(self.trie)

    def __len__(self):
        return len(self.trie)

    @classmethod
    def or_tries(cls, tries: list['VariantTrie'], limit: int = DEFAULT_MAX_DEPTH) -> 'VariantTrie':
        return VariantTrie.aggregate_tries(tries, limit=limit, strategy=lambda x, y: x | y)

    @classmethod
    def and_tries(cls, tries: list['VariantTrie'], limit: int = DEFAULT_MAX_DEPTH) -> 'VariantTrie':
        return VariantTrie.aggregate_tries(tries, limit=limit, strategy=lambda x, y: x & y)

    @classmethod
    def aggregate_tries(cls, tries: list['VariantTrie'], strategy, limit: int = DEFAULT_MAX_DEPTH) -> 'VariantTrie':
        match len(tries):
            case 0: return VariantTrie(limit=limit)
            case 1: return tries[0]
            case _:
                result = tries[0]
                for trie in tries[1:]:
                    result = strategy(result, trie)
                return result
