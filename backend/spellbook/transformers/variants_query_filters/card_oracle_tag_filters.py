from spellbook.models import Card, oracle_tag_condition
from .base import QueryValue, VariantQuery, ValidationError


def card_oracle_tag_filter(qv: QueryValue) -> VariantQuery:
    match qv.operator:
        case ':':
            return qv.to_filter(oracle_tag_condition(qv.value), Card)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card oracle tag search.')
