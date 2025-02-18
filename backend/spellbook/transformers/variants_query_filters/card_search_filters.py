from .base import QueryValue, QueryFilter, VariantFilterCollection, Q, ValidationError


def card_search_filter(search_value: QueryValue) -> VariantFilterCollection:
    value_is_digit = search_value.value.isdigit()
    match search_value.operator:
        case ':' if not value_is_digit:
            return VariantFilterCollection(
                cards_filters=(
                    QueryFilter(
                        q=Q(card__name__icontains=search_value.value) | Q(card__name_unaccented__icontains=search_value.value) | Q(card__name_unaccented_simplified__icontains=search_value.value) | Q(card__name_unaccented_simplified_with_spaces__icontains=search_value.value),
                        negated=search_value.is_negated(),
                    ),
                ),
            )
        case '=' if not value_is_digit:
            return VariantFilterCollection(
                cards_filters=(
                    QueryFilter(
                        q=Q(card__name__iexact=search_value.value) | Q(card__name_unaccented__iexact=search_value.value) | Q(card__name_unaccented_simplified__iexact=search_value.value) | Q(card__name_unaccented_simplified_with_spaces__iexact=search_value.value),
                        negated=search_value.is_negated(),
                    ),
                ),
            )
        case '<' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    QueryFilter(
                        q=Q(card_count__lt=search_value.value),
                        negated=search_value.is_negated(),
                    ),
                ),
            )
        case '>' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    QueryFilter(
                        q=Q(card_count__gt=search_value.value),
                        negated=search_value.is_negated(),
                    ),
                ),
            )
        case '<=' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    QueryFilter(
                        q=Q(card_count__lte=search_value.value),
                        negated=search_value.is_negated(),
                    ),
                ),
            )
        case '>=' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    QueryFilter(
                        q=Q(card_count__gte=search_value.value),
                        negated=search_value.is_negated(),
                    ),
                ),
            )
        case ':' | '=' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    QueryFilter(
                        q=Q(card_count=search_value.value),
                        negated=search_value.is_negated(),
                    ),
                ),
            )
        case _:
            raise ValidationError(f'Operator {search_value.operator} is not supported for card search with {"numbers" if value_is_digit else "strings"}.')
