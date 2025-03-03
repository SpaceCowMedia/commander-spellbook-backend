from .base import QueryValue, VariantFilterCollection, Q, ValidationError
from spellbook.models import Variant


def legality_filter(qv: QueryValue) -> VariantFilterCollection:
    if qv.operator != ':':
        raise ValidationError(f'Operator {qv.operator} is not supported for legality search.')
    format = qv.value.lower()
    supported_formats = {f.removeprefix('legal_') for f in Variant.legalities_fields()}
    if format not in supported_formats:
        raise ValidationError(f'Format {format} is not supported for legality search.')
    legal = True
    match qv.key.lower():
        case 'banned':
            legal = False
    q = Q(**{f'legal_{format}': legal})
    return VariantFilterCollection(variants_filters=(qv.to_query_filter(q),))
