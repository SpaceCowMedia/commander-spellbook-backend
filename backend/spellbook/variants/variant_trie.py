from pygtrie import Trie
from itertools import product
from ..models import Card, Template


def merge_sort(left: list, right: list) -> list:
    return sorted(set(left + right))


class VariantTrie():
    def __init__(self):
        self.trie = Trie()
        self.card_dict = dict[int, Card]()
        self.template_dict = dict[int, Template]()

    def ingredients_to_key(self, cards: list[Card], templates: list[Template]) -> list[str]:
        cards_ids = list[int]()
        templates_ids = list[int]()
        for card in cards:
            self.card_dict[card.id] = card
        for template in templates:
            templates_ids.append(template.id)
            self.template_dict[template.id] = template
        return merge_sort([f'C{c_id}' for c_id in cards_ids] + [f'T{t_id}' for t_id in templates_ids])

    def add(self, cards: list[Card], templates: list[Template]):
        key = self.ingredients_to_key(cards, templates)
        prefix = self.trie.longest_prefix(key)
        if prefix and self.trie.has_key(prefix.key):
            return
        if self.trie.has_subtrie(key):
            del self.trie[key:]
        self.trie[key] = []

    def __or__(self, other: 'VariantTrie') -> 'VariantTrie':
        trie = Trie()
        for key, value in self.trie.items() + other.trie.items():
            prefix = trie.longest_prefix(key)
            if prefix and trie.has_key(prefix.key):
                continue
            if trie.has_subtrie(key):
                del trie[key:]
            trie[key] = value
        result = VariantTrie()
        result.trie = trie
        result.card_dict = self.card_dict | other.card_dict
        result.template_dict = self.template_dict | other.template_dict
        return result

    def __add__(self, other: 'VariantTrie') -> 'VariantTrie':
        return self.__or__(other)

    def __and__(self, other: 'VariantTrie') -> 'VariantTrie':
        trie = Trie()
        for left_part, right_part in product(self.trie.keys(), other.trie.keys()):
            key = merge_sort(left_part, right_part)
            prefix = trie.longest_prefix(key)
            if prefix and trie.has_key(prefix.key):
                continue
            if trie.has_subtrie(key):
                del trie[key:]
            trie[key] = []
        result = VariantTrie()
        result.trie = trie
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


def or_tries(*tries: VariantTrie) -> VariantTrie:
    result = VariantTrie()
    for trie in tries:
        result |= trie
    return result


def and_tries(*tries: VariantTrie) -> VariantTrie:
    result = VariantTrie()
    for trie in tries:
        result &= trie
    return result
