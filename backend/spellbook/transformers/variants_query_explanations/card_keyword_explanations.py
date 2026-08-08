from spellbook.models import Card
from .base import QueryValue, ENTITY, Explanation, USE, ValidationError, about, quoted


def card_keyword_explanation(qv: QueryValue) -> Explanation:
    match qv.operator:
        case ':':
            return about(qv, USE, Card, f'{ENTITY} with the {quoted(qv.value)} keyword')
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card keyword search.')
