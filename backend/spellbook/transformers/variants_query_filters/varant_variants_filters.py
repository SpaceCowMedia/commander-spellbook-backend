from .base import QueryValue, QueryFilter, VariantFilterCollection, Q, ValidationError


def variants_filter(variants_value: QueryValue) -> VariantFilterCollection:
    if not variants_value.value.isdigit():
        raise ValidationError(f'Value {variants_value.value} is not supported for variants search.')
    match variants_value.operator:
        case ':' | '=':
            q = Q(variant_count=variants_value.value)
        case '<':
            q = Q(variant_count__lt=variants_value.value)
        case '<=':
            q = Q(variant_count__lte=variants_value.value)
        case '>':
            q = Q(variant_count__gt=variants_value.value)
        case '>=':
            q = Q(variant_count__gte=variants_value.value)
        case _:
            raise ValidationError(f'Operator {variants_value.operator} is not supported for variants search.')
    return VariantFilterCollection(
        variants_filters=(
            QueryFilter(q=q, negated=variants_value.is_negated()),
        ),
    )
