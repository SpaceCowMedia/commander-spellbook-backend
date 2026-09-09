from spellbook.models import Card
from spellbook.parsers.color_parser import parse_color
from ..query_parsing import compare
from .base import QueryValue, VariantQuery, Q, ValidationError


def card_color_filter(qv: QueryValue) -> VariantQuery:
    value_is_digit = qv.is_numeric()
    color = ''
    not_in_color = ''
    if not value_is_digit:
        parsed_color = parse_color(qv.value)
        if parsed_color is None:
            raise ValidationError(f'Invalid color: {qv.value}')
        color = '' if parsed_color == 'C' else parsed_color
        for c in 'WUBRG':
            if c not in color:
                not_in_color += c
    match qv.operator:
        case ':' | '=' if not value_is_digit:
            q = Q(color=color or 'C')
        case '<' | '<=' if not value_is_digit:
            q = compare('color_count', qv.operator, len(color))
            for c in not_in_color:
                q &= Q(**{f'color_{c.lower()}': False})
        case '>' | '>=' if not value_is_digit:
            q = compare('color_count', qv.operator, len(color))
            for c in color:
                q &= Q(**{f'color_{c.lower()}': True})
        case _ if value_is_digit:
            q = compare('color_count', qv.operator, int(qv.value))
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card color search with {'numbers' if value_is_digit else 'strings'}.')
    return qv.to_filter(q, Card)
