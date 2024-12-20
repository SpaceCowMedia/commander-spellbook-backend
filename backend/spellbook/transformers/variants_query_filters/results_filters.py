from .base import QueryValue, QueryFilter, Q, ValidationError, VariantFilterCollection


def results_filter(results_value: QueryValue) -> VariantFilterCollection:
    value_is_digit = results_value.value.isdigit()
    match results_value.operator:
        case ':' if not value_is_digit:
            return VariantFilterCollection(
                results_filters=(
                    QueryFilter(
                        q=Q(feature__name__icontains=results_value.value),
                        negated=results_value.is_negated(),
                    ),
                ),
            )
        case '=' if not value_is_digit:
            return VariantFilterCollection(
                results_filters=(
                    QueryFilter(
                        q=Q(feature__name__iexact=results_value.value),
                        negated=results_value.is_negated(),
                    ),
                ),
            )
        case '<' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    QueryFilter(
                        q=Q(result_count__lt=results_value.value),
                        negated=results_value.is_negated(),
                    ),
                ),
            )
        case '<=' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    QueryFilter(
                        q=Q(result_count__lte=results_value.value),
                        negated=results_value.is_negated(),
                    ),
                ),
            )
        case '>' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    QueryFilter(
                        q=Q(result_count__gt=results_value.value),
                        negated=results_value.is_negated(),
                    ),
                ),
            )
        case '>=' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    QueryFilter(
                        q=Q(result_count__gte=results_value.value),
                        negated=results_value.is_negated(),
                    ),
                ),
            )
        case ':' | '=' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    QueryFilter(
                        q=Q(result_count=results_value.value),
                        negated=results_value.is_negated(),
                    ),
                ),
            )
        case _:
            raise ValidationError(f'Operator {results_value.operator} is not supported for results search with {"numbers" if value_is_digit else "strings"}.')
