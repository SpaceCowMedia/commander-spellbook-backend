from dataclasses import dataclass
from lark import Lark, Transformer
from django.core.exceptions import ValidationError
from django.db.models import Q
from spellbook.parsers.scryfall_query_grammar import SCRYFALL_GRAMMAR
from .query_parsing import parse_query
from .scryfall_query_filters.base import ScryfallValue, mana_filter
from .scryfall_query_filters.card_filters import (
    color_filter,
    is_filter,
    keyword_filter,
    name_filter,
    numeric_field_filter,
    oracle_filter,
    oracle_id_filter,
    oracle_tag_filter,
    produces_filter,
    type_filter,
)

COLOR_KEYS = {'c', 'color', 'id', 'identity'}
TYPE_KEYS = {'t', 'type'}
ORACLE_KEYS = {'o', 'oracle'}
KEYWORD_KEYS = {'keyword', 'kw'}
TAG_KEYS = {'otag', 'oracletag', 'function'}


@dataclass(frozen=True)
class ScryfallQuery:
    '''The condition a query names, beside the number of terms it was written out of.

    A term counts as one leaf whatever it comes down to: a colour or a mana cost expands into a handful
    of conditions, and an editor writing the query has no way of telling.'''
    q: Q
    leaves: int = 1


class ScryfallQueryTransformer(Transformer):
    '''Turns a Scryfall style query into the condition on a card that it names.'''

    def or_expression(self, values) -> ScryfallQuery:
        return ScryfallQuery(values[0].q | values[-1].q, values[0].leaves + values[-1].leaves)

    def and_expression(self, values) -> ScryfallQuery:
        return ScryfallQuery(values[0].q & values[-1].q, values[0].leaves + values[-1].leaves)

    def group(self, values) -> ScryfallQuery:
        return values[1]

    def negated_group(self, values) -> ScryfallQuery:
        return ScryfallQuery(~values[2].q, values[2].leaves)

    def negation(self, values) -> ScryfallQuery:
        return ScryfallQuery(~values[-1].q, values[-1].leaves)

    def exact_name(self, values) -> ScryfallQuery:
        return ScryfallQuery(name_filter(str(values[0])[1:-1]))

    def comparable_string_pair(self, values) -> ScryfallQuery:
        value = ScryfallValue.from_tokens(str(values[0]), str(values[1]), str(values[2]))
        if value.key in COLOR_KEYS:
            return ScryfallQuery(color_filter(value, 'color' if value.key in ('c', 'color') else 'identity'))
        if value.key == 'produces':
            return ScryfallQuery(produces_filter(value))
        raise value.unsupported()

    def uncomparable_string_pair(self, values) -> ScryfallQuery:
        value = ScryfallValue.from_tokens(str(values[0]), ':', str(values[1]))
        if value.key in TYPE_KEYS:
            return ScryfallQuery(type_filter(value))
        if value.key in ORACLE_KEYS:
            return ScryfallQuery(oracle_filter(value))
        if value.key in KEYWORD_KEYS:
            return ScryfallQuery(keyword_filter(value))
        if value.key in TAG_KEYS:
            return ScryfallQuery(oracle_tag_filter(value))
        if value.key in ('is', 'has'):
            return ScryfallQuery(is_filter(value))
        if value.key == 'oracleid':
            return ScryfallQuery(oracle_id_filter(value))
        raise value.unsupported()

    def numeric_pair(self, values) -> ScryfallQuery:
        return ScryfallQuery(numeric_field_filter(ScryfallValue.from_tokens(str(values[0]), str(values[1]), str(values[2]))))

    def mana_pair(self, values) -> ScryfallQuery:
        operator = str(values[1])
        cost = values[2]
        # a cost is written either as symbols or as a bare number, which names that much generic mana
        symbols = [str(symbol) for symbol in cost.children] if hasattr(cost, 'children') else [f'{{{cost}}}']
        return ScryfallQuery(mana_filter(symbols, operator))

    def start(self, values) -> ScryfallQuery:
        return values[0] if values else ScryfallQuery(Q(), 0)


PARSER = Lark(SCRYFALL_GRAMMAR, parser='lalr', transformer=ScryfallQueryTransformer())


def scryfall_query_parser(query_string: str, max_terms: int | None = None) -> Q:
    '''The cards a Scryfall style query names, as a condition on Card.

    No legality is implied: what a template means by its query and what a search means by one differ,
    so each caller adds the one its own context asks for. A caller taking the query from whoever is
    asking passes the number of terms it is willing to read.'''
    query: ScryfallQuery = parse_query(PARSER, query_string)
    if max_terms is not None and query.leaves > max_terms:
        raise ValidationError('Too many search parameters.')
    return query.q
