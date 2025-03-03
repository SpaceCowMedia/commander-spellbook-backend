from .base import QueryValue, VariantFilterCollection, Q, ValidationError


def bracket_filter(qv: QueryValue) -> VariantFilterCollection:
    if not qv.value.isdigit():
        raise ValidationError(f'Value {qv.value} is not supported for bracket search.')
    if not (1 <= int(qv.value) <= 5):
        raise ValidationError(f'Value {qv.value} is not supported for bracket search. Choose a value between 1 and 5.')
    match qv.operator:
        case ':' | '=':
            q = Q(bracket=qv.value)
        case '<':
            q = Q(bracket__lt=qv.value)
        case '<=':
            q = Q(bracket__lte=qv.value)
        case '>':
            q = Q(bracket__gt=qv.value)
        case '>=':
            q = Q(bracket__gte=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for bracket search.')
    return VariantFilterCollection(variants_filters=(qv.to_query_filter(q),))
