from .base import QueryValue, ENTITY, Explanation, Predicate, PRODUCE, ValidationError, about, count, quoted

RESULT = ('result', 'results')


def results_explanation(qv: QueryValue) -> Explanation:
    value_is_digit = qv.is_numeric()
    if value_is_digit and qv.is_for_all_related():
        raise ValidationError(f'Prefix {qv.prefix} is not supported for result search with numbers.')
    match qv.operator:
        case ':' if not value_is_digit:
            return about(qv, PRODUCE, RESULT, f'{ENTITY} with {quoted(qv.value)} in the name')
        case '=' if not value_is_digit:
            return about(qv, PRODUCE, RESULT, f'{ENTITY} named exactly {quoted(qv.value)}')
        case ':' | '=' | '<' | '<=' | '>' | '>=' if value_is_digit:
            return Predicate(PRODUCE, count(qv.operator, qv.value, *RESULT))
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for results search with {'numbers' if value_is_digit else 'strings'}.')
