from typing import Iterable, Callable
from itertools import product, chain
from functools import reduce
from dataclasses import dataclass
from .multiset import FrozenMultiset
from .minimal_set_of_multisets import MinimalSetOfMultisets

cardid = int
templateid = int
Entry = FrozenMultiset[int]


@dataclass(frozen=True)
class VariantSetParameters:
    max_depth: int | float = float('inf')
    allow_multiple_copies: bool = True
    filter: Entry | None = None

    def _check_entry(self, entry: Entry) -> bool:
        if not entry:
            return False
        if len(entry.distinct_elements()) > self.max_depth:
            return False
        if not self.allow_multiple_copies and any(q > 1 for c, q in entry.items() if c > 0):
            return False
        if self.filter is not None and not self.filter.issuperset(entry):
            return False
        return True


class VariantSet:
    __slots__ = ('__parameters', '__sets')

    def __init__(self, parameters: VariantSetParameters | None = None, entries: Iterable[Entry] = (), _internal: MinimalSetOfMultisets[int] | None = None):
        self.__parameters = parameters if parameters is not None else VariantSetParameters()
        self.__sets = _internal if _internal is not None else MinimalSetOfMultisets[int](e for e in entries if self.parameters._check_entry(e))

    @property
    def parameters(self) -> VariantSetParameters:
        return self.__parameters

    @property
    def sets(self) -> MinimalSetOfMultisets[int]:
        return self.__sets

    @classmethod
    def ingredients_to_entry(cls, cards: FrozenMultiset[cardid], templates: FrozenMultiset[templateid]) -> Entry:
        return FrozenMultiset(dict(chain(((c_id, c_q) for c_id, c_q in cards.items()), ((-t_id, t_q) for t_id, t_q in templates.items()))))

    @classmethod
    def entry_to_ingredients(cls, entry: Entry) -> tuple[FrozenMultiset[cardid], FrozenMultiset[templateid]]:
        cards = dict[cardid, int]()
        templates = dict[templateid, int]()
        for item, quantity in entry.items():
            if item > 0:
                cards[item] = quantity
            else:
                templates[-item] = quantity
        return (FrozenMultiset(cards), FrozenMultiset(templates))

    def entries(self) -> Iterable[Entry]:
        return self.sets

    def filter(self, entry: Entry):
        return self.__class__(
            parameters=VariantSetParameters(
                max_depth=self.parameters.max_depth,
                allow_multiple_copies=self.parameters.allow_multiple_copies,
                filter=entry,
            ),
            _internal=self.sets.subtree(entry),
        )

    def __str__(self) -> str:
        return str(self.sets)

    def __len__(self) -> int:
        return len(self.sets)

    def __or__(self, other: 'VariantSet'):  # TODO: replace with Self from typing with pypy 3.11
        assert self.parameters == other.parameters, "Cannot union VariantSets with different parameters"
        return self.__class__(parameters=self.parameters, _internal=self.sets | other.sets)

    def __and__(self, other: 'VariantSet'):  # TODO: replace with Self from typing with pypy 3.11
        assert self.parameters == other.parameters, "Cannot intersect VariantSets with different parameters"
        result = MinimalSetOfMultisets[int]()
        for left_entry, right_entry in product(self.entries(), other.entries()):
            entry = left_entry | right_entry
            if not self.parameters._check_entry(entry):
                continue
            result.add(entry)
        return self.__class__(parameters=self.parameters, _internal=result)

    def __add__(self, other: 'VariantSet'):  # TODO: replace with Self from typing with pypy 3.11
        assert self.parameters == other.parameters, "Cannot sum VariantSets with different parameters"
        result = MinimalSetOfMultisets[int]()
        for left_key, right_key in product(self.entries(), other.entries()):
            entry = left_key + right_key
            if not self.parameters._check_entry(entry):
                continue
            result.add(entry)
        return self.__class__(parameters=self.parameters, _internal=result)

    def variants(self) -> list[tuple[FrozenMultiset[cardid], FrozenMultiset[templateid]]]:
        return [self.entry_to_ingredients(e) for e in self.entries()]

    @classmethod
    def or_sets(cls, sets: list['VariantSet'], parameters: VariantSetParameters | None = None):  # TODO: replace with Self from typing with pypy 3.11
        return cls.aggregate_sets(sets, strategy=lambda x, y: x | y, parameters=parameters)

    @classmethod
    def and_sets(cls, sets: list['VariantSet'], parameters: VariantSetParameters | None = None):  # TODO: replace with Self from typing with pypy 3.11
        return cls.aggregate_sets(sets, strategy=lambda x, y: x & y, parameters=parameters)

    @classmethod
    def sum_sets(cls, sets: list['VariantSet'], parameters: VariantSetParameters | None = None):  # TODO: replace with Self from typing with pypy 3.11
        return cls.aggregate_sets(sets, strategy=lambda x, y: x + y, parameters=parameters)

    @classmethod
    def aggregate_sets(cls, sets: list['VariantSet'], strategy: Callable[['VariantSet', 'VariantSet'], 'VariantSet'], parameters: VariantSetParameters | None = None):  # TODO: replace with Self from typing with pypy 3.11
        match len(sets):
            case 0: return cls(parameters=parameters)
            case _: return reduce(strategy, sets)

    @classmethod
    def product_sets(cls, sets: list['VariantSet'], parameters: VariantSetParameters | None = None):  # TODO: replace with Self from typing with pypy 3.11
        parameters = parameters if parameters is not None else VariantSetParameters()
        if parameters.allow_multiple_copies:
            return cls.sum_sets(sets, parameters=parameters)
        result = MinimalSetOfMultisets[int]()
        for key_combination in product(*(s.entries() for s in sets)):
            # TODO: check performance gain
            cards_sets = [
                s
                for s in (
                    frozenset(c for c in entry.distinct_elements() if c > 0)
                    for entry in key_combination
                )
                if len(s) > 0
            ]
            if len(cards_sets) != len(set(cards_sets)):
                continue
            entry = sum(key_combination, Entry())
            if not parameters._check_entry(entry):
                continue
            result.add(entry)
        return cls(parameters=parameters, _internal=result)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, VariantSet):
            return self.parameters == other.parameters and self.sets == other.sets
        return False
