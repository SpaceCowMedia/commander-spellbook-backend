from .base import QueryValue, VariantFilterCollection, Q, ValidationError


def variants_filter(qv: QueryValue) -> VariantFilterCollection:
    if not qv.value.isdigit():
        raise ValidationError(f'Value {qv.value} is not supported for variants search.')
    match qv.operator:
        case ':' | '=':
            q = Q(variant_count=qv.value)
        case '<':
            q = Q(variant_count__lt=qv.value)
        case '<=':
            q = Q(variant_count__lte=qv.value)
        case '>':
            q = Q(variant_count__gt=qv.value)
        case '>=':
            q = Q(variant_count__gte=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for variants search.')
    return VariantFilterCollection(variants_filters=(qv.to_query_filter(q),))
