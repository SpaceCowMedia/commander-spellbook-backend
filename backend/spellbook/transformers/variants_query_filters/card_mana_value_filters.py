from spellbook.models import Card
from .base import QueryValue, VariantQuery, Q, ValidationError


def card_mana_value_filter(qv: QueryValue) -> VariantQuery:
    if not qv.is_numeric():
        raise ValidationError(f'Value {qv.value} is not supported for card mana value search.')
    match qv.operator:
        case ':' | '=':
            q = Q(mana_value=qv.value)
        case '<':
            q = Q(mana_value__lt=qv.value)
        case '<=':
            q = Q(mana_value__lte=qv.value)
        case '>':
            q = Q(mana_value__gt=qv.value)
        case '>=':
            q = Q(mana_value__gte=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card mana value search.')
    return qv.to_filter(q, Card)
