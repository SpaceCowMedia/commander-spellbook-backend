from ..query_parsing import compare
from .base import QueryValue, VariantQuery, ValidationError
from spellbook.parsers.variants_query_grammar import SUPPORTED_STORES


def price_store(qv: QueryValue) -> str:
    match qv.key.lower():
        case 'usd' | 'price':
            store = 'cardkingdom'
        case 'eur' | 'mkm':
            store = 'cardmarket'
        case other:
            store = other
    if store not in SUPPORTED_STORES:
        raise ValidationError(f'Store {store} is not supported for price search.')
    return store


def price_filter(qv: QueryValue) -> VariantQuery:
    price = qv.decimal_value('price')
    return qv.to_filter(compare(f'price_{price_store(qv)}', qv.operator, price))
