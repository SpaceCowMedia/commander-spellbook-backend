from .base import IngredientQueryFilter, QueryValue, VariantFilterCollection, Q, ValidationError


def card_type_filter(card_type_value: QueryValue) -> VariantFilterCollection:
    match card_type_value.operator:
        case ':':
            q = Q(card__type_line__icontains=card_type_value.value)
        case '=':
            q = Q(card__type_line__iexact=card_type_value.value)
        case _:
            raise ValidationError(f'Operator {card_type_value.operator} is not supported for card type search.')
    return VariantFilterCollection(
        ingredients_filters=(
            IngredientQueryFilter(
                cards_q=q,
                negated=card_type_value.is_negated(),
            ),
        ),
    )
