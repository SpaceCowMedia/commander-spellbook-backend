from .base import QueryValue, VariantFilterCollection, Q, ValidationError


def id_filter(qv: QueryValue) -> VariantFilterCollection:
    match qv.operator:
        case ':' | '=':
            q = Q(id__iexact=qv.value) | Q(aliases__id__iexact=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for spellbook id search.')
    return VariantFilterCollection(variants_filters=(qv.to_query_filter(q),))
