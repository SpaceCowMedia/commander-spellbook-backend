from .base import IngredientQueryFilter, QueryValue, VariantFilterCollection, Q, ValidationError


def commander_filter(commander_name_value: QueryValue) -> VariantFilterCollection:
    match commander_name_value.operator:
        case ':':
            cards_q = Q(card__name__icontains=commander_name_value.value) \
                | Q(card__name_unaccented__icontains=commander_name_value.value) \
                | Q(card__name_unaccented_simplified__icontains=commander_name_value.value) \
                | Q(card__name_unaccented_simplified_with_spaces__icontains=commander_name_value.value)
            cards_q &= Q(must_be_commander=True)
            templates_q = Q(template__name__icontains=commander_name_value.value, must_be_commander=True)
        case '=':
            cards_q = Q(card__name__iexact=commander_name_value.value) \
                | Q(card__name_unaccented__iexact=commander_name_value.value) \
                | Q(card__name_unaccented_simplified__iexact=commander_name_value.value) \
                | Q(card__name_unaccented_simplified_with_spaces__iexact=commander_name_value.value)
            cards_q &= Q(must_be_commander=True)
            templates_q = Q(template__name__iexact=commander_name_value.value, must_be_commander=True)
        case _:
            raise ValidationError(f'Operator {commander_name_value.operator} is not supported for commander name search.')
    return VariantFilterCollection(
        ingredients_filters=(
            IngredientQueryFilter(
                cards_q=cards_q,
                templates_q=templates_q,
                negated=commander_name_value.is_negated(),
            ),
        ),
    )
