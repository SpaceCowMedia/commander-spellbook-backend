from spellbook.models import Variant
from .base import QueryValue, VariantFilterCollection, Q, ValidationError


BRACKET_TAG_MAPPING = {label.lower(): value for value, label in Variant.BracketTag.choices}


def bracket_filter(qv: QueryValue) -> VariantFilterCollection:
    value_is_digit = qv.is_numeric()
    bracket_tag = None
    if value_is_digit:
        if not (1 <= int(qv.value) <= 5):
            raise ValidationError(f'Value {qv.value} is not supported for bracket search. Choose a value between 1 and 5.')
    else:
        bracket_tag = BRACKET_TAG_MAPPING.get(qv.value.lower())
        if not bracket_tag:
            raise ValidationError(f'Value {qv.value} is not supported for bracket search. Choose one of the following: {", ".join(Variant.BracketTag.labels)}.')
    match qv.operator:
        case ':' | '=' if value_is_digit:
            q = Q(bracket=qv.value)
        case '<' if value_is_digit:
            q = Q(bracket__lt=qv.value)
        case '<=' if value_is_digit:
            q = Q(bracket__lte=qv.value)
        case '>' if value_is_digit:
            q = Q(bracket__gt=qv.value)
        case '>=' if value_is_digit:
            q = Q(bracket__gte=qv.value)
        case ':' | '=' if bracket_tag:
            q = Q(bracket_tag_override=bracket_tag) | Q(bracket_tag_override=None, bracket_tag=bracket_tag)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for bracket search.')
    return VariantFilterCollection(variants_filters=(qv.to_query_filter(q),))
