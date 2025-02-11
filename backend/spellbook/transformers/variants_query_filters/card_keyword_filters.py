from .base import QueryValue, VariantFilterCollection, IngredientQueryFilter, Q, ValidationError


def card_keyword_filter(card_keyword_value: QueryValue) -> VariantFilterCollection:
    match card_keyword_value.operator:
        case ':':
            q = Q(card__keywords__icontains=card_keyword_value.value)
        case _:
            raise ValidationError(f'Operator {card_keyword_value.operator} is not supported for card keyword search.')
    return VariantFilterCollection(
        ingredients_filters=(
            IngredientQueryFilter(
                cards_q=q,
                negated=card_keyword_value.is_negated(),
            ),
        ),
    )
