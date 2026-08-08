from .base import QueryValue, Explanation, Predicate, HAVE, ValidationError, quoted


def id_explanation(qv: QueryValue) -> Explanation:
    match qv.operator:
        case ':' | '=':
            complement = f'the id or alias {quoted(qv.value)}'
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for spellbook id search.')
    return Predicate(HAVE, complement)
