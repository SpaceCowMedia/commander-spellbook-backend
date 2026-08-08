from spellbook.models import Card
from .base import QueryValue, ENTITY, Explanation, USE, ValidationError, about, quoted


def card_type_explanation(qv: QueryValue) -> Explanation:
    match qv.operator:
        case ':':
            return about(qv, USE, Card, f'{ENTITY} with {quoted(qv.value)} in the type line')
        case '=':
            return about(qv, USE, Card, f'{ENTITY} with the exact type line {quoted(qv.value)}')
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card type search.')
