from typing import Iterable, Callable, Self
from itertools import product, chain
from functools import reduce
from operator import add
from dataclasses import dataclass
from .multiset import FrozenMultiset
from .packed_entry import PackedEntry
from .minimal_set_of_multisets import MinimalSetOfMultisets

cardid = int
templateid = int
Entry = PackedEntry


@dataclass(frozen=True)
class VariantIngredients:
    cards: FrozenMultiset[cardid]
    templates: FrozenMultiset[templateid]


@dataclass(frozen=True)
class VariantSetParameters:
    max_depth: float = float('inf')
    allow_multiple_copies: bool = True
    filter: Entry | None = None

    def _check_entry(self, entry: Entry) -> bool:
        if not entry:
            return False
        if entry.distinct_count() > self.max_depth:
            return False
        if not self.allow_multiple_copies and entry.has_repeated_positive_elements():
            return False
        if self.filter is not None and not entry.issubset(self.filter):
            return False
        return True


class VariantSet:
    __slots__ = ('__parameters', '__sets')

    def __init__(self, parameters: VariantSetParameters | None = None, entries: Iterable[Entry] = (), _internal: MinimalSetOfMultisets | None = None):
        self.__parameters = parameters if parameters is not None else VariantSetParameters()
        self.__sets = _internal if _internal is not None else MinimalSetOfMultisets(e for e in entries if self.parameters._check_entry(e))

    @property
    def parameters(self) -> VariantSetParameters:
        return self.__parameters

    @property
    def sets(self) -> MinimalSetOfMultisets:
        return self.__sets

    @classmethod
    def ingredients_to_entry(cls, cards: FrozenMultiset[cardid], templates: FrozenMultiset[templateid]) -> Entry:
        return PackedEntry.from_items(chain(
            cards.items(),
            ((-template_id, quantity) for template_id, quantity in templates.items()),
        ))

    @classmethod
    def entry_to_ingredients(cls, entry: Entry) -> VariantIngredients:
        cards = dict[cardid, int]()
        templates = dict[templateid, int]()
        for item, quantity in entry.items():
            if item > 0:
                cards[item] = quantity
            else:
                templates[-item] = quantity
        return VariantIngredients(FrozenMultiset(cards), FrozenMultiset(templates))

    def entries(self) -> MinimalSetOfMultisets:
        return self.__sets

    def filter(self, entry: Entry):
        return self.__class__(
            parameters=VariantSetParameters(
                max_depth=self.__parameters.max_depth,
                allow_multiple_copies=self.__parameters.allow_multiple_copies,
                filter=entry,
            ),
            _internal=self.__sets.subtree(entry),
        )

    def __str__(self) -> str:
        return str(self.__sets)

    def __len__(self) -> int:
        return len(self.__sets)

    def has_same_parameters(self, other: 'VariantSet') -> bool:
        return self.__parameters is other.__parameters or self.__parameters == other.__parameters

    def __or__(self, other: 'VariantSet'):
        assert self.has_same_parameters(other), 'Cannot union VariantSets with different parameters'
        return self.__class__(parameters=self.__parameters, _internal=self.__sets | other.__sets)

    def __and__(self, other: 'VariantSet'):
        assert self.has_same_parameters(other), 'Cannot intersect VariantSets with different parameters'
        parameters = self.__parameters
        result: MinimalSetOfMultisets = MinimalSetOfMultisets()
        right_entries: list[PackedEntry] = list(other.__sets)
        left_entry: PackedEntry
        right_entry: PackedEntry
        entry: PackedEntry
        for left_entry in self.__sets:
            for right_entry in right_entries:
                entry = left_entry.union(right_entry)
                if parameters._check_entry(entry):
                    result.add(entry)
        return self.__class__(parameters=parameters, _internal=result)

    def __add__(self, other: 'VariantSet'):
        assert self.has_same_parameters(other), 'Cannot sum VariantSets with different parameters'
        parameters = self.__parameters
        result: MinimalSetOfMultisets = MinimalSetOfMultisets()
        right_entries: list[PackedEntry] = list(other.__sets)
        left_entry: PackedEntry
        right_entry: PackedEntry
        entry: PackedEntry
        for left_entry in self.__sets:
            for right_entry in right_entries:
                entry = left_entry.combine(right_entry)
                if parameters._check_entry(entry):
                    result.add(entry)
        return self.__class__(parameters=parameters, _internal=result)

    def implies(self, other: 'VariantSet') -> bool:
        '''Whether every variant of this set satisfies the other one too, each of its entries holding one of the other's.'''
        other_entries = other.entries()
        entry: PackedEntry
        for entry in self.entries():
            if not other_entries.contains_subset_of(entry):
                return False
        return True

    def variants(self) -> list[VariantIngredients]:
        return [self.entry_to_ingredients(e) for e in self.entries()]

    def firing_count(self, ingredients: VariantIngredients) -> int:
        '''How many times a combo with this variant set fires with the given ingredients: once for every copy they hold of each of its variants.'''
        count = 0
        for variant in self.variants():
            count_for_cards: int | None = ingredients.cards // variant.cards if variant.cards else None
            count_for_templates: int | None = ingredients.templates // variant.templates if variant.templates else None
            if count_for_cards is not None:
                if count_for_templates is not None:
                    count += min(count_for_cards, count_for_templates)
                else:
                    count += count_for_cards
            elif count_for_templates is not None:
                count += count_for_templates
        return count

    @classmethod
    def aggregate_sets(cls, sets: list[Self], strategy: Callable[[Self, Self], Self], parameters: VariantSetParameters | None = None):
        if len(sets) == 0:
            return cls(parameters=parameters)
        return reduce(strategy, sets)

    @classmethod
    def product_sets(cls, sets: list[Self], parameters: VariantSetParameters | None = None):
        parameters = parameters if parameters is not None else VariantSetParameters()
        if parameters.allow_multiple_copies:
            return cls.aggregate_sets(sets, strategy=add, parameters=parameters)
        if len(sets) == 0:
            return cls(parameters=parameters)
        result: MinimalSetOfMultisets = MinimalSetOfMultisets()
        entry: PackedEntry
        for key_combination in product(*(s.entries() for s in sets)):
            cards_sets = set()
            duplicated = False
            for entry in key_combination:
                card_set = frozenset(c for c in entry.distinct_elements() if c > 0)
                if card_set:
                    if card_set in cards_sets:
                        duplicated = True
                        break
                    cards_sets.add(card_set)
            if duplicated:
                continue
            entry = reduce(add, key_combination)
            if parameters._check_entry(entry):
                result.add(entry)
        return cls(parameters=parameters, _internal=result)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, VariantSet):
            return self.parameters == other.parameters and self.sets == other.sets
        return False
