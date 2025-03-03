from .base import QueryValue, VariantFilterCollection, Q, ValidationError


def card_mana_value_filter(qv: QueryValue) -> VariantFilterCollection:
    value_is_digit = qv.value.isdigit()
    match qv.operator:
        case ':' | '=' if value_is_digit:
            q = Q(card__mana_value=qv.value)
        case '<' if value_is_digit:
            q = Q(card__mana_value__lt=qv.value)
        case '<=' if value_is_digit:
            q = Q(card__mana_value__lte=qv.value)
        case '>' if value_is_digit:
            q = Q(card__mana_value__gt=qv.value)
        case '>=' if value_is_digit:
            q = Q(card__mana_value__gte=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card mana value search with {"numbers" if value_is_digit else "strings"}.')
    return VariantFilterCollection(cards_filters=(qv.to_query_filter(q),))
