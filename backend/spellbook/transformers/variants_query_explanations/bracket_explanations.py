from spellbook.models import Variant
from .base import QueryValue, Explanation, Predicate, BE, ValidationError, quoted

BRACKET_TAG_MAPPING = {label.lower(): label for label in Variant.BracketTag.labels}


def bracket_explanation(qv: QueryValue) -> Explanation:
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
        case ':' | '=' if value_is_digit:
            complement = f'in bracket {qv.value}'
        case '<' if value_is_digit:
            complement = f'in a bracket lower than {qv.value}'
        case '<=' if value_is_digit:
            complement = f'in bracket {qv.value} or lower'
        case '>' if value_is_digit:
            complement = f'in a bracket higher than {qv.value}'
        case '>=' if value_is_digit:
            complement = f'in bracket {qv.value} or higher'
        case ':' | '=' if bracket_tag:
            complement = f'tagged as {quoted(bracket_tag)}'
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for bracket search.')
    return Predicate(BE, complement)
