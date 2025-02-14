from .base import QueryValue, QueryFilter, VariantFilterCollection, Q, ValidationError


def bracket_filter(bracket_value: QueryValue) -> VariantFilterCollection:
    if not bracket_value.value.isdigit():
        raise ValidationError(f'Value {bracket_value.value} is not supported for bracket search.')
    match bracket_value.operator:
        case ':' | '=':
            q = Q(bracket=bracket_value.value)
        case '<':
            q = Q(bracket__lt=bracket_value.value)
        case '<=':
            q = Q(bracket__lte=bracket_value.value)
        case '>':
            q = Q(bracket__gt=bracket_value.value)
        case '>=':
            q = Q(bracket__gte=bracket_value.value)
        case _:
            raise ValidationError(f'Operator {bracket_value.operator} is not supported for bracket search.')
    return VariantFilterCollection(
        variants_filters=(
            QueryFilter(q=q, negated=bracket_value.is_negated()),
        ),
    )
