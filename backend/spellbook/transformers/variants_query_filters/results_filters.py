from spellbook.models import FeatureProducedByVariant
from .base import QueryValue, VariantQuery, Q, ValidationError


def results_filter(qv: QueryValue) -> VariantQuery:
    value_is_digit = qv.is_numeric()
    if value_is_digit and qv.is_for_all_related():
        raise ValidationError(f'Prefix {qv.prefix} is not supported for result search with numbers.')
    match qv.operator:
        case ':' if not value_is_digit:
            return qv.to_filter(Q(feature__name__icontains=qv.value), FeatureProducedByVariant)
        case '=' if not value_is_digit:
            return qv.to_filter(Q(feature__name__iexact=qv.value), FeatureProducedByVariant)
        case '<' if value_is_digit:
            return qv.to_filter(Q(result_count__lt=qv.value))
        case '<=' if value_is_digit:
            return qv.to_filter(Q(result_count__lte=qv.value))
        case '>' if value_is_digit:
            return qv.to_filter(Q(result_count__gt=qv.value))
        case '>=' if value_is_digit:
            return qv.to_filter(Q(result_count__gte=qv.value))
        case ':' | '=' if value_is_digit:
            return qv.to_filter(Q(result_count=qv.value))
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for results search with {'numbers' if value_is_digit else 'strings'}.')
