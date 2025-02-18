from .base import QueryValue, QueryFilter, VariantFilterCollection, Q, ValidationError


def template_search_filter(search_value: QueryValue) -> VariantFilterCollection:
    match search_value.operator:
        case ':':
            q = Q(template__name__icontains=search_value.value)
        case '=':
            q = Q(template__name__iexact=search_value.value)
        case _:
            raise ValidationError(f'Operator {search_value.operator} is not supported for template search.')
    return VariantFilterCollection(
        templates_filters=(
            QueryFilter(
                q=q,
                negated=search_value.is_negated(),
            ),
        ),
    )
