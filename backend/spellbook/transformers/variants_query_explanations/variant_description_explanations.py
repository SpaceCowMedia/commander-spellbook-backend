from .base import QueryValue, Explanation, Predicate, HAVE, ValidationError, count, quoted


def description_explanation(qv: QueryValue) -> Explanation:
    value_is_digit = qv.is_numeric()
    match qv.operator:
        case ':' if not value_is_digit:
            complement = f'a description containing {quoted(qv.value)}'
        case '=' if not value_is_digit:
            complement = f'a description that is exactly {quoted(qv.value)}'
        case ':' | '=' | '<' | '<=' | '>' | '>=' if value_is_digit:
            complement = count(qv.operator, qv.value, 'step', 'steps')
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for prerequisites search.')
    return Predicate(HAVE, complement)
