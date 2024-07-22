from .base import QueryValue, VariantFilter, VariantFilterCollection, Q, ValidationError
from spellbook.models import Variant


def price_filter(price_value: QueryValue) -> VariantFilterCollection:
    match price_value.key.lower():
        case 'usd' | 'price':
            store = 'cardkingdom'
        case 'eur':
            store = 'cardmarket'
        case other:
            store = other
    supported_stores = {s.removeprefix('price_') for s in Variant.prices_fields()}
    if store not in supported_stores:
        raise ValidationError(f'Store {store} is not supported for price search.')
    if not price_value.value.isdigit():
        raise ValidationError(f'Value {price_value.value} is not supported for price search.')
    match price_value.operator:
        case ':' | '=':
            q = Q(**{f'price_{store}': price_value.value})
        case '<':
            q = Q(**{f'price_{store}__lt': price_value.value})
        case '<=':
            q = Q(**{f'price_{store}__lte': price_value.value})
        case '>':
            q = Q(**{f'price_{store}__gt': price_value.value})
        case '>=':
            q = Q(**{f'price_{store}__gte': price_value.value})
        case _:
            raise ValidationError(f'Operator {price_value.operator} is not supported for price search.')
    return VariantFilterCollection(
        variants_filters=(
            VariantFilter(q=q, negated=price_value.is_negated()),
        ),
    )
