from .base import QueryValue, VariantFilterCollection, Q, ValidationError


def card_oracle_filter(qv: QueryValue) -> VariantFilterCollection:
    match qv.operator:
        case ':':
            q = Q(oracle_text__icontains=qv.value)
        case '=':
            q = Q(oracle_text__iexact=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card oracle search.')
    return VariantFilterCollection(cards_filters=(qv.to_query_filter(q),))
