from pygtrie import Trie
from itertools import product
from ..models import Card, Template


DEFAULT_MAX_DEPTH = 100


def rotate(li: list, x: int) -> list:
  return li[-x % len(li):] + li[:-x % len(li)]


def all_rotations(li: list) -> list[list]:
    return [rotate(li, x) for x in range(len(li))]


def merge_sort(left: list, right: list) -> list:
    return sorted(set(left + right))


class VariantTrie():
    def __init__(self, limit: int = DEFAULT_MAX_DEPTH):
        self.trie = Trie()
        self.card_dict = dict[int, Card]()
        self.template_dict = dict[int, Template]()
        self.max_depth = limit

    def ingredients_to_key(self, cards: list[Card], templates: list[Template]) -> list[str]:
        cards_ids = list[int]()
        templates_ids = list[int]()
        for card in cards:
            self.card_dict[card.id] = card
            cards_ids.append(card.id)
        for template in templates:
            self.template_dict[template.id] = template
            templates_ids.append(template.id)
        return merge_sort([f'C{c_id}' for c_id in cards_ids], [f'T{t_id}' for t_id in templates_ids])

    def add(self, cards: list[Card], templates: list[Template]):
        base_key = self.ingredients_to_key(cards, templates)
        if len(base_key) > self.max_depth:
            return
        keys = all_rotations(base_key)
        self._add(base_key, keys)
        
    
    def _add(self, key: list[str], all_rotations: list[list[str]]):
        if len(key) > self.max_depth:
            return
        for key in all_rotations:
            prefix = self.trie.longest_prefix(key)
            if prefix and self.trie.has_key(prefix.key):
                return
        for key in all_rotations:
            if self.trie.has_subtrie(key):
                for subkey in self.trie.keys(prefix=key):
                    for rotated_subkey in self.trie[subkey]:
                        del self.trie[rotated_subkey]
            self.trie[key] = all_rotations

    def __or__(self, other: 'VariantTrie') -> 'VariantTrie':
        result = VariantTrie(limit=self.max_depth)
        for key, value in self.trie.items() + other.trie.items():
            result._add(key, value)
        result.card_dict = self.card_dict | other.card_dict
        result.template_dict = self.template_dict | other.template_dict
        return result

    def __add__(self, other: 'VariantTrie') -> 'VariantTrie':
        return self.__or__(other)

    def __and__(self, other: 'VariantTrie') -> 'VariantTrie':
        result = VariantTrie(limit=self.max_depth)
        for left_part, right_part in product(self.trie.keys(), other.trie.keys()):
            key = merge_sort(left_part, right_part)
            if len(key) > self.max_depth:
                continue
            result._add(key, all_rotations(key))
        result.card_dict = self.card_dict | other.card_dict
        result.template_dict = self.template_dict | other.template_dict
        return result

    def __mul__(self, other: 'VariantTrie') -> 'VariantTrie':
        return self.__and__(other)

    def variants(self) -> list[tuple[list[Card], list[Template]]]:
        result = list[tuple[list[Card], list[Template]]]()
        for key in self.trie.keys():
            cards = list[Card]()
            templates = list[Template]()
            for item in key:
                if item[0] == 'C':
                    cards.append(self.card_dict[int(item[1:])])
                elif item[0] == 'T':
                    templates.append(self.template_dict[int(item[1:])])
            result.append((cards, templates))
        return result

    def __str__(self):
        return str(self.trie)


def or_tries(tries: list[VariantTrie], limit: int = DEFAULT_MAX_DEPTH) -> VariantTrie:
    return aggregate_tries(tries, limit=limit, strategy=lambda x, y: x | y)


def and_tries(tries: list[VariantTrie], limit: int = DEFAULT_MAX_DEPTH) -> VariantTrie:
    return aggregate_tries(tries, limit=limit, strategy=lambda x, y: x & y)


def aggregate_tries(tries: list[VariantTrie], strategy, limit: int = DEFAULT_MAX_DEPTH) -> VariantTrie:
    match len(tries):
        case 0: return VariantTrie(limit=limit)
        case 1: return tries[0]
        case _:
            result = tries[0]
            for trie in tries[1:]:
                result = strategy(result, trie)
            return result
