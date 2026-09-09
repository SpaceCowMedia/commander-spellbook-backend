from uuid import UUID
from spellbook.models import Card
from .base import QueryValue, ENTITY, Explanation, USE, ValidationError, about, quoted


def card_oracle_id_explanation(qv: QueryValue) -> Explanation:
    match qv.operator:
        case ':' | '=':
            try:
                UUID(qv.value)
            except ValueError:
                raise ValidationError(f'Value {qv.value} is not a valid oracle id.')
            return about(qv, USE, Card, f'{ENTITY} with oracle id {quoted(qv.value)}')
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card oracle id search.')
