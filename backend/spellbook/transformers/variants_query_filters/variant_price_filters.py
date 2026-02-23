from .base import QueryValue, VariantFilterCollection, Q, ValidationError
from spellbook.parsers.variants_query_grammar import SUPPORTED_STORES


def price_filter(qv: QueryValue) -> VariantFilterCollection:
    if not qv.is_numeric():
        raise ValidationError(f'Value {qv.value} is not supported for price search.')
    match qv.key.lower():
        case 'usd' | 'price':
            store = 'cardkingdom'
        case 'eur' | 'mkm':
            store = 'cardmarket'
        case other:
            store = other
    if store not in SUPPORTED_STORES:
        raise ValidationError(f'Store {store} is not supported for price search.')
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
