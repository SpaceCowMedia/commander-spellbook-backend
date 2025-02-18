from .base import QueryFilter, QueryValue, VariantFilterCollection, Q, ValidationError


def commander_filter(commander_name_value: QueryValue) -> VariantFilterCollection:
    match commander_name_value.operator:
        case ':':
            q = Q(card__name__icontains=commander_name_value.value) \
                | Q(card__name_unaccented__icontains=commander_name_value.value) \
                | Q(card__name_unaccented_simplified__icontains=commander_name_value.value) \
                | Q(card__name_unaccented_simplified_with_spaces__icontains=commander_name_value.value)
            q &= Q(must_be_commander=True)
        case '=':
            q = Q(card__name__iexact=commander_name_value.value) \
                | Q(card__name_unaccented__iexact=commander_name_value.value) \
                | Q(card__name_unaccented_simplified__iexact=commander_name_value.value) \
                | Q(card__name_unaccented_simplified_with_spaces__iexact=commander_name_value.value)
            q &= Q(must_be_commander=True)
        case _:
            raise ValidationError(f'Operator {commander_name_value.operator} is not supported for commander name search.')
    return VariantFilterCollection(
        cards_filters=(
            QueryFilter(
                q=q,
                negated=commander_name_value.is_negated(),
            ),
        ),
    )
