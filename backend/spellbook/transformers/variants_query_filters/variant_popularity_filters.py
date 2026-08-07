from .base import QueryValue, VariantQuery, Q, ValidationError


def popularity_filter(qv: QueryValue) -> VariantQuery:
    if not qv.is_numeric():
        raise ValidationError(f'Value {qv.value} is not supported for popularity search.')
    match qv.operator:
        case ':' | '=':
            q = Q(popularity=qv.value)
        case '<':
            q = Q(popularity__lt=qv.value)
        case '<=':
            q = Q(popularity__lte=qv.value)
        case '>':
            q = Q(popularity__gt=qv.value)
        case '>=':
            q = Q(popularity__gte=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for popularity search.')
    return qv.to_filter(q)
