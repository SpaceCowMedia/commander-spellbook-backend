from spellbook.models import Card
from .base import QueryValue, ENTITY, Explanation, USE, ValidationError, about, quoted


def card_oracle_tag_explanation(qv: QueryValue) -> Explanation:
    match qv.operator:
        case ':':
            return about(qv, USE, Card, f'{ENTITY} tagged {quoted(qv.value)} on Scryfall')
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card oracle tag search.')
