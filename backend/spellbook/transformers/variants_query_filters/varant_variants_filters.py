from ..query_parsing import compare
from .base import QueryValue, VariantQuery, ValidationError


def variants_filter(qv: QueryValue) -> VariantQuery:
    if not qv.is_numeric():
        raise ValidationError(f'Value {qv.value} is not supported for variants search.')
    return qv.to_filter(compare('variant_count', qv.operator, int(qv.value)))
