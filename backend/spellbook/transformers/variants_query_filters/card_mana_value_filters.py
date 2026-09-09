from spellbook.models import Card
from ..query_parsing import compare
from .base import QueryValue, VariantQuery, ValidationError


def card_mana_value_filter(qv: QueryValue) -> VariantQuery:
    if not qv.is_numeric():
        raise ValidationError(f'Value {qv.value} is not supported for card mana value search.')
    return qv.to_filter(compare('mana_value', qv.operator, int(qv.value)), Card)
