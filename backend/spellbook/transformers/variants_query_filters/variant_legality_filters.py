from .base import QueryValue, VariantFilter, VariantFilterCollection, Q, ValidationError
from spellbook.models import Variant


def legality_filter(legality_value: QueryValue) -> VariantFilterCollection:
    if legality_value.operator != ':':
        raise ValidationError(f'Operator {legality_value.operator} is not supported for legality search.')
    format = legality_value.value.lower()
    supported_formats = {f.removeprefix('legal_') for f in Variant.legalities_fields()}
    if format not in supported_formats:
        raise ValidationError(f'Format {format} is not supported for legality search.')
    legal = True
    match legality_value.key.lower():
        case 'banned':
            legal = False
    return VariantFilterCollection(
        variants_filters=(
            VariantFilter(
                Q(**{f'legal_{format}': legal}),
                negated=legality_value.is_negated(),
            ),
        ),
    )
