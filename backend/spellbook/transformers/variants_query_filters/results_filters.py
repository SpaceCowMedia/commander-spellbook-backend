from spellbook.models import FeatureProducedByVariant
from ..query_parsing import compare
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
        case _ if value_is_digit:
            return qv.to_filter(compare('result_count', qv.operator, int(qv.value)))
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for results search with {'numbers' if value_is_digit else 'strings'}.')
