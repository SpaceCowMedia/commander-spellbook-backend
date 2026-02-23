from .base import QueryValue, VariantFilterCollection, Q, ValidationError


def card_mana_value_filter(qv: QueryValue) -> VariantFilterCollection:
    if not qv.is_numeric():
        raise ValidationError(f'Value {qv.value} is not supported for card mana value search.')
    match qv.operator:
        case ':' | '=':
            q = Q(mana_value=qv.value)
        case '<':
            q = Q(mana_value__lt=qv.value)
        case '<=':
            q = Q(mana_value__lte=qv.value)
        case '>':
            q = Q(mana_value__gt=qv.value)
        case '>=':
            q = Q(mana_value__gte=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card mana value search.')
    return VariantFilterCollection(cards_filters=(qv.to_query_filter(q),))
