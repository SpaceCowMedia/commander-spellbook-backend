from .base import QueryValue, VariantFilterCollection, Q, ValidationError
from spellbook.models import Variant


def price_filter(qv: QueryValue) -> VariantFilterCollection:
    match qv.key.lower():
        case 'usd' | 'price':
            store = 'cardkingdom'
        case 'eur':
            store = 'cardmarket'
        case other:
            store = other
    supported_stores = {s.removeprefix('price_') for s in Variant.prices_fields()}
    if store not in supported_stores:
        raise ValidationError(f'Store {store} is not supported for price search.')
    if not qv.value.isdigit():
        raise ValidationError(f'Value {qv.value} is not supported for price search.')
    match qv.operator:
        case ':' | '=':
            q = Q(**{f'price_{store}': qv.value})
        case '<':
            q = Q(**{f'price_{store}__lt': qv.value})
        case '<=':
            q = Q(**{f'price_{store}__lte': qv.value})
        case '>':
            q = Q(**{f'price_{store}__gt': qv.value})
        case '>=':
            q = Q(**{f'price_{store}__gte': qv.value})
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for price search.')
    return VariantFilterCollection(variants_filters=(qv.to_query_filter(q),))
