from .base import QueryValue, Explanation, Predicate, BE, ValidationError, count


def popularity_explanation(qv: QueryValue) -> Explanation:
    if not qv.is_numeric():
        raise ValidationError(f'Value {qv.value} is not supported for popularity search.')
    match qv.operator:
        case ':' | '=' | '<' | '<=' | '>' | '>=':
            complement = f'in {count(qv.operator, qv.value, 'deck', 'decks')}'
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for popularity search.')
    return Predicate(BE, complement)
