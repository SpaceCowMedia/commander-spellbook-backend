from ..query_parsing import compare
from .base import QueryValue, VariantQuery, ValidationError


def popularity_filter(qv: QueryValue) -> VariantQuery:
    if not qv.is_numeric():
        raise ValidationError(f'Value {qv.value} is not supported for popularity search.')
    return qv.to_filter(compare('popularity', qv.operator, int(qv.value)))
