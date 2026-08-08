from spellbook.models import Card
from spellbook.parsers.color_parser import parse_color
from .base import QueryValue, ENTITY, Explanation, USE, ValidationError, about, color_names, count


def card_color_explanation(qv: QueryValue) -> Explanation:
    value_is_digit = qv.is_numeric()
    colors = ''
    colorless = False
    if not value_is_digit:
        parsed_color = parse_color(qv.value)
        if parsed_color is None:
            raise ValidationError(f'Invalid color: {qv.value}')
        colorless = parsed_color == 'C'
        colors = color_names(parsed_color)
    match qv.operator:
        case ':' | '=' if not value_is_digit:
            return about(qv, USE, Card, f'colorless {ENTITY}' if colorless else f'{ENTITY} whose colors are exactly {colors}')
        case '<' if not value_is_digit:
            return about(qv, USE, Card, f'{ENTITY} whose colors are within, but not all of, {colors}')
        case '<=' if not value_is_digit:
            return about(qv, USE, Card, f'{ENTITY} whose colors are within {colors}')
        case '>' if not value_is_digit:
            return about(qv, USE, Card, f'{ENTITY} whose colors include {colors} and more')
        case '>=' if not value_is_digit:
            return about(qv, USE, Card, f'{ENTITY} whose colors include {colors}')
        case ':' | '=' | '<' | '<=' | '>' | '>=' if value_is_digit:
            return about(qv, USE, Card, f'{ENTITY} with {count(qv.operator, qv.value, 'color', 'colors')}')
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card color search with {'numbers' if value_is_digit else 'strings'}.')
