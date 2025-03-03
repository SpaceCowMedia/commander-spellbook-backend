from .base import QueryValue, VariantFilterCollection, Q, ValidationError


def commander_filter(qv: QueryValue) -> VariantFilterCollection:
    match qv.operator:
        case ':':
            q = Q(card__name__icontains=qv.value) \
                | Q(card__name_unaccented__icontains=qv.value) \
                | Q(card__name_unaccented_simplified__icontains=qv.value) \
                | Q(card__name_unaccented_simplified_with_spaces__icontains=qv.value)
            q &= Q(must_be_commander=True)
        case '=':
            q = Q(card__name__iexact=qv.value) \
                | Q(card__name_unaccented__iexact=qv.value) \
                | Q(card__name_unaccented_simplified__iexact=qv.value) \
                | Q(card__name_unaccented_simplified_with_spaces__iexact=qv.value)
            q &= Q(must_be_commander=True)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for commander name search.')
    return VariantFilterCollection(cards_filters=(qv.to_query_filter(q),))
