from spellbook.models import Card
from spellbook.parsers.color_parser import parse_produced_mana
from ..scryfall_query_filters.card_filters import produced_mana_condition
from .base import QueryValue, VariantQuery, ValidationError


def card_produces_filter(qv: QueryValue) -> VariantQuery:
    '''The mana a card can produce, read the way a Scryfall search reads it.'''
    produced = parse_produced_mana(qv.value, qv.operator)
    if produced is None:
        raise ValidationError(f'Invalid color: {qv.value}')
    return qv.to_filter(produced_mana_condition(*produced), Card)
