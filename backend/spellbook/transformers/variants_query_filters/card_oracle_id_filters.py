from uuid import UUID
from spellbook.models import Card
from .base import QueryValue, VariantQuery, Q, ValidationError


def card_oracle_id_filter(qv: QueryValue) -> VariantQuery:
    match qv.operator:
        case ':' | '=':
            try:
                oracle_id = UUID(qv.value)
            except ValueError:
                raise ValidationError(f'Value {qv.value} is not a valid oracle id.')
            return qv.to_filter(Q(oracle_id=oracle_id), Card)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card oracle id search.')
