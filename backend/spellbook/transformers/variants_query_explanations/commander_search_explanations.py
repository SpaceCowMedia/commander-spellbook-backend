from .base import QueryValue, Explanation, Predicate, REQUIRE, ValidationError, quoted


def commander_explanation(qv: QueryValue) -> Explanation:
    match qv.operator:
        case ':':
            complement = f'a commander whose name contains {quoted(qv.value)}'
        case '=':
            complement = f'a commander named {quoted(qv.value)}'
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for commander name search.')
    return Predicate(REQUIRE, complement)
