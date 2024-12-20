from .base import QueryValue, QueryFilter, VariantFilterCollection, Q, ValidationError
from spellbook.models import Variant


def prerequisites_filter(prerequisites_value: QueryValue) -> VariantFilterCollection:
    value_is_digit = prerequisites_value.value.isdigit()
    match prerequisites_value.operator:
        case ':' if not value_is_digit:
            q = Q(other_prerequisites__icontains=prerequisites_value.value)
        case '=' if not value_is_digit:
            q = Q(other_prerequisites__iexact=prerequisites_value.value)
        case '<' if value_is_digit:
            q = Q(other_prerequisites_line_count__lt=prerequisites_value.value)
        case '<=' if value_is_digit:
            q = Q(other_prerequisites_line_count__lte=prerequisites_value.value)
        case '>' if value_is_digit:
            q = Q(other_prerequisites_line_count__gt=prerequisites_value.value)
        case '>=' if value_is_digit:
            q = Q(other_prerequisites_line_count__gte=prerequisites_value.value)
        case ':' | '=' if value_is_digit:
            q = Q(other_prerequisites_line_count=prerequisites_value.value)
        case _:
            raise ValidationError(f'Operator {prerequisites_value.operator} is not supported for prerequisites search.')
    return VariantFilterCollection(
        variants_filters=(
            QueryFilter(q=q, negated=prerequisites_value.is_negated()),
            QueryFilter(q=~Q(status=Variant.Status.EXAMPLE)),
        ),
    )
