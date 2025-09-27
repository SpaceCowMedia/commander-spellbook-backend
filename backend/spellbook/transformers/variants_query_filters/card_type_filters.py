from .base import QueryValue, VariantFilterCollection, Q, ValidationError


def card_type_filter(qv: QueryValue) -> VariantFilterCollection:
    match qv.operator:
        case ':':
            q = Q(type_line__icontains=qv.value)
        case '=':
            q = Q(type_line__iexact=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card type search.')
    return VariantFilterCollection(cards_filters=(qv.to_query_filter(q),))
