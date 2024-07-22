from .base import QueryValue, VariantFilter, VariantFilterCollection, Q, ValidationError


def popularity_filter(popularity_value: QueryValue) -> VariantFilterCollection:
    if not popularity_value.value.isdigit():
        raise ValidationError(f'Value {popularity_value.value} is not supported for popularity search.')
    match popularity_value.operator:
        case ':' | '=':
            q = Q(popularity=popularity_value.value)
        case '<':
            q = Q(popularity__lt=popularity_value.value)
        case '<=':
            q = Q(popularity__lte=popularity_value.value)
        case '>':
            q = Q(popularity__gt=popularity_value.value)
        case '>=':
            q = Q(popularity__gte=popularity_value.value)
        case _:
            raise ValidationError(f'Operator {popularity_value.operator} is not supported for popularity search.')
    return VariantFilterCollection(
        variants_filters=(
            VariantFilter(q=q, negated=popularity_value.is_negated()),
        ),
    )
