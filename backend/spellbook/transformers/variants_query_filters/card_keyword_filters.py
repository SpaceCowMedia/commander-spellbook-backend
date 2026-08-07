from spellbook.models import Card
from .base import QueryValue, VariantQuery, Q, ValidationError


def card_keyword_filter(qv: QueryValue) -> VariantQuery:
    match qv.operator:
        case ':':
            q = Q(keywords__icontains=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card keyword search.')
    return qv.to_filter(q, Card)
