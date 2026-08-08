from django.db.models import Field
from spellbook.models import Variant
from .base import QueryValue, Explanation, Predicate, BE, ValidationError

FORMAT_NAMES = {
    field.name.removeprefix('legal_'): str(field.verbose_name).removeprefix('is legal in ')
    for field in Variant._meta.get_fields()
    if isinstance(field, Field) and field.name.startswith('legal_')
}


def legality_explanation(qv: QueryValue) -> Explanation:
    if qv.operator != ':':
        raise ValidationError(f'Operator {qv.operator} is not supported for legality search.')
    format = qv.value.lower()
    if format not in FORMAT_NAMES:
        raise ValidationError(f'Format {format} is not supported for legality search.')
    match qv.key.lower():
        case 'banned':
            return Predicate(BE, f'banned in {FORMAT_NAMES[format]}')
        case _:
            return Predicate(BE, f'legal in {FORMAT_NAMES[format]}')
