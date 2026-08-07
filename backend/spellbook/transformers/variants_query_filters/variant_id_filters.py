from spellbook.models import VariantAlias
from .base import QueryValue, VariantQuery, Q, ValidationError


def id_filter(qv: QueryValue) -> VariantQuery:
    match qv.operator:
        case ':' | '=':
            return qv.to_filter(Q(id__iexact=qv.value)) | qv.to_filter(Q(id__iexact=qv.value), VariantAlias)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for spellbook id search.')
