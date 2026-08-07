from spellbook.models import Card
from .base import QueryValue, VariantQuery, Q, ValidationError


def card_search_filter(qv: QueryValue) -> VariantQuery:
    value_is_digit = qv.is_numeric()
    if value_is_digit and qv.is_for_all_related():
        raise ValidationError(f'Prefix {qv.prefix} is not supported for card search with numbers.')
    match qv.operator:
        case ':' if not value_is_digit:
            return qv.to_filter(
                Q(name__icontains=qv.value) | Q(name_unaccented__icontains=qv.value) | Q(name_unaccented_simplified__icontains=qv.value) | Q(name_unaccented_simplified_with_spaces__icontains=qv.value),
                Card,
            )
        case '=' if not value_is_digit:
            return qv.to_filter(
                Q(name__iexact=qv.value) | Q(name_unaccented__iexact=qv.value) | Q(name_unaccented_simplified__iexact=qv.value) | Q(name_unaccented_simplified_with_spaces__iexact=qv.value),
                Card,
            )
        case '<' if value_is_digit:
            return qv.to_filter(Q(card_count__lt=qv.value))
        case '>' if value_is_digit:
            return qv.to_filter(Q(card_count__gt=qv.value))
        case '<=' if value_is_digit:
            return qv.to_filter(Q(card_count__lte=qv.value))
        case '>=' if value_is_digit:
            return qv.to_filter(Q(card_count__gte=qv.value))
        case ':' | '=' if value_is_digit:
            return qv.to_filter(Q(card_count=qv.value))
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card search with {'numbers' if value_is_digit else 'strings'}.')
