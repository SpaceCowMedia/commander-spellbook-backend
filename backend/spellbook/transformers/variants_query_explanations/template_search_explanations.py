from spellbook.models import Template
from .base import QueryValue, ENTITY, Explanation, Predicate, USE, ValidationError, about, count, entity_names, quoted


def template_search_explanation(qv: QueryValue) -> Explanation:
    value_is_digit = qv.is_numeric()
    if value_is_digit and qv.is_for_all_related():
        raise ValidationError(f'Prefix {qv.prefix} is not supported for template search with numbers.')
    match qv.operator:
        case ':' if not value_is_digit:
            return about(qv, USE, Template, f'{ENTITY} with {quoted(qv.value)} in the name')
        case '=' if not value_is_digit:
            return about(qv, USE, Template, f'{ENTITY} named exactly {quoted(qv.value)}')
        case ':' | '=' | '<' | '<=' | '>' | '>=' if value_is_digit:
            return Predicate(USE, count(qv.operator, qv.value, *entity_names(Template)))
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for template search.')
