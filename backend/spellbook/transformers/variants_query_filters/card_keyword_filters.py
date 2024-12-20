from .base import QueryValue, VariantFilterCollection, QueryFilter, Q, ValidationError


def card_keyword_filter(card_keyword_value: QueryValue) -> VariantFilterCollection:
    match card_keyword_value.operator:
        case ':':
            q = Q(card__keywords__icontains=card_keyword_value.value)
        case _:
            raise ValidationError(f'Operator {card_keyword_value.operator} is not supported for card keyword search.')
    return VariantFilterCollection(
        cards_filters=(
            QueryFilter(
                q,
                negated=card_keyword_value.is_negated(),
            ),
        ),
    )
