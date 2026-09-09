from spellbook.models import Card
from ..query_parsing import compare
from .base import QueryValue, VariantQuery, Q, ValidationError


def characteristic_filter(qv: QueryValue, field: str, label: str) -> VariantQuery:
    '''A printed characteristic compared to a number, over the cards that print one at all.

    A card printing a star instead of a number leaves the column null, so it fails every comparison,
    and an all- prefixed term therefore rejects a variant that uses one.'''
    if not qv.is_numeric():
        raise ValidationError(f'Value {qv.value} is not supported for card {label} search.')
    q = compare(field, qv.operator, int(qv.value))
    if qv.is_for_all_related():
        # an all- prefixed term becomes the negation of this one, and negating a comparison against
        # null yields null rather than a match, so the null has to be spelled out to reject the card
        q &= Q(**{f'{field}__isnull': False})
    return qv.to_filter(q, Card)


def card_power_filter(qv: QueryValue) -> VariantQuery:
    return characteristic_filter(qv, 'power_value', 'power')


def card_toughness_filter(qv: QueryValue) -> VariantQuery:
    return characteristic_filter(qv, 'toughness_value', 'toughness')


def card_loyalty_filter(qv: QueryValue) -> VariantQuery:
    return characteristic_filter(qv, 'loyalty_value', 'loyalty')
