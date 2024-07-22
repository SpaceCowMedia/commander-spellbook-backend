from .base import QueryValue, VariantFilterCollection, VariantFilter, Q, ValidationError
from spellbook.models import Variant


def description_filter(description_value: QueryValue) -> VariantFilterCollection:
    value_is_digit = description_value.value.isdigit()
    match description_value.operator:
        case ':' if not value_is_digit:
            q = Q(description__icontains=description_value.value)
        case '=' if not value_is_digit:
            q = Q(description__iexact=description_value.value)
        case '<' if value_is_digit:
            q = Q(description_line_count__lt=description_value.value)
        case '<=' if value_is_digit:
            q = Q(description_line_count__lte=description_value.value)
        case '>' if value_is_digit:
            q = Q(description_line_count__gt=description_value.value)
        case '>=' if value_is_digit:
            q = Q(description_line_count__gte=description_value.value)
        case ':' | '=' if value_is_digit:
            q = Q(description_line_count=description_value.value)
        case _:
            raise ValidationError(f'Operator {description_value.operator} is not supported for prerequisites search.')
    return VariantFilterCollection(
        variants_filters=(
            VariantFilter(q=q, negated=description_value.is_negated()),
            VariantFilter(q=~Q(status=Variant.Status.EXAMPLE)),
        ),
    )
