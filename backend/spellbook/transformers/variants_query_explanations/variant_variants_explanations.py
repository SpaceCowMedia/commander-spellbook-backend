from spellbook.models import Variant
from .base import QueryValue, Explanation, Predicate, HAVE, ValidationError, count, entity_names


def variants_explanation(qv: QueryValue) -> Explanation:
    if not qv.is_numeric():
        raise ValidationError(f'Value {qv.value} is not supported for variants search.')
    match qv.operator:
        case ':' | '=' | '<' | '<=' | '>' | '>=':
            return Predicate(HAVE, count(qv.operator, qv.value, *entity_names(Variant)))
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for variants search.')
