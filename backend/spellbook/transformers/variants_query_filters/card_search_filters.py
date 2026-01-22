from .base import QueryValue, VariantFilterCollection, Q, ValidationError


def card_search_filter(qv: QueryValue) -> VariantFilterCollection:
    value_is_digit = qv.value.isdigit()
    if value_is_digit and qv.is_for_all_related():
        raise ValidationError(f'Prefix {qv.prefix} is not supported for card search with numbers.')
    match qv.operator:
        case ':' if not value_is_digit:
            return VariantFilterCollection(cards_filters=(qv.to_query_filter(
                Q(name__icontains=qv.value) | Q(name_unaccented__icontains=qv.value) | Q(name_unaccented_simplified__icontains=qv.value) | Q(name_unaccented_simplified_with_spaces__icontains=qv.value)
            ),))
        case '=' if not value_is_digit:
            return VariantFilterCollection(cards_filters=(qv.to_query_filter(
                Q(name__iexact=qv.value) | Q(name_unaccented__iexact=qv.value) | Q(name_unaccented_simplified__iexact=qv.value) | Q(name_unaccented_simplified_with_spaces__iexact=qv.value),
            ),))
        case '<' if value_is_digit:
            return VariantFilterCollection(variants_filters=(qv.to_query_filter(
                Q(card_count__lt=qv.value),
            ),))
        case '>' if value_is_digit:
            return VariantFilterCollection(variants_filters=(qv.to_query_filter(
                Q(card_count__gt=qv.value),
            ),))
        case '<=' if value_is_digit:
            return VariantFilterCollection(variants_filters=(qv.to_query_filter(
                Q(card_count__lte=qv.value),
            ),))
        case '>=' if value_is_digit:
            return VariantFilterCollection(variants_filters=(qv.to_query_filter(
                Q(card_count__gte=qv.value),
            ),))
        case ':' | '=' if value_is_digit:
            return VariantFilterCollection(variants_filters=(qv.to_query_filter(
                Q(card_count=qv.value),
            ),))
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card search with {'numbers' if value_is_digit else 'strings'}.')
