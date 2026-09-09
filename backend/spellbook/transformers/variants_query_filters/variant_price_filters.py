from ..query_parsing import compare
from .base import QueryValue, VariantQuery, ValidationError
from spellbook.parsers.variants_query_grammar import SUPPORTED_STORES


def price_filter(qv: QueryValue) -> VariantQuery:
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
    return qv.to_filter(compare(f'price_{store}', qv.operator, int(qv.value)))
