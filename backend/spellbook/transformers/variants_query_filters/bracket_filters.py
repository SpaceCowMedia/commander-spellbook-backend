from spellbook.models import Variant
from ..query_parsing import compare
from .base import QueryValue, VariantQuery, Q, ValidationError


BRACKET_TAG_MAPPING = {label.lower(): value for value, label in Variant.BracketTag.choices}


def bracket_filter(qv: QueryValue) -> VariantQuery:
    value_is_digit = qv.is_numeric()
    bracket_tag = None
    if value_is_digit:
        if not (1 <= int(qv.value) <= 5):
            raise ValidationError(f'Value {qv.value} is not supported for bracket search. Choose a value between 1 and 5.')
    else:
        bracket_tag = BRACKET_TAG_MAPPING.get(qv.value.lower())
        if not bracket_tag:
            raise ValidationError(f'Value {qv.value} is not supported for bracket search. Choose one of the following: {", ".join(map(str, Variant.BracketTag.labels))}.')
    match qv.operator:
        case _ if value_is_digit:
            q = compare('bracket', qv.operator, int(qv.value))
        case ':' | '=' if bracket_tag:
            q = Q(bracket_tag=bracket_tag)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for bracket search.')
    return qv.to_filter(q)
