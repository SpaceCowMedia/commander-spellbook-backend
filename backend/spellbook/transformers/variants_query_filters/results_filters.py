from .base import QueryValue, Q, ValidationError, VariantFilterCollection


def results_filter(qv: QueryValue) -> VariantFilterCollection:
    value_is_digit = qv.value.isdigit()
    if value_is_digit and qv.is_for_all_related():
        raise ValidationError(f'Prefix {qv.prefix} is not supported for result search with numbers.')
    match qv.operator:
        case ':' if not value_is_digit:
            return VariantFilterCollection(results_filters=(qv.to_query_filter(
                Q(feature__name__icontains=qv.value),
            ),))
        case '=' if not value_is_digit:
            return VariantFilterCollection(results_filters=(qv.to_query_filter(
                Q(feature__name__iexact=qv.value),
            ),))
        case '<' if value_is_digit:
            return VariantFilterCollection(variants_filters=(qv.to_query_filter(
                Q(result_count__lt=qv.value),
            ),))
        case '<=' if value_is_digit:
            return VariantFilterCollection(variants_filters=(qv.to_query_filter(
                Q(result_count__lte=qv.value),
            ),))
        case '>' if value_is_digit:
            return VariantFilterCollection(variants_filters=(qv.to_query_filter(
                Q(result_count__gt=qv.value),
            ),))
        case '>=' if value_is_digit:
            return VariantFilterCollection(variants_filters=(qv.to_query_filter(
                Q(result_count__gte=qv.value),
            ),))
        case ':' | '=' if value_is_digit:
            return VariantFilterCollection(variants_filters=(qv.to_query_filter(
                Q(result_count=qv.value),
            ),))
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for results search with {"numbers" if value_is_digit else "strings"}.')
