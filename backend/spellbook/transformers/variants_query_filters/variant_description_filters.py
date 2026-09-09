from spellbook.models import Variant
from ..query_parsing import compare
from .base import QueryValue, VariantQuery, Q, ValidationError, guard


def description_filter(qv: QueryValue) -> VariantQuery:
    value_is_digit = qv.is_numeric()
    match qv.operator:
        case ':' if not value_is_digit:
            q = Q(description__icontains=qv.value)
        case '=' if not value_is_digit:
            q = Q(description__iexact=qv.value)
        case _ if value_is_digit:
            q = compare('description_line_count', qv.operator, int(qv.value))
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for prerequisites search.')
    return qv.to_filter(q) & guard(~Q(status=Variant.Status.EXAMPLE))
