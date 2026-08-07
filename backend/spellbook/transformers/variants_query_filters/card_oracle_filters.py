from spellbook.models import Card
from .base import QueryValue, VariantQuery, Q, ValidationError


def card_oracle_filter(qv: QueryValue) -> VariantQuery:
    match qv.operator:
        case ':':
            q = Q(oracle_text__icontains=qv.value)
        case '=':
            q = Q(oracle_text__iexact=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card oracle search.')
    return qv.to_filter(q, Card)
