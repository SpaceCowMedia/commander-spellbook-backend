from .base import QueryFilter, QueryValue, VariantFilterCollection, Q, ValidationError
from spellbook.models import Variant


def description_filter(qv: QueryValue) -> VariantFilterCollection:
    value_is_digit = qv.value.isdigit()
    match qv.operator:
        case ':' if not value_is_digit:
            q = Q(description__icontains=qv.value)
        case '=' if not value_is_digit:
            q = Q(description__iexact=qv.value)
        case '<' if value_is_digit:
            q = Q(description_line_count__lt=qv.value)
        case '<=' if value_is_digit:
            q = Q(description_line_count__lte=qv.value)
        case '>' if value_is_digit:
            q = Q(description_line_count__gt=qv.value)
        case '>=' if value_is_digit:
            q = Q(description_line_count__gte=qv.value)
        case ':' | '=' if value_is_digit:
            q = Q(description_line_count=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for prerequisites search.')
    return VariantFilterCollection(variants_filters=(
        qv.to_query_filter(q),
        QueryFilter(
            q=~Q(status=Variant.Status.EXAMPLE),
            excludable=False,
        )
    ))
