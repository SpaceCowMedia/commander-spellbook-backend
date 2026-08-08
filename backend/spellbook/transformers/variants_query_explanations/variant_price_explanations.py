from spellbook.parsers.variants_query_grammar import SUPPORTED_STORES
from .base import QueryValue, Explanation, Predicate, COST, ValidationError, amount

STORE_NAMES = {'tcgplayer': 'TCGPlayer', 'cardkingdom': 'Card Kingdom', 'cardmarket': 'Cardmarket'}
STORE_CURRENCIES = {'cardmarket': '€'}


def price_explanation(qv: QueryValue) -> Explanation:
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
        case ':' | '=' | '<' | '<=' | '>' | '>=':
            price = amount(qv.operator, f'{STORE_CURRENCIES.get(store, '$')}{qv.value}')
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for price search.')
    return Predicate(COST, f'{price} on {STORE_NAMES.get(store, store)}')
