from .base import QueryValue, VariantFilter, VariantFilterCollection, Q, ValidationError


def card_search_filter(card_value: QueryValue) -> VariantFilterCollection:
    value_is_digit = card_value.value.isdigit()
    match card_value.operator:
        case ':' if not value_is_digit:
            return VariantFilterCollection(
                cards_filters=(
                    VariantFilter(
                        q=Q(card__name__icontains=card_value.value) | Q(card__name_unaccented__icontains=card_value.value) | Q(card__name_unaccented_simplified__icontains=card_value.value) | Q(card__name_unaccented_simplified_with_spaces__icontains=card_value.value),
                        negated=card_value.is_negated(),
                    ),
                ),
            )
        case '=' if not value_is_digit:
            return VariantFilterCollection(
                cards_filters=(
                    VariantFilter(
                        q=Q(card__name__iexact=card_value.value) | Q(card__name_unaccented__iexact=card_value.value) | Q(card__name_unaccented_simplified__iexact=card_value.value) | Q(card__name_unaccented_simplified_with_spaces__iexact=card_value.value),
                        negated=card_value.is_negated(),
                    ),
                ),
            )
        case '<' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    VariantFilter(
                        q=Q(cards_count__lt=card_value.value),
                        negated=card_value.is_negated(),
                    ),
                ),
            )
        case '>' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    VariantFilter(
                        q=Q(cards_count__gt=card_value.value),
                        negated=card_value.is_negated(),
                    ),
                ),
            )
        case '<=' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    VariantFilter(
                        q=Q(cards_count__lte=card_value.value),
                        negated=card_value.is_negated(),
                    ),
                ),
            )
        case '>=' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    VariantFilter(
                        q=Q(cards_count__gte=card_value.value),
                        negated=card_value.is_negated(),
                    ),
                ),
            )
        case ':' | '=' if value_is_digit:
            return VariantFilterCollection(
                variants_filters=(
                    VariantFilter(
                        q=Q(cards_count=card_value.value),
                        negated=card_value.is_negated(),
                    ),
                ),
            )
        case _:
            raise ValidationError(f'Operator {card_value.operator} is not supported for card search with {"numbers" if value_is_digit else "strings"}.')
