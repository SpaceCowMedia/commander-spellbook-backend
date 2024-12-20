from .base import QueryValue, QueryFilter, VariantFilterCollection, Q, ValidationError


def card_mana_value_filter(card_mana_value_value: QueryValue) -> VariantFilterCollection:
    value_is_digit = card_mana_value_value.value.isdigit()
    match card_mana_value_value.operator:
        case ':' | '=' if value_is_digit:
            q = Q(card__mana_value=card_mana_value_value.value)
        case '<' if value_is_digit:
            q = Q(card__mana_value__lt=card_mana_value_value.value)
        case '<=' if value_is_digit:
            q = Q(card__mana_value__lte=card_mana_value_value.value)
        case '>' if value_is_digit:
            q = Q(card__mana_value__gt=card_mana_value_value.value)
        case '>=' if value_is_digit:
            q = Q(card__mana_value__gte=card_mana_value_value.value)
        case _:
            raise ValidationError(f'Operator {card_mana_value_value.operator} is not supported for card mana value search with {"numbers" if value_is_digit else "strings"}.')
    return VariantFilterCollection(
        cards_filters=(
            QueryFilter(
                q,
                negated=card_mana_value_value.is_negated(),
            ),
        ),
    )
