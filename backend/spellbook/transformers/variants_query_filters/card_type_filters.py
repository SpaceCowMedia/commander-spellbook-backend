from spellbook.models import Card
from .base import QueryValue, VariantQuery, Q, ValidationError


def card_type_filter(qv: QueryValue) -> VariantQuery:
    match qv.operator:
        case ':':
            q = Q(type_line__icontains=qv.value)
        case '=':
            q = Q(type_line__iexact=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card type search.')
    return qv.to_filter(q, Card)
