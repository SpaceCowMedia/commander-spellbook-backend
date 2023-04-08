from itertools import product

cardid = int
templateid = int


DEFAULT_MAX_DEPTH = 100


class VariantTrie():
    def __init__(self, limit: int = DEFAULT_MAX_DEPTH):
        self.trie = object() # TODO: implement using settries
        self.max_depth = limit

    def ingredients_to_key(self, cards: list[cardid], templates: list[templateid]) -> frozenset[str]:
        return frozenset([f'C{c_id}' for c_id in cards] + [f'T{t_id}' for t_id in templates])

    def key_to_ingredients(self, key: frozenset[str]) -> tuple[list[cardid], list[templateid]]:
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
        raise NotImplementedError() # TODO: implement

    def is_satisfied_by(self, cards: list[cardid], templates: list[templateid]) -> bool:
        key = self.ingredients_to_key(cards, templates)
        if len(key) > self.max_depth:
            return False
        raise NotImplementedError() # TODO: implement

    def __copy__(self) -> 'VariantTrie':
        raise NotImplementedError() # TODO: implement

    def _keys(self) -> frozenset[frozenset[str]]:
        raise NotImplementedError() # TODO: implement

    def __str__(self) -> str:
        raise NotImplementedError() # TODO: implement

    def __len__(self) -> int:
        raise NotImplementedError() # TODO: implement

    def __or__(self, other: 'VariantTrie'):
        result = self.copy()
        for key in other._keys():
            result._add(key)
        return result

    def __add__(self, other):
        return self.__or__(other)

    def __and__(self, other: 'VariantTrie'):
        result = VariantTrie(limit=self.max_depth)
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
    def or_tries(cls, tries: list['VariantTrie'], limit: int = DEFAULT_MAX_DEPTH) -> 'VariantTrie':
        return VariantTrie.aggregate_tries(tries, limit=limit, strategy=lambda x, y: x | y)

    @classmethod
    def and_tries(cls, tries: list['VariantTrie'], limit: int = DEFAULT_MAX_DEPTH) -> 'VariantTrie':
        return VariantTrie.aggregate_tries(tries, limit=limit, strategy=lambda x, y: x & y)

    @classmethod
    def aggregate_tries(cls, tries: list['VariantTrie'], strategy, limit: int = DEFAULT_MAX_DEPTH) -> 'VariantTrie':
        match len(tries):
            case 0: return VariantTrie(limit=limit)
            case 1: return tries[0].copy()
            case _:
                result = tries[0]
                for trie in tries[1:]:
                    result = strategy(result, trie)
                return result
