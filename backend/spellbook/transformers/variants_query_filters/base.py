import re
from dataclasses import dataclass
from django.core.exceptions import ValidationError
from django.db.models import Q


@dataclass(frozen=True)
class QueryValue:
    prefix: str
    key: str
    operator: str
    value: str

    def is_for_all_related(self) -> bool:
        match self.prefix.lower():
            case '':
                return False
            case '@' | 'all-':
                return True
            case _:
                raise ValidationError(f'Prefix {self.prefix} is not supported for {self.key} search.')

    @classmethod
    def from_string(cls, string: str) -> 'QueryValue':
        match re.fullmatch(r'(?P<prefix>all-|@)?(?P<key>[a-zA-Z_]+)(?P<operator><=|>=|:|=|<|>)(?:"(?P<long_value>(?:[^"\\]|\\")+)"|(?P<short_value>.+))', string, re.IGNORECASE):
            case None:
                raise ValidationError(f'Invalid query value: {string}')
            case match:
                return cls(match['prefix'] or '', match['key'], match['operator'], match['long_value'] or match['short_value'])

    @classmethod
    def from_short_string(cls, string: str, key: str, operator: str) -> 'QueryValue':
        match re.fullmatch(r'"(?P<long_value>(?:[^"\\]|\\")+)"|(?P<short_value>.+)', string, re.IGNORECASE):
            case None:
                raise ValidationError(f'Invalid query value: {string}')
            case match:
                return cls('', key, operator, match['long_value'] or match['short_value'])

    def to_query_filter(self, q: Q) -> 'QueryFilter':
        if self.is_for_all_related():
            return QueryFilter(q=~q, negated=True)
        return QueryFilter(q=q)


@dataclass(frozen=True)
class QueryFilter:
    q: Q
    negated: bool = False
    negatable: bool = True


@dataclass(frozen=True)
class VariantFilterCollection:
    cards_filters: tuple[QueryFilter, ...] = ()
    templates_filters: tuple[QueryFilter, ...] = ()
    results_filters: tuple[QueryFilter, ...] = ()
    variants_filters: tuple[QueryFilter, ...] = ()

    def __invert__(self) -> 'VariantFilterCollection':
        return VariantFilterCollection(
            cards_filters=tuple(QueryFilter(q=qf.q, negated=not qf.negated if qf.negatable else qf.negated) for qf in self.cards_filters),
            templates_filters=tuple(QueryFilter(q=qf.q, negated=not qf.negated if qf.negatable else qf.negated) for qf in self.templates_filters),
            results_filters=tuple(QueryFilter(q=qf.q, negated=not qf.negated if qf.negatable else qf.negated) for qf in self.results_filters),
            variants_filters=tuple(QueryFilter(q=qf.q, negated=not qf.negated if qf.negatable else qf.negated) for qf in self.variants_filters),
        )

    def __and__(self, other: 'VariantFilterCollection') -> 'VariantFilterCollection':
        return VariantFilterCollection(
            cards_filters=self.cards_filters + other.cards_filters,
            templates_filters=self.templates_filters + other.templates_filters,
            results_filters=self.results_filters + other.results_filters,
            variants_filters=self.variants_filters + other.variants_filters
        )

    def __len__(self) -> int:
        return len(self.cards_filters) + len(self.templates_filters) + len(self.results_filters) + len(self.variants_filters)
