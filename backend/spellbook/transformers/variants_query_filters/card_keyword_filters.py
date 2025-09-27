from .base import QueryValue, VariantFilterCollection, Q, ValidationError


def card_keyword_filter(qv: QueryValue) -> VariantFilterCollection:
    match qv.operator:
        case ':':
            q = Q(keywords__icontains=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card keyword search.')
    return VariantFilterCollection(cards_filters=(qv.to_query_filter(q),))
