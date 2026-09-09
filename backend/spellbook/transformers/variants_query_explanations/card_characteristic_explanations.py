from spellbook.models import Card
from .base import QueryValue, ENTITY, Explanation, USE, ValidationError, about, amount


def characteristic_explanation(qv: QueryValue, label: str) -> Explanation:
    if not qv.is_numeric():
        raise ValidationError(f'Value {qv.value} is not supported for card {label} search.')
    match qv.operator:
        case ':' | '=' | '<' | '<=' | '>' | '>=':
            return about(qv, USE, Card, f'{ENTITY} with {label} {amount(qv.operator, qv.value)}')
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card {label} search.')


def card_power_explanation(qv: QueryValue) -> Explanation:
    return characteristic_explanation(qv, 'power')


def card_toughness_explanation(qv: QueryValue) -> Explanation:
    return characteristic_explanation(qv, 'toughness')


def card_loyalty_explanation(qv: QueryValue) -> Explanation:
    return characteristic_explanation(qv, 'loyalty')
