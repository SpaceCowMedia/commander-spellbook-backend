from spellbook.models import Card
from .base import QueryValue, ENTITY, Explanation, USE, ValidationError, about, quoted


def card_oracle_explanation(qv: QueryValue) -> Explanation:
    match qv.operator:
        case ':':
            return about(qv, USE, Card, f'{ENTITY} with {quoted(qv.value)} in the oracle text')
        case '=':
            return about(qv, USE, Card, f'{ENTITY} with the exact oracle text {quoted(qv.value)}')
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card oracle search.')
