from .base import QueryValue, VariantFilterCollection, Q, ValidationError


def popularity_filter(qv: QueryValue) -> VariantFilterCollection:
    if not qv.value.isdigit():
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
    return VariantFilterCollection(variants_filters=(qv.to_query_filter(q),))
