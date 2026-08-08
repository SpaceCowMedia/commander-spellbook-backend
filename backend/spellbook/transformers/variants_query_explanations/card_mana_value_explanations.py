from spellbook.models import Card
from .base import QueryValue, ENTITY, Explanation, USE, ValidationError, about, amount


def card_mana_value_explanation(qv: QueryValue) -> Explanation:
    if not qv.is_numeric():
        raise ValidationError(f'Value {qv.value} is not supported for card mana value search.')
    match qv.operator:
        case ':' | '=' | '<' | '<=' | '>' | '>=':
            return about(qv, USE, Card, f'{ENTITY} with mana value {amount(qv.operator, qv.value)}')
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card mana value search.')
