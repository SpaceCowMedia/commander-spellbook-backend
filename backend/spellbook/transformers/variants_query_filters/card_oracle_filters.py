from .base import QueryValue, QueryFilter, VariantFilterCollection, Q, ValidationError


def card_oracle_filter(card_oracle_value: QueryValue) -> VariantFilterCollection:
    match card_oracle_value.operator:
        case ':':
            q = Q(card__oracle_text__icontains=card_oracle_value.value)
        case '=':
            q = Q(card__oracle_text__iexact=card_oracle_value.value)
        case _:
            raise ValidationError(f'Operator {card_oracle_value.operator} is not supported for card oracle search.')
    return VariantFilterCollection(
        cards_filters=(
            QueryFilter(
                q,
                negated=card_oracle_value.is_negated(),
            ),
        ),
    )
