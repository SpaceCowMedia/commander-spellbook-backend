from ..variants_query_filters.variant_price_filters import price_store
from .base import QueryValue, Explanation, Predicate, COST, ValidationError, amount

STORE_NAMES = {'tcgplayer': 'TCGPlayer', 'cardkingdom': 'Card Kingdom', 'cardmarket': 'Cardmarket'}
STORE_CURRENCIES = {'cardmarket': '€'}


def price_explanation(qv: QueryValue) -> Explanation:
    value = qv.decimal_value('price')
    store = price_store(qv)
    match qv.operator:
        case ':' | '=' | '<' | '<=' | '>' | '>=':
            price = amount(qv.operator, f'{STORE_CURRENCIES.get(store, '$')}{value:f}')
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for price search.')
    return Predicate(COST, f'{price} on {STORE_NAMES.get(store, store)}')
