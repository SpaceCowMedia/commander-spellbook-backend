from .base import QueryValue, VariantFilterCollection, Q, ValidationError


def template_search_filter(qv: QueryValue) -> VariantFilterCollection:
    match qv.operator:
        case ':':
            q = Q(template__name__icontains=qv.value)
        case '=':
            q = Q(template__name__iexact=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for template search.')
    return VariantFilterCollection(templates_filters=(qv.to_query_filter(q),))
